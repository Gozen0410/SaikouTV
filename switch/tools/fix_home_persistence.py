from pathlib import Path

path = Path("switch/source/main.cpp")
source = path.read_text()

# The first Home screen is populated by the application and attached through
# TabFrame::setTabContent(). When the user leaves Home, TabFrame later invokes
# its original lazy XML creator when Home is selected again, which recreates
# only the static XML and loses the runtime trending cards. Keep the existing
# architecture and simply request the same Home rebuild when Home becomes
# active again.
if "g_homeSidebarItem" in source:
    print("Home persistence patch already present")
    raise SystemExit(0)

# Controller-controls.py installs these globals before this script runs.
marker = 'static bool g_refreshRequested = false;\n'
addition = marker + 'static brls::View* g_homeSidebarItem = nullptr;\nstatic bool g_homeContentInstalled = false;\nstatic bool g_homeRefreshInProgress = false;\n'
if source.count(marker) != 1:
    raise SystemExit("Could not locate controller refresh global")
source = source.replace(marker, addition, 1)

# Remember which SidebarItem is Home. The XML defines Home as the first tab,
# and getDefaultFocus() resolves to that first SidebarItem in this layout.
marker = '                g_activeSidebarItem = sidebarBox->getDefaultFocus();\n'
replacement = marker + '                g_homeSidebarItem = sidebarBox->getDefaultFocus();\n'
if source.count(marker) != 1:
    raise SystemExit("Could not locate sidebar default-focus initialization")
source = source.replace(marker, replacement, 1)

# Reuse the existing active-item subscription. Only request a rebuild when the
# user actually transitions from another tab back to Home. setTabContent() can
# itself emit Home activation while replacing content; treating that as a real
# navigation event causes an endless refresh loop, especially when the API is
# offline and every refresh completes quickly.
old = '''                                item->getActiveEvent()->subscribe([](brls::View* active) {\n                                    g_activeSidebarItem = active;\n                                    if (g_homeContentInstalled && !g_homeRefreshInProgress && active == g_homeSidebarItem)\n                                        g_refreshRequested = true;\n                                });'''
new = '''                                item->getActiveEvent()->subscribe([](brls::View* active) {\n                                    brls::View* previous = g_activeSidebarItem;\n                                    g_activeSidebarItem = active;\n                                    if (g_homeContentInstalled && !g_homeRefreshInProgress &&\n                                        active == g_homeSidebarItem && previous != g_homeSidebarItem)\n                                        g_refreshRequested = true;\n                                });'''
if source.count(old) != 1:
    raise SystemExit("Could not locate sidebar active-event subscription")
source = source.replace(old, new, 1)

# Mark the initial, already-working Home content as installed. This prevents
# the initial Home activation from causing a second API request.
marker = '                        homeContent = nullptr;\n'
replacement = marker + '                        g_homeContentInstalled = true;\n'
if source.count(marker) != 1:
    raise SystemExit("Could not locate initial Home content ownership handoff")
source = source.replace(marker, replacement, 1)

# Guard the existing deferred refresh helper against an activation callback
# firing while our refresh is replacing the Home content. Clear the guard on
# every early failure path so a later Home activation can retry normally.
marker = '    log_stage("CONTROLLER REFRESH START");\n'
replacement = marker + '    g_homeRefreshInProgress = true;\n'
if source.count(marker) != 1:
    raise SystemExit("Could not locate refresh helper start")
source = source.replace(marker, replacement, 1)

old = '''    if (!homeContent)\n    {\n        log_stage("CONTROLLER REFRESH XML FAILED");\n        return;\n    }'''
new = '''    if (!homeContent)\n    {\n        log_stage("CONTROLLER REFRESH XML FAILED");\n        g_homeRefreshInProgress = false;\n        return;\n    }'''
if source.count(old) != 1:
    raise SystemExit("Could not locate Home refresh XML failure path")
source = source.replace(old, new, 1)

marker = '    log_stage("AFTER REFRESH TABFRAME CONTENT SET");\n'
replacement = marker + '    g_homeRefreshInProgress = false;\n    g_homeContentInstalled = true;\n'
if source.count(marker) != 1:
    raise SystemExit("Could not locate refresh helper completion")
source = source.replace(marker, replacement, 1)

path.write_text(source)
print("Home persistence patch applied: refresh only on a real transition back to Home")