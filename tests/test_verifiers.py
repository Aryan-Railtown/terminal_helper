"""The user_approval pre_verifier that gates run_command."""

import os

import pytest

from sage import tools, verifiers


@pytest.fixture(autouse=True)
def _no_run_logs(monkeypatch):
    monkeypatch.setenv("RAILTRACKS_DISABLE_EVENTS", "True")


def test_approved(monkeypatch):
    monkeypatch.setattr(tools, "confirm", lambda command, reason: True)
    v = verifiers.approve_command("echo hi", "test")
    assert v.accepted is True and v.comment == verifiers.APPROVED


def test_declined(monkeypatch):
    monkeypatch.setattr(tools, "confirm", lambda command, reason: False)
    v = verifiers.approve_command("echo hi", "test")
    assert v.accepted is False and v.comment == tools.DECLINED


def test_denylisted_refused_without_prompting(monkeypatch):
    monkeypatch.setattr(tools, "confirm", lambda command, reason: pytest.fail("must not prompt"))
    v = verifiers.approve_command("diskpart", "test")
    assert v.accepted is False and "denylist" in v.comment


def test_every_gated_tool_has_a_verifier():
    assert set(verifiers.VERIFIERS) == tools.GATED


def _run_gated(command: str):
    import railtracks as rt

    node = verifiers.tool_node(tools.run_command)
    return rt.Flow(name="verifier-test", entry_point=node).invoke(command, "test")


def test_gated_node_declined_never_runs_body(monkeypatch):
    from railtracks.middleware import VerifierRejectedError

    monkeypatch.setattr(tools, "confirm", lambda command, reason: False)
    monkeypatch.setattr(tools, "run_in_shell", lambda *a, **k: pytest.fail("body ran"))
    with pytest.raises(VerifierRejectedError, match="declined"):
        _run_gated("echo hi")


def test_gated_node_approved_runs(monkeypatch):
    monkeypatch.setattr(tools, "confirm", lambda command, reason: True)
    out = _run_gated("echo hi")
    assert "hi" in str(out) and "exit code: 0" in str(out)


def test_ungated_tool_node_has_no_prompt(monkeypatch):
    import railtracks as rt

    monkeypatch.setattr(tools, "confirm", lambda command, reason: pytest.fail("must not prompt"))
    node = verifiers.tool_node(tools.which)
    assert "installed" in str(rt.Flow(name="t", entry_point=node).invoke("python"))
