"""Railtracks verifiers that gate sage's tools.

`run_command` is wrapped in a `user_approval` pre_verifier: the user sees the command and
answers y/N before the tool body runs. A decline raises VerifierRejectedError, which the
agent receives as the tool result (so it falls back to giving advice), and every decision is
recorded in the run logs as `middleware.verifier.pre.*` events (visible in `railtracks viz`).
"""

from __future__ import annotations

from collections.abc import Callable

import railtracks as rt
from railtracks.middleware import Verdict
from railtracks.prebuilt.middleware import pre_verifier

from sage import tools

APPROVED = "Approved by the user."
REFUSED = "Refused: this command is on sage's denylist of destructive commands. Do not run it; explain instead."


def approve_command(command: str, reason: str) -> Verdict:
    """Gate for run_command: denylisted commands are refused outright, everything else asks y/N."""
    if tools.is_denied(command):
        return Verdict(accepted=False, comment=REFUSED)
    if tools.confirm(command, reason):
        return Verdict(accepted=True, comment=APPROVED)
    return Verdict(accepted=False, comment=tools.DECLINED)


# Tool name -> verifier. Must cover tools.GATED.
VERIFIERS: dict[str, Callable[..., Verdict]] = {"run_command": approve_command}


def tool_node(fn: Callable, wrap: Callable[[Callable], Callable] | None = None):
    """Build the railtracks tool node for `fn`, attaching its verifier if it has one."""
    body = wrap(fn) if wrap else fn
    verifier = VERIFIERS.get(fn.__name__)
    if verifier is None:
        return rt.function_node(body)
    return rt.function_node(middleware=[pre_verifier(verifier, name="user_approval")])(body)
