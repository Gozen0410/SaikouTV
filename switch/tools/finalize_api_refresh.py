from pathlib import Path

# Provider routing is deliberately kept in this final generated-source pass.
# Miruro remains the known-good provider. AnimePahe is the first real alternate
# provider and is normalized by the existing Home parser (data/title/image).
main = Path("switch/source/main.cpp")
source = main.read_text()

declaration = "static bool g_apiSourceRefreshPending = false;"
if declaration not in source:
    marker = "static bool g_refreshRequested = false;\n"
    if source.count(marker) != 1:
        raise SystemExit("Could not locate controller refresh global")
    source = source.replace(marker, marker + declaration + "\n", 1)

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

# Accept the provider-specific AnimePahe response shape in addition to the
# Miruro/AniList 'results' shape. This is only validation; parsing is handled
# by the common Home extraction helpers below.
old_validation = 'requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && response.find("results") != std::string::npos'
new_validation = 'requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && (response.find("results") != std::string::npos || response.find("\\\"data\\\"") != std::string::npos)'
if old_validation in source:
    source = source.replace(old_validation, new_validation, 1)

# Route the actual HTTP request from the selected provider. Do not silently
# fall back to Miruro when AnimePahe is selected; a failed alternate provider
# should be visible in the log instead of pretending the switch worked.
old_url = 'const char* url = "https://miruro.zenos.my.id/trending?per_page=6";'
new_url = '''const char* url = nullptr;\n    const char* providerMarker = nullptr;\n    if (g_apiSource == 1)\n    {\n        url = "https://animepahe.com/api?m=airing&page=1";\n        providerMarker = "ANIMEPAHE REQUEST";\n    }\n    else\n    {\n        url = "https://miruro.zenos.my.id/trending?per_page=6";\n        providerMarker = "MIRURO REQUEST";\n    }'''
if old_url in source:
    source = source.replace(old_url, new_url, 1)
else:
    raise SystemExit("Could not locate provider request URL")

old_request_loop = 'primaryOk = api_response_is_valid(requestRc, httpCode, response, "MIRURO REQUEST");'
new_request_loop = 'primaryOk = api_response_is_valid(requestRc, httpCode, response, providerMarker);'
if old_request_loop in source:
    source = source.replace(old_request_loop, new_request_loop, 1)

# Prevent the Miruro-specific AniList fallback from making a failed selected
# provider look like it succeeded. Keep the existing fallback only for Miruro.
old_fallback = 'if (primaryOk)\n    {\n        result.status = "API online - trending data received";\n        result.response = response;\n    }\n    else\n    {\n        log_stage("MIRURO FAILED - STARTING ANILIST FALLBACK");'
new_fallback = '''if (primaryOk)\n    {\n        result.status = std::string(api_source_name(g_apiSource)) + " online - trending data received";\n        result.response = response;\n    }\n    else if (g_apiSource == 0)\n    {\n        log_stage("MIRURO FAILED - STARTING ANILIST FALLBACK");'''
if old_fallback in source:
    source = source.replace(old_fallback, new_fallback, 1)

# The existing generic JSON extractor only knows AniList/Miruro's nested
# results shape. Extend it to AnimePahe's {data:[{title,image,...}]} shape.
old_titles = '''static std::vector<std::string> extract_trending_titles(const std::string& response)\n{\n    std::vector<std::string> titles;\n    size_t resultsPos = response.find("\\\"results\\\"");\n    if (resultsPos == std::string::npos) return titles;'''
new_titles = '''static std::vector<std::string> extract_trending_titles(const std::string& response)\n{\n    std::vector<std::string> titles;\n    size_t resultsPos = response.find("\\\"results\\\"");\n    if (resultsPos == std::string::npos)\n    {\n        size_t dataPos = response.find("\\\"data\\\"");\n        if (dataPos == std::string::npos) return titles;\n        size_t cursor = dataPos;\n        while (titles.size() < 6)\n        {\n            size_t titlePos = response.find("\\\"title\\\"", cursor);\n            if (titlePos == std::string::npos) break;\n            std::string title = json_string_after(response, titlePos, "title", response.size());\n            if (!title.empty()) titles.push_back(title);\n            cursor = titlePos + 7;\n        }\n        return titles;\n    }'''
if old_titles in source:
    source = source.replace(old_titles, new_titles, 1)

old_covers = '''static std::vector<std::string> extract_trending_covers(const std::string& response)\n{\n    std::vector<std::string> covers;\n    size_t resultsPos = response.find("\\\"results\\\"");\n    if (resultsPos == std::string::npos) return covers;'''
new_covers = '''static std::vector<std::string> extract_trending_covers(const std::string& response)\n{\n    std::vector<std::string> covers;\n    size_t resultsPos = response.find("\\\"results\\\"");\n    if (resultsPos == std::string::npos)\n    {\n        size_t dataPos = response.find("\\\"data\\\"");\n        if (dataPos == std::string::npos) return covers;\n        size_t cursor = dataPos;\n        while (covers.size() < 6)\n        {\n            size_t titlePos = response.find("\\\"title\\\"", cursor);\n            if (titlePos == std::string::npos) break;\n            size_t nextTitle = response.find("\\\"title\\\"", titlePos + 8);\n            if (nextTitle == std::string::npos) nextTitle = response.size();\n            std::string cover = json_string_after(response, titlePos, "image", nextTitle);\n            covers.push_back(cover);\n            cursor = nextTitle;\n        }\n        return covers;\n    }'''
if old_covers in source:
    source = source.replace(old_covers, new_covers, 1)

# Add a controller-only X fallback. This is intentionally not a new visible
# settings control; it is just an escape hatch when Home content is empty.
if 'tabFrame->registerAction("Refresh Home", brls::BUTTON_X' not in source:
    marker = '    if (tabFrame)\n    {\n        brls::View* sidebarView = tabFrame->getView("brls/tab_frame/sidebar");\n'
    replacement = '''    if (tabFrame)\n    {\n        tabFrame->registerAction("Refresh Home", brls::BUTTON_X, [](brls::View*) {\n            if (!g_homeSidebarItem || g_activeSidebarItem != g_homeSidebarItem)\n                return false;\n            g_refreshRequested = true;\n            log_stage("MANUAL HOME REFRESH REQUESTED");\n            return true;\n        });\n\n        brls::View* sidebarView = tabFrame->getView("brls/tab_frame/sidebar");\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate TabFrame sidebar setup")
    source = source.replace(marker, replacement, 1)

main.write_text(source)
print("Provider routing enabled: Miruro remains baseline; AnimePahe uses its airing endpoint and common Home parser")
