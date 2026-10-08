"""Tools sage can use. Plain functions; agent.py wraps them with rt.function_node.

Read-only tools run freely. `run_command` always asks the user first.
"""

from __future__ import annotations

import getpass
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from sage.shell import DEFAULT_SHELL, run_in_shell, truncate

# Set by the CLI to the shell sage was invoked from.
CURRENT_SHELL = DEFAULT_SHELL


def _noop(*args) -> None:
    pass


# Set by the CLI: freezes the live answer display before something else writes to the terminal.
pause_output = _noop
# Set by the CLI: shows a spinner status line, e.g. "checking git…" (None clears it).
show_status = _noop

# Spinner text while each tool runs (run_command has its own prompt instead).
STATUS = {
    "get_environment": "checking your environment…",
    "list_directory": "looking at files…",
    "read_file": "reading file…",
    "which": "checking what's installed…",
    "command_help": "reading the help…",
    "recent_commands": "reading shell history…",
    "git_overview": "checking git…",
}

DECLINED = "User declined to run the command. Do not retry it; give the command as advice instead."

# Safety net, not a security boundary: refused even if the user says yes.
_DENY_PATTERNS = [
    r"\bformat(\.com)?\s+[a-z]:",
    r"\brm\s+(-\w*\s+)*-\w*r\w*\s+(-\w+\s+)*/(\s|$|\*)",
    r"\bremove-item\b.*-recurse\b.*\b[a-z]:\\?\s*$",
    r"\b(rd|rmdir)\s+/s\b.*\b[a-z]:\\?\s*$",
    r"\bdiskpart\b",
    r"\breg(\.exe)?\s+delete\b",
    r"\bshutdown\b",
    r"\bstop-computer\b",
    r"\brestart-computer\b",
    r"\bformat-volume\b",
    r"\bclear-disk\b",
    r"\bbcdedit\b",
    r"\bcipher\s+/w\b",
    r"\bmkfs(\.\w+)?\b",
    r"\bdd\s+.*\bof=/dev/",
    # macOS
    r"\bdiskutil\s+(erase\w*|zero\w*|reformat|secureerase|partitiondisk)\b",
    r"\bcsrutil\b",
    r"\brm\s+(-\w+\s+)*(~|\$home|\$\{home\})/?(\s|$)",
]
_DENY_RE = [re.compile(p, re.IGNORECASE) for p in _DENY_PATTERNS]


def is_denied(command: str) -> bool:
    return any(r.search(command) for r in _DENY_RE)


def _console_reader():
    """Return a readline for the interactive console, or None if there isn't one.

    Reads the console directly when stdin is piped (`cmd 2>&1 | sage explain`).
    """
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            return sys.stdin.readline
    except (AttributeError, ValueError):
        pass
    try:
        console = open("CONIN$" if sys.platform == "win32" else "/dev/tty", encoding="utf-8")
    except OSError:
        return None
    return console.readline


def confirm(command: str, reason: str) -> bool:
    """Show the command and ask the user y/N on the console. No console -> no."""
    reader = _console_reader()
    if reader is None:
        return False
    from rich.console import Console
    from rich.markup import escape
    from rich.panel import Panel

    pause_output()
    console = Console(stderr=True)
    console.print(
        Panel(
            f"[bold]{escape(command)}[/bold]\n[dim]{escape(reason)}[/dim]",
            title=f"sage wants to run ({CURRENT_SHELL})",
            border_style="yellow",
        )
    )
    console.print("Run this? [y/N] ", end="", markup=False)
    try:
        answer = reader()
    except (EOFError, KeyboardInterrupt, OSError):
        return False
    return answer.strip().lower() in ("y", "yes")


_SECRET_RES = [
    re.compile(
        r"(?i)((?:api[_-]?key|token|secret|password|passwd|pwd)\w*['\"]?\s*[:=]\s*)(['\"]?)[^\s'\"]+"
    ),
    re.compile(r"\b(sk-[\w-]{8,}|AIza[\w-]{20,}|gh[pousr]_\w{20,}|xox[bpas]-[\w-]+)"),
]


def redact(text: str) -> str:
    text = _SECRET_RES[0].sub(r"\1\2<redacted>", text)
    return _SECRET_RES[1].sub("<redacted>", text)


