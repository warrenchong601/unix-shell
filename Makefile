CC = cc
CPPFLAGS = -D_POSIX_C_SOURCE=200809L -Iinclude
CFLAGS = -std=c11 -Wall -Wextra -Wpedantic -O2
LDFLAGS =
LDLIBS =
PYTHON = python3
SOURCES = src/main.c src/shell.c src/parser.c src/executor.c
OBJECTS = $(SOURCES:.c=.o)

.PHONY: all clean test
all: minishell

minishell: $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $(OBJECTS) $(LDLIBS)

$(OBJECTS): include/shell.h

test: minishell
	$(PYTHON) tests/test_shell.py ./minishell

clean:
	rm -f $(OBJECTS) minishell
