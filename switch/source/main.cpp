#include <borealis.hpp>
#include <borealis/views/tab_frame.hpp>
#include <borealis/views/image.hpp>
#include <switch.h>
#include <curl/curl.h>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

static FILE* g_log = nullptr;
static void log_stage(const char* stage)
{
    if (!g_log) g_log = std::fopen("sdmc:/switch/saikou_debug.log", "a");
    if (!g_log) return;
    std::fprintf(g_log, "[Saikou] %s\n", stage);
    std::fflush(g_log);
}

static size_t api_write_callback(char* ptr, size_t size, size_t nmemb, void* userdata)
{
    std::string* output = static_cast<std::string*>(userdata);
    const size_t bytes = size * nmemb;
    constexpr size_t kMaxResponse = 512 * 1024;
    if (output->size() < kMaxResponse)
    {
        const size_t remaining = kMaxResponse - output->size();
        output->append(ptr, bytes < remaining ? bytes : remaining);
    }
    return bytes;
}

static size_t file_write_callback(char* ptr, size_t size, size_t nmemb, void* userdata)
{
    FILE* file = static_cast<FILE*>(userdata);
    return std::fwrite(ptr, size, nmemb, file);
}

class HomeActivity : public brls::Activity
{
public:
    brls::View* getDefaultFocus() override { return nullptr; }
    brls::View* createContentView() override
    {
        return brls::View::createFromXMLResource("activity/main.xml");
    }
};

struct ApiResult
{
    std::string status;
    std::string response;
};

static ApiResult run_api_probe()
{
    ApiResult result;

    log_stage("BEFORE SOCKET INITIALIZE");
    Result socketRc = socketInitializeDefault();
    bool socketOwned = false;

    if (R_SUCCEEDED(socketRc))
    {
        socketOwned = true;
        log_stage("SOCKET INITIALIZE OK");
    }
    else if (socketRc == MAKERESULT(Module_Libnx, LibnxError_AlreadyInitialized))
    {
        log_stage("SOCKET ALREADY INITIALIZED - REUSING EXISTING SOCKET DEVICE");
    }
    else
    {
        char marker[128];
        std::snprintf(marker, sizeof(marker), "SOCKET INITIALIZE FAILED RC 0x%08X LAST 0x%08X", static_cast<unsigned int>(socketRc), static_cast<unsigned int>(socketGetLastResult()));
        log_stage(marker);

        SocketInitConfig config = *socketGetDefaultInitConfig();
        config.bsd_service_type = BsdServiceType_Auto;
        log_stage("BEFORE SOCKET AUTO INITIALIZE");
        socketRc = socketInitialize(&config);
        if (R_SUCCEEDED(socketRc))
        {
            socketOwned = true;
            log_stage("SOCKET AUTO INITIALIZE OK");
        }
        else
        {
            std::snprintf(marker, sizeof(marker), "SOCKET AUTO INITIALIZE FAILED RC 0x%08X LAST 0x%08X", static_cast<unsigned int>(socketRc), static_cast<unsigned int>(socketGetLastResult()));
            log_stage(marker);
            result.status = "Network init failed";
            return result;
        }
    }

    CURLcode globalRc = curl_global_init(CURL_GLOBAL_DEFAULT);
    if (globalRc != CURLE_OK)
    {
        log_stage("CURL GLOBAL INIT FAILED");
        if (socketOwned) socketExit();
        result.status = "HTTP init failed";
        return result;
    }
    log_stage("CURL GLOBAL INIT OK");

    CURL* curl = curl_easy_init();
    if (!curl)
    {
        log_stage("CURL EASY INIT FAILED");
        curl_global_cleanup();
        if (socketOwned) socketExit();
        result.status = "HTTP client init failed";
        return result;
    }

    std::string response;
    const char* url = "https://miruro.zenos.my.id/trending?per_page=6";
    log_stage("BEFORE API REQUEST");
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_HTTPGET, 1L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_MAXREDIRS, 3L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 5L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 12L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "SaikouSwitch/0.2");
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, api_write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

    CURLcode requestRc = curl_easy_perform(curl);
    long httpCode = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &httpCode);

    if (requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && response.find("results") != std::string::npos)
    {
        char marker[96];
        std::snprintf(marker, sizeof(marker), "API REQUEST OK HTTP %ld BYTES %zu", httpCode, response.size());
        log_stage(marker);
        result.status = "API online - trending data received";
        result.response = response;
    }
    else
    {
        char marker[128];
        std::snprintf(marker, sizeof(marker), "API REQUEST FAILED CURL %d HTTP %ld BYTES %zu", static_cast<int>(requestRc), httpCode, response.size());
        log_stage(marker);
        result.status = "API request failed - UI still running";
    }

    curl_easy_cleanup(curl);
    curl_global_cleanup();
    if (socketOwned) socketExit();
    log_stage("API PROBE CLEANUP COMPLETE");
    return result;
}

