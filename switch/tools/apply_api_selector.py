from pathlib import Path

path = Path("switch/source/main.cpp")
source = path.read_text()

if "g_apiSource" in source:
    print("API selector patch already present")
    raise SystemExit(0)

# Add the selector state next to the existing Home persistence state.
marker = 'static bool g_homeRefreshInProgress = false;\n'
addition = marker + '''static int g_apiSource = 0; // 0=Miruro, 1=AnimePahe, 2=Gogoanime
static bool g_settingsRefreshRequested = false;
static brls::View* g_settingsSidebarItem = nullptr;
'''
if source.count(marker) != 1:
    raise SystemExit("Could not locate Home persistence globals")
source = source.replace(marker, addition, 1)

# Persistent selector storage. Keep it deliberately tiny and independent from
# the API implementation so changing providers cannot corrupt Home state.
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

static brls::View* create_api_settings_content()
{
    brls::List* list = new brls::List();
    list->addView(new brls::Header("API Source", false));

    brls::ListItem* apiItem = new brls::ListItem("Anime API");
    apiItem->setValue(api_source_name(g_apiSource));
    apiItem->getClickEvent()->subscribe([apiItem](brls::View*) {
        brls::Dropdown::open(
            "Anime API",
            {"Miruro", "AnimePahe", "Gogoanime"},
            [apiItem](int selection) {
                if (selection < 0 || selection > 2)
                    return;

                g_apiSource = selection;
                apiItem->setValue(api_source_name(g_apiSource));
                save_api_source();
                char marker[96];
                std::snprintf(marker, sizeof(marker), "API SOURCE SELECTED %s", api_source_name(g_apiSource));
                log_stage(marker);
            },
            g_apiSource);
    });
    list->addView(apiItem);

    brls::Label* note = new brls::Label();
    note->setText("Select the provider used by Saikou Switch.");
    note->setFontSize(15);
    note->setMargins(0, 12, 0, 0);
    list->addView(note);

    return list;
}

static void refresh_settings_content(brls::TabFrame* tabFrame)
{
    if (!tabFrame)
        return;

    log_stage("SETTINGS CONTENT REFRESH START");
    brls::View* settingsContent = create_api_settings_content();
    if (!settingsContent)
    {
        log_stage("SETTINGS CONTENT CREATE FAILED");
        return;
    }

    tabFrame->setTabContent(settingsContent);
    log_stage("SETTINGS CONTENT ATTACHED");
}

'''
if source.count(marker) != 1:
    raise SystemExit("Could not locate Home refresh helper boundary")
source = source.replace(marker, helper + marker, 1)

# Add the Settings sidebar pointer and an activation callback to the existing
# public SidebarItem tracking. Settings is the last sidebar item in main.xml.
marker = '                        log_stage("SIDEBAR ACTIVE ITEM TRACKING INSTALLED");\n'
addition = marker + '''                        if (!sidebarContent->getChildren().empty())
                        {
                            g_settingsSidebarItem = sidebarContent->getChildren().back();
                            if (g_settingsSidebarItem)
                            {
                                brls::SidebarItem* settingsItem = dynamic_cast<brls::SidebarItem*>(g_settingsSidebarItem);
                                if (settingsItem)
                                {
                                    settingsItem->getActiveEvent()->subscribe([](brls::View*) {
                                        g_settingsRefreshRequested = true;
                                    });
                                    log_stage("SETTINGS ACTIVE ITEM TRACKING INSTALLED");
                                }
                            }
                        }
'''
if source.count(marker) != 1:
    raise SystemExit("Could not locate sidebar tracking completion")
source = source.replace(marker, addition, 1)

# Process Settings refresh between frames, just like Home refresh, so the
# active-item callback never replaces a view during input dispatch.
marker = '        if (g_refreshRequested)\n        {\n            g_refreshRequested = false;\n            refresh_home_content(tabFrame);\n        }\n\n'
addition = marker + '''        if (g_settingsRefreshRequested)
        {
            g_settingsRefreshRequested = false;
            refresh_settings_content(tabFrame);
        }

'''
if source.count(marker) != 1:
    raise SystemExit("Could not locate deferred refresh processing")
source = source.replace(marker, addition, 1)

# Load the persisted provider before the first UI is created.
marker = '    ensure_app_dirs();\n'
replacement = marker + '    load_api_source();\n'
if source.count(marker) != 1:
    raise SystemExit("Could not locate app directory initialization")
source = source.replace(marker, replacement, 1)

path.write_text(source)
print("API source selector patch applied")
