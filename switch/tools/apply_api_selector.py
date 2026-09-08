from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")
borealis_header = Path("switch/borealis/library/include/borealis/views/tab_frame.hpp")

source = source_path.read_text()
xml = xml_path.read_text()

if "static int g_apiSource" not in source:
    marker = 'static bool g_homeRefreshInProgress = false;\n'
    addition = marker + '''static int g_apiSource = 0; // 0=Miruro, 1=AnimePahe, 2=Gogoanime, 3=Aniwatch, 4=HiAnime
static brls::View* g_boundSettingsTab = nullptr;
'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home persistence globals")
    source = source.replace(marker, addition, 1)

# Use the shared provider registry. Never inject a second api_source_name().
if "static const char* api_source_name(int source)" in source:
    start = source.find("static const char* api_source_name(int source)")
    end = source.find("\nstatic void bind_api_settings_actions", start)
    if start == -1 or end == -1:
        raise SystemExit("Could not locate generated local api_source_name helper")
    source = source[:start] + source[end+1:]

if "static constexpr const char* kSettingsPath" not in source:
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

    auto selectSource = [current](int sourceId) {
        g_apiSource = sourceId;
        save_api_source();
        g_apiSourceRefreshPending = true;
        current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
        log_stage("API SOURCE CHANGED - REFRESH PENDING UNTIL HOME");
    };

    miruro->registerClickAction([selectSource](brls::View*) { selectSource(0); return true; });
    animepahe->registerClickAction([selectSource](brls::View*) { selectSource(1); return true; });
    gogoanime->registerClickAction([selectSource](brls::View*) { selectSource(2); return true; });
    aniwatch->registerClickAction([selectSource](brls::View*) { selectSource(3); return true; });
    hianime->registerClickAction([selectSource](brls::View*) { selectSource(4); return true; });

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

# The workflow starts from the stable Settings XML. Inject the complete
# provider selector there; do not depend on a previously generated block.
base_settings = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="Settings" fontSize="36" />
            <brls:Label width="auto" height="auto" text="Saikou Switch native port" marginTop="20" />
        </brls:Box>
    </brls:Tab>'''
selector_settings = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="Settings" fontSize="36" />
            <brls:Label id="api-source-current" width="auto" height="auto" text="Anime API: Miruro" marginTop="20" />
            <brls:Button id="api-source-miruro" width="auto" height="auto" text="Miruro" marginTop="20" />
            <brls:Button id="api-source-animepahe" width="auto" height="auto" text="AnimePahe" />
            <brls:Button id="api-source-gogoanime" width="auto" height="auto" text="Gogoanime" />
            <brls:Button id="api-source-aniwatch" width="auto" height="auto" text="Aniwatch" />
            <brls:Button id="api-source-hianime" width="auto" height="auto" text="HiAnime" />
        </brls:Box>
    </brls:Tab>'''
if 'id="api-source-aniwatch"' not in xml:
    if base_settings in xml:
        xml = xml.replace(base_settings, selector_settings, 1)
    else:
        raise SystemExit("Could not locate stable Settings XML tab")

xml_path.write_text(xml)
source_path.write_text(source)
print("API selector generator now uses shared provider registry and stable Settings XML")
