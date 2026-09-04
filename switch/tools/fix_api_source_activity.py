from pathlib import Path

path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/api_source.xml")
source = path.read_text()

start = source.find("class ApiSourceView : public brls::Box")
if start < 0:
    raise SystemExit("Could not locate ApiSourceView")
end = source.find("static void bind_api_settings_actions", start)
if end < 0:
    raise SystemExit("Could not locate API settings binder")

xml_path.write_text(r'''<brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingLeft="50" paddingRight="50">
    <brls:Label width="auto" height="auto" text="API Source" fontSize="36" />
    <brls:Label id="api-source-current" width="auto" height="auto" text="Anime API: Miruro" marginTop="16" />
    <brls:Label width="auto" height="auto" text="Choose the anime metadata provider" marginTop="8" />
    <brls:Button id="api-source-miruro" width="auto" height="auto" text="Miruro" marginTop="28" />
    <brls:Button id="api-source-animepahe" width="auto" height="auto" text="AnimePahe" marginTop="18" />
    <brls:Button id="api-source-gogoanime" width="auto" height="auto" text="Gogoanime" marginTop="18" />
</brls:Box>''')

replacement = r'''class ApiSourceView : public brls::Box
{
public:
    ApiSourceView()
    {
        this->inflateFromXMLRes("xml/activity/api_source.xml");

        brls::Label* current = dynamic_cast<brls::Label*>(this->getView("api-source-current"));
        brls::Button* miruro = dynamic_cast<brls::Button*>(this->getView("api-source-miruro"));
        brls::Button* animepahe = dynamic_cast<brls::Button*>(this->getView("api-source-animepahe"));
        brls::Button* gogoanime = dynamic_cast<brls::Button*>(this->getView("api-source-gogoanime"));

        if (current)
            current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));

        auto bindProvider = [current](brls::Button* button, int sourceId) {
            if (!button) return;
            button->registerClickAction([current, sourceId](brls::View*) {
                g_apiSource = sourceId;
                save_api_source();
                if (current)
                    current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
                log_stage("API SOURCE SELECTION SAVED");
                return true;
            });
        };

        bindProvider(miruro, 0);
        bindProvider(animepahe, 1);
        bindProvider(gogoanime, 2);

        this->registerAction("Back", brls::BUTTON_B, [](brls::View* view) {
            log_stage("API SOURCE VIEW BACK");
            view->dismiss();
            return true;
        });
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
    openApiSource->registerClickAction([](brls::View* view) {
        log_stage("API SOURCE VIEW OPEN");
        view->present(new ApiSourceView());
        return true;
    });

    if (g_activeSidebarItem)
        openApiSource->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);

    g_boundSettingsTab = settingsTab;
    log_stage("SETTINGS API PAGE BOUND");
}

'''

path.write_text(source[:start] + replacement + source[end:])
print("API source selector now uses a presented Borealis Box instead of an Activity stack")