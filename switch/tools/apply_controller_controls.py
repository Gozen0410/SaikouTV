from pathlib import Path

path = Path("switch/source/main.cpp")
source = path.read_text()

# Controller behavior is layered on top of the stable carousel and TabFrame
# lifetime fix. Do not bypass Borealis focus; the normal TabFrame/sidebar
# navigation is now safe and should own initial focus.
if "g_refreshRequested" not in source:
    marker = 'static FILE* g_log = nullptr;\n'
    addition = marker + 'static bool g_refreshRequested = false;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate log global")
    source = source.replace(marker, addition, 1)

# Do NOT force focus onto a carousel card here. The Activity/TabFrame normal
# default-focus path should initially focus the sidebar. Borealis' native
# SidebarItem A action already enters the content area, and the row-based
# focus traversal returns to the sidebar with LEFT.
source = source.replace('        if (i == 0) brls::Application::giveFocus(card);\n', '', 1)

# Add X/Y refresh actions to the carousel. Back is deliberately NOT handled
# here: it must bubble through the content view to the TabFrame-level Back
# action, which returns focus to the sidebar instead of popping the activity.
if '"Refresh", brls::BUTTON_X' not in source:
    marker = '    void registerCardAction(brls::View* card, size_t index)\n    {\n'
    addition = '''    void registerCardAction(brls::View* card, size_t index)\n    {\n        (void)index;\n        if (this->getActions().empty())\n        {\n            this->registerAction("Refresh", brls::BUTTON_X, [](brls::View*) {\n                g_refreshRequested = true;\n                return true;\n            });\n            this->registerAction("Refresh", brls::BUTTON_Y, [](brls::View*) {\n                g_refreshRequested = true;\n                return true;\n            });\n        }\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate TrendingCarouselViewport::registerCardAction")
    source = source.replace(marker, addition, 1)

# Install one public TabFrame-level Back action. It must only handle B while
# focus is in the active content region. If B is pressed on any sidebar item,
# return false so the normal global Back/Quit behavior remains available.
# For content, use the content root's existing LEFT custom-focus route. That
# route was installed by TabFrame itself and points to the exact sidebar item
# for the active tab (Home/Search/Library/Settings), rather than always using
# the sidebar's default Home item.
if '"Back to sidebar", brls::BUTTON_B' not in source:
    marker = '    if (tabFrame)\n    {\n'
    addition = '''    if (tabFrame)\n    {\n        brls::View* sidebar = tabFrame->getView("brls/tab_frame/sidebar");\n        if (sidebar)\n        {\n            tabFrame->registerAction("Back to sidebar", brls::BUTTON_B, [tabFrame, sidebar](brls::View*) {\n                brls::View* current = brls::Application::getCurrentFocus();\n                if (!current)\n                    return false;\n\n                // B on the sidebar must not jump to Home. Let Borealis'\n                // normal global Back/Quit handling process it instead.\n                for (brls::View* node = current; node; node = node->getParent())\n                {\n                    if (node == sidebar)\n                        return false;\n                }\n\n                // Find the root of the currently focused content region.\n                // TabFrame -> content Box -> active tab content -> children.\n                // The active tab content is the node whose parent is the\n                // content Box and whose grandparent is this TabFrame.\n                brls::View* contentRoot = current;\n                while (contentRoot && contentRoot->getParent() &&\n                       contentRoot->getParent()->getParent() != tabFrame)\n                {\n                    contentRoot = contentRoot->getParent();\n                }\n\n                if (!contentRoot || !contentRoot->getParent() ||\n                    contentRoot->getParent()->getParent() != tabFrame)\n                    return false;\n\n                // TabFrame's normal creator path installs a LEFT custom route\n                // from this exact content root to its corresponding sidebar\n                // item. Reuse that public focus behavior instead of touching\n                // TabFrame's private active-tab state.\n                brls::View* sidebarTarget = contentRoot->getNextFocus(\n                    brls::FocusDirection::LEFT, contentRoot);\n                if (!sidebarTarget)\n                    return false;\n\n                brls::Application::giveFocus(sidebarTarget);\n                return true;\n            });\n            log_stage("TABFRAME BACK-TO-SIDEBAR ACTION REGISTERED");\n        }\n        else\n            log_stage("TABFRAME SIDEBAR LOOKUP FAILED");\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame content block")
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
        homeBox->setFocusable(true);
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

# Keep the normal Borealis global quit action enabled.
source = source.replace('brls::Application::setGlobalQuit(false);', 'brls::Application::setGlobalQuit(true);', 1)

# Process a deferred X/Y refresh between Borealis frames.
if "if (g_refreshRequested)" not in source:
    marker = '    while (brls::Application::mainLoop())\n    {\n        ++loopCount;\n'
    replacement = '''    while (brls::Application::mainLoop())\n    {\n        if (g_refreshRequested)\n        {\n            g_refreshRequested = false;\n            refresh_home_content(tabFrame);\n        }\n\n        ++loopCount;\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate main loop")
    source = source.replace(marker, replacement, 1)

path.write_text(source)
print("Controller controls patch applied with tab-aware Back routing")
