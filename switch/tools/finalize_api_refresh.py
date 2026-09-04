from pathlib import Path

# Finalize the generated application source.
# Keep this pass limited to refresh triggering. Provider routing remains a
# separate stage and the existing API selector/navigation is left untouched.
main = Path("switch/source/main.cpp")
source = main.read_text()

declaration = "static bool g_apiSourceRefreshPending = false;"
if declaration not in source:
    marker = "static bool g_refreshRequested = false;\n"
    if source.count(marker) != 1:
        raise SystemExit("Could not locate controller refresh global")
    source = source.replace(marker, marker + declaration + "\n", 1)

# The previous refresh gate required focus to already be inside the dynamic
# Home content. That is too strict: after leaving the API Source activity the
# focus can be on the Home sidebar item, so a pending provider refresh was
# never consumed. Treat the Home sidebar item as an equally valid Home state.
if "static bool home_is_active()" not in source:
    marker = "\nint main(int argc, char* argv[])\n"
    helper = '''\nstatic bool home_is_active()\n{\n    if (g_homeSidebarItem && g_activeSidebarItem == g_homeSidebarItem)\n        return true;\n    return focus_is_inside(g_homeContentView);\n}\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate main() boundary")
    source = source.replace(marker, helper + marker, 1)

source = source.replace(
    "if (g_apiSourceRefreshPending && focus_is_inside(g_homeContentView))",
    "if (g_apiSourceRefreshPending && home_is_active())",
    1,
)
source = source.replace(
    "if (g_refreshRequested && focus_is_inside(g_homeContentView))",
    "if (g_refreshRequested && home_is_active())",
    1,
)

# Add a controller-only fallback on the TabFrame itself. This is deliberately
# not a visible UI button: X refreshes Home even when the cards are currently
# missing and focus is sitting on the Home sidebar item.
if 'tabFrame->registerAction("Refresh Home", brls::BUTTON_X' not in source:
    marker = "    if (tabFrame)\n    {\n        brls::View* sidebarView = tabFrame->getView(\"brls/tab_frame/sidebar\");\n"
    replacement = '''    if (tabFrame)\n    {\n        tabFrame->registerAction("Refresh Home", brls::BUTTON_X, [](brls::View*) {\n            if (!g_homeSidebarItem || g_activeSidebarItem != g_homeSidebarItem)\n                return false;\n            g_refreshRequested = true;\n            log_stage("MANUAL HOME REFRESH REQUESTED");\n            return true;\n        });\n\n        brls::View* sidebarView = tabFrame->getView("brls/tab_frame/sidebar");\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame sidebar setup")
    source = source.replace(marker, replacement, 1)

main.write_text(source)
print("Home refresh now activates from the Home sidebar and exposes X as a manual fallback")
