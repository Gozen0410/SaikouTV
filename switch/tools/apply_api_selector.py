from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")
borealis_header = Path("switch/borealis/library/include/borealis/views/tab_frame.hpp")

source = source_path.read_text()
xml = xml_path.read_text()

# Keep Settings content XML-owned. Replacing the currently active Settings
# view with TabFrame::setTabContent() crashes this pinned Borealis build and
# also disappears when the tab is recreated. Instead, put the three buttons in
# the normal Settings XML and bind their actions after TabFrame creates them.

if "static int g_apiSource" not in source:
    marker = 'static bool g_homeRefreshInProgress = false;\n'
    addition = marker + '''static int g_apiSource = 0; // 0=Miruro, 1=AnimePahe, 2=Gogoanime
static brls::View* g_boundSettingsTab = nullptr;
'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home persistence globals")
    source = source.replace(marker, addition, 1)

# Add the minimal accessor needed to inspect the XML-created active tab.
header = borealis_header.read_text()
if "View* getActiveTab() const" not in header:
    marker = '    void addSeparator();\n'
    addition = marker + '    View* getActiveTab() const { return this->activeTab; }\n'
    if header.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame addSeparator declaration")
    header = header.replace(marker, addition, 1)
    borealis_header.write_text(header)

# The main source already uses <functional> in the controller patch on some
# revisions, but make the dependency explicit for the recursive visitor.
if '#include <functional>' not in source:
    marker = '#include <algorithm>\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate standard include boundary")
    source = source.replace(marker, marker + '#include <functional>\n', 1)

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

    brls::Label* current = nullptr;
    std::vector<brls::Button*> buttons;

    std::function<void(brls::View*)> visit = [&](brls::View* view) {
        if (!view)
            return;

        if (brls::Label* label = dynamic_cast<brls::Label*>(view))
        {
            const std::string text = label->getFullText();
            if (text == "Anime API: Miruro" || text == "Anime API: AnimePahe" || text == "Anime API: Gogoanime")
                current = label;
        }

        if (brls::Button* button = dynamic_cast<brls::Button*>(view))
            buttons.push_back(button);

        for (brls::View* child : view->getChildren())
            visit(child);
    };

    visit(settingsTab);
    if (!current || buttons.size() < 3)
        return;

    int bound = 0;
    for (brls::Button* button : buttons)
    {
        const std::string name = button->getText();
        int source = -1;
        if (name == "Miruro") source = 0;
        else if (name == "AnimePahe") source = 1;
        else if (name == "Gogoanime") source = 2;
        if (source < 0)
            continue;

        button->registerClickAction([source, current](brls::View*) {
            g_apiSource = source;
            current->setText(std::string("Anime API: ") + api_source_name(source));
            save_api_source();
            return true;
        });
        ++bound;
    }

    if (bound == 3)
    {
        current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
        g_boundSettingsTab = settingsTab;
        log_stage("SETTINGS API ACTIONS BOUND");
    }
}

'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home XML helper boundary")
    source = source.replace(marker, helper + marker, 1)

# Replace the placeholder Settings tab with a static, safe XML UI.
old_settings = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="Settings" fontSize="36" />
            <brls:Label width="auto" height="auto" text="Saikou Switch native port" marginTop="20" />
        </brls:Box>
    </brls:Tab>'''
new_settings = '''    <brls:Tab label="Settings">
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="API Source" fontSize="36" />
            <brls:Label width="auto" height="auto" text="Anime API: Miruro" marginTop="20" />
            <brls:Button width="auto" height="auto" text="Miruro" marginTop="10" />
            <brls:Button width="auto" height="auto" text="AnimePahe" />
            <brls:Button width="auto" height="auto" text="Gogoanime" />
        </brls:Box>
    </brls:Tab>'''
if old_settings in xml:
    xml = xml.replace(old_settings, new_settings, 1)
elif 'text="AnimePahe"' not in xml or 'text="Gogoanime"' not in xml:
    raise SystemExit("Could not locate Settings XML block")
xml_path.write_text(xml)

# The Settings activation callback only invalidates the pointer. No view is
# replaced from inside the event callback. The main loop binds actions to the
# newly-created tab on the following frame.
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

# Bind after the current TabFrame has completed its lazy XML tab creation.
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
print("API selector converted to static Settings XML with deferred action binding")