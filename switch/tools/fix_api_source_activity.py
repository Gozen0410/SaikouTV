from pathlib import Path

path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/api_source.xml")
source = path.read_text()

start = source.find("class ApiSourceActivity : public brls::Activity")
if start < 0:
    raise SystemExit("Could not locate ApiSourceActivity")
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

replacement = r'''class ApiSourceActivity : public brls::Activity
{
public:
    brls::View* createContentView() override
    {
        brls::View* root = brls::View::createFromXMLResource("activity/api_source.xml");
        if (!root)
            return nullptr;

        brls::Label* current = dynamic_cast<brls::Label*>(root->getView("api-source-current"));
        brls::Button* miruro = dynamic_cast<brls::Button*>(root->getView("api-source-miruro"));
        brls::Button* animepahe = dynamic_cast<brls::Button*>(root->getView("api-source-animepahe"));
        brls::Button* gogoanime = dynamic_cast<brls::Button*>(root->getView("api-source-gogoanime"));

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

        root->registerAction("Back", brls::BUTTON_B, [](brls::View*) {
            log_stage("API SOURCE ACTIVITY BACK");
            brls::Application::popActivity(brls::TransitionAnimation::SLIDE_RIGHT);
            return true;
        });

        return root;
    }
};

'''

path.write_text(source[:start] + replacement + source[end:])
print("API source activity now uses themed XML content")