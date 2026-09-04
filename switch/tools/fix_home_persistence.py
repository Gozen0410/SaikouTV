from pathlib import Path
import re

path = Path("switch/source/main.cpp")
source = path.read_text()

# Keep lightweight Home state only. The retained Home View is owned by
# Borealis TabFrame; do not keep a raw View* here.
if "static brls::View* g_homeSidebarItem" not in source:
    marker = 'static bool g_refreshRequested = false;\n'
    addition = marker + 'static brls::View* g_homeSidebarItem = nullptr;\nstatic bool g_homeContentInstalled = false;\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate controller refresh global")
    source = source.replace(marker, addition, 1)

if "g_homeSidebarItem = sidebarBox->getDefaultFocus();" not in source:
    marker = '                g_activeSidebarItem = sidebarBox->getDefaultFocus();\n'
    if source.count(marker) != 1:
        raise SystemExit("Could not locate sidebar default-focus initialization")
    source = source.replace(marker, marker + '                g_homeSidebarItem = sidebarBox->getDefaultFocus();\n', 1)

pattern = re.compile(
    r'item->getActiveEvent\(\)->subscribe\(\[\]\(brls::View\* active\) \{\s*'
    r'g_activeSidebarItem = active;\s*\}\);'
)
replacement = '''item->getActiveEvent()->subscribe([](brls::View* active) {
                                    g_activeSidebarItem = active;
                                });'''
if pattern.search(source):
    source = pattern.sub(replacement, source, count=1)

if "g_homeContentInstalled = true;" not in source:
    marker = '                        homeContent = nullptr;\n'
    if source.count(marker) == 1:
        source = source.replace(marker, '                        g_homeContentInstalled = true;\n' + marker, 1)

# Never retain a raw Home View pointer here; TabFrame owns the retained view.
source = re.sub(r'\s*g_homeContentView\s*=\s*homeContent;\n', '\n', source)
source = source.replace('    log_stage("HOME FOCUS REFRESH CHECK INSTALLED");\n', '', 1)

path.write_text(source)
print("Home persistence uses TabFrame ownership without stale View pointers")
