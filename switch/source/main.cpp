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

static void log_dims(const char* prefix, u32 width, u32 height)
{
    if (!g_log)
        return;
    std::fprintf(g_log, "[Saikou] %s: %ux%u\n", prefix, width, height);
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

    DkDevice device = dkDeviceCreate(&deviceMaker);
    if (!device)
    {
        log_stage("dkDeviceCreate FAILED");
        return EXIT_FAILURE;
    }
    log_stage("dkDeviceCreate OK");

    DkQueueMaker queueMaker;
    dkQueueMakerDefaults(&queueMaker, device);
    queueMaker.flags = DkQueueFlags_Graphics;

    DkQueue queue = dkQueueCreate(&queueMaker);
    if (!queue)
    {
        log_stage("dkQueueCreate FAILED");
        dkDeviceDestroy(device);
        return EXIT_FAILURE;
    }
    log_stage("dkQueueCreate OK");

    log_stage("getting default NWindow");
    NWindow* window = nwindowGetDefault();
    if (!window || !nwindowIsValid(window))
    {
        log_stage("nwindowGetDefault INVALID");
        dkQueueDestroy(queue);
        dkDeviceDestroy(device);
        return EXIT_FAILURE;
    }
    log_stage("default NWindow OK");

    u32 width = 0;
    u32 height = 0;
    Result rc = nwindowGetDimensions(window, &width, &height);
    if (R_FAILED(rc))
    {
        log_stage("nwindowGetDimensions FAILED");
        dkQueueDestroy(queue);
        dkDeviceDestroy(device);
        return EXIT_FAILURE;
    }
    log_dims("NWindow dimensions", width, height);

    // Two manually allocated render targets, following the same deko3d
    // swapchain pattern used by existing Switch GPU-console code.
    constexpr unsigned FB_NUM = 2;
    DkImageLayoutMaker layoutMaker;
    dkImageLayoutMakerDefaults(&layoutMaker, device);
    layoutMaker.flags = DkImageFlags_UsageRender | DkImageFlags_UsagePresent;
    layoutMaker.format = DkImageFormat_RGBA8_Unorm;
    layoutMaker.dimensions[0] = width;
    layoutMaker.dimensions[1] = height;
    layoutMaker.dimensions[2] = 1;

    log_stage("initializing framebuffer image layout");
    DkImageLayout framebufferLayout;
    dkImageLayoutInitialize(&framebufferLayout, &layoutMaker);

    const uint32_t imageSize = dkImageLayoutGetSize(&framebufferLayout);
    const uint32_t imageAlign = dkImageLayoutGetAlignment(&framebufferLayout);
    const uint32_t framebufferSize = (imageSize + imageAlign - 1) & ~(imageAlign - 1);

    if (framebufferSize == 0)
    {
        log_stage("framebuffer layout returned zero size");
        dkQueueDestroy(queue);
        dkDeviceDestroy(device);
        return EXIT_FAILURE;
    }
    log_stage("framebuffer image layout OK");

    DkMemBlockMaker memMaker;
    dkMemBlockMakerDefaults(&memMaker, device, FB_NUM * framebufferSize);
    memMaker.flags = DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image;

    log_stage("creating framebuffer memory block");
    DkMemBlock imageMem = dkMemBlockCreate(&memMaker);
    if (!imageMem)
    {
        log_stage("framebuffer memory block FAILED");
        dkQueueDestroy(queue);
        dkDeviceDestroy(device);
        return EXIT_FAILURE;
    }
    log_stage("framebuffer memory block OK");

    DkImage framebuffers[FB_NUM];
    const DkImage* swapchainImages[FB_NUM];

    for (unsigned i = 0; i < FB_NUM; ++i)
    {
        log_stage(i == 0 ? "initializing framebuffer 0" : "initializing framebuffer 1");
        dkImageInitialize(&framebuffers[i], &framebufferLayout, imageMem, i * framebufferSize);
        swapchainImages[i] = &framebuffers[i];
    }
    log_stage("framebuffer images initialized");

    log_stage("creating deko3d swapchain");
    DkSwapchainMaker swapchainMaker;
    dkSwapchainMakerDefaults(&swapchainMaker, device, window, swapchainImages, FB_NUM);
    DkSwapchain swapchain = dkSwapchainCreate(&swapchainMaker);

    if (!swapchain)
    {
        log_stage("dkSwapchainCreate FAILED");
        dkMemBlockDestroy(imageMem);
        dkQueueDestroy(queue);
        dkDeviceDestroy(device);
        return EXIT_FAILURE;
    }
    log_stage("dkSwapchainCreate OK");
    log_stage("DISPLAY/SWAPCHAIN INITIALIZATION SUCCESS");

    while (true)
        svcSleepThread(1000000000LL);

    return EXIT_SUCCESS;
}
