from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")
borealis_header = Path("switch/borealis/library/include/borealis/views/tab_frame.hpp")

source = source_path.read_text()
xml = xml_path.read_text()

# Stable API state must live next to the controller refresh state. Do not key
# this patch off Home-specific persistence globals, because that layer is
# intentionally independent from the selector.
if "static int g_apiSource" not in source:
    marker = 'static bool g_refreshRequested = false;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate stable controller refresh global")
    addition = marker + '''static int g_apiSource = 0; // 0=Miruro, 1=AnimePahe, 2=Gogoanime
static brls::View* g_boundSettingsTab = nullptr;
'''
    source = source.replace(marker, addition, 1)

# Expose the currently attached TabFrame content. The accessor is read-only;
# the selector never replaces Settings content at runtime.
header = borealis_header.read_text()
if "View* getActiveTab() const" not in header:
    marker = '    void addSeparator();\n'
    if header.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame addSeparator declaration")
    header = header.replace(marker, marker + '    View* getActiveTab() const { return this->activeTab; }\n', 1)
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
    brls::Button* miruro = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-miruro"));
    brls::Button* animepahe = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-animepahe"));
    brls::Button* gogoanime = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-gogoanime"));
    if (!current || !miruro || !animepahe || !gogoanime)
        return;

    auto set_source = [current](int value, const char* name) {
        if (g_apiSource == value)
            return true;
        g_apiSource = value;
        current->setText(std::string("Anime API: ") + name);
        save_api_source();
        g_refreshRequested = true;
        log_stage("API SOURCE CHANGED - REFRESH REQUESTED");
        return true;
    };

    miruro->registerClickAction([set_source](brls::View*) { return set_source(0, "Miruro"); });
    animepahe->registerClickAction([set_source](brls::View*) { return set_source(1, "AnimePahe"); });
    gogoanime->registerClickAction([set_source](brls::View*) { return set_source(2, "Gogoanime"); });

    current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
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
print("API selector patch now targets stable refresh state and current TabFrame content")