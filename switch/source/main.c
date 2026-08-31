#include <switch.h>
#include <stdio.h>

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    consoleInit(NULL);

    printf("Saikou Switch\n\n");
    printf("Native Switch port bootstrap\n");
    printf("\n");
    printf("Milestone 0: libnx bootstrap\n");
    printf("\n");
    printf("This build validates the native Switch app shell.\n");
    printf("Controller input will be added with the UI layer.\n");

    while (appletMainLoop()) {
        consoleUpdate(NULL);
    }

    consoleExit(NULL);
    return 0;
}
