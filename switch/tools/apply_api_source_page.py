from pathlib import Path
import re

source_path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")
api_xml_path = Path("switch/romfs/xml/activity/api_source.xml")

source = source_path.read_text()
xml = xml_path.read_text()

# The existing working selector patch is deliberately kept as the base. This
# second-stage patch only changes its Settings presentation to an Activity
# page, avoiding any new Borealis widgets or unsupported dependencies.

# Replace the three provider buttons in Settings with one entry point.
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
xml = xml.replace(old_settings, new_settings, 1)
xml_path.write_text(xml)

# Dedicated API source Activity. This uses only controls already present in
# the pinned Borealis build (Activity, Box, Label, Button).
api_xml_path.write_text('''<brls:Box width="auto" height="auto" axis="column" paddingTop="50" paddingLeft="70" paddingRight="70">
    <brls:Label width="auto" height="auto" text="API Source" fontSize="40" />
    <brls:Label id="api-source-selected" width="auto" height="auto" text="Selected: Miruro" marginTop="18" />
    <brls:Label width="auto" height="auto" text="Choose the anime metadata provider" marginTop="10" />
    <brls:Button id="api-source-miruro" width="auto" height="auto" text="Miruro" marginTop="28" />
    <brls:Button id="api-source-animepahe" width="auto" height="auto" text="AnimePahe" marginTop="10" />
    <brls:Button id="api-source-gogoanime" width="auto" height="auto" text="Gogoanime" marginTop="10" />
</brls:Box>
''')

# Replace the existing selector binder with a small Settings entry-point
# binder. The provider buttons are now owned by ApiSourceActivity.
start = source.find("static void bind_api_settings_actions(brls::TabFrame* tabFrame)")
if start == -1:
    raise SystemExit("Could not locate existing API settings binder")
end = source.find("static brls::View* load_home_content_from_xml()", start)
if end == -1:
    raise SystemExit("Could not locate API binder end anchor")

api_class = r'''class ApiSourceActivity : public brls::Activity
{
public:
    brls::View* createContentView() override
    {
        return brls::View::createFromXMLResource("activity/api_source.xml");
    }

    void onContentAvailable() override
    {
        brls::Label* selected = dynamic_cast<brls::Label*>(getView("api-source-selected"));
        brls::Button* miruro = dynamic_cast<brls::Button*>(getView("api-source-miruro"));
        brls::Button* animepahe = dynamic_cast<brls::Button*>(getView("api-source-animepahe"));
        brls::Button* gogoanime = dynamic_cast<brls::Button*>(getView("api-source-gogoanime"));
        if (!selected || !miruro || !animepahe || !gogoanime)
            return;

        auto update = [selected](int source) {
            g_apiSource = source;
            selected->setText(std::string("Selected: ") + api_source_name(g_apiSource));
            save_api_source();
        };

        miruro->registerClickAction([update](brls::View*) {
            update(0);
            return true;
        });
        animepahe->registerClickAction([update](brls::View*) {
            update(1);
            return true;
        });
        gogoanime->registerClickAction([update](brls::View*) {
            update(2);
            return true;
        });

        selected->setText(std::string("Selected: ") + api_source_name(g_apiSource));
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
        brls::Application::pushActivity(new ApiSourceActivity(), brls::TransitionAnimation::SLIDE_LEFT);
        return true;
    });

    if (g_activeSidebarItem)
        openApiSource->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);

    g_boundSettingsTab = settingsTab;
    log_stage("SETTINGS API PAGE BOUND");
}

'''
source = source[:start] + api_class + source[end:]
source_path.write_text(source)
print("API source Settings page patch applied")
