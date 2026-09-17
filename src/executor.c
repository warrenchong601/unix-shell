#include "shell.h"

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static int change_directory(const struct command *command)
{
    const char *path = command->argv[1];

    if (path != NULL && command->argv[2] != NULL) {
        fprintf(stderr, "cd: expected at most one argument\n");
        return 1;
    }
    if (path == NULL) {
        path = getenv("HOME");
        if (path == NULL || *path == '\0') {
            fprintf(stderr, "cd: HOME not set\n");
            return 1;
        }
    }
    if (chdir(path) < 0) {
        perror("cd");
        return 1;
    }
    return 0;
}

static int open_output(const char *path)
{
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (fd < 0)
        perror(path);
    return fd;
}

static int run_external(const struct command *command)
{
    pid_t pid = fork();
    int status;

    if (pid < 0) {
        perror("fork");
        return 1;
    }
    if (pid == 0) {
        struct sigaction action = {0};
        action.sa_handler = SIG_DFL;
        sigemptyset(&action.sa_mask);
        if (sigaction(SIGINT, &action, NULL) < 0) {
            perror("sigaction");
            _exit(1);
        }
        if (command->output_path != NULL) {
            int fd = open_output(command->output_path);
            if (fd < 0)
                _exit(1);
            if (dup2(fd, STDOUT_FILENO) < 0) {
                perror("dup2");
                close(fd);
                _exit(1);
            }
            if (fd != STDOUT_FILENO)
                close(fd);
        }
        execvp(command->argv[0], command->argv);
        status = errno == ENOENT ? 127 : 126;
        perror(command->argv[0]);
        _exit(status);
    }

    while (waitpid(pid, &status, 0) < 0) {
        if (errno == EINTR)
            continue;
        perror("waitpid");
        return 1;
    }
    if (WIFEXITED(status))
        return WEXITSTATUS(status);
    if (WIFSIGNALED(status))
        return 128 + WTERMSIG(status);
    return 1;
}

int execute_command(const struct command *command)
{
    if (strcmp(command->argv[0], "cd") == 0) {
        /* cd produces no stdout, but redirection must still create/truncate
         * its file and prevent the directory change if opening fails. */
        if (command->output_path != NULL) {
            int fd = open_output(command->output_path);
            if (fd < 0)
                return 1;
            if (close(fd) < 0) {
                perror("close");
                return 1;
            }
        }
        return change_directory(command);
    }
    return run_external(command);
}
