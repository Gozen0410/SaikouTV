from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")
borealis_header = Path("switch/borealis/library/include/borealis/views/tab_frame.hpp")

source = source_path.read_text()
xml = xml_path.read_text()

# Keep the Settings UI XML-owned. The working #163 implementation binds to
# controls created by the normal Settings tab; do not replace tab content.
if "#include <borealis/dropdown.hpp>" not in source:
    marker = "#include <borealis/views/image.hpp>\n"
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Borealis include boundary")
    source = source.replace(marker, marker + "#include <borealis/dropdown.hpp>\n", 1)

if "static int g_apiSource" not in source:
    marker = 'static bool g_homeRefreshInProgress = false;\n'
    addition = marker + '''static int g_apiSource = 0; // 0=Miruro, 1=AnimePahe, 2=Gogoanime
static brls::View* g_boundSettingsTab = nullptr;
'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home persistence globals")
    source = source.replace(marker, addition, 1)

# The pinned TabFrame does not expose its active content publicly. This is the
# same tiny accessor used by the known-good API selector implementation.
header = borealis_header.read_text()
if "View* getActiveTab() const" not in header:
    marker = '    void addSeparator();\n'
    addition = marker + '    View* getActiveTab() const { return this->activeTab; }\n'
    if header.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame addSeparator declaration")
    header = header.replace(marker, addition, 1)
    borealis_header.write_text(header)

if "static const char* api_source_name" not in source:
    marker = 'static brls::View* load_home_content_from_xml()\n'
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

    current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
    selector->setText(api_source_name(g_apiSource));

    selector->registerClickAction([current, selector](brls::View*) {
        const std::vector<std::string> values = {"Miruro", "AnimePahe", "Gogoanime"};
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

    // Keep the working LEFT behaviour: leave the API Source subsection back
    // to the Settings sidebar item instead of falling through to Home.
    if (g_activeSidebarItem)
        selector->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);

    g_boundSettingsTab = settingsTab;
    log_stage("SETTINGS API ACTIONS BOUND");
}

'''
    # The lambda needs values available after the callback is created, so keep
    # the provider list outside the callback body as a static helper instead.
    helper = helper.replace('    selector->registerClickAction([current, selector](brls::View*) {\n        const std::vector<std::string> values = {"Miruro", "AnimePahe", "Gogoanime"};\n', '    static const std::vector<std::string> values = {"Miruro", "AnimePahe", "Gogoanime"};\n\n    selector->registerClickAction([current, selector](brls::View*) {\n')
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home XML helper boundary")
    source = source.replace(marker, helper + marker, 1)

# Replace only the Settings body. The rest of the TabFrame stays untouched.
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
    raise SystemExit("Could not locate Settings XML block")
xml_path.write_text(xml)

# Invalidate the cached Settings view whenever the sidebar's Settings item is
# activated so a lazily recreated tab gets its callback bound again.
if "SETTINGS API ACTIVE ITEM TRACKING INSTALLED" not in source:
    marker = '                        log_stage("SIDEBAR ACTIVE ITEM TRACKING INSTALLED");\n'
    addition = marker + '''                        if (!sidebarContent->getChildren().empty())
                        {
                            brls::View* candidate = sidebarContent->getChildren().back();
                            brls::SidebarItem* settingsItem = dynamic_cast<brls::SidebarItem*>(candidate);
                            if (settingsItem)
                            {
                                settingsItem->getActiveEvent()->subscribe([](brls::View*) {
                                    g_boundSettingsTab = nullptr;
                                });
                                log_stage("SETTINGS API ACTIVE ITEM TRACKING INSTALLED");
                            }
                        }
'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate sidebar tracking completion")
    source = source.replace(marker, addition, 1)

if "bind_api_settings_actions(tabFrame);" not in source:
    marker = '    while (brls::Application::mainLoop())\n    {\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate main loop")
    source = source.replace(marker, marker + '        bind_api_settings_actions(tabFrame);\n', 1)

if 'load_api_source();' not in source:
    marker = '    ensure_app_dirs();\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate app directory initialization")
    source = source.replace(marker, marker + '    load_api_source();\n', 1)

source_path.write_text(source)
print("API Source converted to a Settings subsection with a Borealis dropdown")
