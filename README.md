# Unix Shell in C

A small Unix shell by Warren Chong, refactored from a university C assignment.
It demonstrates process creation, command execution, file descriptors, signal
handling, and a built-in command that changes the shell's own working directory.

## Features

- Run external programs found through `PATH`, using `fork` and `execvp`.
- Change directories with `cd PATH`, or `cd` to use `HOME`.
- Redirect standard output with `command > file` (create or truncate).
- Show a timestamped prompt in interactive terminals.
- Keep the shell alive on Ctrl+C while allowing the foreground command to stop.
- Read commands from standard input without adding prompts to batch output.
- Report syntax errors and return the last command's exit status at EOF.

## Build and run

Requires a POSIX environment, a C11 compiler, and Make. Use Linux, macOS, or WSL
on Windows; native Windows is not supported.

```sh
make
./minishell
```

Example commands entered at the shell prompt:

```text
pwd
ls -l
echo hello > greeting.txt
cat greeting.txt
cd /tmp
pwd
```

Press Ctrl+D at an empty prompt to exit. For batch input, run this from your
existing system shell:

```sh
printf 'echo hello\npwd\n' | ./minishell
```

## Test

Python 3 is needed only for tests:

```sh
make test
```

The regression suite covers directory changes, output redirection and failure
paths, argument limits, long lines, exit statuses, and Ctrl+C through a pseudo
terminal. GitHub Actions builds with GCC and Clang using warnings as errors.

## Structure

| File | Responsibility |
| --- | --- |
| `src/main.c` | Entry point |
| `src/shell.c` | Input loop, prompt, and signal handling |
| `src/parser.c` | Tokenization and redirection validation |
| `src/executor.c` | Built-in command, child processes, and output files |
| `include/shell.h` | Shared command structure and public interfaces |
| `tests/test_shell.py` | Black-box behavior and terminal tests |

The parser borrows pointers into the current input buffer. Execution completes
before the next line is read, so those pointers remain valid. The signal handler
only sets a `sig_atomic_t` flag; prompt output happens in the main loop. The parent
retries interrupted waits and children restore the default SIGINT behavior.

## Deliberate limits

This is an educational shell, with whitespace-separated arguments and at most
127 words including the command name. One `>` redirection is supported and must
appear at the end with one filename. Quoting, escaping, variables, globbing,
pipes, append/input redirection, command chaining, and background jobs are not
implemented. Unsupported syntax other than malformed `>` is treated literally.
There is no built-in `exit`; use EOF. It is not a POSIX shell implementation.

## Refactoring notes

The original assignment provided external commands, `cd`, a timestamped prompt,
and output redirection. This version separates parsing, execution, and terminal
interaction; validates malformed redirection instead of silently dropping input;
reports argument overflow; handles interrupted waits; and avoids stdio operations
inside signal handlers. It also applies redirection to `cd` and propagates command
statuses. A small Makefile replaces the generated Autotools distribution files.
Assignment identifiers and the student email are omitted from the source headers;
authorship and the coursework origin are retained here.
