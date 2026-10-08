"""macOS / Unix support: shell history formats, help fallback, denylist, prompt context."""

import pytest

from sage import agent, tools

ZSH_EXTENDED = (
    ": 1712345670:0;cd ~/proj\n"
    ": 1712345671:0;git pull --rebase\n"
    ": 1712345672:3;npm run build\n"
    ": 1712345673:0;sage what did I just break?\n"
)
FISH = (
    "- cmd: cd ~/proj\n"
    "  when: 1712345670\n"
    "- cmd: git pull --rebase\n"
    "  when: 1712345671\n"
    "  paths:\n"
    "    - ~/proj\n"
    "- cmd: npm run build\n"
    "  when: 1712345672\n"
)


def test_parse_zsh_extended_history():
    assert tools.parse_history("zsh", ZSH_EXTENDED)[-2:] == ["npm run build", "sage what did I just break?"]


def test_parse_zsh_plain_and_multiline():
    text = "ls -la\nfor f in *.py; do \\\n  echo $f\\\ndone\n"
    assert tools.parse_history("zsh", text) == ["ls -la", "for f in *.py; do \n  echo $f\ndone"]


def test_parse_fish_history():
    assert tools.parse_history("fish", FISH) == ["cd ~/proj", "git pull --rebase", "npm run build"]


def test_parse_bash_and_pwsh_unchanged():
    assert tools.parse_history("bash", "ls\n\ngit status\n") == ["ls", "git status"]


@pytest.mark.parametrize("shell_name, text", [("zsh", ZSH_EXTENDED), ("fish", FISH)])
def test_recent_commands_unix_formats(monkeypatch, tmp_path, shell_name, text):
    f = tmp_path / "hist"
    f.write_text(text)
    monkeypatch.setattr(tools, "CURRENT_SHELL", shell_name)
    monkeypatch.setattr(tools, "history_file", lambda: f)
    out = tools.recent_commands(2)
    assert "git pull --rebase" in out and "npm run build" in out
    assert "1712345" not in out and "cmd:" not in out and "sage what" not in out


@pytest.mark.parametrize(
    "shell_name, rel",
    [
        ("zsh", ".zsh_history"),
        ("bash", ".bash_history"),
        ("fish", ".local/share/fish/fish_history"),
        ("pwsh", ".local/share/powershell/PSReadLine/ConsoleHost_history.txt"),
    ],
)
def test_history_file_unix_locations(monkeypatch, tmp_path, shell_name, rel):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("ls\n")
    monkeypatch.setattr(tools.Path, "home", lambda: tmp_path)
    monkeypatch.delenv("HISTFILE", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(tools, "CURRENT_SHELL", shell_name)
    assert tools.history_file() == f


def test_history_file_respects_histfile(monkeypatch, tmp_path):
    f = tmp_path / "custom_hist"
    f.write_text("ls\n")
    monkeypatch.setenv("HISTFILE", str(f))
    monkeypatch.setattr(tools, "CURRENT_SHELL", "zsh")
    assert tools.history_file() == f


def test_command_help_falls_back_to_man(monkeypatch):
    calls = []

    def fake_run(cmd, shell, timeout=60):
        calls.append(cmd)
        if "--help" in cmd:
            return "exit code: 1\nls: unrecognized option `--help'"
        return "exit code: 0\nLS(1)  General Commands Manual\n     ls -- list directory contents"

    monkeypatch.setattr(tools, "CURRENT_SHELL", "zsh")
    monkeypatch.setattr(tools, "run_in_shell", fake_run)
    out = tools.command_help("ls")
    assert "list directory contents" in out
    assert calls[0] == "ls --help" and calls[1].startswith("man ls")


def test_command_help_keeps_good_help(monkeypatch):
    monkeypatch.setattr(tools, "CURRENT_SHELL", "zsh")
    monkeypatch.setattr(tools, "run_in_shell", lambda cmd, shell, timeout=60: "exit code: 0\nusage: git [--version]")
    assert "usage: git" in tools.command_help("git")


@pytest.mark.parametrize(
    "command",
    ["diskutil eraseDisk APFS Blank disk2", "diskutil zeroDisk disk2", "sudo rm -rf /", "rm -rf ~", "rm -rf ~/", "rm -rf $HOME", "csrutil disable"],
)
def test_mac_denylist(command):
    assert tools.is_denied(command)


@pytest.mark.parametrize("command", ["diskutil list", "rm -rf ./build", "rm -rf ~/proj/node_modules", "lsof -i :8080"])
def test_mac_safe_commands(command):
    assert not tools.is_denied(command)


def test_system_message_on_macos(monkeypatch):
    monkeypatch.setattr(agent.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(agent.platform, "mac_ver", lambda: ("15.1", ("", "", ""), "arm64"))
    msg = agent.build_system_message("zsh", "/Users/me/proj")
    assert "macOS 15.1" in msg and "zsh" in msg
    assert "lsof" in msg and "Git Bash" not in msg


def test_system_message_on_windows(monkeypatch):
    monkeypatch.setattr(agent.platform, "system", lambda: "Windows")
    monkeypatch.setattr(agent.platform, "release", lambda: "11")
    msg = agent.build_system_message("bash", "C:\proj")
    assert "Windows 11" in msg and "Git Bash" in msg and "macOS" not in msg
