#include <borealis.hpp>
#include <switch.h>
#include <cstdio>
#include <cstdlib>

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

    // Final isolation step: do not touch TabFrame at all. Inflate the already
    // proven Home XML into an independent Box and keep it alive for one loop.
    log_stage("BEFORE HOME CONTENT XML");
    brls::View* homeContent = brls::View::createFromXMLResource("activity/home.xml");
    log_stage(homeContent ? "HOME CONTENT XML RETURNED VIEW" : "HOME CONTENT XML RETURNED NULL");
    if (homeContent)
    {
        log_stage("HOME CONTENT XML VIEW VALID");
        brls::Box* host = new brls::Box();
        log_stage(host ? "HOME HOST BOX CREATED" : "HOME HOST BOX NULL");
        if (host)
        {
            host->addView(homeContent);
            log_stage("HOME CONTENT ADDED TO HOST BOX");
            homeContent = nullptr; // host owns it now
            log_stage("HOME CONTENT OWNERSHIP TRANSFERRED");
            delete host;
            log_stage("HOME HOST BOX DELETED");
        }
        else
        {
            delete homeContent;
            log_stage("HOME CONTENT XML VIEW DELETED AFTER HOST FAILURE");
        }
    }
    log_stage("AFTER HOME CONTENT XML");

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
