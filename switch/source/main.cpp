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

    // Final experiment: avoid the resource-file loader entirely. Create the
    // already-known-good Home markup directly from an XML string, then attach
    // it through the public Box child API to the existing displayed hierarchy.
    const char* homeXml = R"xml(
        <brls:Box width="auto" height="auto" axis="column" paddingTop="40" paddingBottom="40" paddingLeft="50" paddingRight="50">
            <brls:Label width="auto" height="auto" text="Saikou Switch" fontSize="42" horizontalAlign="center" />
            <brls:Label width="auto" height="auto" text="Your anime, rebuilt for Nintendo Switch" marginTop="20" horizontalAlign="center" />
            <brls:Separator marginTop="35" marginBottom="35" />
            <brls:Label width="auto" height="auto" text="Trending" fontSize="30" />
            <brls:Label width="auto" height="auto" text="AniList integration coming next" marginTop="20" />
        </brls:Box>
    )xml";

    log_stage("BEFORE DIRECT HOME XML STRING");
    brls::View* homeContent = brls::View::createFromXMLString(homeXml);
    log_stage(homeContent ? "DIRECT HOME XML RETURNED VIEW" : "DIRECT HOME XML RETURNED NULL");

    if (homeContent && root)
    {
        log_stage("DIRECT HOME XML VIEW VALID");
        auto& rootChildren = root->getChildren();
        char marker[64];
        std::snprintf(marker, sizeof(marker), "ROOT CHILD COUNT %zu", rootChildren.size());
        log_stage(marker);

        // TabFrame inherits Box. Its AppletFrame layout contains one outer
        // Box; that Box contains header, content row, and footer. Use only
        // public getChildren()/addView() APIs to reach that existing content row.
        if (!rootChildren.empty())
        {
            brls::View* outer = rootChildren[0];
            auto& outerChildren = outer->getChildren();
            std::snprintf(marker, sizeof(marker), "OUTER CHILD COUNT %zu", outerChildren.size());
            log_stage(marker);

            if (outerChildren.size() >= 2)
            {
                brls::View* contentRow = outerChildren[1];
                contentRow->addView(homeContent);
                homeContent = nullptr;
                log_stage("DIRECT HOME XML ADDED TO CONTENT ROW");
            }
        }
    }

    if (homeContent)
    {
        delete homeContent;
        log_stage("DIRECT HOME XML VIEW DELETED AFTER ATTACHMENT FAILURE");
    }
    log_stage("AFTER DIRECT HOME XML ATTACHMENT");

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
