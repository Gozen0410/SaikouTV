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

    log_stage("calling Borealis Application::init");
    if (!brls::Application::init())
    {
        log_stage("Application::init FAILED");
        if (g_log)
            std::fclose(g_log);
        return EXIT_FAILURE;
    }
    log_stage("Application::init OK");

    log_stage("creating Borealis window");
    brls::Application::createWindow("Saikou Switch");
    log_stage("Borealis window created");

    brls::Application::setGlobalQuit(true);
    log_stage("global quit configured");

    log_stage("pushing HomeActivity");
    brls::Application::pushActivity(new HomeActivity());
    log_stage("HomeActivity pushed");

    while (brls::Application::mainLoop())
        ;

    log_stage("main loop ended");
    if (g_log)
        std::fclose(g_log);
    return EXIT_SUCCESS;
}
