from pathlib import Path
import re

main = Path("switch/source/main.cpp")
xml_path = Path("switch/romfs/xml/activity/main.xml")
source = main.read_text()
xml = xml_path.read_text()

# Refresh state / Home lifecycle guards.
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

# Accept the different response envelopes used by the providers.
old_validation = 'requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && response.find("results") != std::string::npos'
new_validation = 'requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && (response.find("results") != std::string::npos || response.find("\\\"data\\\"") != std::string::npos)'
if old_validation in source:
    source = source.replace(old_validation, new_validation, 1)

# Route every stable provider ID to its own endpoint. Miruro remains the
# default and the only provider allowed to use the existing AniList fallback.
old_url = '''const char* url = "https://miruro.zenos.my.id/trending?per_page=6";'''
if old_url in source:
    new_url = '''const char* url = nullptr;\n    const char* providerMarker = nullptr;\n    switch (g_apiSource)\n    {\n        case 1:\n            url = "https://animepahe.com/api?m=airing&page=1";\n            providerMarker = "ANIMEPAHE REQUEST";\n            break;\n        case 2:\n            url = "https://jaybeeanime.vercel.app/";\n            providerMarker = "GOGOANIME REQUEST";\n            break;\n        case 3:\n            url = "https://aniwatch-api-v1-0.onrender.com/api/parse";\n            providerMarker = "ANIWATCH REQUEST";\n            break;\n        case 4:\n            url = "https://hianime-api-production.up.railway.app/api/v1/home";\n            providerMarker = "HIANIME REQUEST";\n            break;\n        default:\n            url = "https://miruro.zenos.my.id/trending?per_page=6";\n            providerMarker = "MIRURO REQUEST";\n            break;\n    }'''
    source = source.replace(old_url, new_url, 1)
elif 'case 4:\n            url = "https://hianime-api-production.up.railway.app/api/v1/home";' not in source:
    raise SystemExit("Could not locate provider request block")

# Use generic HTTP success validation for the three JSON shapes that do not
# expose a `results` envelope.
source = source.replace(
    'primaryOk = api_response_is_valid(requestRc, httpCode, response, "MIRURO REQUEST");',
    '''if (g_apiSource >= 2)\n        {\n            primaryOk = requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && !response.empty();\n            char providerStatus[160];\n            std::snprintf(providerStatus, sizeof(providerStatus), "%s %s HTTP %ld BYTES %zu", providerMarker, primaryOk ? "OK" : "FAILED", httpCode, response.size());\n            log_stage(providerStatus);\n        }\n        else\n            primaryOk = api_response_is_valid(requestRc, httpCode, response, providerMarker);''',
    1,
)
source = source.replace(
    'primaryOk = api_response_is_valid(requestRc, httpCode, response, providerMarker);',
    '''if (g_apiSource >= 2)\n            {\n                primaryOk = requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && !response.empty();\n                char providerStatus[160];\n                std::snprintf(providerStatus, sizeof(providerStatus), "%s %s HTTP %ld BYTES %zu", providerMarker, primaryOk ? "OK" : "FAILED", httpCode, response.size());\n                log_stage(providerStatus);\n            }\n            else\n                primaryOk = api_response_is_valid(requestRc, httpCode, response, providerMarker);''',
    1,
)

