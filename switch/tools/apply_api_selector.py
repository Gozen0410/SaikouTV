from pathlib import Path

path = Path("switch/source/main.cpp")
source = path.read_text()

if "g_apiSource" in source:
    print("API selector patch already present")
    raise SystemExit(0)

marker = 'static bool g_homeRefreshInProgress = false;\n'
addition = marker + '''static int g_apiSource = 0; // 0=Miruro, 1=AnimePahe, 2=Gogoanime
'''
if source.count(marker) != 1:
    raise SystemExit("Could not locate Home persistence globals")
source = source.replace(marker, addition, 1)

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
    brls::Box* root = new brls::Box(brls::Axis::COLUMN);
    root->setJustifyContent(brls::JustifyContent::FLEX_START);

    brls::Header* header = new brls::Header("API Source");
    root->addView(header);

    brls::Label* current = new brls::Label();
    current->setText("Anime API");
    current->setFontSize(18);
    root->addView(current);

    const char* providers[] = {"Miruro", "AnimePahe", "Gogoanime"};
    for (int i = 0; i < 3; ++i)
    {
        brls::Button* button = new brls::Button(providers[i]);
        button->registerClickAction([i, current, providers](brls::View*) {
            g_apiSource = i;
            current->setText(std::string("Anime API: ") + providers[i]);
            save_api_source();
            return true;
        });
        root->addView(button);
    }

    current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
    return root;
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

# Defer the Settings content replacement to the frame loop. The Settings
# sidebar item is discovered from the existing sidebar children.
marker = '                        log_stage("SIDEBAR ACTIVE ITEM TRACKING INSTALLED");\n'
addition = marker + '''                        if (!sidebarContent->getChildren().empty())
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
if source.count(marker) != 1:
    raise SystemExit("Could not locate sidebar tracking completion")
source = source.replace(marker, addition, 1)

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

marker = '    ensure_app_dirs();\n'
replacement = marker + '    load_api_source();\n'
if source.count(marker) != 1:
    raise SystemExit("Could not locate app directory initialization")
source = source.replace(marker, replacement, 1)

path.write_text(source)
print("API source selector patch applied")
