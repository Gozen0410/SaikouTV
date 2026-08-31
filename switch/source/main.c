#include <switch.h>
#include <stdio.h>

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    consoleInit(NULL);

    printf("Saikou Switch\n\n");
    printf("Native Switch port bootstrap\n");
    printf("\n");
    printf("Milestone 0: libnx + input loop\n");
    printf("\n");
    printf("A/B/X/Y: test input\n");
    printf("+ : exit\n");

    while (appletMainLoop()) {
        hidScanInput();
        const u64 kDown = hidKeysDown(CONTROLLER_P1_AUTO);

        if (kDown & KEY_PLUS)
            break;

        consoleUpdate(NULL);
    }

    consoleExit(NULL);
    return 0;
}
