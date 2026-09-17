#include "shell.h"

#include <stdio.h>
#include <string.h>

static int syntax_error(const char *message)
{
    fprintf(stderr, "shell: %s\n", message);
    return -1;
}

int parse_command(char *line, struct command *command)
{
    char *redirect;
    char *token;
    char *save = NULL;
    size_t count = 0;

    memset(command, 0, sizeof(*command));
    redirect = strchr(line, '>');
    if (redirect != NULL) {
        *redirect++ = '\0';
        if (strchr(redirect, '>') != NULL)
            return syntax_error("only one > redirection is supported");
        command->output_path = strtok_r(redirect, " \t\r\n", &save);
        if (command->output_path == NULL)
            return syntax_error("missing output filename");
        if (strtok_r(NULL, " \t\r\n", &save) != NULL)
            return syntax_error("redirection must end with one filename");
    }

    for (token = strtok_r(line, " \t\r\n", &save); token != NULL;
         token = strtok_r(NULL, " \t\r\n", &save)) {
        if (count == SHELL_MAX_ARGS - 1)
            return syntax_error("too many arguments");
        command->argv[count++] = token;
    }
    if (count == 0 && command->output_path != NULL)
        return syntax_error("missing command before >");
    return 0;
}
