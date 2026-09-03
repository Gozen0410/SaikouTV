from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")

source = source_path.read_text()
xml = xml_path.read_text()

# Keep the known-good #163 selector architecture. This patch must be safe to
# run after the controller/home-persistence scripts, regardless of whether a
# previous selector binder is present in the checked-in main.cpp.

# The pinned Borealis checkout exposes Dropdown through the umbrella
# <borealis.hpp> include. Never add the unavailable dropdown.hpp path.
source = source.replace('#include <borealis/dropdown.hpp>\n', '', 1)

# Add the API state globals exactly once.
if "static int g_apiSource" not in source:
    marker = 'static bool g_homeRefreshInProgress = false;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home persistence globals")
    source = source.replace(marker, marker + 'static int g_apiSource = 0;\nstatic brls::View* g_boundSettingsTab = nullptr;\n', 1)

# The working selector uses a tiny accessor on the pinned TabFrame.
header_path = Path("switch/borealis/library/include/borealis/views/tab_frame.hpp")
if not header_path.exists():
    raise SystemExit("Pinned Borealis TabFrame header is missing")
header = header_path.read_text()
if "View* getActiveTab() const" not in header:
    marker = '    void addSeparator();\n'
    if header.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame separator declaration")
    header = header.replace(marker, marker + '    View* getActiveTab() const { return this->activeTab; }\n', 1)
    header_path.write_text(header)

# Remove a prior generated binder if one exists, otherwise just insert a new
# one. We use a stable helper anchor in the generated main.cpp rather than
# requiring the binder itself to already exist in the checked-in main.cpp.
start = source.find('static void bind_api_settings_actions(')
if start != -1:
    end = source.find('\nstatic brls::View* load_home_content_from_xml()', start)
    if end == -1:
        end = source.find('\nint main(int argc, char* argv[])', start)
    if end == -1:
        raise SystemExit('Could not locate API settings binder end')
    source = source[:start] + source[end:]

anchor = '\nstatic brls::View* load_home_content_from_xml()'
if source.count(anchor) != 1:
    raise SystemExit('Could not locate stable Home XML anchor')

helper = r'''static constexpr const char* kSettingsPath = "sdmc:/switch/SaikouTV/settings.cfg";

static void load_api_source()
{
    FILE* file = std::fopen(kSettingsPath, "rb");
    if (!file) return;

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
    if (!tabFrame) return;

    brls::View* settingsTab = tabFrame->getActiveTab();
    if (!settingsTab || settingsTab == g_boundSettingsTab) return;

    brls::Label* current = dynamic_cast<brls::Label*>(settingsTab->getView("api-source-current"));
    brls::Button* selector = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-selector"));
    if (!current || !selector) return;

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

    // Preserve the working LEFT navigation from the known-good selector build.
    if (g_activeSidebarItem)
        selector->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);

    g_boundSettingsTab = settingsTab;
    log_stage("SETTINGS API ACTIONS BOUND");
}
'''
source = source.replace(anchor, '\n' + helper + anchor, 1)

# Make Settings one clean API Source row. Selecting it opens the native
# Borealis dropdown, leaving room for more settings later.
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

# Bind after the normal lazy-created tab exists. This keeps Settings XML-owned
# and avoids replacing its content from an activation callback.
if 'bind_api_settings_actions(tabFrame);' not in source:
    marker = '    while (brls::Application::mainLoop())\n    {\n'
    if source.count(marker) != 1:
        raise SystemExit('Could not locate main loop')
    source = source.replace(marker, marker + '        bind_api_settings_actions(tabFrame);\n', 1)

if 'load_api_source();' not in source:
    marker = '    ensure_app_dirs();\n'
    if source.count(marker) != 1:
        raise SystemExit('Could not locate app directory initialization')
    source = source.replace(marker, marker + '    load_api_source();\n', 1)

xml_path.write_text(xml)
source_path.write_text(source)
print('API Source dropdown patch applied')