static bool download_image(const std::string& url, const std::string& path)
{
    if (url.empty()) return false;

    log_stage("BEFORE COVER IMAGE DOWNLOAD");
    Result socketRc = socketInitializeDefault();
    bool socketOwned = false;
    if (R_SUCCEEDED(socketRc))
        socketOwned = true;
    else if (socketRc != MAKERESULT(Module_Libnx, LibnxError_AlreadyInitialized))
    {
        log_stage("COVER IMAGE SOCKET INITIALIZE FAILED");
        return false;
    }

    CURLcode globalRc = curl_global_init(CURL_GLOBAL_DEFAULT);
    if (globalRc != CURLE_OK)
    {
        log_stage("COVER IMAGE CURL GLOBAL INIT FAILED");
        if (socketOwned) socketExit();
        return false;
    }

    CURL* curl = curl_easy_init();
    FILE* file = std::fopen(path.c_str(), "wb");
    if (!curl || !file)
    {
        log_stage("COVER IMAGE CURL OR FILE INIT FAILED");
        if (file) std::fclose(file);
        if (curl) curl_easy_cleanup(curl);
        curl_global_cleanup();
        if (socketOwned) socketExit();
        return false;
    }

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPGET, 1L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_MAXREDIRS, 3L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 5L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 12L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "SaikouSwitch/0.2");
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, file_write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, file);

    CURLcode requestRc = curl_easy_perform(curl);
    long httpCode = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &httpCode);
    std::fclose(file);
    curl_easy_cleanup(curl);
    curl_global_cleanup();
    if (socketOwned) socketExit();

    if (requestRc != CURLE_OK || httpCode < 200 || httpCode >= 300)
    {
        std::remove(path.c_str());
        log_stage("COVER IMAGE DOWNLOAD FAILED");
        return false;
    }

    log_stage("COVER IMAGE DOWNLOAD OK");
    return true;
}

static std::string json_string_after(const std::string& text, size_t from, const char* key, size_t limit)
{
    const std::string needle = std::string("\"") + key + "\"";
    size_t keyPos = text.find(needle, from);
    if (keyPos == std::string::npos || keyPos >= limit) return std::string();

    size_t colon = text.find(':', keyPos + needle.size());
    if (colon == std::string::npos || colon >= limit) return std::string();
    size_t quote = text.find('"', colon + 1);
    if (quote == std::string::npos || quote >= limit) return std::string();

    std::string value;
    for (size_t i = quote + 1; i < limit; ++i)
    {
        if (text[i] == '\\' && i + 1 < limit)
        {
            const char escaped = text[i + 1];
            if (escaped == '"' || escaped == '\\' || escaped == '/') value.push_back(escaped);
            else if (escaped == 'n' || escaped == 't') value.push_back(' ');
            else value.push_back(escaped);
            ++i;
            continue;
        }
        if (text[i] == '"') break;
        value.push_back(text[i]);
    }
    return value;
}

static std::string json_value_after(const std::string& text, size_t from, const char* key, size_t limit)
{
    const std::string needle = std::string("\"") + key + "\"";
    size_t keyPos = text.find(needle, from);
    if (keyPos == std::string::npos || keyPos >= limit) return std::string();
    size_t colon = text.find(':', keyPos + needle.size());
    if (colon == std::string::npos || colon >= limit) return std::string();

    size_t start = colon + 1;
    while (start < limit && (text[start] == ' ' || text[start] == '\n' || text[start] == '\r' || text[start] == '\t')) ++start;
    size_t end = start;
    while (end < limit && text[end] != ',' && text[end] != '}' && text[end] != '\n') ++end;
    return text.substr(start, end - start);
}

static std::string json_nested_string_after(const std::string& text, size_t from, const char* parentKey, const char* childKey, size_t limit)
{
    const std::string parent = std::string("\"") + parentKey + "\"";
    size_t parentPos = text.find(parent, from);
    if (parentPos == std::string::npos || parentPos >= limit) return std::string();
    return json_string_after(text, parentPos + parent.size(), childKey, limit);
}

static std::vector<std::string> extract_trending_titles(const std::string& response)
{
    std::vector<std::string> titles;
    size_t resultsPos = response.find("\"results\"");
    if (resultsPos == std::string::npos) return titles;

    size_t cursor = resultsPos;
    while (titles.size() < 6)
    {
        size_t titlePos = response.find("\"title\"", cursor);
        if (titlePos == std::string::npos) break;

        size_t objectStart = response.find('{', titlePos);
        if (objectStart == std::string::npos) break;
        size_t objectEnd = response.find('}', objectStart + 1);
        if (objectEnd == std::string::npos) break;

        std::string title = json_string_after(response, objectStart, "english", objectEnd);
        if (title.empty()) title = json_string_after(response, objectStart, "romaji", objectEnd);
        if (title.empty()) title = json_string_after(response, objectStart, "native", objectEnd);

        if (!title.empty()) titles.push_back(title);
        cursor = objectEnd + 1;
    }
    return titles;
}

