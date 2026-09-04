from pathlib import Path

path = Path("switch/source/main.cpp")
source = path.read_text()

start = source.find("class ApiSourceActivity : public brls::Activity")
if start < 0:
    raise SystemExit("Could not locate ApiSourceActivity")
end = source.find("static void bind_api_settings_actions", start)
if end < 0:
    raise SystemExit("Could not locate API settings binder")

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

        auto addProvider = [root, selected](const char* name, int sourceId, float topMargin) {
            brls::Button* button = new brls::Button();
            button->setText(name);
            button->setWidth(760);
            button->setMargins(0, topMargin, 0, 0);
            button->registerClickAction([selected, sourceId](brls::View*) {
                g_apiSource = sourceId;
                save_api_source();
                selected->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
                log_stage("API SOURCE SELECTION SAVED");
                return true;
            });
            root->addView(button);
        };

        addProvider("Miruro", 0, 28);
        addProvider("AnimePahe", 1, 18);
        addProvider("Gogoanime", 2, 18);

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
print("API source activity rebuilt with direct content and B-back action")
