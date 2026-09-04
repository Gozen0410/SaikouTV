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
                                });'''
    # Keep the base subscription simple; activation-aware refresh is handled
    # centrally by the main loop using the actual Home content focus tree.
    source, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise SystemExit("Could not locate sidebar active-event subscription")

# Mark the dynamically installed Home content and keep a direct pointer to it.
# Do not use a TabFrame getter: this Borealis revision intentionally exposes
# setTabContent() but has no public getTabContent().
if "g_homeContentView = homeContent;" not in source:
    marker = '                        homeContent = nullptr;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate initial Home ownership handoff")
    addition = '''                        g_homeContentView = homeContent;
                        g_homeContentInstalled = true;
                        homeContent = nullptr;
'''
    source = source.replace(marker, addition, 1)

# Offline Home remains a single focus target.
if 'if (api.response.empty()) homeBox->setFocusable(true);' not in source:
    marker = '                        if (homeBox)\n                        {\n'
    if source.count(marker) >= 1:
        source = source.replace(marker, marker + '                            if (api.response.empty()) homeBox->setFocusable(true);\n', 1)

# The refresh helper replaces Home safely. The controller owns the in-progress
# guard and updates g_homeContentView after a successful replacement.

# Remove the old experimental TabFrame getter if an earlier generator pass left it behind.
source = source.replace('    g_homeContentView = tabFrame ? tabFrame->getTabContent() : nullptr;\n', '', 1)
source = source.replace('    log_stage("HOME FOCUS REFRESH CHECK INSTALLED");\n', '', 1)

path.write_text(source)
print("Home persistence now tracks the installed Home view directly and leaves refresh activation to the main loop")