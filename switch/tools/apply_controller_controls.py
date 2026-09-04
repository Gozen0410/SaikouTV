from pathlib import Path
import re

path = Path("switch/source/main.cpp")
source = path.read_text()

if "g_activeSidebarItem" not in source:
    marker = 'static FILE* g_log = nullptr;\n'
    addition = marker + 'static brls::View* g_activeSidebarItem = nullptr;\nstatic bool g_refreshRequested = false;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate log global")
    source = source.replace(marker, addition, 1)

source = source.replace('            homeBox->setFocusable(true);\n', '', 1)
source = source.replace('        homeBox->setFocusable(true);\n', '', 1)
source = source.replace('        if (i == 0) brls::Application::giveFocus(card);\n', '', 1)

if '"Refresh", brls::BUTTON_X' not in source:
    marker = '    void registerCardAction(brls::View* card, size_t index)\n    {\n'
    addition = '''    void registerCardAction(brls::View* card, size_t index)\n    {\n        (void)index;\n        if (this->getActions().empty())\n        {\n            this->registerAction("Refresh", brls::BUTTON_X, [](brls::View*) {\n                g_refreshRequested = true;\n                return true;\n            });\n            this->registerAction("Refresh", brls::BUTTON_Y, [](brls::View*) {\n                g_refreshRequested = true;\n                return true;\n            });\n        }\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate TrendingCarouselViewport::registerCardAction")
    source = source.replace(marker, addition, 1)

if "SIDEBAR ACTIVE ITEM TRACKING INSTALLED" not in source:
    marker = '    if (tabFrame)\n    {\n'
    addition = '''    if (tabFrame)\n    {\n        brls::View* sidebarView = tabFrame->getView("brls/tab_frame/sidebar");\n        tabFrame->registerAction("Back to sidebar", brls::BUTTON_B, [](brls::View*) {\n            brls::View* current = brls::Application::getCurrentFocus();\n            if (!current || !g_activeSidebarItem)\n                return false;\n            for (brls::View* node = current; node; node = node->getParent())\n            {\n                if (node == g_activeSidebarItem)\n                    return false;\n            }\n            brls::Application::giveFocus(g_activeSidebarItem);\n            return true;\n        });\n        log_stage("TABFRAME BACK-TO-ACTIVE-SIDEBAR ACTION REGISTERED");\n\n        if (sidebarView)\n        {\n            brls::Box* sidebarBox = dynamic_cast<brls::Box*>(sidebarView);\n            if (sidebarBox)\n            {\n                g_activeSidebarItem = sidebarBox->getDefaultFocus();\n                auto& sidebarChildren = sidebarBox->getChildren();\n                if (!sidebarChildren.empty())\n                {\n                    brls::Box* sidebarContent = dynamic_cast<brls::Box*>(sidebarChildren.front());\n                    if (sidebarContent)\n                    {\n                        for (brls::View* child : sidebarContent->getChildren())\n                        {\n                            brls::SidebarItem* item = dynamic_cast<brls::SidebarItem*>(child);\n                            if (item)\n                            {\n                                item->getActiveEvent()->subscribe([](brls::View* active) {\n                                    g_activeSidebarItem = active;\n                                });\n                            }\n                        }\n                        log_stage("SIDEBAR ACTIVE ITEM TRACKING INSTALLED");\n                    }\n                }\n            }\n        }\n        else\n            log_stage("SIDEBAR ACTIVE ITEM TRACKING LOOKUP FAILED");\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame content block")
    source = source.replace(marker, addition, 1)

if "static brls::View* load_home_content_from_xml()" not in source:
    main_marker = '\nint main(int argc, char* argv[])\n'
    helper = r'''
static brls::View* load_home_content_from_xml()
{
    const char* homePath = "romfs:/xml/activity/home.xml";
    FILE* homeFile = std::fopen(homePath, "rb");
    if (!homeFile) return nullptr;
    std::fseek(homeFile, 0, SEEK_END);
    long fileSize = std::ftell(homeFile);
    std::fseek(homeFile, 0, SEEK_SET);
    if (fileSize <= 0 || fileSize > 1024 * 1024) { std::fclose(homeFile); return nullptr; }
    std::string xml(static_cast<size_t>(fileSize), '\0');
    const size_t readSize = std::fread(xml.data(), 1, xml.size(), homeFile);
    std::fclose(homeFile);
    if (readSize != xml.size()) return nullptr;
    return brls::View::createFromXMLString(xml);
}

static void refresh_home_content(brls::TabFrame* tabFrame)
{
    if (!tabFrame) return;
    log_stage("CONTROLLER REFRESH START");
    brls::View* homeContent = load_home_content_from_xml();
    if (!homeContent) return;
    ApiResult api = run_api_probe();
    brls::Box* homeBox = dynamic_cast<brls::Box*>(homeContent);
    if (homeBox)
    {
        brls::Label* status = new brls::Label();
        status->setText(api.status.empty() ? "Refresh complete" : api.status);
        status->setFontSize(16);
        homeBox->addView(status);
        if (!api.response.empty()) render_trending(homeBox, api.response);
    }
    tabFrame->setTabContent(homeContent);
    if (g_homeSidebarItem)
    {
        brls::View* entry = homeContent->getDefaultFocus();
        g_homeSidebarItem->setCustomNavigationRoute(brls::FocusDirection::RIGHT, entry ? entry : homeContent);
    }
    log_stage("AFTER REFRESH TABFRAME CONTENT SET");
}
'''
    if source.count(main_marker) != 1:
        raise SystemExit("Could not locate main() boundary")
    source = source.replace(main_marker, helper + main_marker, 1)

source = source.replace('brls::Application::setGlobalQuit(false);', 'brls::Application::setGlobalQuit(true);', 1)

if "if (g_refreshRequested)" not in source:
    marker = '    while (brls::Application::mainLoop())\n    {\n        ++loopCount;\n'
    replacement = '''    while (brls::Application::mainLoop())\n    {\n        if (g_refreshRequested)\n        {\n            g_refreshRequested = false;\n            refresh_home_content(tabFrame);\n        }\n\n        ++loopCount;\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate main loop")
    source = source.replace(marker, replacement, 1)

# The workflow's TabFrame patch currently routes sidebar RIGHT to the content
# root. Replace that with the content's default focus when available, so Home
# enters the first real card and Settings enters its API Source button.
borealis_tab = Path("switch/borealis/library/lib/views/tab_frame.cpp")
if borealis_tab.exists():
    tab_source = borealis_tab.read_text()
    old = '''        newContent->setFocusable(true);\n        view->setCustomNavigationRoute(FocusDirection::RIGHT, newContent);\n        newContent->setCustomNavigationRoute(FocusDirection::LEFT, view);'''
    new = '''        View* entryFocus = newContent->getDefaultFocus();\n        if (entryFocus)\n        {\n            view->setCustomNavigationRoute(FocusDirection::RIGHT, entryFocus);\n            entryFocus->setCustomNavigationRoute(FocusDirection::LEFT, view);\n        }\n        else\n        {\n            newContent->setFocusable(true);\n            view->setCustomNavigationRoute(FocusDirection::RIGHT, newContent);\n            newContent->setCustomNavigationRoute(FocusDirection::LEFT, view);\n        }'''
    if old in tab_source:
        tab_source = tab_source.replace(old, new, 1)
    borealis_tab.write_text(tab_source)

# After the application's dynamically populated Home replaces the original
# tab content, update the actual Home sidebar item's RIGHT route to the new
# content's first focusable descendant. The old route otherwise points at the
# deleted placeholder Home view.
old_home_set = '''                        tabFrame->setTabContent(homeContent);\n                        log_stage("AFTER HOME CONTENT ATTACHMENT PATH");'''
new_home_set = '''                        tabFrame->setTabContent(homeContent);\n                        if (g_homeSidebarItem)\n                        {\n                            brls::View* entryFocus = homeContent->getDefaultFocus();\n                            g_homeSidebarItem->setCustomNavigationRoute(brls::FocusDirection::RIGHT, entryFocus ? entryFocus : homeContent);\n                        }\n                        log_stage("AFTER HOME CONTENT ATTACHMENT PATH");'''
if old_home_set in source:
    source = source.replace(old_home_set, new_home_set, 1)

path.write_text(source)
print("Controller focus routing patch applied")