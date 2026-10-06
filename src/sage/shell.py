"""Detects the invoking shell and runs commands in it."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable

DEFAULT_SHELL = "powershell"

# Process name (lowercased) -> shell id.
KNOWN_SHELLS = {
    "pwsh.exe": "pwsh",
    "pwsh": "pwsh",
    "powershell.exe": "powershell",
    "cmd.exe": "cmd",
    "bash.exe": "bash",
    "bash": "bash",
    "zsh": "bash",
    "sh.exe": "bash",
}

MAX_OUTPUT_CHARS = 4000


def _parent_process_names() -> list[str]:
    try:
        import psutil

        return [p.name() for p in psutil.Process().parents()]
    except Exception:
        return []


def detect_shell(process_names: Iterable[str] | None = None) -> str:
    """Return the nearest shell in the parent-process chain (skipping uv/python/sage)."""
    names = _parent_process_names() if process_names is None else process_names
    for name in names:
        shell = KNOWN_SHELLS.get(name.lower())
        if shell:
            return shell
    return DEFAULT_SHELL


def shell_argv(shell: str, command: str) -> list[str]:
    if shell in ("pwsh", "powershell"):
        return [shell, "-NoProfile", "-NonInteractive", "-Command", command]
    if shell == "cmd":
        return ["cmd", "/c", command]
    return ["bash", "-c", command]


def truncate(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated {len(text) - max_chars} chars]"


def run_in_shell(command: str, shell: str, timeout: int = 60) -> str:
    """Run `command` in `shell`; return exit code plus combined, truncated output."""
    try:
        proc = subprocess.run(
            shell_argv(shell, command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return f"error: shell {shell!r} not found"
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {timeout}s"
    output = (proc.stdout or "") + (proc.stderr or "")
    return f"exit code: {proc.returncode}\n{truncate(output.strip())}"
