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
    printf("Press + to exit.\n");

    while (appletMainLoop()) {
        consoleUpdate(NULL);
    }

    consoleExit(NULL);
    return 0;
}
