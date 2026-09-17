"""Black-box regression tests. Run on a POSIX host with Python 3."""
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest

BINARY = str(Path(sys.argv.pop(1) if len(sys.argv) > 1 else "./minishell").resolve())


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="shell-test-")
        self.addCleanup(self.directory.cleanup)
        self.cwd = Path(self.directory.name)

    def run_shell(self, commands, **kwargs):
        return subprocess.run([BINARY], input=commands, text=True,
                              capture_output=True, cwd=self.cwd, timeout=5, **kwargs)

    def test_empty_input_and_whitespace(self):
        for commands in ("", "\n \t\r\n"):
            with self.subTest(commands=commands):
                result = self.run_shell(commands)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_external_command_and_final_line_without_newline(self):
        result = self.run_shell("echo hello world")
        self.assertEqual((result.returncode, result.stdout), (0, "hello world\n"))

    def test_cd_changes_parent_directory(self):
        (self.cwd / "sub").mkdir()
        result = self.run_shell("cd sub\npwd\n")
        self.assertEqual(result.stdout.strip(), str((self.cwd / "sub").resolve()))

    def test_cd_home(self):
        (self.cwd / "home").mkdir()
        result = self.run_shell("cd\npwd\n", env={**os.environ, "HOME": str(self.cwd / "home")})
        self.assertEqual(result.stdout.strip(), str((self.cwd / "home").resolve()))

    def test_cd_missing_home(self):
        env = dict(os.environ)
        env.pop("HOME", None)
        result = self.run_shell("cd\n", env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("HOME not set", result.stderr)

    def test_cd_rejects_extra_arguments(self):
        (self.cwd / "sub").mkdir()
        result = self.run_shell("cd sub extra\npwd\n")
        self.assertIn("at most one", result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.cwd.resolve()))

    def test_cd_missing_directory(self):
        self.assertEqual(self.run_shell("cd missing-directory\n").returncode, 1)

    def test_redirection_truncates_and_does_not_leak(self):
        (self.cwd / "out").write_text("previous longer contents")
        result = self.run_shell("echo first>out\necho second\n")
        self.assertEqual(result.stdout, "second\n")
        self.assertEqual((self.cwd / "out").read_text(), "first\n")

    def test_cd_redirection_creates_file_before_changing_directory(self):
        (self.cwd / "sub").mkdir()
        result = self.run_shell("cd sub > out\npwd\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual((self.cwd / "out").read_text(), "")
        self.assertEqual(result.stdout.strip(), str((self.cwd / "sub").resolve()))

    def test_failed_redirection_prevents_cd(self):
        (self.cwd / "sub").mkdir()
        result = self.run_shell("cd sub > missing/out\npwd\n")
        self.assertTrue(result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.cwd.resolve()))

    def test_failed_external_redirection(self):
        result = self.run_shell("echo hidden > missing/out\n")
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertTrue(result.stderr)

    def test_malformed_redirection_does_not_execute(self):
        for command in ("touch marker >", "touch marker >> out", "touch marker > out extra",
                        "touch marker > out > other", "> out"):
            with self.subTest(command=command):
                result = self.run_shell(command + "\n")
                self.assertEqual(result.returncode, 2)
                self.assertFalse((self.cwd / "marker").exists())
                self.assertFalse((self.cwd / "out").exists())

    def test_argument_limit(self):
        result = self.run_shell("echo " + " ".join(["a"] * 126) + "\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.split()), 126)
        result = self.run_shell("touch marker " + " ".join(["a"] * 126) + "\n")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.cwd / "marker").exists())

    def test_long_line(self):
        word = "x" * 8192
        result = self.run_shell("echo " + word + "\n")
        self.assertEqual(result.stdout, word + "\n")

    def test_child_status_and_recovery(self):
        self.assertEqual(self.run_shell("false\n").returncode, 1)
        self.assertEqual(self.run_shell("no-such-shell-test-command\n").returncode, 127)
        result = self.run_shell("no-such-shell-test-command\necho recovered\n")
        self.assertEqual((result.returncode, result.stdout), (0, "recovered\n"))

    def test_non_executable_status(self):
        (self.cwd / "not-executable").write_text("data\n")
        self.assertEqual(self.run_shell("./not-executable\n").returncode, 126)

    def test_sigint_at_prompt_and_during_child(self):
        pid, terminal = pty.fork()
        if pid == 0:
            os.chdir(self.cwd)
            os.execv(BINARY, [BINARY])
        reaped = False

        def read_until(marker):
            data = b""
            deadline = time.monotonic() + 5
            while marker not in data:
                remaining = deadline - time.monotonic()
                self.assertGreater(remaining, 0, repr(data))
                if select.select([terminal], [], [], remaining)[0]:
                    chunk = os.read(terminal, 4096)
                    self.assertTrue(chunk, repr(data))
                    data += chunk
            return data

        try:
            read_until(b"# ")
            os.write(terminal, b"\x03")
            read_until(b"# ")
            # The helper prints only after exec, then waits for SIGINT.
            helper = self.cwd / "wait.py"
            helper.write_text("import signal, time\nsignal.signal(signal.SIGINT, signal.SIG_DFL)\n"
                              "print('CHILD_READY', flush=True)\ntime.sleep(30)\n")
            os.write(terminal, f"{sys.executable} {helper}\n".encode())
            read_until(b"CHILD_READY\r\n")
            # Interrupt only the parent: it must keep waiting for its child.
            os.kill(pid, signal.SIGINT)
            self.assertFalse(select.select([terminal], [], [], 0.2)[0],
                             "shell stopped waiting after EINTR")
            os.write(terminal, b"\x03")
            read_until(b"# ")
            os.write(terminal, b"echo recovered\n")
            self.assertIn(b"recovered\r\n", read_until(b"# "))
            os.write(terminal, b"\x04")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                waited, status = os.waitpid(pid, os.WNOHANG)
                if waited:
                    reaped = True
                    self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                    break
                time.sleep(0.02)
            self.assertTrue(reaped, "shell did not exit on EOF")
        finally:
            if not reaped:
                os.killpg(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(terminal)


if __name__ == "__main__":
    unittest.main(verbosity=2)
