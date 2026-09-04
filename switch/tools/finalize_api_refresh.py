from pathlib import Path

# Finalize the generated application source.
# Keep this pass deliberately limited to the API refresh state declaration.
# TabFrame lifecycle changes are handled separately so the working API-source
# navigation is not coupled to Home persistence experiments.
main = Path("switch/source/main.cpp")
source = main.read_text()
declaration = "static bool g_apiSourceRefreshPending = false;"
if declaration not in source:
    marker = "static bool g_refreshRequested = false;\n"
    if source.count(marker) != 1:
        raise SystemExit("Could not locate controller refresh global")
    source = source.replace(marker, marker + declaration + "\n", 1)
    main.write_text(source)

print("Finalized API refresh global")
