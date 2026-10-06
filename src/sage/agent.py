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
- Only use run_command when actually running something is needed to answer. Prefer giving the command as advice. Never run commands that change or delete things unless the user clearly asked you to do that.
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


def trace(fn):
    """Wrap a tool so each call is logged to stderr (for --debug)."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        shown = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
        tools.pause_output()
        print(f"[sage] tool {fn.__name__}({shown})", file=sys.stderr, flush=True)
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        print(
            f"[sage]   -> {len(str(result))} chars in {time.perf_counter() - start:.2f}s",
            file=sys.stderr,
            flush=True,
        )
        return result

    return wrapper


def build_agent(cfg: Config, shell: str, cwd: str, debug: bool = False):
    import railtracks as rt

    tools.CURRENT_SHELL = shell
    fns = [trace(fn) for fn in tools.ALL_TOOLS] if debug else tools.ALL_TOOLS
    return rt.agent_node(
        "Sage",
        tool_nodes=[rt.function_node(fn) for fn in fns],
        llm=build_llm(cfg),
        system_message=build_system_message(shell, cwd),
    )
