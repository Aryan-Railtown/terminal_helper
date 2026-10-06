"""Live end-to-end checks against a real model.

Opt-in: `uv run pytest -m live`. Skipped unless the provider's API key is set
(env or ~/.sage/.env). Pick the model with SAGE_LIVE_MODEL (alias or id).
Assertions are loose keyword checks: models phrase things differently.
"""

import io
import os
import subprocess

import pytest

from sage import cli, config, tools

pytestmark = pytest.mark.live


@pytest.fixture
def sage(monkeypatch, tmp_path, capsys):
    real_home = config.sage_home()
    config.load_env(real_home)
    cfg = config.load_config(real_home)
    if spec := os.environ.get("SAGE_LIVE_MODEL"):
        cfg.provider, cfg.model = config.resolve_model(spec, cfg.provider)
    try:
        config.check_api_key(cfg)
    except config.ConfigError as e:
        pytest.skip(str(e))

    sandbox = tmp_path / "sage_home"
    sandbox.mkdir()
    monkeypatch.setenv("SAGE_HOME", str(sandbox))  # isolated history
    monkeypatch.setattr(tools, "confirm", lambda command, reason: False)  # never run commands
    monkeypatch.setattr(cli, "read_piped_input", lambda *a, **k: "")

    def ask(*argv: str, piped: str = "") -> str:
        if piped:
            monkeypatch.setattr(cli, "read_piped_input", lambda *a, **k: piped)
        code = cli.main(["--model", f"{cfg.provider}:{cfg.model}", *argv])
        out = capsys.readouterr()
        assert code == 0, out.err
        return out.out.lower()

    return ask


def has_any(text: str, *needles: str) -> bool:
    return any(n.lower() in text for n in needles)


def test_port_8080(sage):
    out = sage("how do I find which process is using port 8080?")
    assert "8080" in out
    assert has_any(out, "Get-NetTCPConnection", "netstat", "OwningProcess")


def test_git_diverged(sage):
    out = sage("why is git telling me my branch has diverged?")
    assert has_any(out, "rebase", "merge", "pull")
    assert has_any(out, "commit")


def test_recursive_python_string_search(sage):
    out = sage("how do I recursively find all Python files containing this string?")
    assert ".py" in out
    assert has_any(out, "Select-String", "findstr", "grep", "rg ")


def test_explain_this_error_piped(sage):
    err = (
        "Traceback (most recent call last):\n"
        '  File "app.py", line 1, in <module>\n'
        "    import requests\n"
        "ModuleNotFoundError: No module named 'requests'\n"
    )
    out = sage("explain", "this", "error", piped=err)
    assert "requests" in out and has_any(out, "install")


def test_dot_overview(sage, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    (proj / "README.md").write_text("# demo\nRun with `uv run demo`.\n")
    monkeypatch.chdir(proj)
    out = sage(".")
    assert has_any(out, "python", "pyproject", "demo")


def test_what_did_i_just_break(sage, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "settings.py").write_text("DEBUG = True\n")
    monkeypatch.chdir(repo)
    hist = tmp_path / "history.txt"
    hist.write_text("git checkout -b feature\nRemove-Item config.json\n")
    monkeypatch.setattr(tools, "history_file", lambda: hist)
    out = sage("what did I just break?")
    assert has_any(out, "settings.py", "config.json")
