from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")

source = source_path.read_text()
xml = xml_path.read_text()

# The pinned Borealis source exposes Dropdown through borealis.hpp. Avoid a
# direct dropdown.hpp include because this checkout's include tree does not
# install that header at that path.
source = source.replace('#include <borealis/dropdown.hpp>\n', '', 1)

# Replace the selector helper with the dropdown implementation while keeping
# the known-good #163 active-tab binding and LEFT navigation behavior.
start = source.find('static void bind_api_settings_actions(brls::TabFrame* tabFrame)')
if start == -1:
    raise SystemExit('Could not locate API settings binder')
end = source.find('\nstatic brls::View* load_home_content_from_xml()', start)
if end == -1:
    raise SystemExit('Could not locate API settings binder end')

helper = r'''static constexpr const char* kSettingsPath = "sdmc:/switch/SaikouTV/settings.cfg";

static void load_api_source()
{
    FILE* file = std::fopen(kSettingsPath, "rb");
    if (!file)
        return;

    int value = 0;
    if (std::fscanf(file, "%d", &value) == 1 && value >= 0 && value <= 2)
        g_apiSource = value;
    std::fclose(file);
}

static void save_api_source()
{
    FILE* file = std::fopen(kSettingsPath, "wb");
    if (!file)
    {
        log_stage("API SOURCE SETTINGS SAVE FAILED");
        return;
    }

    std::fprintf(file, "%d\n", g_apiSource);
    std::fclose(file);
    log_stage("API SOURCE SETTINGS SAVED");
}

static const char* api_source_name(int source)
{
    switch (source)
    {
        case 1: return "AnimePahe";
        case 2: return "Gogoanime";
        default: return "Miruro";
    }
}

static void bind_api_settings_actions(brls::TabFrame* tabFrame)
{
    if (!tabFrame)
        return;

    brls::View* settingsTab = tabFrame->getActiveTab();
    if (!settingsTab || settingsTab == g_boundSettingsTab)
        return;

    brls::Label* current = dynamic_cast<brls::Label*>(settingsTab->getView("api-source-current"));
    brls::Button* selector = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-selector"));
    if (!current || !selector)
        return;

    static const std::vector<std::string> values = {"Miruro", "AnimePahe", "Gogoanime"};

    current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
    selector->setText(api_source_name(g_apiSource));

    selector->registerClickAction([current, selector](brls::View*) {
        brls::Dropdown::open(
            "Anime API",
            values,
            [current, selector](int selected) {
                if (selected < 0 || selected >= static_cast<int>(values.size()))
                    return;

                g_apiSource = selected;
                const char* name = api_source_name(g_apiSource);
                current->setText(std::string("Anime API: ") + name);
                selector->setText(name);
                save_api_source();
            },
            g_apiSource);
        return true;
    });

    // Preserve the working navigation fix from #163-derived builds.
    if (g_activeSidebarItem)
        selector->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);

    g_boundSettingsTab = settingsTab;
    log_stage("SETTINGS API ACTIONS BOUND");
}

'''
source = source[:start] + helper + source[end:]

# One Settings row opens the native Borealis dropdown.
old_settings = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="Settings" fontSize="36" />
            <brls:Label width="auto" height="auto" text="Saikou Switch native port" marginTop="20" />
        </brls:Box>
    </brls:Tab>'''
new_settings = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="Settings" fontSize="36" />
            <brls:Label width="auto" height="auto" text="API Source" fontSize="30" marginTop="28" />
            <brls:Button id="api-source-selector" width="auto" height="auto" text="Miruro" marginTop="14" />
            <brls:Label id="api-source-current" width="auto" height="auto" text="Anime API: Miruro" marginTop="10" />
        </brls:Box>
    </brls:Tab>'''
if old_settings in xml:
    xml = xml.replace(old_settings, new_settings, 1)
elif 'id="api-source-selector"' not in xml:
    raise SystemExit('Could not locate Settings XML block')
xml_path.write_text(xml)
source_path.write_text(source)
print('API Source dropdown patch applied')
