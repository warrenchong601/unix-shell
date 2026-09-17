/* Warren Chong — educational Unix shell. */
#ifndef SHELL_H
#define SHELL_H

#define SHELL_MAX_ARGS 128

/* Pointers borrow storage from the mutable input line. */
struct command {
    char *argv[SHELL_MAX_ARGS];
    char *output_path;
};

/* Returns 0 on success (including an empty line), -1 on syntax error. */
int parse_command(char *line, struct command *command);
int execute_command(const struct command *command);
int shell_run(void);

#endif
