"""Detects the invoking shell and runs commands in it."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterable

# Shell ids sage knows how to run commands in and read history for.
SHELLS = ("pwsh", "powershell", "cmd", "bash", "zsh", "fish", "sh")

# Normalised process name (lowercase, no .exe, no login-shell dash) -> shell id.
_PROCESS_SHELLS = {
    "pwsh": "pwsh",
    "powershell": "powershell",
    "cmd": "cmd",
    "bash": "bash",
    "zsh": "zsh",
    "fish": "fish",
    "sh": "sh",
    "dash": "sh",
}

MAX_OUTPUT_CHARS = 4000


def default_shell() -> str:
    """Shell to assume when none is found among the parent processes."""
    if sys.platform == "win32":
        return "powershell"  # $SHELL is unreliable on Windows (often set by Git Bash)
    from_env = shell_for_process(os.path.basename(os.environ.get("SHELL", "")))
    if from_env:
        return from_env
    return "zsh" if sys.platform == "darwin" else "bash"


# Kept for callers that need a static default before detection runs.
DEFAULT_SHELL = "powershell" if sys.platform == "win32" else ("zsh" if sys.platform == "darwin" else "bash")


def shell_for_process(name: str) -> str | None:
    """Map a process name like 'pwsh.exe', '-zsh' or 'ZSH' to a shell id (None if not a shell)."""
    name = name.strip().lower().lstrip("-")
    if name.endswith(".exe"):
        name = name[:-4]
    return _PROCESS_SHELLS.get(name)


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
        shell = shell_for_process(name)
        if shell:
            return shell
    return default_shell()


def shell_argv(shell: str, command: str) -> list[str]:
    if shell in ("pwsh", "powershell"):
        return [shell, "-NoProfile", "-NonInteractive", "-Command", command]
    if shell == "cmd":
        return ["cmd", "/c", command]
    if shell in ("zsh", "fish", "sh"):
        return [shell, "-c", command]
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
