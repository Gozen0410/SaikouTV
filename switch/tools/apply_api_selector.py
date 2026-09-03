from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")
borealis_header = Path("switch/borealis/library/include/borealis/views/tab_frame.hpp")

source = source_path.read_text()
xml = xml_path.read_text()

# Keep Settings content XML-owned. Replacing the active Settings view with
# setTabContent() is unsafe on the pinned Borealis build and also disappears
# when the tab is recreated. The selector therefore lives in normal Settings
# XML and its actions are attached after Borealis creates the tab.

if "static int g_apiSource" not in source:
    marker = 'static bool g_homeRefreshInProgress = false;\n'
    addition = marker + '''static int g_apiSource = 0; // 0=Miruro, 1=AnimePahe, 2=Gogoanime
static brls::View* g_boundSettingsTab = nullptr;
'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home persistence globals")
    source = source.replace(marker, addition, 1)

# The Settings tab is XML-created, so expose only the active tab pointer from
# the already-patched TabFrame. No content is replaced through this accessor.
header = borealis_header.read_text()
if "View* getActiveTab() const" not in header:
    marker = '    void addSeparator();\n'
    addition = marker + '    View* getActiveTab() const { return this->activeTab; }\n'
    if header.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame addSeparator declaration")
    header = header.replace(marker, addition, 1)
    borealis_header.write_text(header)

# Persistent provider selection helpers.
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
    brls::Button* miruro = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-miruro"));
    brls::Button* animepahe = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-animepahe"));
    brls::Button* gogoanime = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-gogoanime"));

    if (!current || !miruro || !animepahe || !gogoanime)
        return;

    miruro->registerClickAction([current](brls::View*) {
        g_apiSource = 0;
        current->setText("Anime API: Miruro");
        save_api_source();
        return true;
    });

    animepahe->registerClickAction([current](brls::View*) {
        g_apiSource = 1;
        current->setText("Anime API: AnimePahe");
        save_api_source();
        return true;
    });

    gogoanime->registerClickAction([current](brls::View*) {
        g_apiSource = 2;
        current->setText("Anime API: Gogoanime");
        save_api_source();
        return true;
    });

    current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));

    // The Settings selector buttons live inside the Settings content. Route
    // LEFT explicitly to the currently active Settings sidebar item so it
    // cannot fall through the generic TabFrame content route to Home.
    if (g_activeSidebarItem)
    {
        miruro->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);
        animepahe->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);
        gogoanime->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);
    }

    g_boundSettingsTab = settingsTab;
    log_stage("SETTINGS API ACTIONS BOUND");
}

'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home XML helper boundary")
    source = source.replace(marker, helper + marker, 1)

# Replace the placeholder Settings body with the working selector XML.
old_settings = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="Settings" fontSize="36" />
            <brls:Label width="auto" height="auto" text="Saikou Switch native port" marginTop="20" />
        </brls:Box>
    </brls:Tab>'''
new_settings = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="API Source" fontSize="36" />
            <brls:Label id="api-source-current" width="auto" height="auto" text="Anime API: Miruro" marginTop="20" />
            <brls:Button id="api-source-miruro" width="auto" height="auto" text="Miruro" marginTop="10" />
            <brls:Button id="api-source-animepahe" width="auto" height="auto" text="AnimePahe" />
            <brls:Button id="api-source-gogoanime" width="auto" height="auto" text="Gogoanime" />
        </brls:Box>
    </brls:Tab>'''
if old_settings in xml:
    xml = xml.replace(old_settings, new_settings, 1)
elif 'id="api-source-miruro"' not in xml or 'id="api-source-gogoanime"' not in xml:
    raise SystemExit("Could not locate Settings XML block")
xml_path.write_text(xml)

# Invalidate the bound-tab pointer when Settings is activated so that a newly
# lazy-created XML tab gets its callbacks attached on the following frame.
old_block = '''                        if (!sidebarContent->getChildren().empty())
                        {
                            brls::View* candidate = sidebarContent->getChildren().back();
                            brls::SidebarItem* settingsItem = dynamic_cast<brls::SidebarItem*>(candidate);
                            if (settingsItem)
                            {
                                settingsItem->getActiveEvent()->subscribe([](brls::View*) {
                                    g_settingsRefreshRequested = true;
                                });
                                log_stage("SETTINGS ACTIVE ITEM TRACKING INSTALLED");
                            }
                        }
'''
if old_block in source:
    source = source.replace(old_block, '', 1)

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

# Bind only after the active XML tab exists. No Settings content replacement
# occurs in the sidebar activation callback or main loop.
if "bind_api_settings_actions(tabFrame);" not in source:
    marker = '    while (brls::Application::mainLoop())\n    {\n'
    addition = marker + '''        bind_api_settings_actions(tabFrame);
'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate main loop")
    source = source.replace(marker, addition, 1)

if 'load_api_source();' not in source:
    marker = '    ensure_app_dirs();\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate app directory initialization")
    source = source.replace(marker, marker + '    load_api_source();\n', 1)

source_path.write_text(source)
print("API selector binding fixed: direct XML IDs, LEFT routes back to Settings")
