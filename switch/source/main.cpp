#include <borealis.hpp>
#include <switch.h>

#include <cstdio>
#include <cstdlib>

static FILE* g_log = nullptr;

static void log_stage(const char* stage)
{
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
    log_stage("closing Saikou log before Borealis init");

    // Borealis has its own diagnostic writer. Close our handle before entering
    // Application::init() so two libc FILE handles never access the same file.
    if (g_log)
    {
        std::fclose(g_log);
        g_log = nullptr;
    }

    // Borealis' SwitchPlatform instrumentation now owns the log during init.
    if (!brls::Application::init())
    {
        FILE* log = std::fopen("sdmc:/switch/saikou_debug.log", "a");
        if (log)
        {
            std::fprintf(log, "[Saikou] Application::init FAILED\n");
            std::fclose(log);
        }
        return EXIT_FAILURE;
    }

    FILE* log = std::fopen("sdmc:/switch/saikou_debug.log", "a");
    if (log)
    {
        std::fprintf(log, "[Saikou] Application::init OK\n");
        std::fclose(log);
    }

    brls::Application::createWindow("Saikou Switch");
    log = std::fopen("sdmc:/switch/saikou_debug.log", "a");
    if (log)
    {
        std::fprintf(log, "[Saikou] Borealis window created\n");
        std::fclose(log);
    }

    brls::Application::setGlobalQuit(true);
    brls::Application::pushActivity(new HomeActivity());

    while (brls::Application::mainLoop())
        ;

    return EXIT_SUCCESS;
}
