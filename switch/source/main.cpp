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

int main(int argc, char* argv[])
{
    (void)argc;
    (void)argv;

    // Keep the diagnostic completely independent of Borealis resources/UI.
    fsdevMountSdmc();
    g_log = std::fopen("sdmc:/switch/saikou_debug.log", "w");
    log_stage("entered main");

    brls::Logger::setLogLevel(brls::LogLevel::DEBUG);
    log_stage("logger configured");

    if (!brls::Application::init())
    {
        log_stage("Application::init FAILED");
        if (g_log) std::fclose(g_log);
        return EXIT_FAILURE;
    }
    log_stage("Application::init OK");

    // Do not create a window or load XML yet. This isolates Application::init().
    while (true)
    {
        svcSleepThread(1000000000LL);
    }

    return EXIT_SUCCESS;
}
