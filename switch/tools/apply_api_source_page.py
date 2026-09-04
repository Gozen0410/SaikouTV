from pathlib import Path

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")
source = source_path.read_text()
xml = xml_path.read_text()

old_settings = '''        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="API Source" fontSize="36" />
            <brls:Label id="api-source-current" width="auto" height="auto" text="Anime API: Miruro" marginTop="20" />
            <brls:Button id="api-source-miruro" width="auto" height="auto" text="Miruro" marginTop="10" />
            <brls:Button id="api-source-animepahe" width="auto" height="auto" text="AnimePahe" />
            <brls:Button id="api-source-gogoanime" width="auto" height="auto" text="Gogoanime" />
        </brls:Box>'''
new_settings = '''        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="Settings" fontSize="36" />
            <brls:Button id="api-source-open" width="auto" height="auto" text="API Source" marginTop="24" />
            <brls:Label id="api-source-current" width="auto" height="auto" text="Anime API: Miruro" marginTop="10" />
        </brls:Box>'''
if old_settings not in xml:
    raise SystemExit("Could not locate working API selector Settings block")
xml_path.write_text(xml.replace(old_settings, new_settings, 1))

start = source.find("static void bind_api_settings_actions(brls::TabFrame* tabFrame)")
if start == -1:
    raise SystemExit("Could not locate existing API settings binder")
end = source.find("static brls::View* load_home_content_from_xml()", start)
if end == -1:
    raise SystemExit("Could not locate API binder end anchor")

replacement = r'''class ApiSourceActivity : public brls::Activity
{
public:
    brls::View* createContentView() override
    {
        brls::Box* root = new brls::Box(brls::Axis::COLUMN);
        root->setWidth(900);
        root->setGrow(1.0f);
        root->setPadding(50, 70, 40, 70);

        brls::Label* heading = new brls::Label();
        heading->setText("API Source");
        heading->setFontSize(40);
        heading->setFocusable(false);
        root->addView(heading);

        brls::Label* selected = new brls::Label();
        selected->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
        selected->setFontSize(20);
        selected->setMargins(0, 16, 0, 0);
        selected->setFocusable(false);
        root->addView(selected);

        brls::Label* hint = new brls::Label();
        hint->setText("Choose the anime metadata provider");
        hint->setFontSize(15);
        hint->setMargins(0, 8, 0, 0);
        hint->setFocusable(false);
        root->addView(hint);

        auto makeProvider = [root, selected](const char* name, int source, float topMargin) {
            brls::Button* button = new brls::Button();
            button->setText(name);
            button->setWidth(760);
            button->setMargins(0, topMargin, 0, 0);
            button->registerClickAction([selected, source](brls::View*) {
                g_apiSource = source;
                save_api_source();
                selected->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
                log_stage("API SOURCE SELECTION SAVED");
                return true;
            });
            root->addView(button);
            return button;
        };

        makeProvider("Miruro", 0, 28);
        makeProvider("AnimePahe", 1, 18);
        makeProvider("Gogoanime", 2, 18);
        return root;
    }
};

static void bind_api_settings_actions(brls::TabFrame* tabFrame)
{
    if (!tabFrame)
        return;

    brls::View* settingsTab = tabFrame->getActiveTab();
    if (!settingsTab || settingsTab == g_boundSettingsTab)
        return;

    brls::Label* current = dynamic_cast<brls::Label*>(settingsTab->getView("api-source-current"));
    brls::Button* openApiSource = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-open"));
    if (!current || !openApiSource)
        return;

    current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
    openApiSource->registerClickAction([](brls::View*) {
        log_stage("API SOURCE ACTIVITY OPEN");
        brls::Application::pushActivity(new ApiSourceActivity(), brls::TransitionAnimation::SLIDE_LEFT);
        return true;
    });

    if (g_activeSidebarItem)
        openApiSource->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);

    g_boundSettingsTab = settingsTab;
    log_stage("SETTINGS API PAGE BOUND");
}

'''
source_path.write_text(source[:start] + replacement + source[end:])
print("API source Activity rewritten programmatically")