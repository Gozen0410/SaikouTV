from pathlib import Path

path = Path("switch/source/main.cpp")
source = path.read_text()

# This patch intentionally builds on the known-good carousel patch. It adds
# controller behavior without touching TabFrame internals.
if "g_refreshRequested" not in source:
    marker = 'static FILE* g_log = nullptr;\n'
    addition = marker + 'static bool g_refreshRequested = false;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate log global")
    source = source.replace(marker, addition, 1)

# Give the first trending card initial focus. Borealis handles D-pad/analog
# navigation from there, and the card's A action remains the selector.
if "Application::giveFocus(card);" not in source:
    marker = '        row->addView(card);\n'
    replacement = marker + '        if (i == 0) brls::Application::giveFocus(card);\n'
    if source.count(marker) != 1:
        raise SystemExit(f"expected one carousel card insertion point, found {source.count(marker)}")
    source = source.replace(marker, replacement, 1)

# Add X/Y refresh and B back to the carousel's parent. Actions bubble from a
# focused card to this viewport, so no raw TabFrame internals are required.
if '"Refresh", brls::BUTTON_X' not in source:
    marker = '    void registerCardAction(brls::View* card, size_t index)\n    {\n'
    addition = '''    void registerCardAction(brls::View* card, size_t index)\n    {\n        (void)index;\n        if (this->getActions().empty())\n        {\n            this->registerAction("Refresh", brls::BUTTON_X, [](brls::View*) {\n                g_refreshRequested = true;\n                return true;\n            });\n            this->registerAction("Refresh", brls::BUTTON_Y, [](brls::View*) {\n                g_refreshRequested = true;\n                return true;\n            });\n            this->registerAction("Back", brls::BUTTON_B, [](brls::View*) {\n                brls::Application::popActivity();\n                return true;\n            });\n        }\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate TrendingCarouselViewport::registerCardAction")
    source = source.replace(marker, addition, 1)

# Insert a deferred refresh helper. The action only flips a flag; the actual
# content replacement happens in the main-loop body after input processing,
# avoiding deletion of the currently focused view during its action callback.
if "static void refresh_home_content" not in source:
    main_marker = '\nint main(int argc, char* argv[])\n'
    helper = r'''
static brls::View* load_home_content_from_xml()
{
    const char* homePath = "romfs:/xml/activity/home.xml";
    FILE* homeFile = std::fopen(homePath, "rb");
    if (!homeFile)
    {
        log_stage("REFRESH HOME XML OPEN FAILED");
        return nullptr;
    }

    std::fseek(homeFile, 0, SEEK_END);
    long fileSize = std::ftell(homeFile);
    std::fseek(homeFile, 0, SEEK_SET);
    if (fileSize <= 0 || fileSize > 1024 * 1024)
    {
        std::fclose(homeFile);
        log_stage("REFRESH HOME XML INVALID SIZE");
        return nullptr;
    }

    std::string xml(static_cast<size_t>(fileSize), '\0');
    const size_t readSize = std::fread(xml.data(), 1, xml.size(), homeFile);
    std::fclose(homeFile);
    if (readSize != xml.size())
    {
        log_stage("REFRESH HOME XML READ FAILED");
        return nullptr;
    }

    log_stage("BEFORE REFRESH HOME XML STRING INFLATION");
    brls::View* content = brls::View::createFromXMLString(xml);
    log_stage(content ? "REFRESH HOME XML RETURNED VIEW" : "REFRESH HOME XML RETURNED NULL");
    return content;
}

static void refresh_home_content(brls::TabFrame* tabFrame)
{
    if (!tabFrame)
        return;

    log_stage("CONTROLLER REFRESH START");
    brls::View* homeContent = load_home_content_from_xml();
    if (!homeContent)
    {
        log_stage("CONTROLLER REFRESH XML FAILED");
        return;
    }

    ApiResult api = run_api_probe();
    brls::Box* homeBox = dynamic_cast<brls::Box*>(homeContent);
    if (homeBox)
    {
        brls::Label* status = new brls::Label();
        status->setText(api.status.empty() ? "Refresh complete" : api.status);
        status->setFontSize(16);
        homeBox->addView(status);
        if (!api.response.empty())
            render_trending(homeBox, api.response);
    }

    log_stage("BEFORE REFRESH TABFRAME CONTENT SET");
    tabFrame->setTabContent(homeContent);
    log_stage("AFTER REFRESH TABFRAME CONTENT SET");
}
'''
    if source.count(main_marker) != 1:
        raise SystemExit("Could not locate main() boundary")
    source = source.replace(main_marker, helper + main_marker, 1)

# + should use Borealis' normal global quit action.
source = source.replace('brls::Application::setGlobalQuit(false);', 'brls::Application::setGlobalQuit(true);', 1)

# Process a deferred X/Y refresh between Borealis frames.
if "if (g_refreshRequested)" not in source:
    marker = '    while (brls::Application::mainLoop())\n    {\n        ++loopCount;\n'
    replacement = '''    while (brls::Application::mainLoop())\n    {\n        if (g_refreshRequested)\n        {\n            g_refreshRequested = false;\n            refresh_home_content(tabFrame);\n        }\n\n        ++loopCount;\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate main loop")
    source = source.replace(marker, replacement, 1)

path.write_text(source)
print("Controller controls patch applied")
