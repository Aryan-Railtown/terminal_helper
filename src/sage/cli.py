"""`sage <question>` entry point."""

from __future__ import annotations

import argparse
import asyncio
import os
import stat
import sys
import traceback
from pathlib import Path

from sage import __version__, history, tools
from sage.agent import build_agent, compose_prompt
from sage.config import (
    Config,
    ConfigError,
    api_key_var,
    check_api_key,
    load_config,
    load_env,
    resolve_model,
    sage_home,
)
from sage.render import StreamRenderer, make_renderer
from sage.shell import detect_shell

DOT_QUESTION = (
    "Give me a quick overview of the current directory: what kind of project it is, "
    "the key files, and how to build, run, and test it."
)
PIPED_QUESTION = "Explain this output. If it shows an error, say what caused it and how to fix it."
MAX_PIPED_CHARS = 8000


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sage",
        description="Ask sage, your terminal helper. Example: sage how do I find what is using port 3000",
        epilog="`sage .` explains the current directory. Pipe output in: `cmd 2>&1 | sage explain this error`.",
    )
    parser.add_argument("--new", action="store_true", help="forget the recent conversation first")
    parser.add_argument("--model", help="model for this call: alias (sonnet, opus, haiku, flash-lite), id, or provider:id")
    parser.add_argument("--debug", action="store_true", help="show tool calls, tracebacks and keep railtracks logs; alone, print diagnostics")
    parser.add_argument("--tools", action="store_true", help="list the tools sage can use and exit")
    parser.add_argument("--plain", action="store_true", help="print raw text instead of rendered markdown")
    parser.add_argument("--version", action="version", version=f"sage {__version__}")
    parser.add_argument("question", nargs=argparse.REMAINDER, help="your question (quotes optional)")
    args = parser.parse_args(argv)
    args.question = " ".join(args.question).strip()
    if args.question == ".":
        args.question = DOT_QUESTION
    args.print_usage = parser.print_usage
    return args


def prepare_env(home: Path) -> None:
    """Must run before railtracks is imported: keep its run data out of the user's cwd."""
    os.environ["RAILTRACKS_HOME"] = str(home)
    if not os.environ.get("SAGE_DEBUG"):
        os.environ.setdefault("RAILTRACKS_DISABLE_EVENTS", "True")


def read_piped_input(stream=None, limit: int = MAX_PIPED_CHARS) -> str:
    """Return text piped/redirected into sage (tail-truncated), or "" for a console or nothing."""
    stream = sys.stdin if stream is None else stream
    try:
        if stream is None or stream.isatty():
            return ""
        mode = os.fstat(stream.fileno()).st_mode
        if not (stat.S_ISFIFO(mode) or stat.S_ISREG(mode)):
            return ""
        data = stream.read().strip()
    except (OSError, ValueError, AttributeError):
        return ""
    if len(data) > limit:
        data = f"[... earlier output truncated ({len(data) - limit} chars)]\n" + data[-limit:]
    return data


def print_tools() -> None:
    print("Tools sage can use:")
    for fn in tools.ALL_TOOLS:
        summary = (fn.__doc__ or "").strip().splitlines()[0]
        flag = "  (asks first)" if fn.__name__ in tools.GATED else ""
        print(f"  {fn.__name__:<16} {summary}{flag}")


def print_diagnostics(cfg: Config, home: Path) -> None:
    var = api_key_var(cfg)
    key = "not needed" if var is None else f"{var} {'set' if os.environ.get(var) else 'not set'}"
    turns = history.load_turns(cfg.history_path, cfg.history_ttl_minutes)

    def found(name: str) -> str:
        return "found" if (home / name).exists() else "missing"

    print(f"sage {__version__}")
    print(f"home:     {home}  (config.toml: {found('config.toml')}, .env: {found('.env')})")
    print(f"model:    {cfg.provider}/{cfg.model}")
    print(f"api key:  {key}")
    print(f"shell:    {detect_shell()}")
    print(f"cwd:      {os.getcwd()}")
    print(f"history:  {len(turns)} recent turn(s) in {cfg.history_path}")
    print(f"logs:     {home / '.railtracks'} (written with --debug)")


def build_flow(agent, renderer: StreamRenderer):
    """Flow whose entry node streams the agent's answer into `renderer` (railtracks' nested streaming pattern)."""
    import railtracks as rt

    async def sage_answer(prompt: str) -> str:
        """Stream sage's answer to the terminal and return the final text."""
        stream = rt.astream(agent, user_input=prompt)
        async for chunk in stream:
            await renderer.afeed(chunk)
        renderer.finish()
        result = stream.result
        # .result is authoritative; fall back to the streamed text if it has none.
        return getattr(result, "text", None) or renderer.text

    return rt.Flow(name="sage", entry_point=rt.function_node(sage_answer))


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")
        except AttributeError:
            pass

    args = parse_args(sys.argv[1:] if argv is None else argv)
    home = sage_home()
    if args.debug:
        os.environ["SAGE_DEBUG"] = "1"
    debug = bool(os.environ.get("SAGE_DEBUG"))

    if args.tools:
        print_tools()
        return 0
    if args.new:
        history.clear(home / "history.json")
        if not args.question:
            print("sage: conversation cleared.")
            return 0

    try:
        cfg = load_config(home)
        if args.model:
            cfg.provider, cfg.model = resolve_model(args.model, cfg.provider)
        load_env(home)
    except ConfigError as e:
        print(f"sage: {e}", file=sys.stderr)
        return 2

    piped = ""
    if not args.question:
        piped = read_piped_input()
        if piped:
            args.question = PIPED_QUESTION
        elif args.debug or args.model:
            print_diagnostics(cfg, home)
            return 0
        else:
            args.print_usage(sys.stdout)
            return 2

    try:
        check_api_key(cfg)
    except ConfigError as e:
        print(f"sage: {e}", file=sys.stderr)
        return 2

    prepare_env(home)
    piped = piped or read_piped_input()
    shell = detect_shell()
    cwd = os.getcwd()
    turns = history.load_turns(cfg.history_path, cfg.history_ttl_minutes)
    prompt = compose_prompt(args.question, turns, piped=piped)
    if debug:
        print(
            f"[sage] {cfg.provider}/{cfg.model} | shell {shell} | {len(turns)} history turn(s)"
            f" | piped {len(piped)} chars | logs {home / '.railtracks'}",
            file=sys.stderr,
        )

    renderer = make_renderer(plain=args.plain)
    tools.pause_output = renderer.pause
    tools.show_status = renderer.status
    renderer.status("thinking…")
    try:
        agent = build_agent(cfg, shell, cwd, debug=debug)
        result = asyncio.run(build_flow(agent, renderer).ainvoke(prompt))
        answer = result if isinstance(result, str) else renderer.text
    except KeyboardInterrupt:
        renderer.pause()
        print("\nsage: interrupted.", file=sys.stderr)
        return 130
    except Exception as e:
        renderer.pause()
        if debug:
            traceback.print_exc()
        print(f"\nsage: error talking to {cfg.provider}/{cfg.model}: {e}", file=sys.stderr)
        return 1

    history.save_turn(cfg.history_path, args.question, answer, cwd, cfg.history_turns)
    return 0


if __name__ == "__main__":
    sys.exit(main())
