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

class LabelActivity : public brls::Activity
{
  public:
    brls::View* createContentView() override
    {
        log_stage("BEFORE Label construction");
        brls::Label* label = new brls::Label();
        log_stage("AFTER Label construction");

        log_stage("BEFORE Label setText");
        label->setText("Saikou Label Test");
        log_stage("AFTER Label setText");

        return label;
    }
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

    log_stage("BEFORE LabelActivity construction");
    LabelActivity* activity = new LabelActivity();
    log_stage("AFTER LabelActivity construction");

    log_stage("BEFORE pushActivity(label)");
    brls::Application::pushActivity(activity);
    log_stage("AFTER pushActivity(label)");

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
