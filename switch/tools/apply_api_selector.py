from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")
borealis_header = Path("switch/borealis/library/include/borealis/views/tab_frame.hpp")

source = source_path.read_text()
xml = xml_path.read_text()

# The first selector implementation replaced the active Settings content with
# setTabContent(). That is unsafe during TabFrame activation on this pinned
# Borealis build. Keep Settings XML-owned and only attach actions to the
# already-created buttons after the tab exists.

marker = 'static bool g_homeRefreshInProgress = false;\n'
addition = marker + '''static int g_apiSource = 0; // 0=Miruro, 1=AnimePahe, 2=Gogoanime
static brls::View* g_boundSettingsTab = nullptr;
'''
if "static int g_apiSource" not in source:
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home persistence globals")
    source = source.replace(marker, addition, 1)

# Add a tiny public read-only accessor to the already-patched TabFrame. The
# active tab remains private; this only lets the application bind callbacks to
# the XML-created Settings controls without replacing the active view.
header = borealis_header.read_text()
if "View* getActiveTab() const" not in header:
    marker = '    void addSeparator();\n'
    addition = marker + '    View* getActiveTab() const { return this->activeTab; }\n'
    if header.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame addSeparator declaration")
    header = header.replace(marker, addition, 1)
    borealis_header.write_text(header)

# Replace the placeholder Settings body in the app XML with native Buttons.
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

# Bind actions only after the XML-created Settings tab is active. This avoids
# deleting/replacing the active view during the sidebar activation callback.
if "static void bind_api_settings_actions" not in source:
    marker = 'static brls::View* load_home_content_from_xml()\n'
    helper = r'''static void bind_api_settings_actions(brls::TabFrame* tabFrame)
{
    if (!tabFrame)
        return;

    brls::View* settingsTab = tabFrame->getActiveTab();
    if (!settingsTab || settingsTab == g_boundSettingsTab)
        return;

    g_boundSettingsTab = settingsTab;
    brls::Label* current = nullptr;
    std::vector<brls::Button*> buttons;

    std::function<void(brls::View*)> visit = [&](brls::View* view) {
        if (!view)
            return;
        if (brls::Label* label = dynamic_cast<brls::Label*>(view))
        {
            if (label->getFullText() == "Anime API: Miruro" ||
                label->getFullText() == "Anime API: AnimePahe" ||
                label->getFullText() == "Anime API: Gogoanime")
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
    }

    current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
    log_stage("SETTINGS API ACTIONS BOUND");
}

'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home XML helper boundary")
    source = source.replace(marker, helper + marker, 1)

# Remove the old settings replacement machinery if it is present.
start = source.find('static constexpr const char* kSettingsPath')
end = source.find('static brls::View* load_home_content_from_xml()')
if start != -1 and end != -1 and start < end:
    source = source[:start] + source[end:]

# Remove the old Settings active subscription and replace it with a simple
# deferred bind request. The controller's existing main-loop refresh flag is
# reused, but no setTabContent() is performed for Settings.
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

# Bind on the main loop after TabFrame has finished creating the active XML tab.
if "bind_api_settings_actions(tabFrame);" not in source:
    marker = '    while (brls::Application::mainLoop())\n    {\n'
    addition = marker + '''        if (g_boundSettingsTab == nullptr)
            bind_api_settings_actions(tabFrame);
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