# Alternate providers must fail without falling through to Miruro/AniList.
if "ALTERNATE PROVIDER FAILED - NO FALLBACK" not in source:
    marker = '    if (primaryOk)\n    {\n'
    guard = '''    if (!primaryOk && g_apiSource != 0)\n    {\n        log_stage("ALTERNATE PROVIDER FAILED - NO FALLBACK");\n        result.status = std::string(api_source_name(g_apiSource)) + " request failed";\n        result.response.clear();\n        curl_easy_cleanup(curl);\n        curl_global_cleanup();\n        if (socketOwned) socketExit();\n        return result;\n    }\n\n'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate primary result handling")
    source = source.replace(marker, guard + marker, 1)

source = source.replace(
    '''    else\n    {\n        log_stage("MIRURO FAILED - STARTING ANILIST FALLBACK");''',
    '''    else if (g_apiSource == 0)\n    {\n        log_stage("MIRURO FAILED - STARTING ANILIST FALLBACK");''',
    1,
)

# Provider-specific parsers. They normalize only at the field-extraction layer,
# keeping the existing Home card renderer unchanged.
if "static std::vector<std::string> extract_provider_titles" not in source:
    marker = 'static std::vector<std::string> extract_trending_titles(const std::string& response)\n'
    helper = r'''static std::vector<std::string> extract_provider_titles(const std::string& response, int source)
{
    std::vector<std::string> titles;
    const char* arrayKey = source == 3 ? "trend" : (source == 4 ? "trending" : "root");
    const char* titleKey = source == 3 ? "name" : "title";
    size_t cursor = source == 2 ? 0 : response.find(std::string("\"") + arrayKey + "\"");
    if (cursor == std::string::npos) return titles;
    while (titles.size() < 6)
    {
        size_t objectStart = response.find('{', cursor);
        if (objectStart == std::string::npos) break;
        size_t objectEnd = response.find('}', objectStart + 1);
        if (objectEnd == std::string::npos) break;
        std::string title = json_string_after(response, objectStart, titleKey, objectEnd);
        if (!title.empty()) titles.push_back(title);
        cursor = objectEnd + 1;
    }
    return titles;
}

static std::vector<std::string> extract_provider_covers(const std::string& response, int source)
{
    std::vector<std::string> covers;
    const char* arrayKey = source == 3 ? "trend" : (source == 4 ? "trending" : "root");
    const char* imageKey = source == 3 ? "imgAni" : (source == 4 ? "poster" : "image");
    size_t cursor = source == 2 ? 0 : response.find(std::string("\"") + arrayKey + "\"");
    if (cursor == std::string::npos) return covers;
    while (covers.size() < 6)
    {
        size_t objectStart = response.find('{', cursor);
        if (objectStart == std::string::npos) break;
        size_t objectEnd = response.find('}', objectStart + 1);
        if (objectEnd == std::string::npos) break;
        covers.push_back(json_string_after(response, objectStart, imageKey, objectEnd));
        cursor = objectEnd + 1;
    }
    return covers;
}

'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate trending parser")
    source = source.replace(marker, helper + marker, 1)

old_extract = '''    std::vector<std::string> titles = extract_trending_titles(response);\n    std::vector<std::string> details = extract_trending_details(response);\n    std::vector<std::string> covers = extract_trending_covers(response);'''
new_extract = '''    std::vector<std::string> titles;\n    std::vector<std::string> details;\n    std::vector<std::string> covers;\n    if (g_apiSource >= 2)\n    {\n        titles = extract_provider_titles(response, g_apiSource);\n        covers = extract_provider_covers(response, g_apiSource);\n    }\n    else\n    {\n        titles = extract_trending_titles(response);\n        details = extract_trending_details(response);\n        covers = extract_trending_covers(response);\n    }'''
if old_extract in source:
    source = source.replace(old_extract, new_extract, 1)

# Keep failed refreshes transactional.
if "REFRESH ABORTED - KEEPING CURRENT HOME" not in source:
    pattern = re.compile(
        r'(static void refresh_home_content\(brls::TabFrame\* tabFrame\)\s*\{.*?'
        r'ApiResult api = run_api_probe\(\);\s*)', re.S)
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
    struct RefreshGuard { ~RefreshGuard() { g_homeRefreshInProgress = false; } } refreshGuard;
'''
    if source.count(marker) != 1:
        raise SystemExit("Could not locate refresh_home_content definition")
    source = source.replace(marker, replacement, 1)

# Extend the selector from the original three entries to all five stable IDs.
xml = xml.replace(
    '<brls:Button id="api-source-gogoanime" width="auto" height="auto" text="Gogoanime" />',
    '''<brls:Button id="api-source-gogoanime" width="auto" height="auto" text="Gogoanime" />\n            <brls:Button id="api-source-aniwatch" width="auto" height="auto" text="Aniwatch" />\n            <brls:Button id="api-source-hianime" width="auto" height="auto" text="HiAnime" />''', 1)

if 'api-source-aniwatch' not in source:
    old = '''    brls::Button* gogoanime = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-gogoanime"));'''
    new = old + '''\n    brls::Button* aniwatch = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-aniwatch"));\n    brls::Button* hianime = dynamic_cast<brls::Button*>(settingsTab->getView("api-source-hianime"));'''
    if source.count(old) != 1:
        raise SystemExit("Could not locate Gogoanime binding")
    source = source.replace(old, new, 1)
    source = source.replace('if (!current || !miruro || !animepahe || !gogoanime)', 'if (!current || !miruro || !animepahe || !gogoanime || !aniwatch || !hianime)', 1)
    old_action = '''    gogoanime->registerClickAction([current](brls::View*) {\n        g_apiSource = 2;\n        current->setText("Anime API: Gogoanime");\n        save_api_source();\n        return true;\n    });'''
    new_action = old_action + '''\n\n    aniwatch->registerClickAction([current](brls::View*) {\n        g_apiSource = 3;\n        current->setText("Anime API: Aniwatch");\n        save_api_source();\n        return true;\n    });\n\n    hianime->registerClickAction([current](brls::View*) {\n        g_apiSource = 4;\n        current->setText("Anime API: HiAnime");\n        save_api_source();\n        return true;\n    });'''
    if source.count(old_action) != 1:
        raise SystemExit("Could not locate Gogoanime action")
    source = source.replace(old_action, new_action, 1)
    old_route = '        gogoanime->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);'
    new_route = old_route + '''\n        aniwatch->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);\n        hianime->setCustomNavigationRoute(brls::FocusDirection::LEFT, g_activeSidebarItem);'''
    if source.count(old_route) != 1:
        raise SystemExit("Could not locate Gogoanime navigation route")
    source = source.replace(old_route, new_route, 1)

# Permit persisted IDs 0..4. apply_api_selector.py runs before this script.
source = source.replace('value >= 0 && value <= 2', 'value >= 0 && value <= 4')
source = source.replace('value >= 0 && value <= 4 && value <= 2', 'value >= 0 && value <= 4')

# Add names for the two new IDs if the selector helper has not already done it.
source = source.replace(
    'case 1: return "AnimePahe";\n        case 2: return "Gogoanime";',
    'case 1: return "AnimePahe";\n        case 2: return "Gogoanime";\n        case 3: return "Aniwatch";\n        case 4: return "HiAnime";', 1)

main.write_text(source)
xml_path.write_text(xml)
print("API refresh finalized with all five provider routes and selector entries")
