from pathlib import Path

path = Path("switch/source/main.cpp")
source = path.read_text()

declaration = "static bool g_apiSourceRefreshPending = false;"
if declaration not in source:
    marker = "static bool g_refreshRequested = false;\n"
    if source.count(marker) != 1:
        raise SystemExit("Could not locate the controller refresh global")
    source = source.replace(marker, marker + declaration + "\n", 1)

path.write_text(source)
print("API refresh global finalized")
