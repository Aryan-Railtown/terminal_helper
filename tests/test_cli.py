import os

import pytest

from sage import agent, cli, config


def test_parse_args_joins_words():
    args = cli.parse_args(["how", "do", "I", "list", "ports"])
    assert args.question == "how do I list ports"
    assert args.new is False


def test_parse_args_flags():
    args = cli.parse_args(["--new", "--model", "gemini-x", "hello"])
    assert args.new and args.model == "gemini-x" and args.question == "hello"


def test_no_question_prints_usage(capsys):
    assert cli.main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()


def test_prepare_env_always_logs_to_sage_home(monkeypatch, tmp_path):
    for var in ("RAILTRACKS_HOME", "RAILTRACKS_DISABLE_EVENTS", "SAGE_DEBUG"):
        monkeypatch.delenv(var, raising=False)
    cli.prepare_env(tmp_path)
    assert os.environ["RAILTRACKS_HOME"] == str(tmp_path)
    assert "RAILTRACKS_DISABLE_EVENTS" not in os.environ


def test_prepare_env_respects_explicit_opt_out(monkeypatch, tmp_path):
    monkeypatch.setenv("RAILTRACKS_DISABLE_EVENTS", "True")
    cli.prepare_env(tmp_path)
    assert os.environ["RAILTRACKS_DISABLE_EVENTS"] == "True"


def test_missing_key_is_config_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("SAGE_HOME", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert cli.main(["hello"]) == 2
    err = capsys.readouterr().err
    assert "GEMINI_API_KEY" in err and str(tmp_path) in err


def test_load_config_defaults_and_override(tmp_path):
    cfg = config.load_config(tmp_path)
    assert cfg.provider == config.DEFAULT_PROVIDER and cfg.model == config.DEFAULT_MODEL
    (tmp_path / "config.toml").write_text('provider = "anthropic"\nmodel = "claude-haiku-4-5"\n')
    cfg = config.load_config(tmp_path)
    assert cfg.provider == "anthropic" and cfg.model == "claude-haiku-4-5"


def test_unknown_provider_rejected(tmp_path):
    (tmp_path / "config.toml").write_text('provider = "nope"\n')
    with pytest.raises(config.ConfigError):
        config.load_config(tmp_path)


def test_compose_prompt_includes_history():
    turns = [{"question": "how to list files", "answer": "Get-ChildItem", "cwd": "C:\\"}]
    out = agent.compose_prompt("only .py ones", turns)
    assert "how to list files" in out and "only .py ones" in out
    assert agent.compose_prompt("hi", []) == "hi"


def test_system_message_mentions_shell_and_cwd():
    msg = agent.build_system_message("pwsh", "C:\\work")
    assert "pwsh" in msg and "C:\\work" in msg
