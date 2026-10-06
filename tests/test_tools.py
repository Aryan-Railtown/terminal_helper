import sys

import pytest

from sage import tools


@pytest.fixture(autouse=True)
def _shell(monkeypatch):
    monkeypatch.setattr(tools, "CURRENT_SHELL", "cmd" if sys.platform == "win32" else "bash")


def test_list_directory_lists_entries(tmp_path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.txt").write_text("y")
    (tmp_path / "sub").mkdir()
    out = tools.list_directory(str(tmp_path))
    assert "a.py" in out and "b.txt" in out and "sub" in out


def test_list_directory_pattern_and_cap(tmp_path):
    for i in range(10):
        (tmp_path / f"f{i}.py").write_text("x")
    (tmp_path / "skip.txt").write_text("x")
    out = tools.list_directory(str(tmp_path), pattern="*.py", limit=3)
    assert "skip.txt" not in out
    assert "7 more" in out


def test_list_directory_missing_path(tmp_path):
    assert "does not exist" in tools.list_directory(str(tmp_path / "nope"))


def test_read_file_caps_lines(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("\n".join(f"line{i}" for i in range(500)))
    out = tools.read_file(str(f), max_lines=5)
    assert "line4" in out and "line5" not in out
    assert "truncated" in out


def test_read_file_missing(tmp_path):
    assert "does not exist" in tools.read_file(str(tmp_path / "nope.txt"))


def test_read_file_binary(tmp_path):
    f = tmp_path / "bin.dat"
    f.write_bytes(b"\x00\x01\x02binary")
    assert "binary" in tools.read_file(str(f)).lower()


def test_which_hit_and_miss():
    assert "installed" in tools.which("python").lower()
    assert "not found" in tools.which("definitely-not-a-real-cmd-xyz").lower()


def test_run_command_confirmed(monkeypatch):
    monkeypatch.setattr(tools, "confirm", lambda command, reason: True)
    out = tools.run_command("echo hi", "test")
    assert "hi" in out and "exit code: 0" in out


@pytest.mark.parametrize("answer", [False])
def test_run_command_declined(monkeypatch, answer):
    ran = []
    monkeypatch.setattr(tools, "confirm", lambda command, reason: answer)
    monkeypatch.setattr(tools, "run_in_shell", lambda *a, **k: ran.append(a))
    out = tools.run_command("echo hi", "test")
    assert out == tools.DECLINED
    assert not ran


@pytest.mark.parametrize(
    "command",
    [
        "format C:",
        "rm -rf /",
        "Remove-Item -Recurse -Force C:\\",
        "diskpart",
        "reg delete HKLM\\Software\\X",
        "shutdown /s /t 0",
    ],
)
def test_run_command_denylist_blocks_even_when_confirmed(monkeypatch, command):
    monkeypatch.setattr(tools, "confirm", lambda command, reason: True)
    monkeypatch.setattr(tools, "run_in_shell", lambda *a, **k: pytest.fail("should not run"))
    assert "refused" in tools.run_command(command, "test").lower()


def test_safe_commands_not_denied():
    assert not tools.is_denied("git status")
    assert not tools.is_denied("Get-ChildItem -Recurse src")


def test_confirm_without_console_declines(monkeypatch):
    monkeypatch.setattr(tools, "_console_reader", lambda: None)
    assert tools.confirm("echo hi", "test") is False


def test_every_tool_has_docstring_and_hints():
    for fn in tools.ALL_TOOLS:
        assert fn.__doc__ and "Args:" in fn.__doc__ or fn.__code__.co_argcount == 0
        assert "return" in fn.__annotations__
