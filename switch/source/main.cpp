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
    brls::Application::setGlobalQuit(false);

    log_stage("BEFORE HomeActivity construction");
    HomeActivity* activity = new HomeActivity();
    log_stage("AFTER HomeActivity construction");

    // Probe the exact post-inflation stages performed by pushActivity().
    // This intentionally avoids pushActivity() so the first failing stage is visible.
    log_stage("PROBE BEFORE createContentView");
    brls::View* content = activity->createContentView();
    log_stage(content ? "PROBE AFTER createContentView" : "PROBE createContentView returned NULL");

    log_stage("PROBE BEFORE setContentView");
    activity->setContentView(content);
    log_stage("PROBE AFTER setContentView");

    log_stage("PROBE BEFORE onContentAvailable");
    activity->onContentAvailable();
    log_stage("PROBE AFTER onContentAvailable");

    log_stage("PROBE BEFORE isTranslucent");
    bool translucent = activity->isTranslucent();
    log_stage(translucent ? "PROBE AFTER isTranslucent TRUE" : "PROBE AFTER isTranslucent FALSE");

    log_stage("PROBE BEFORE resizeToFitWindow");
    activity->resizeToFitWindow();
    log_stage("PROBE AFTER resizeToFitWindow");

    log_stage("PROBE BEFORE getDefaultFocus");
    brls::View* defaultFocus = activity->getDefaultFocus();
    log_stage(defaultFocus ? "PROBE AFTER getDefaultFocus NONNULL" : "PROBE AFTER getDefaultFocus NULL");

    log_stage("PROBE BEFORE willAppear");
    activity->willAppear(true);
    log_stage("PROBE AFTER willAppear");

    log_stage("PROBE ALL POST-INFLATION STAGES OK");

    // If every public stage above survives, hand control back to the real pushActivity()
    // to determine whether its remaining stack/animation/focus bookkeeping is the fault.
    delete activity;

    log_stage("BEFORE HomeActivity construction (REAL PUSH)");
    activity = new HomeActivity();
    log_stage("AFTER HomeActivity construction (REAL PUSH)");
    log_stage("BEFORE pushActivity(home)");
    brls::Application::pushActivity(activity);
    log_stage("AFTER pushActivity(home)");

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
