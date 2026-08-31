#include <switch.h>
#include <switch/services/hid.h>
#include <stdio.h>

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    consoleInit(NULL);

    // The current libnx no longer exposes the old hidScanInput() helper in
    // the public input path used by this toolchain. Initialize Npad support
    // explicitly and read the shared-memory state directly.
    hidInitializeNpad();
    hidSetSupportedNpadStyleSet(HidNpadStyleSet_NpadFullCtrl);

    const HidNpadIdType ids[] = {
        HidNpadIdType_No1,
        HidNpadIdType_Handheld,
    };
    hidSetSupportedNpadIdType(ids, sizeof(ids) / sizeof(ids[0]));

    printf("Saikou Switch\n\n");
    printf("Native Switch port bootstrap\n");
    printf("\n");
    printf("Milestone 0: libnx + controller input\n");
    printf("\n");
    printf("Press + to exit.\n");

    while (appletMainLoop()) {
        HidNpadFullKeyState state;
        size_t count = hidGetNpadStatesFullKey(HidNpadIdType_No1, &state, 1);

        if (count > 0 && (state.buttons & HidNpadButton_Plus))
            break;

        HidNpadHandheldState handheld;
        count = hidGetNpadStatesHandheld(HidNpadIdType_Handheld, &handheld, 1);

        if (count > 0 && (handheld.buttons & HidNpadButton_Plus))
            break;

        consoleUpdate(NULL);
    }

    consoleExit(NULL);
    return 0;
}
