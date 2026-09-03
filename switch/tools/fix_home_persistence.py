from pathlib import Path
import re

path = Path("switch/source/main.cpp")
source = path.read_text()

# Home is populated dynamically and attached with TabFrame::setTabContent().
# When another sidebar item becomes active and Home is selected again, ask the
# existing deferred refresh path to rebuild Home. Do not try to change the
# TabFrame implementation here.

# Controller-controls.py installs these globals before this script runs.
if "static brls::View* g_homeSidebarItem" not in source:
    marker = 'static bool g_refreshRequested = false;\n'
    addition = marker + 'static brls::View* g_homeSidebarItem = nullptr;\nstatic bool g_homeContentInstalled = false;\nstatic bool g_homeRefreshInProgress = false;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate controller refresh global")
    source = source.replace(marker, addition, 1)

# Remember the Home sidebar item alongside the existing active-item tracking.
if "g_homeSidebarItem = sidebarBox->getDefaultFocus();" not in source:
    marker = '                g_activeSidebarItem = sidebarBox->getDefaultFocus();\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate sidebar default-focus initialization")
    source = source.replace(marker, marker + '                g_homeSidebarItem = sidebarBox->getDefaultFocus();\n', 1)

# Replace the existing active-event body in a tolerant way. A Home activation
# is intentionally enough to request a refresh: this is exactly what happens
# when the user moves Search -> Home while Home is still the selected tab.
pattern = re.compile(
    r'(item->getActiveEvent\(\)->subscribe\(\[\]\(brls::View\* active\) \{)\n'
    r'\s*g_activeSidebarItem = active;\n'
    r'\s*(?:if \([^\n]+\)\n\s*g_refreshRequested = true;\n)?'
    r'\s*\}\);'
)
replacement = '''item->getActiveEvent()->subscribe([](brls::View* active) {
                                    g_activeSidebarItem = active;
                                    if (g_homeContentInstalled && !g_homeRefreshInProgress && active == g_homeSidebarItem)
                                        g_refreshRequested = true;
                                });'''
source, count = pattern.subn(replacement, source, count=1)
if count != 1:
    # If the already-patched form is present, leave it alone.
    if "active == g_homeSidebarItem" not in source:
        raise SystemExit("Could not locate sidebar active-event subscription")

# Mark the initial dynamic Home content as installed. Use the unique ownership
# handoff rather than relying on line numbers.
if "g_homeContentInstalled = true;" not in source:
    marker = '                        homeContent = nullptr;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate initial Home content ownership handoff")
    source = source.replace(marker, marker + '                        g_homeContentInstalled = true;\n', 1)

# When the API is unavailable there are no cards, so Home needs one simple
# focusable target. When cards exist, keep the existing card-level focus model.
# This is deliberately applied to both the initial Home load and the deferred
# Home refresh path.
needle = '                        if (homeBox)\n                        {\n'
replacement = '                        if (homeBox)\n                        {\n                            if (api.response.empty()) homeBox->setFocusable(true);\n'
if source.count(needle) >= 1 and 'if (api.response.empty()) homeBox->setFocusable(true);' not in source:
    source = source.replace(needle, replacement, 1)

needle = '    if (homeBox)\n    {\n'
replacement = '    if (homeBox)\n    {\n        if (api.response.empty()) homeBox->setFocusable(true);\n'
if source.count(needle) >= 1 and 'if (api.response.empty()) homeBox->setFocusable(true);' in source:
    # Only add the refresh-path instance if it is not already present there.
    # Count the exact refresh indentation separately.
    if source.count(replacement) == 0:
        source = source.replace(needle, replacement, 1)

# Guard the deferred refresh while setTabContent() replaces the content. This
# prevents the activation event emitted by our own replacement from scheduling
# another refresh, while still allowing a later user-driven Home activation.
if 'g_homeRefreshInProgress = true;' not in source:
    marker = '    log_stage("CONTROLLER REFRESH START");\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate refresh helper start")
    source = source.replace(marker, marker + '    g_homeRefreshInProgress = true;\n', 1)

    old = '''    if (!homeContent)\n    {\n        log_stage("CONTROLLER REFRESH XML FAILED");\n        return;\n    }'''
    new = '''    if (!homeContent)\n    {\n        log_stage("CONTROLLER REFRESH XML FAILED");\n        g_homeRefreshInProgress = false;\n        return;\n    }'''
    if source.count(old) != 1:
        raise SystemExit("Could not locate Home refresh XML failure path")
    source = source.replace(old, new, 1)

    marker = '    log_stage("AFTER REFRESH TABFRAME CONTENT SET");\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate refresh helper completion")
    source = source.replace(marker, marker + '    g_homeRefreshInProgress = false;\n    g_homeContentInstalled = true;\n', 1)

path.write_text(source)
print("Home persistence/offline focus patch applied")
