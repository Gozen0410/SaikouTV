#include <borealis.hpp>
#include <borealis/views/tab_frame.hpp>
#include <switch.h>
#include <curl/curl.h>
#include <cstdio>
#include <cstdlib>
#include <string>

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
    // This is deliberately a tiny proof-of-life request, not a general downloader.
    // Keep the response bounded so a bad server cannot consume the UI process heap.
    constexpr size_t kMaxResponse = 512 * 1024;
    if (output->size() < kMaxResponse)
    {
        const size_t remaining = kMaxResponse - output->size();
        output->append(ptr, bytes < remaining ? bytes : remaining);
    }
    return bytes;
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

static std::string run_api_probe()
{
    log_stage("BEFORE SOCKET INITIALIZE");
    Result socketRc = socketInitializeDefault();
    if (R_FAILED(socketRc))
    {
        log_stage("SOCKET INITIALIZE FAILED");
        return "Network init failed";
    }
    log_stage("SOCKET INITIALIZE OK");

    CURLcode globalRc = curl_global_init(CURL_GLOBAL_DEFAULT);
    if (globalRc != CURLE_OK)
    {
        log_stage("CURL GLOBAL INIT FAILED");
        socketExit();
        return "HTTP init failed";
    }
    log_stage("CURL GLOBAL INIT OK");

    std::string response;
    CURL* curl = curl_easy_init();
    if (!curl)
    {
        log_stage("CURL EASY INIT FAILED");
        curl_global_cleanup();
        socketExit();
        return "HTTP client init failed";
    }

    // Public Miruro API v3 deployment used only as a networking proof target.
    // The app's own fork can replace this base URL once it is deployed.
    const char* url = "https://miruro.zenos.my.id/trending?per_page=1";
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

    std::string result;
    if (requestRc == CURLE_OK && httpCode >= 200 && httpCode < 300 && response.find("results") != std::string::npos)
    {
        char marker[96];
        std::snprintf(marker, sizeof(marker), "API REQUEST OK HTTP %ld BYTES %zu", httpCode, response.size());
        log_stage(marker);
        result = "API online - trending data received";
    }
    else
    {
        char marker[128];
        std::snprintf(marker, sizeof(marker), "API REQUEST FAILED CURL %d HTTP %ld BYTES %zu", static_cast<int>(requestRc), httpCode, response.size());
        log_stage(marker);
        result = "API request failed - UI still running";
    }

    curl_easy_cleanup(curl);
    curl_global_cleanup();
    socketExit();
    log_stage("API PROBE CLEANUP COMPLETE");
    return result;
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

    // Do not touch TabFrame's private creator/focus machinery. The public
    // content API is retained, but first prove the actual Home resource exists
    // and bypass Borealis' resource-name wrapper so the path is unambiguous.
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
                        std::string apiStatus = run_api_probe();
                        log_stage("AFTER API PROBE");

                        brls::Box* homeBox = dynamic_cast<brls::Box*>(homeContent);
                        if (homeBox)
                        {
                            brls::Label* status = new brls::Label();
                            status->setText(apiStatus);
                            homeBox->addView(status);
                            log_stage("API STATUS LABEL ATTACHED");
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
