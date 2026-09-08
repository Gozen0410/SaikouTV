from pathlib import Path
import re

# Final generated-source pass for Home refresh/provider routing.
# Keep provider failure handling explicit: an alternate provider must never
# fall through to Miruro or hand an HTTP error body to the Home parser.
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

old_validation = 'requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && response.find("results") != std::string::npos'
new_validation = 'requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && (response.find("results") != std::string::npos || response.find("\\\"data\\\"") != std::string::npos)'
if old_validation in source:
    source = source.replace(old_validation, new_validation, 1)

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

if "ALTERNATE PROVIDER FAILED - NO FALLBACK" not in source:
    marker = '    if (primaryOk)\n    {\n'
    guard = '''    if (!primaryOk && g_apiSource != 0)\n    {\n        log_stage("ALTERNATE PROVIDER FAILED - NO FALLBACK");\n        result.status = std::string(api_source_name(g_apiSource)) + " request failed";\n        result.response.clear();\n        curl_easy_cleanup(curl);\n        curl_global_cleanup();\n        if (socketOwned) socketExit();\n        return result;\n    }\n\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate primary result handling")
    source = source.replace(marker, guard + marker, 1)

# Only Miruro may use the existing AniList fallback.
old_fallback = '''    else\n    {\n        log_stage("MIRURO FAILED - STARTING ANILIST FALLBACK");'''
new_fallback = '''    else if (g_apiSource == 0)\n    {\n        log_stage("MIRURO FAILED - STARTING ANILIST FALLBACK");'''
if old_fallback in source:
    source = source.replace(old_fallback, new_fallback, 1)

# Keep the existing Home parser safe if an upstream response is unexpectedly
# empty. No visible UI changes are made here.
source = source.replace(
    'if (!homeBox || response.empty()) return;\n    log_stage("BEFORE TRENDING PARSE");',
    'if (!homeBox || response.empty()) { log_stage("TRENDING RENDER SKIPPED - EMPTY RESPONSE"); return; }\n    log_stage("BEFORE TRENDING PARSE");',
    1,
)

# The controller's refresh helper must be transactional. Build and validate
# the replacement Home view first; only swap it into the TabFrame when the
# selected provider returned usable data. A 4xx/5xx or empty response leaves
# the currently displayed Home untouched.
if "REFRESH ABORTED - KEEPING CURRENT HOME" not in source:
    pattern = re.compile(
        r'(static void refresh_home_content\(brls::TabFrame\* tabFrame\)\s*\{.*?'
        r'ApiResult api = run_api_probe\(\);\s*)',
        re.S,
    )
    replacement = r'''\1    if (api.response.empty())
    {
        log_stage("REFRESH ABORTED - KEEPING CURRENT HOME");
        delete homeContent;
        return;
    }
'''
    source, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise SystemExit("Could not locate refresh_home_content provider result")

# Prevent overlapping refresh transactions. API changes that arrive while a
# refresh is running are coalesced into the next loop instead of rebuilding
# the TabFrame twice at once.
if "g_homeRefreshInProgress" in source and "REFRESH IGNORED - ALREADY IN PROGRESS" not in source:
    marker = 'static void refresh_home_content(brls::TabFrame* tabFrame)\n{\n'
    replacement = '''static void refresh_home_content(brls::TabFrame* tabFrame)
{
    if (g_homeRefreshInProgress)
    {
        log_stage("REFRESH IGNORED - ALREADY IN PROGRESS");
        return;
    }
    g_homeRefreshInProgress = true;
    struct RefreshGuard
    {
        ~RefreshGuard() { g_homeRefreshInProgress = false; }
    } refreshGuard;
'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate refresh_home_content definition")
    source = source.replace(marker, replacement, 1)

main.write_text(source)
print("Failed Home refreshes now leave the current Home intact and overlapping refreshes are coalesced")
