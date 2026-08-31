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
    CONTENT_FROM_XML_RES("activity/main.xml");
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

    log_stage("BEFORE createContentView");
    brls::View* content = activity->createContentView();
    log_stage("AFTER createContentView");
    activity->setContentView(content);
    log_stage("AFTER setContentView");
    activity->onContentAvailable();
    log_stage("AFTER onContentAvailable");
    activity->resizeToFitWindow();
    log_stage("AFTER resizeToFitWindow");
    activity->show([] { log_stage("show callback"); }, true,
                   activity->getShowAnimationDuration(brls::TransitionAnimation::FADE));
    log_stage("AFTER show");
    activity->willAppear(true);
    log_stage("AFTER willAppear");

    // FINAL CONTROL: remove the HomeActivity focus target entirely.
    // Do not call pushActivity(); if this reaches mainLoop, focus is the
    // confirmed difference between the working probe and the crash.
    log_stage("BEFORE giveFocus(nullptr) CONTROL");
    brls::Application::giveFocus(nullptr);
    log_stage("AFTER giveFocus(nullptr) CONTROL");
    log_stage("FOCUS BYPASS COMPLETE - BEFORE mainLoop");

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
    delete activity;
    romfsExit();
    return EXIT_SUCCESS;
}
