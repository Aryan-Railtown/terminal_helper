"""Config modes: --model aliases, --tools, --debug, `sage .`, piped input."""

import io
import os

import pytest

from sage import agent, cli, config, tools


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("SAGE_HOME", str(tmp_path))
    for var in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "SAGE_DEBUG"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


# --model -------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec, expected",
    [
        ("sonnet", ("anthropic", "claude-sonnet-5-5")),
        ("opus", ("anthropic", "claude-opus-5-5")),
        ("haiku", ("anthropic", "claude-haiku-4-5-20251001")),
        ("flash-lite", ("gemini", config.DEFAULT_MODEL)),
        ("SONNET", ("anthropic", "claude-sonnet-5-5")),
        ("claude-opus-5-5", ("anthropic", "claude-opus-5-5")),
        ("gemini-3.5-flash-lite", ("gemini", "gemini-3.5-flash-lite")),
        ("gpt-5", ("openai", "gpt-5")),
        ("anthropic:claude-x", ("anthropic", "claude-x")),
        ("my-local-model", ("gemini", "my-local-model")),
    ],
)
def test_resolve_model(spec, expected):
    assert config.resolve_model(spec, "gemini") == expected


def test_model_alias_in_config_file(tmp_path):
    (tmp_path / "config.toml").write_text('model = "sonnet"\n')
    cfg = config.load_config(tmp_path)
    assert (cfg.provider, cfg.model) == ("anthropic", "claude-sonnet-5-5")


def test_model_flag_switches_required_key(home, capsys):
    assert cli.main(["--model", "sonnet", "hi"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_model_flag_alone_shows_resolution(home, capsys):
    assert cli.main(["--model", "sonnet"]) == 0
    out = capsys.readouterr().out
    assert "anthropic/claude-sonnet-5-5" in out and "ANTHROPIC_API_KEY" in out


# --tools -------------------------------------------------------------------


def test_tools_flag_lists_tools(home, capsys):
    assert cli.main(["--tools"]) == 0
    out = capsys.readouterr().out
    for fn in tools.ALL_TOOLS:
        assert fn.__name__ in out
    run_line = next(line for line in out.splitlines() if "run_command" in line)
    assert "asks first" in run_line


# --debug -------------------------------------------------------------------


def test_debug_alone_prints_diagnostics(home, capsys):
    assert cli.main(["--debug"]) == 0
    out = capsys.readouterr().out
    for needle in ("sage", "gemini/", "GEMINI_API_KEY", "not set", "shell:", str(home)):
        assert needle in out


def test_debug_flag_enables_debug_env(home, monkeypatch, capsys):
    monkeypatch.delenv("RAILTRACKS_DISABLE_EVENTS", raising=False)
    cli.main(["--debug", "hi"])  # fails on missing key, but env is set first
    assert os.environ.get("SAGE_DEBUG") == "1"


def test_traced_tool_logs_calls_and_keeps_metadata(capsys):
    traced = agent.trace(tools.which)
    assert traced.__name__ == "which" and traced.__doc__ == tools.which.__doc__
    traced("python")
    err = capsys.readouterr().err
    assert "which" in err and "python" in err


# `sage .` ------------------------------------------------------------------


def test_dot_expands_to_directory_overview():
    args = cli.parse_args(["."])
    assert args.question == cli.DOT_QUESTION


# piped input ---------------------------------------------------------------


class FakeStdin(io.StringIO):
    def isatty(self):
        return False

    def fileno(self):
        raise OSError("no fileno")


def test_read_piped_input_ignores_tty_and_unreadable():
    class Tty(io.StringIO):
        def isatty(self):
            return True

    assert cli.read_piped_input(Tty("x")) == ""
    assert cli.read_piped_input(FakeStdin("x")) == ""


def test_read_piped_input_keeps_tail(tmp_path):
    f = tmp_path / "out.txt"
    f.write_text("start\n" + "x" * 20000 + "\nFATAL: the real error")
    with open(f, encoding="utf-8") as stream:
        out = cli.read_piped_input(stream, limit=100)
    assert out.endswith("FATAL: the real error")
    assert "truncated" in out and "start" not in out


def test_compose_prompt_includes_piped_input():
    out = agent.compose_prompt("explain this error", [], piped="ModuleNotFoundError: requests")
    assert "ModuleNotFoundError" in out and "explain this error" in out


# recent_commands / git_overview -------------------------------------------


def test_recent_commands_reads_history_and_skips_sage(tmp_path, monkeypatch):
    hist = tmp_path / "ConsoleHost_history.txt"
    hist.write_text("cd proj\ngit pull\nnpm run build\nsage what did I just break?\n")
    monkeypatch.setattr(tools, "history_file", lambda: hist)
    out = tools.recent_commands(2)
    assert "git pull" in out and "npm run build" in out
    assert "cd proj" not in out and "sage what" not in out


def test_recent_commands_redacts_secrets(tmp_path, monkeypatch):
    hist = tmp_path / "h.txt"
    hist.write_text("$env:OPENAI_API_KEY='sk-abc123'\ncurl -H 'token: abc'\n")
    monkeypatch.setattr(tools, "history_file", lambda: hist)
    out = tools.recent_commands(5)
    assert "sk-abc123" not in out and "redacted" in out


def test_recent_commands_no_history(monkeypatch):
    monkeypatch.setattr(tools, "history_file", lambda: None)
    assert "no shell history" in tools.recent_commands().lower()


def test_git_overview(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "app.py").write_text("print(1)\n")
    out = tools.git_overview(str(tmp_path))
    assert "app.py" in out


def test_git_overview_not_a_repo(tmp_path):
    assert "not a git repository" in tools.git_overview(str(tmp_path)).lower()


# confirm via console --------------------------------------------------------


@pytest.mark.parametrize("line, expected", [("y\n", True), ("yes\n", True), ("\n", False), ("n\n", False)])
def test_confirm_reads_console(monkeypatch, line, expected):
    monkeypatch.setattr(tools, "_console_reader", lambda: (lambda: line))
    assert tools.confirm("echo hi", "test") is expected
