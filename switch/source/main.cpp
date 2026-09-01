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

static brls::View* makeHomeDiagnosticView()
{
    log_stage("CREATOR DIAG: ENTER");
    brls::Label* label = new brls::Label();
    log_stage(label ? "CREATOR DIAG: LABEL NEW OK" : "CREATOR DIAG: LABEL NEW NULL");
    if (!label) return nullptr;
    label->setText("Home Content");
    log_stage("CREATOR DIAG: SET TEXT OK");
    return label;
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
    brls::TabFrame* tabFrame = dynamic_cast<brls::TabFrame*>(root);
    log_stage(tabFrame ? "TABFRAME POINTER VALID AFTER PUSH" : "TABFRAME POINTER NULL AFTER PUSH");
    if (tabFrame)
    {
        log_stage("BEFORE REAL TABFRAME CREATOR CONTROL");
        brls::View* content = tabFrame->createFirstTabView();
        log_stage(content ? "REAL TABFRAME CREATOR RETURNED VIEW" : "REAL TABFRAME CREATOR RETURNED NULL");
        if (content)
        {
            log_stage("REAL TABFRAME CREATOR VIEW VALID");
            delete content;
            log_stage("REAL TABFRAME CREATOR VIEW DELETED");
        }
        log_stage("AFTER REAL TABFRAME CREATOR CONTROL");
    }

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
