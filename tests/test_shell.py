import sys

import pytest

from sage import shell


@pytest.mark.parametrize(
    "chain, expected",
    [
        (["python.exe", "uv.exe", "sage.exe", "pwsh.exe", "explorer.exe"], "pwsh"),
        (["python.exe", "powershell.exe"], "powershell"),
        (["sage.exe", "cmd.exe", "WindowsTerminal.exe"], "cmd"),
        (["python.exe", "bash.exe", "mintty.exe"], "bash"),
        (["python.exe", "explorer.exe"], "powershell"),
        ([], "powershell"),
    ],
)
def test_detect_shell(chain, expected):
    assert shell.detect_shell(chain) == expected


def test_shell_argv():
    assert shell.shell_argv("pwsh", "ls")[0] == "pwsh"
    assert shell.shell_argv("powershell", "ls")[0] == "powershell"
    assert shell.shell_argv("cmd", "dir")[:2] == ["cmd", "/c"]
    assert shell.shell_argv("bash", "ls")[:2] == ["bash", "-c"]


def test_truncate():
    assert shell.truncate("abc", 10) == "abc"
    out = shell.truncate("x" * 100, 10)
    assert out.startswith("x" * 10) and "truncated" in out


def test_run_in_shell_round_trip():
    sh = "cmd" if sys.platform == "win32" else "bash"
    out = shell.run_in_shell("echo hello", sh)
    assert "hello" in out and "exit code: 0" in out


def test_run_in_shell_nonzero_exit():
    sh = "cmd" if sys.platform == "win32" else "bash"
    assert "exit code: 3" in shell.run_in_shell("exit 3", sh)
