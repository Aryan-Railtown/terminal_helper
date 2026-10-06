"""Builds the sage railtracks agent."""

from __future__ import annotations

import functools
import platform
import sys
import time
from datetime import date

from sage import tools
from sage.config import Config, build_llm

_SHELL_NAMES = {
    "pwsh": "PowerShell 7 (pwsh)",
    "powershell": "Windows PowerShell 5.1",
    "cmd": "cmd.exe",
    "bash": "bash (likely Git Bash)",
}


def build_system_message(shell: str, cwd: str, today: date | None = None) -> str:
    today = today or date.today()
    shell_name = _SHELL_NAMES.get(shell, shell)
    return f"""You are sage, a concise terminal assistant living in the user's shell.

Environment:
- OS: {platform.system()} {platform.release()}
- Shell: {shell_name} [{shell}]
- Current directory: {cwd}
- Date: {today.isoformat()}

How to answer:
- Be brief and terminal-first. Your output is rendered as markdown in a terminal: use fenced code blocks with a language tag, short bullet lists and **bold** sparingly; no tables or headings.
- When the answer is a command, lead with the exact command in a fenced code block, written for the user's shell ({shell_name}), then one or two short lines of explanation.
- If the user asks something general, just answer it in a few sentences.
- Check facts with your read-only tools (which, list_directory, read_file, command_help, get_environment, git_overview, recent_commands) instead of guessing whether something is installed or exists.
- For git questions in a repository, look at git_overview first so your answer fits their actual state.
- For "what did I just break?" / "explain this error" with no error text, use recent_commands and git_overview to see what they did. If text was piped into sage, that is the output to explain.
- "How do I ..." questions are requests for a command, not for you to run it: answer with the command and do NOT call run_command.
- Only use run_command when the user asks you to check or do something on their machine and your read-only tools can't answer it. Never run commands that change or delete things unless the user clearly asked you to do that.
- If the user declines a command, do not retry it; give it as advice instead.
"""


def compose_prompt(question: str, turns: list[dict], piped: str = "") -> str:
    """Fold recent Q&A turns and any piped-in text into the prompt."""
    if not turns and not piped:
        return question
    lines = []
    if turns:
        lines.append("Recent conversation (for context only):")
        for t in turns:
            lines.append(f"User (in {t.get('cwd', '?')}): {t['question']}")
            lines.append(f"Sage: {t['answer']}")
        lines.append("")
    if piped:
        lines += ["Output piped into sage:", "```", piped, "```", ""]
    lines.append(f"Current question: {question}")
    return "\n".join(lines)


def instrument(fn, debug: bool = False):
    """Wrap a tool to show a spinner status while it runs, and log calls to stderr if debug."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if debug:
            shown = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
            tools.pause_output()
            print(f"[sage] tool {fn.__name__}({shown})", file=sys.stderr, flush=True)
        tools.show_status(tools.STATUS.get(fn.__name__))
        start = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        finally:
            tools.show_status("thinking…")
        if debug:
            print(
                f"[sage]   -> {len(str(result))} chars in {time.perf_counter() - start:.2f}s",
                file=sys.stderr,
                flush=True,
            )
        return result

    return wrapper


def trace(fn):
    """Wrap a tool so each call is logged to stderr (for --debug)."""
    return instrument(fn, debug=True)


def build_agent(cfg: Config, shell: str, cwd: str, debug: bool = False):
    import railtracks as rt

    from sage import verifiers

    tools.CURRENT_SHELL = shell
    return rt.agent_node(
        "Sage",
        tool_nodes=[verifiers.tool_node(fn, wrap=lambda f: instrument(f, debug)) for fn in tools.ALL_TOOLS],
        llm=build_llm(cfg),
        system_message=build_system_message(shell, cwd),
    )
