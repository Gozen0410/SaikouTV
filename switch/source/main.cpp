#include <borealis.hpp>

#include <cstdlib>

class HomeActivity : public brls::Activity
{
  public:
    CONTENT_FROM_XML_RES("activity/main.xml");
};

int main(int argc, char* argv[])
{
    (void)argc;
    (void)argv;

    brls::Logger::setLogLevel(brls::LogLevel::INFO);

    if (!brls::Application::init())
        return EXIT_FAILURE;

    brls::Application::createWindow("Saikou Switch");
    brls::Application::setGlobalQuit(true);
    brls::Application::pushActivity(new HomeActivity());

    while (brls::Application::mainLoop())
        ;

    return EXIT_SUCCESS;
}
