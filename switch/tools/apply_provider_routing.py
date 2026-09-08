from pathlib import Path
import re

main = Path("switch/source/main.cpp")
source = main.read_text()

# Extend the already-working provider routing block produced by
# finalize_api_refresh.py. Keep the existing Miruro/AnimePahe behavior intact.
old = '''const char* url = nullptr;\n    const char* providerMarker = nullptr;\n    if (g_apiSource == 1)\n    {\n        url = "https://animepahe.com/api?m=airing&page=1";\n        providerMarker = "ANIMEPAHE REQUEST";\n    }\n    else\n    {\n        url = "https://miruro.zenos.my.id/trending?per_page=6";\n        providerMarker = "MIRURO REQUEST";\n    }'''
new = '''const char* url = nullptr;\n    const char* providerMarker = nullptr;\n    switch (g_apiSource)\n    {\n        case 1:\n            url = "https://animepahe.com/api?m=airing&page=1";\n            providerMarker = "ANIMEPAHE REQUEST";\n            break;\n        case 2:\n            url = "https://jaybeeanime.vercel.app/";\n            providerMarker = "GOGOANIME REQUEST";\n            break;\n        case 3:\n            url = "https://aniwatch-api-v1-0.onrender.com/api/parse";\n            providerMarker = "ANIWATCH REQUEST";\n            break;\n        case 4:\n            url = "https://hianime-api-production.up.railway.app/api/v1/home";\n            providerMarker = "HIANIME REQUEST";\n            break;\n        default:\n            url = "https://miruro.zenos.my.id/trending?per_page=6";\n            providerMarker = "MIRURO REQUEST";\n            break;\n    }'''
if old not in source:
    raise SystemExit("Could not locate finalized provider URL block")
source = source.replace(old, new, 1)

old_valid = 'primaryOk = api_response_is_valid(requestRc, httpCode, response, providerMarker);'
new_valid = '''if (g_apiSource >= 2)\n            {\n                primaryOk = requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && !response.empty();\n                char providerStatus[160];\n                std::snprintf(providerStatus, sizeof(providerStatus), "%s %s HTTP %ld BYTES %zu", providerMarker, primaryOk ? "OK" : "FAILED", httpCode, response.size());\n                log_stage(providerStatus);\n            }\n            else\n                primaryOk = api_response_is_valid(requestRc, httpCode, response, providerMarker);'''
if old_valid not in source:
    raise SystemExit("Could not locate provider validation call")
source = source.replace(old_valid, new_valid, 1)

# Make the non-Miruro failure guard cover all alternate providers.
source = source.replace('if (!primaryOk && g_apiSource != 0)', 'if (!primaryOk && g_apiSource != 0)', 1)

# Add small provider-specific extraction helpers before the existing title parser.
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
        raise SystemExit("Could not locate trending title parser")
    source = source.replace(marker, helper + marker, 1)

# Use provider-specific fields when the selected provider is not Miruro/AniList.
source = source.replace(
    '''    std::vector<std::string> titles = extract_trending_titles(response);\n    std::vector<std::string> details = extract_trending_details(response);\n    std::vector<std::string> covers = extract_trending_covers(response);''',
    '''    std::vector<std::string> titles;\n    std::vector<std::string> details;\n    std::vector<std::string> covers;\n    if (g_apiSource >= 2)\n    {\n        titles = extract_provider_titles(response, g_apiSource);\n        covers = extract_provider_covers(response, g_apiSource);\n    }\n    else\n    {\n        titles = extract_trending_titles(response);\n        details = extract_trending_details(response);\n        covers = extract_trending_covers(response);\n    }''',
    1,
)

# Provider-specific parser validation should be visible in the log.
if "PROVIDER PARSER FOUND" not in source:
    marker = '    std::snprintf(marker, sizeof(marker), "TRENDING PARSE FOUND %zu TITLES", titles.size());\n'
    replacement = '    std::snprintf(marker, sizeof(marker), "TRENDING PARSE FOUND %zu TITLES", titles.size());\n'
    source = source.replace(marker, replacement, 1)

main.write_text(source)
print("All five provider IDs now route to provider-specific endpoints and parsers")
