#include <borealis.hpp>

#include <cstdio>
#include <cstdlib>

static void log_stage(const char* stage)
{
    std::printf("[Saikou] %s\n", stage);
    std::fflush(stdout);
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

    log_stage("entered main");
    brls::Logger::setLogLevel(brls::LogLevel::DEBUG);
    log_stage("logger configured");

    if (!brls::Application::init())
    {
        log_stage("Application::init FAILED");
        return EXIT_FAILURE;
    }
    log_stage("Application::init OK");

    brls::Application::createWindow("Saikou Switch");
    log_stage("window created");

    brls::Application::setGlobalQuit(true);
    log_stage("global quit configured");

    brls::Application::pushActivity(new HomeActivity());
    log_stage("HomeActivity pushed");

    while (brls::Application::mainLoop())
        ;

    log_stage("main loop ended");
    return EXIT_SUCCESS;
}
