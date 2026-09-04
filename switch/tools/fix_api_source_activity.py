from pathlib import Path

path = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/api_source.xml")
source = path.read_text()

# The provider registry is the single source of truth for the selector. This
# keeps adding/removing providers independent from the Activity implementation.
include = '#include "api_sources.hpp"\n'
if include not in source:
    first_include_end = source.find("\n", source.find("#include"))
    if first_include_end < 0:
        raise SystemExit("Could not locate main.cpp include boundary")
    source = source[:first_include_end + 1] + include + source[first_include_end + 1:]

# The selector patch originally owned api_source_name(). Replace that local
# helper with the shared registry helper and allow all currently registered IDs.
old_name = '''static const char* api_source_name(int source)
{
    switch (source)
    {
        case 1: return "AnimePahe";
        case 2: return "Gogoanime";
        default: return "Miruro";
    }
}

'''
if old_name in source:
    source = source.replace(old_name, '', 1)
source = source.replace('value >= 0 && value <= 2', 'api_source_is_valid(value)', 1)

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
</brls:Box>''')

replacement = r'''class ApiSourceActivity : public brls::Activity
{
public:
    brls::View* getDefaultFocus() override
    {
        return defaultFocus;
    }

    brls::View* createContentView() override
    {
        brls::View* root = brls::View::createFromXMLResource("activity/api_source.xml");
        if (!root)
            return nullptr;

        brls::Label* current = dynamic_cast<brls::Label*>(root->getView("api-source-current"));
        if (current)
            current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));

        // Build every enabled provider from the shared registry. Adding or
        // removing an API therefore only changes api_sources.hpp; this Activity
        // does not need another provider-specific branch.
        brls::Button* firstButton = nullptr;
        for (std::size_t i = 0; i < kApiSourceCount; ++i)
        {
            const ApiSourceInfo& provider = kApiSources[i];
            if (!provider.enabled)
                continue;

            brls::Button* button = new brls::Button();
            button->setText(provider.name);
            button->setWidth(760);
            button->setMargins(0, firstButton ? 18 : 28, 0, 0);
            const int sourceId = static_cast<int>(provider.id);
            button->registerClickAction([current, sourceId](brls::View*) {
                if (g_apiSource == sourceId)
                {
                    log_stage("API SOURCE SELECTION UNCHANGED");
                    return true;
                }

                g_apiSource = sourceId;
                clear_api_cache();
                save_api_source();
                if (current)
                    current->setText(std::string("Anime API: ") + api_source_name(g_apiSource));
                g_refreshRequested = true;
                log_stage("API SOURCE CHANGED - CACHE CLEARED - HOME REFRESH REQUESTED");
                return true;
            });
            root->addView(button);
            if (!firstButton)
                firstButton = button;
        }
        defaultFocus = firstButton;

        // A newly-created Activity content view starts with hidden=false.
        // Borealis' FADE push sets its alpha to 0 and the later show() is a
        // no-op when hidden=false, leaving the page permanently invisible.
        // Mark it hidden here so pushActivity's show() performs the fade-in.
        root->hide([] {}, false, 0);

        root->registerAction("Back", brls::BUTTON_B, [](brls::View*) {
            log_stage("API SOURCE ACTIVITY BACK");
            brls::Application::popActivity(brls::TransitionAnimation::FADE);
            return true;
        });

        return root;
    }

private:
    brls::View* defaultFocus = nullptr;
};

'''

# Keep cache invalidation local and deliberately narrow: current Home uses the
# six generic trending cover files. Settings and debug logs are never touched.
if "static void clear_api_cache()" not in source:
    marker = 'class ApiSourceActivity : public brls::Activity\n'
    helper = r'''static void clear_api_cache()
{
    int removed = 0;
    for (int i = 0; i < 6; ++i)
    {
        char path[128];
        std::snprintf(path, sizeof(path), "%s/trending_%d.jpg", kCacheDir, i);
        if (std::remove(path) == 0)
            ++removed;
    }

    char marker[96];
    std::snprintf(marker, sizeof(marker), "API CACHE CLEARED FILES %d", removed);
    log_stage(marker);
}

'''
    source = source.replace(marker, helper + marker, 1)

source = source[:start] + replacement + source[end:]
path.write_text(source)
print("API selector now uses the shared five-provider registry and cache invalidation")