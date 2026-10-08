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
        # macOS / Linux: login shells show up with a leading dash
        (["python3.11", "uv", "sage", "-zsh", "login", "Terminal"], "zsh"),
        (["Python", "zsh", "tmux: server"], "zsh"),
        (["python3", "fish", "iTerm2"], "fish"),
        (["python3", "-bash", "sshd"], "bash"),
        (["python3", "sh"], "sh"),
        (["python3", "pwsh", "Terminal"], "pwsh"),
    ],
)
def test_detect_shell(chain, expected):
    assert shell.detect_shell(chain) == expected


@pytest.mark.parametrize(
    "platform, shell_env, expected",
    [
        ("win32", None, "powershell"),
        ("win32", "/usr/bin/bash", "powershell"),  # $SHELL is often stale on Windows
        ("darwin", "/bin/zsh", "zsh"),
        ("darwin", "/opt/homebrew/bin/fish", "fish"),
        ("darwin", None, "zsh"),
        ("darwin", "/usr/local/bin/nu", "zsh"),  # unsupported shell -> platform default
        ("linux", "/bin/bash", "bash"),
        ("linux", None, "bash"),
    ],
)
def test_fallback_shell_per_platform(monkeypatch, platform, shell_env, expected):
    monkeypatch.setattr(shell.sys, "platform", platform)
    if shell_env:
        monkeypatch.setenv("SHELL", shell_env)
    else:
        monkeypatch.delenv("SHELL", raising=False)
    assert shell.detect_shell([]) == expected
    assert shell.detect_shell(["python3", "launchd"]) == expected


@pytest.mark.parametrize("name, expected", [("-zsh", "zsh"), ("ZSH", "zsh"), ("bash.exe", "bash"), ("pwsh.exe", "pwsh"), ("Finder", None)])
def test_normalise(name, expected):
    assert shell.shell_for_process(name) == expected


def test_shell_argv():
    assert shell.shell_argv("pwsh", "ls")[0] == "pwsh"
    assert shell.shell_argv("powershell", "ls")[0] == "powershell"
    assert shell.shell_argv("cmd", "dir")[:2] == ["cmd", "/c"]
    assert shell.shell_argv("bash", "ls")[:2] == ["bash", "-c"]
    assert shell.shell_argv("zsh", "ls") == ["zsh", "-c", "ls"]
    assert shell.shell_argv("fish", "ls") == ["fish", "-c", "ls"]
    assert shell.shell_argv("sh", "ls") == ["sh", "-c", "ls"]


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
