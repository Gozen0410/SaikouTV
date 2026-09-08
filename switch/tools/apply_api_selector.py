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
    addition = marker + '''static int g_apiSource = 0; // 0=Miruro, 1=AnimePahe, 2=Gogoanime, 3=Aniwatch, 4=HiAnime
static brls::View* g_boundSettingsTab = nullptr;
'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home persistence globals")
    source = source.replace(marker, addition, 1)

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
    if (std::fscanf(file, "%d", &value) == 1 && value >= 0 && value <= 4)
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
        case 3: return "Aniwatch";
        case 4: return "HiAnime";
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
    brls::Button* aniwatch = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-aniwatch"));
    brls::Button* hianime = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-hianime"));

    if (!current || !miruro || !animepahe || !gogoanime || !aniwatch || !hianime)
        return;

    miruro->registerClickAction([current](brls::View*) {
        g_apiSource = 0;
        current->setText("Anime API: Miruro");
        save_api_source();
        g_apiSourceRefreshPending = true;
        log_stage("API SOURCE CHANGED - REFRESH PENDING UNTIL HOME");
        return true;
    });

    animepahe->registerClickAction([current](brls::View*) {
        g_apiSource = 1;
        current->setText("Anime API: AnimePahe");
        save_api_source();
        g_apiSourceRefreshPending = true;
        log_stage("API SOURCE CHANGED - REFRESH PENDING UNTIL HOME");
        return true;
    });

    gogoanime->registerClickAction([current](brls::View*) {
        g_apiSource = 2;
        current->setText("Anime API: Gogoanime");
        save_api_source();
        g_apiSourceRefreshPending = true;
        log_stage("API SOURCE CHANGED - REFRESH PENDING UNTIL HOME");
        return true;
    });

    aniwatch->registerClickAction([current](brls::View*) {
        g_apiSource = 3;
        current->setText("Anime API: Aniwatch");
        save_api_source();
        g_apiSourceRefreshPending = true;
        log_stage("API SOURCE CHANGED - REFRESH PENDING UNTIL HOME");
        return true;
    });

    hianime->registerClickAction([current](brls::View*) {
        g_apiSource = 4;
        current->setText("Anime API: HiAnime");
        save_api_source();
        g_apiSourceRefreshPending = true;
        log_stage("API SOURCE CHANGED - REFRESH PENDING UNTIL HOME");
        return true;
    });

    current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));

    if (g_activeSidebarItem)
    {
        miruro->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);
        animepahe->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);
        gogoanime->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);
        aniwatch->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);
        hianime->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);
    }

    g_boundSettingsTab = settingsTab;
    log_stage("SETTINGS API ACTIONS BOUND");
}

'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home XML helper boundary")
    source = source.replace(marker, helper + marker, 1)

# Replace Settings block or extend an existing three-provider block.
if 'id="api-source-aniwatch"' not in xml:
    needle = '            <brls:Button id="api-source-gogoanime" width="auto" height="auto" text="Gogoanime" />'
    if xml.count(needle) != 1:
        raise SystemExit("Could not locate Gogoanime Settings button")
    xml = xml.replace(needle, needle + '''
            <brls:Button id="api-source-aniwatch" width="auto" height="auto" text="Aniwatch" />
            <brls:Button id="api-source-hianime" width="auto" height="auto" text="HiAnime" />''', 1)
xml_path.write_text(xml)

# Ensure the settings callback pointer is invalidated when a Settings tab is recreated.
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
print("API selector now exposes all five providers and queues Home refresh on selection")