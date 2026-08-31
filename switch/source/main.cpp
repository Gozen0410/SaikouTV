#include <borealis.hpp>
#include <switch.h>

#include <cstdio>
#include <cstdlib>

static FILE* g_log = nullptr;

static void log_stage(const char* stage)
{
    if (!g_log)
        g_log = std::fopen("sdmc:/switch/saikou_debug.log", "a");
    if (!g_log)
        return;
    std::fprintf(g_log, "[Saikou] %s\n", stage);
    std::fflush(g_log);
}

class HomeActivity : public brls::Activity
{
  public:
    CONTENT_FROM_XML_RES("activity/main.xml");
};

int main(int argc, char* argv[])
{
    (void)argc;
    (void)argv;

    fsdevMountSdmc();
    g_log = std::fopen("sdmc:/switch/saikou_debug.log", "w");
    log_stage("entered main");

    brls::Logger::setLogLevel(brls::LogLevel::DEBUG);
    log_stage("logger configured");

    Result romfsRc = romfsInit();
    if (R_SUCCEEDED(romfsRc))
        log_stage("romfsInit OK");
    else
        log_stage("romfsInit FAILED");

    log_stage("closing Saikou log before Borealis init");
    if (g_log)
    {
        std::fclose(g_log);
        g_log = nullptr;
    }

    if (!brls::Application::init())
    {
        log_stage("Application::init FAILED");
        romfsExit();
        return EXIT_FAILURE;
    }

    log_stage("Application::init OK");

    brls::Application::createWindow("Saikou Switch");
    log_stage("Borealis window created");

    log_stage("BEFORE setGlobalQuit(false)");
    brls::Application::setGlobalQuit(false);
    log_stage("AFTER setGlobalQuit(false)");

    log_stage("BEFORE HomeActivity construction");
    HomeActivity* home = new HomeActivity();
    log_stage("AFTER HomeActivity construction");

    log_stage("BEFORE pushActivity");
    brls::Application::pushActivity(home);
    log_stage("AFTER pushActivity");

    log_stage("BEFORE mainLoop");
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