def history_file() -> Path | None:
    """The current shell's saved command history file, if it has one."""
    home = Path.home()
    if CURRENT_SHELL in ("pwsh", "powershell"):
        appdata = os.environ.get("APPDATA")
        if appdata:  # Windows
            folder = Path(appdata) / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine"
        else:  # pwsh on macOS/Linux
            folder = home / ".local" / "share" / "powershell" / "PSReadLine"
        files = sorted(folder.glob("*_history.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
        return files[0] if files else None
    if CURRENT_SHELL in ("bash", "zsh", "sh"):
        histfile = os.environ.get("HISTFILE")
        default = ".zsh_history" if CURRENT_SHELL == "zsh" else ".bash_history"
        f = Path(histfile) if histfile else home / default
        return f if f.exists() else None
    if CURRENT_SHELL == "fish":
        f = home / ".local" / "share" / "fish" / "fish_history"
        return f if f.exists() else None
    return None  # cmd.exe keeps no history on disk


_ZSH_EXTENDED = re.compile(r"^: \d+:\d+;")


def parse_history(shell: str, text: str) -> list[str]:
    """Turn a shell history file's text into a list of commands, oldest first."""
    if shell == "fish":
        # fish_history is YAML-ish: "- cmd: <command>" followed by indented metadata.
        return [ln[len("- cmd: "):].strip() for ln in text.splitlines() if ln.startswith("- cmd: ")]
    commands: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = _ZSH_EXTENDED.sub("", raw) if shell == "zsh" else raw
        if shell == "zsh" and line.endswith("\\"):  # zsh stores multi-line commands with trailing backslashes
            pending += line[:-1] + "\n"
            continue
        line = (pending + line).strip()
        pending = ""
        if line:
            commands.append(line)
    return commands


def get_environment() -> str:
    """Get facts about the user's terminal environment: OS, shell, current directory, user, and PATH entries.

    Returns:
        A multi-line summary of the environment.
    """
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    return "\n".join(
        [
            f"os: {platform.system()} {platform.release()} ({platform.version()})",
            f"shell: {CURRENT_SHELL}",
            f"cwd: {os.getcwd()}",
            f"user: {getpass.getuser()}",
            "PATH:",
            *(f"  {p}" for p in path_entries if p),
        ]
    )


def list_directory(path: str = ".", pattern: str = "*", limit: int = 200) -> str:
    """List files and folders in a directory (non-recursive), with sizes.

    Args:
        path: Directory to list; relative paths resolve from the user's current directory.
        pattern: Glob pattern to filter names, e.g. "*.py".
        limit: Maximum number of entries to return.

    Returns:
        One entry per line ("<dir>" or size in bytes, then name), or an error message.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return f"error: {p} does not exist"
    if not p.is_dir():
        return f"error: {p} is not a directory"
    entries = sorted(p.glob(pattern), key=lambda e: (not e.is_dir(), e.name.lower()))
    lines = []
    for e in entries[:limit]:
        try:
            size = "<dir>" if e.is_dir() else str(e.stat().st_size)
        except OSError:
            size = "?"
        lines.append(f"{size:>12}  {e.name}")
    if len(entries) > limit:
        lines.append(f"... and {len(entries) - limit} more")
    return f"{p.resolve()}\n" + ("\n".join(lines) if lines else "(empty)")


def read_file(path: str, max_lines: int = 200) -> str:
    """Read the first lines of a text file.

    Args:
        path: File to read; relative paths resolve from the user's current directory.
        max_lines: Maximum number of lines to return.

    Returns:
        The file contents (possibly truncated), or an error message.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return f"error: {p} does not exist"
    if not p.is_file():
        return f"error: {p} is not a file"
    try:
        with p.open("rb") as f:
            head = f.read(8192)
        if b"\x00" in head:
            return f"error: {p} looks like a binary file"
        with p.open(encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"... [truncated after {max_lines} lines]")
                    break
                lines.append(line.rstrip("\n"))
    except OSError as e:
        return f"error: {e}"
    return truncate("\n".join(lines), 20000)


def which(command: str) -> str:
    """Check whether a command/program is installed and on PATH.

    Args:
        command: Program name, e.g. "git" or "node".

    Returns:
        Where it is installed, or that it was not found.
    """
    found = shutil.which(command)
    return f"{command} is installed at {found}" if found else f"{command}: not found on PATH"


def command_help(command: str) -> str:
    """Show the built-in help text for a command (Get-Help in PowerShell, `/?` in cmd, `--help` or the man page otherwise). Read-only.

    Args:
        command: The command name only, e.g. "Get-ChildItem", "robocopy", "git".

    Returns:
        The help text (truncated), or an error message.
    """
    if not re.fullmatch(r"[\w.\-]+", command):
        return "error: pass a bare command name only"
    if CURRENT_SHELL in ("pwsh", "powershell"):
        cmd = (
            f"if (Get-Command '{command}' -CommandType Cmdlet,Function,Alias -ErrorAction SilentlyContinue) "
            f"{{ Get-Help '{command}' | Out-String -Width 120 }} else {{ & '{command}' --help }}"
        )
    elif CURRENT_SHELL == "cmd":
        cmd = f"{command} /?"
    else:
        # Many macOS/BSD tools don't support --help; fall back to the man page.
        out = run_in_shell(f"{command} --help", CURRENT_SHELL, timeout=20)
        body = out.split("\n", 1)[1].strip() if "\n" in out else ""
        if out.startswith("exit code: 0") and body:
            return out
        return run_in_shell(f"man {command} 2>/dev/null | col -b", CURRENT_SHELL, timeout=20)
    return run_in_shell(cmd, CURRENT_SHELL, timeout=20)


def recent_commands(count: int = 10) -> str:
    """Get the user's most recent shell commands (from their shell history), oldest first.
    Use this for questions like "what did I just break?" or "explain this error" when no error text was given.
    Only commands are available, not their output.

    Args:
        count: How many recent commands to return.

    Returns:
        The recent commands with obvious secrets redacted, or a note that no history is available.
    """
    f = history_file()
    if f is None:
        return f"No shell history is available for {CURRENT_SHELL}. Ask the user to paste the command or error."
    try:
        with f.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 65536))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError as e:
        return f"error reading shell history: {e}"
    lines = parse_history(CURRENT_SHELL, tail)
    lines = [ln for ln in lines if ln != "sage" and not ln.startswith("sage ")]
    recent = lines[-count:]
    if not recent:
        return "Shell history is empty."
    return f"Recent {CURRENT_SHELL} commands (oldest first):\n" + "\n".join(redact(ln) for ln in recent)


