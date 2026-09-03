from pathlib import Path

path = Path("switch/source/main.cpp")
source = path.read_text()

# Controller state: remember the actual SidebarItem that is active. This is
# public Borealis state (SidebarItem::getActiveEvent), so B can return to the
# exact tab instead of guessing/defaulting to Home.
if "g_activeSidebarItem" not in source:
    marker = 'static FILE* g_log = nullptr;\n'
    addition = marker + 'static brls::View* g_activeSidebarItem = nullptr;\nstatic bool g_refreshRequested = false;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate log global")
    source = source.replace(marker, addition, 1)

# Never make the Home root itself focusable. Home has real focusable cards;
# making the root focusable causes the entire content panel to become the
# selected object and prevents the card-level focus model from working.
source = source.replace('            homeBox->setFocusable(true);\n', '', 1)
source = source.replace('        homeBox->setFocusable(true);\n', '', 1)

# Do NOT force focus onto a carousel card here. The TabFrame/sidebar route
# should enter the content root, whose getDefaultFocus() resolves to the first
# real focusable child (the first trending card on Home).
source = source.replace('        if (i == 0) brls::Application::giveFocus(card);\n', '', 1)

# Add X/Y refresh actions to the carousel. They only flip a flag; refresh is
# performed between frames so the focused view is never deleted in its action.
if '"Refresh", brls::BUTTON_X' not in source:
    marker = '    void registerCardAction(brls::View* card, size_t index)\n    {\n'
    addition = '''    void registerCardAction(brls::View* card, size_t index)\n    {\n        (void)index;\n        if (this->getActions().empty())\n        {\n            this->registerAction("Refresh", brls::BUTTON_X, [](brls::View*) {\n                g_refreshRequested = true;\n                return true;\n            });\n            this->registerAction("Refresh", brls::BUTTON_Y, [](brls::View*) {\n                g_refreshRequested = true;\n                return true;\n            });\n        }\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate TrendingCarouselViewport::registerCardAction")
    source = source.replace(marker, addition, 1)

# Track the exact sidebar item for every tab through public SidebarItem APIs.
# Sidebar is a ScrollingFrame whose single public Box child contains the
# SidebarItems. Initialize from the normal default focus, then subscribe to
# active events so the pointer follows Home/Search/Library/Settings.
if "SIDEBAR ACTIVE ITEM TRACKING INSTALLED" not in source:
    marker = '    if (tabFrame)\n    {\n'
    addition = '''    if (tabFrame)\n    {\n        brls::View* sidebarView = tabFrame->getView("brls/tab_frame/sidebar");\n        tabFrame->registerAction("Back to sidebar", brls::BUTTON_B, [](brls::View*) {\n            brls::View* current = brls::Application::getCurrentFocus();\n            if (!current || !g_activeSidebarItem)\n                return false;\n\n            // B while the sidebar is focused must not select Home or otherwise\n            // hijack normal global Back/Quit behavior.\n            for (brls::View* node = current; node; node = node->getParent())\n            {\n                if (node == g_activeSidebarItem)\n                    return false;\n            }\n\n            brls::Application::giveFocus(g_activeSidebarItem);\n            return true;\n        });\n        log_stage("TABFRAME BACK-TO-ACTIVE-SIDEBAR ACTION REGISTERED");\n\n        if (sidebarView)\n        {\n            brls::Box* sidebarBox = dynamic_cast<brls::Box*>(sidebarView);\n            if (sidebarBox)\n            {\n                g_activeSidebarItem = sidebarBox->getDefaultFocus();\n                auto& sidebarChildren = sidebarBox->getChildren();\n                if (!sidebarChildren.empty())\n                {\n                    brls::Box* sidebarContent = dynamic_cast<brls::Box*>(sidebarChildren.front());\n                    if (sidebarContent)\n                    {\n                        for (brls::View* child : sidebarContent->getChildren())\n                        {\n                            brls::SidebarItem* item = dynamic_cast<brls::SidebarItem*>(child);\n                            if (item)\n                            {\n                                item->getActiveEvent()->subscribe([](brls::View* active) {\n                                    g_activeSidebarItem = active;\n                                });\n                            }\n                        }\n                        log_stage("SIDEBAR ACTIVE ITEM TRACKING INSTALLED");\n                    }\n                }\n            }\n        }\n        else\n            log_stage("SIDEBAR ACTIVE ITEM TRACKING LOOKUP FAILED");\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame content block")
    source = source.replace(marker, addition, 1)

# Insert a deferred refresh helper. The action only flips a flag; actual
# content replacement happens after the current frame's input processing.
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

# Keep normal global B/back/quit behavior enabled when the sidebar itself is
# focused. The TabFrame action above consumes B only from content.
source = source.replace('brls::Application::setGlobalQuit(false);', 'brls::Application::setGlobalQuit(true);', 1)

# Process a deferred X/Y refresh between frames.
if "if (g_refreshRequested)" not in source:
    marker = '    while (brls::Application::mainLoop())\n    {\n        ++loopCount;\n'
    replacement = '''    while (brls::Application::mainLoop())\n    {\n        if (g_refreshRequested)\n        {\n            g_refreshRequested = false;\n            refresh_home_content(tabFrame);\n        }\n\n        ++loopCount;\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate main loop")
    source = source.replace(marker, replacement, 1)

# The workflow patches Borealis before this script runs. Correct that patch's
# focus model using only public APIs: sidebar RIGHT enters the content root;
# content root itself is focusable only when it has no focusable descendant.
# For Home, the real cards remain individual focus targets. For static tabs,
# the page root is a valid single focus target.
borealis_tab = Path("switch/borealis/library/lib/views/tab_frame.cpp")
if borealis_tab.exists():
    tab_source = borealis_tab.read_text()

    old_add = '''        // Treat the tab content as one focusable region for now. Its internal\n        // controls can later provide their own routes without changing the\n        // sidebar/content boundary.\n        newContent->setFocusable(true);\n        view->setCustomNavigationRoute(FocusDirection::RIGHT, newContent);\n        newContent->setCustomNavigationRoute(FocusDirection::LEFT, view);\n\n        newContent->setGrow(1.0f);'''
    new_add = '''        // Enter the tab through its default focus. Only make the root itself\n        // focusable when it has no focusable descendant (static pages such as\n        // Search/Library/Settings). Home's cards therefore remain individual\n        // focus targets instead of selecting the whole panel.\n        if (!newContent->getDefaultFocus())\n            newContent->setFocusable(true);\n\n        view->setCustomNavigationRoute(FocusDirection::RIGHT, newContent);\n        if (newContent->isFocusable())\n            newContent->setCustomNavigationRoute(FocusDirection::LEFT, view);\n\n        newContent->setGrow(1.0f);'''
    if old_add in tab_source:
        tab_source = tab_source.replace(old_add, new_add, 1)
    elif 'newContent->setFocusable(true);' in tab_source and 'view->setCustomNavigationRoute(FocusDirection::RIGHT, newContent);' in tab_source:
        import re
        pattern = re.compile(r'        newContent->setFocusable\(true\);\n        view->setCustomNavigationRoute\(FocusDirection::RIGHT, newContent\);\n        newContent->setCustomNavigationRoute\(FocusDirection::LEFT, view\);')
        replacement = '''        if (!newContent->getDefaultFocus())\n            newContent->setFocusable(true);\n\n        view->setCustomNavigationRoute(FocusDirection::RIGHT, newContent);\n        if (newContent->isFocusable())\n            newContent->setCustomNavigationRoute(FocusDirection::LEFT, view);'''
        tab_source, count = pattern.subn(replacement, tab_source, count=1)
        if count != 1:
            raise SystemExit("Could not correct TabFrame addTab focus patch")

    # The workflow's setTabContent patch installs a LEFT route on content even
    # when that content is not focusable. Keep only the public sidebar ->
    # content route; normal traversal and the application B action handle back.
    old_set = '''    // Establish an explicit left/right focus bridge between the sidebar\n    // and the currently attached content region. This avoids depending on\n    // TabFrame's internal focus heuristics and keeps the route valid while\n    // the active tab is replaced.\n    View* sidebarFocus = this->sidebar->getDefaultFocus();\n    if (sidebarFocus)\n    {\n        sidebarFocus->setCustomNavigationRoute(FocusDirection::RIGHT, content);\n        content->setCustomNavigationRoute(FocusDirection::LEFT, sidebarFocus);\n    }'''
    new_set = '''    // Attach the public right-side entry route for the Home content that is\n    // manually supplied by the application. Do not install a LEFT route on\n    // a potentially non-focusable content root; normal focus traversal and\n    // the application-level B action handle the return path.\n    View* sidebarFocus = this->sidebar->getDefaultFocus();\n    if (sidebarFocus)\n        sidebarFocus->setCustomNavigationRoute(FocusDirection::RIGHT, content);'''
    if old_set in tab_source:
        tab_source = tab_source.replace(old_set, new_set, 1)

    borealis_tab.write_text(tab_source)

path.write_text(source)
print("Controller controls patch applied with explicit active-tab focus and B routing")