static std::vector<std::string> extract_trending_details(const std::string& response)
{
    std::vector<std::string> details;
    size_t resultsPos = response.find("\"results\"");
    if (resultsPos == std::string::npos) return details;

    size_t cursor = resultsPos;
    while (details.size() < 6)
    {
        size_t titlePos = response.find("\"title\"", cursor);
        if (titlePos == std::string::npos) break;
        size_t objectStart = response.find('{', titlePos);
        if (objectStart == std::string::npos) break;
        size_t objectEnd = response.find('}', objectStart + 1);
        if (objectEnd == std::string::npos) break;

        size_t itemEnd = response.find("\"title\"", objectEnd + 1);
        if (itemEnd == std::string::npos) itemEnd = response.size();

        std::string format = json_string_after(response, objectEnd, "format", itemEnd);
        if (format.empty()) format = json_string_after(response, objectEnd, "type", itemEnd);
        std::string score = json_value_after(response, objectEnd, "averageScore", itemEnd);

        std::string detail;
        if (!format.empty()) detail += format;
        if (!score.empty() && score != "null")
        {
            if (!detail.empty()) detail += "  •  ";
            detail += "Score: " + score;
        }
        details.push_back(detail);
        cursor = objectEnd + 1;
    }
    return details;
}

static std::vector<std::string> extract_trending_covers(const std::string& response)
{
    std::vector<std::string> covers;
    size_t resultsPos = response.find("\"results\"");
    if (resultsPos == std::string::npos) return covers;

    size_t cursor = resultsPos;
    while (covers.size() < 6)
    {
        size_t titlePos = response.find("\"title\"", cursor);
        if (titlePos == std::string::npos) break;
        size_t itemEnd = response.find("\"title\"", titlePos + 8);
        if (itemEnd == std::string::npos) itemEnd = response.size();

        std::string cover = json_nested_string_after(response, titlePos, "coverImage", "large", itemEnd);
        covers.push_back(cover);
        cursor = itemEnd;
    }
    return covers;
}

static void render_trending(brls::Box* homeBox, const std::string& response)
{
    if (!homeBox || response.empty()) return;

    log_stage("BEFORE TRENDING PARSE");
    std::vector<std::string> titles = extract_trending_titles(response);
    std::vector<std::string> details = extract_trending_details(response);
    std::vector<std::string> covers = extract_trending_covers(response);

    char marker[64];
    std::snprintf(marker, sizeof(marker), "TRENDING PARSE FOUND %zu TITLES", titles.size());
    log_stage(marker);

    if (titles.empty())
    {
        log_stage("TRENDING PARSE FOUND NO TITLES");
        return;
    }

    brls::Label* heading = new brls::Label();
    heading->setText("Trending Now");
    heading->setFontSize(28);
    homeBox->addView(heading);

    // First real card only: prove the complete cover download + Image path before
    // scaling the same component to all six results.
    brls::Box* row = new brls::Box(brls::Axis::ROW);
    row->setGrow(0.0f);
    row->setAlignItems(brls::AlignItems::FLEX_START);
    row->setMargins(8, 0, 8, 0);
    homeBox->addView(row);

    brls::Box* card = new brls::Box(brls::Axis::COLUMN);
    card->setWidth(190);
    card->setMargins(0, 12, 0, 0);

    bool imageAttached = false;
    if (!covers.empty() && !covers[0].empty())
    {
        const std::string imagePath = "sdmc:/switch/saikou_trending_0.jpg";
        if (download_image(covers[0], imagePath))
        {
            brls::Image* image = new brls::Image();
            image->setDimensions(180, 255);
            image->setScalingType(brls::ImageScalingType::CROP);
            image->setImageFromFile(imagePath);
            card->addView(image);
            imageAttached = true;
            log_stage("FIRST TRENDING COVER ATTACHED");
        }
    }

    if (!imageAttached)
        log_stage("FIRST TRENDING COVER NOT ATTACHED");

    brls::Label* title = new brls::Label();
    title->setText(titles[0]);
    title->setFontSize(20);
    title->setMaxWidth(180);
    title->setMargins(6, 0, 2, 0);
    card->addView(title);

    if (!details.empty() && !details[0].empty())
    {
        brls::Label* detail = new brls::Label();
        detail->setText(details[0]);
        detail->setFontSize(15);
        detail->setMaxWidth(180);
        card->addView(detail);
    }

    row->addView(card);

    // Keep the remaining five results as text for this first image-card build.
    // They will be converted to the same card component after image loading is
    // proven stable on hardware.
    for (size_t i = 1; i < titles.size(); ++i)
    {
        brls::Label* remaining = new brls::Label();
        remaining->setText(titles[i]);
        remaining->setFontSize(18);
        homeBox->addView(remaining);
    }

    log_stage("TRENDING UI ATTACHED");
}

