#include <deko3d.h>
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

static void deko_debug(void*, const char* context, DkResult result, const char* message)
{
    if (!g_log)
        return;
    std::fprintf(g_log, "[Deko3D] context=%s result=%d message=%s\n",
        context ? context : "(null)", (int)result, message ? message : "(null)");
    std::fflush(g_log);
}

int main(int argc, char* argv[])
{
    (void)argc;
    (void)argv;

    fsdevMountSdmc();
    g_log = std::fopen("sdmc:/switch/saikou_debug.log", "w");
    log_stage("entered main");

    log_stage("creating deko3d device maker");
    DkDeviceMaker deviceMaker;
    dkDeviceMakerDefaults(&deviceMaker);
    deviceMaker.cbDebug = deko_debug;
    log_stage("device maker configured");

    log_stage("calling dkDeviceCreate");
    DkDevice device = dkDeviceCreate(&deviceMaker);
    if (!device)
    {
        log_stage("dkDeviceCreate FAILED");
        if (g_log) std::fclose(g_log);
        return EXIT_FAILURE;
    }
    log_stage("dkDeviceCreate OK");

    log_stage("creating graphics queue maker");
    DkQueueMaker queueMaker;
    dkQueueMakerDefaults(&queueMaker, device);
    log_stage("queue maker configured");

    log_stage("calling dkQueueCreate");
    DkQueue queue = dkQueueCreate(&queueMaker);
    if (!queue)
    {
        log_stage("dkQueueCreate FAILED");
        dkDeviceDestroy(device);
        if (g_log) std::fclose(g_log);
        return EXIT_FAILURE;
    }
    log_stage("dkQueueCreate OK");

    log_stage("deko3d device and queue initialized successfully");

    while (true)
        svcSleepThread(1000000000LL);

    return EXIT_SUCCESS;
}
