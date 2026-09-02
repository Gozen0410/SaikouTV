#include <borealis.hpp>
#include <borealis/views/tab_frame.hpp>
#include <switch.h>
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

class HomeActivity : public brls::Activity
{
public:
    brls::View* getDefaultFocus() override { return nullptr; }
    brls::View* createContentView() override
    {
        return brls::View::createFromXMLResource("activity/main.xml");
    }
};

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
