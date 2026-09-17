#include "shell.h"

#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t interrupted;

static void handle_interrupt(int signal_number)
{
    (void)signal_number;
    interrupted = 1;
}

static void print_prompt(void)
{
    time_t now = time(NULL);
    struct tm *local = localtime(&now);
    char prompt[32];

    if (local != NULL &&
        strftime(prompt, sizeof(prompt), "[%d/%m %H:%M]# ", local) != 0)
        fputs(prompt, stdout);
    else
        fputs("# ", stdout);
    fflush(stdout);
}

int shell_run(void)
{
    struct sigaction action = {0};
    char *line = NULL;
    size_t capacity = 0;
    int status = 0;
    int interactive = isatty(STDIN_FILENO);

    action.sa_handler = handle_interrupt;
    sigemptyset(&action.sa_mask);
    /* No SA_RESTART: Ctrl+C interrupts an idle getline call. */
    if (sigaction(SIGINT, &action, NULL) < 0) {
        perror("sigaction");
        return 1;
    }

    for (;;) {
        struct command command;

        if (interrupted) {
            interrupted = 0;
            if (interactive)
                putchar('\n');
        }
        if (interactive)
            print_prompt();
        errno = 0;
        if (getline(&line, &capacity, stdin) < 0) {
            if (errno == EINTR) {
                clearerr(stdin);
                status = 130;
                continue;
            }
            if (!feof(stdin)) {
                perror("getline");
                status = 1;
            }
            break;
        }
        if (parse_command(line, &command) < 0) {
            status = 2;
            continue;
        }
        if (command.argv[0] != NULL)
            status = execute_command(&command);
    }
    free(line);
    return status;
}