int main(int argc, char* argv[])
{
    (void)argc; (void)argv;
    fsdevMountSdmc();
    g_log = std::fopen("sdmc:/switch/saikou_debug.log", "w");
    log_stage("entered main");
    brls::Logger::setLogLevel(brls::LogLevel::DEBUG);
    log_stage("logger configured");
    Result romfsRc = romfsInit();
    log_stage(R_SUCCEEDED(romfsRc) ? "romfsInit OK" : "romfsInit FAILED");
    log_stage("closing Saikou log before Borealis init");
    if (g_log) { std::fclose(g_log); g_log = nullptr; }

    if (!brls::Application::init()) return EXIT_FAILURE;
    log_stage("Application::init OK");
    brls::Application::createWindow("Saikou Switch");
    log_stage("Borealis window created");
    brls::Application::setGlobalQuit(false);

    log_stage("BEFORE HomeActivity construction");
    HomeActivity* activity = new HomeActivity();
    log_stage("AFTER HomeActivity construction");
    log_stage("BEFORE pushActivity(home) WITH FOCUS BYPASS");
    brls::Application::pushActivity(activity);
    log_stage("AFTER pushActivity(home) WITH FOCUS BYPASS");

    brls::View* root = activity->getContentView();
    log_stage(root ? "ROOT VIEW VALID AFTER PUSH" : "ROOT VIEW NULL AFTER PUSH");

    brls::TabFrame* tabFrame = dynamic_cast<brls::TabFrame*>(root);
    log_stage(tabFrame ? "TABFRAME PUBLIC API TARGET VALID" : "TABFRAME PUBLIC API TARGET NULL");

    if (tabFrame)
    {
        const char* homePath = "romfs:/xml/activity/home.xml";
        log_stage("BEFORE HOME RESOURCE PREFLIGHT");

        FILE* homeFile = std::fopen(homePath, "rb");
        if (!homeFile)
        {
            log_stage("HOME RESOURCE PREFLIGHT OPEN FAILED");
        }
        else
        {
            log_stage("HOME RESOURCE PREFLIGHT OPEN OK");
            std::fseek(homeFile, 0, SEEK_END);
            long fileSize = std::ftell(homeFile);
            std::fseek(homeFile, 0, SEEK_SET);

            if (fileSize <= 0 || fileSize > 1024 * 1024)
            {
                std::fclose(homeFile);
                log_stage("HOME RESOURCE PREFLIGHT INVALID SIZE");
            }
            else
            {
                std::string xml(static_cast<size_t>(fileSize), '\0');
                size_t readSize = std::fread(xml.data(), 1, xml.size(), homeFile);
                std::fclose(homeFile);

                if (readSize != xml.size())
                {
                    log_stage("HOME RESOURCE PREFLIGHT READ FAILED");
                }
                else
                {
                    log_stage("HOME RESOURCE PREFLIGHT READ OK");
                    log_stage("BEFORE HOME XML STRING INFLATION");
                    brls::View* homeContent = brls::View::createFromXMLString(xml);
                    log_stage(homeContent ? "HOME XML STRING RETURNED VIEW" : "HOME XML STRING RETURNED NULL");

                    if (homeContent)
                    {
                        log_stage("BEFORE API PROBE");
                        ApiResult api = run_api_probe();
                        log_stage("AFTER API PROBE");

                        brls::Box* homeBox = dynamic_cast<brls::Box*>(homeContent);
                        if (homeBox)
                        {
                            brls::Label* status = new brls::Label();
                            status->setText(api.status);
                            status->setFontSize(16);
                            homeBox->addView(status);
                            log_stage("API STATUS LABEL ATTACHED");

                            if (!api.response.empty())
                                render_trending(homeBox, api.response);
                        }
                        else
                        {
                            log_stage("HOME ROOT IS NOT BOX");
                        }

                        log_stage("BEFORE PUBLIC TABFRAME CONTENT SET");
                        tabFrame->setTabContent(homeContent);
                        log_stage("AFTER PUBLIC TABFRAME CONTENT SET");
                        homeContent = nullptr;
                    }
                }
            }
        }
    }

    log_stage("AFTER HOME CONTENT ATTACHMENT PATH");

    int loopCount = 0;
    while (brls::Application::mainLoop())
    {
        ++loopCount;
        if (loopCount <= 5)
        {
            char marker[64];
            std::snprintf(marker, sizeof(marker), "mainLoop returned true #%d", loopCount);
            log_stage(marker);
        }
    }
    log_stage("mainLoop returned false");
    romfsExit();
    return EXIT_SUCCESS;
}
