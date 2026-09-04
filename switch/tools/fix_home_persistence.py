from pathlib import Path
import re

path = Path("switch/source/main.cpp")
source = path.read_text()

# Controller-controls installs these globals first.
if "static brls::View* g_homeSidebarItem" not in source:
    marker = 'static bool g_refreshRequested = false;\n'
    addition = marker + 'static brls::View* g_homeSidebarItem = nullptr;\nstatic bool g_homeContentInstalled = false;\nstatic bool g_homeRefreshInProgress = false;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate controller refresh global")
    source = source.replace(marker, addition, 1)

# Track Home explicitly when the sidebar is discovered.
if "g_homeSidebarItem = sidebarBox->getDefaultFocus();" not in source:
    marker = '                g_activeSidebarItem = sidebarBox->getDefaultFocus();\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate sidebar default-focus initialization")
    source = source.replace(marker, marker + '                g_homeSidebarItem = sidebarBox->getDefaultFocus();\n', 1)

# Update the sidebar active-event subscription without depending on the exact
# formatting of the controller patch. A pending API-source refresh is consumed
# only when Home actually becomes the active sidebar item.
if "g_apiSourceRefreshPending = false;" not in source:
    pattern = re.compile(
        r'item->getActiveEvent\(\)->subscribe\(\[\]\(brls::View\* active\) \{\s*'
        r'g_activeSidebarItem = active;\s*\}\);'
    )
    replacement = '''item->getActiveEvent()->subscribe([](brls::View* active) {
                                    g_activeSidebarItem = active;
                                    if (g_homeContentInstalled && !g_homeRefreshInProgress && active == g_homeSidebarItem)
                                    {
                                        if (g_apiSourceRefreshPending)
                                        {
                                            g_apiSourceRefreshPending = false;
                                            g_refreshRequested = true;
                                            log_stage("HOME ACTIVE - CONSUMING API SOURCE REFRESH");
                                        }
                                        else
                                            g_refreshRequested = true;
                                    }
                                });'''
    source, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise SystemExit("Could not locate sidebar active-event subscription")

# Mark the dynamically installed Home content and make its sidebar RIGHT route
# target the first real focusable child rather than the deleted placeholder.
if "g_homeContentInstalled = true;" not in source:
    marker = '                        homeContent = nullptr;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate initial Home ownership handoff")
    addition = '''                        if (g_homeSidebarItem)
                        {
                            brls::View* entryFocus = homeContent->getDefaultFocus();
                            g_homeSidebarItem->setCustomNavigationRoute(brls::FocusDirection::RIGHT, entryFocus ? entryFocus : homeContent);
                        }
                        g_homeContentInstalled = true;
                        homeContent = nullptr;
'''
    source = source.replace(marker, addition, 1)

# Offline Home remains a single focus target.
if 'if (api.response.empty()) homeBox->setFocusable(true);' not in source:
    marker = '                        if (homeBox)\n                        {\n'
    if source.count(marker) >= 1:
        source = source.replace(marker, marker + '                            if (api.response.empty()) homeBox->setFocusable(true);\n', 1)

# The refresh helper already replaces Home safely. Add the same focus route and
# guard around its completion, but do not depend on a specific failure block.
if 'g_homeRefreshInProgress = true;' not in source:
    marker = '    log_stage("CONTROLLER REFRESH START");\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home refresh start")
    source = source.replace(marker, marker + '    g_homeRefreshInProgress = true;\n', 1)

# Ensure every refresh failure returns with the guard cleared.
source = source.replace(
    '    if (!homeContent) return nullptr;\n',
    '    if (!homeContent) { g_homeRefreshInProgress = false; return; }\n',
    1
)

# Add the route update immediately after the refresh content replacement.
marker = '    tabFrame->setTabContent(homeContent);\n'
if source.count(marker) >= 1 and 'CONTROLLER REFRESH START' in source:
    refresh_block_start = source.find('static void refresh_home_content')
    route = '''    if (g_homeSidebarItem)
    {
        brls::View* entryFocus = homeContent->getDefaultFocus();
        g_homeSidebarItem->setCustomNavigationRoute(brls::FocusDirection::RIGHT, entryFocus ? entryFocus : homeContent);
    }
'''
    pos = source.find(marker, refresh_block_start)
    if pos >= 0 and source[pos:pos + len(marker) + len(route)].find('g_homeSidebarItem->setCustomNavigationRoute') < 0:
        source = source[:pos + len(marker)] + route + source[pos + len(marker):]

if 'g_homeRefreshInProgress = false;' not in source:
    marker = '    log_stage("AFTER REFRESH TABFRAME CONTENT SET");\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate Home refresh completion")
    source = source.replace(marker, marker + '    g_homeRefreshInProgress = false;\n    g_homeContentInstalled = true;\n', 1)

path.write_text(source)
print("Home refresh now consumes pending API changes only when Home becomes active")