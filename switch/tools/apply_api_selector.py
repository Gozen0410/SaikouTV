from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")

source = source_path.read_text()
xml = xml_path.read_text()

# Provider state is shared with the existing refresh pipeline.
if "static int g_apiSource" not in source:
    marker = 'static bool g_homeRefreshInProgress = false;\n'
    addition = marker + '''static int g_apiSource = 0; // 0=Miruro, 1=AnimePahe, 2=Gogoanime, 3=Aniwatch, 4=HiAnime\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home persistence globals")
    source = source.replace(marker, addition, 1)

# api_sources.hpp owns the provider-name helper. Remove any legacy helper from
# main.cpp using brace matching rather than relying on the following function's
# exact name/spacing.
legacy_marker = "static const char* api_source_name(int source)"
if legacy_marker in source:
    start = source.find(legacy_marker)
    brace_start = source.find("{", start)
    if brace_start == -1:
        raise SystemExit("Could not locate legacy api_source_name body")
    depth = 0
    end = -1
    for index in range(brace_start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end == -1:
        raise SystemExit("Could not find end of legacy api_source_name body")
    while end < len(source) and source[end] in " \t\r\n":
        end += 1
    source = source[:start] + source[end:]

# Persist the selected provider.
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

static void bind_api_settings_actions(brls::View* root)
{
    if (!root)
        return;

    brls::Label* current = dynamic_cast<brls::Label*>(root->getView("api-source-current"));
    brls::Button* miruro = dynamic_cast<brls::Button*>(root->getView("api-source-miruro"));
    brls::Button* animepahe = dynamic_cast<brls::Button*>(root->getView("api-source-animepahe"));
    brls::Button* gogoanime = dynamic_cast<brls::Button*>(root->getView("api-source-gogoanime"));
    brls::Button* aniwatch = dynamic_cast<brls::Button*>(root->getView("api-source-aniwatch"));
    brls::Button* hianime = dynamic_cast<brls::Button*>(root->getView("api-source-hianime"));

    if (!current || !miruro || !animepahe || !gogoanime || !aniwatch || !hianime)
    {
        log_stage("SETTINGS API CONTROLS NOT FOUND");
        return;
    }

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
    log_stage("SETTINGS API ACTIONS BOUND");
}

'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home XML helper boundary")
    source = source.replace(marker, helper + marker, 1)

# Bind immediately after HomeActivity creates the XML root. This avoids
# TabFrame::getActiveTab() and avoids waiting for a later focus event.
needle = '''        return brls::View::createFromXMLResource("activity/main.xml");'''
replacement = '''        brls::View* root = brls::View::createFromXMLResource("activity/main.xml");
        bind_api_settings_actions(root);
        return root;'''
if needle in source and "bind_api_settings_actions(root);" not in source:
    source = source.replace(needle, replacement, 1)

# Stable Settings section: provider controls are directly visible and there is
# a separator before the rest of Settings. No separate API activity is needed.
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
            <brls:Button id="api-source-miruro" width="auto" height="auto" text="Miruro" marginTop="16" />
            <brls:Button id="api-source-animepahe" width="auto" height="auto" text="AnimePahe" />
            <brls:Button id="api-source-gogoanime" width="auto" height="auto" text="Gogoanime" />
            <brls:Button id="api-source-aniwatch" width="auto" height="auto" text="Aniwatch" />
            <brls:Button id="api-source-hianime" width="auto" height="auto" text="HiAnime" />
            <brls:Separator marginTop="28" />
            <brls:Label width="auto" height="auto" text="Other Settings" fontSize="30" marginTop="24" />
            <brls:Label width="auto" height="auto" text="Saikou Switch native port" marginTop="20" />
        </brls:Box>
    </brls:Tab>'''
if 'id="api-source-aniwatch"' not in xml:
    if base_settings in xml:
        xml = xml.replace(base_settings, selector_settings, 1)
    else:
        raise SystemExit("Could not locate stable Settings XML tab")

xml_path.write_text(xml)
source_path.write_text(source)
print("API selector converted to direct Settings section")