def git_overview(path: str = ".") -> str:
    """Get a read-only summary of a git repo: branch, ahead/behind, changed files, recent commits.
    Use for git questions and "what did I just break?".

    Args:
        path: A directory inside the repository; defaults to the user's current directory.

    Returns:
        The repository summary, or a message if it is not a git repository.
    """
    p = Path(path).expanduser()

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(p), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            stdin=subprocess.DEVNULL,
        )

    try:
        top = git("rev-parse", "--show-toplevel")
    except FileNotFoundError:
        return "git is not installed"
    except subprocess.TimeoutExpired:
        return "error: git timed out"
    if top.returncode != 0:
        return f"{p.resolve()} is not a git repository"
    sections = [f"repository: {top.stdout.strip()}"]
    for title, args in (
        ("status", ("status", "--short", "--branch")),
        ("diff stat (unstaged)", ("diff", "--stat")),
        ("diff stat (staged)", ("diff", "--cached", "--stat")),
        ("recent commits", ("log", "--oneline", "--decorate", "-n", "5")),
    ):
        try:
            r = git(*args)
            body = (r.stdout or r.stderr).strip() or "(none)"
        except subprocess.TimeoutExpired:
            body = "(timed out)"
        sections.append(f"## {title}\n{body}")
    return truncate("\n\n".join(sections), 6000)


def run_command(command: str, reason: str) -> str:
    """Run a shell command on the user's machine. The user is shown the command and must approve it first.
    Only use this when actually running something is needed to answer; prefer read-only tools.

    Args:
        command: The exact command line to run, in the user's shell syntax.
        reason: One short sentence telling the user why you want to run it.

    Returns:
        The exit code and output. If the user declines, the call fails with that reason instead.
    """
    # Approval happens in the `user_approval` pre_verifier (sage/verifiers.py) before this
    # body runs. The denylist check here is defence in depth in case the node is built without it.
    if is_denied(command):
        return "Refused: this command is on sage's denylist of destructive commands. Do not run it; explain instead."
    return run_in_shell(command, CURRENT_SHELL)


ALL_TOOLS = [
    get_environment,
    list_directory,
    read_file,
    which,
    command_help,
    recent_commands,
    git_overview,
    run_command,
]

# Tools gated by a railtracks pre_verifier that asks the user (see sage/verifiers.py).
GATED = {"run_command"}
