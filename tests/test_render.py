import io

from rich.console import Console

from sage import cli
from sage.render import StreamRenderer


def make(markdown: bool):
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=markdown, width=80, color_system=None)
    return StreamRenderer(console=console, markdown=markdown), buf


def test_markdown_mode_renders_code_block_without_fences():
    r, buf = make(markdown=True)
    for chunk in ["Run:\n\n```powershell\n", "Get-NetTCPConnection", " -LocalPort 8080\n```\n"]:
        r.feed(chunk)
    r.finish()
    out = buf.getvalue()
    assert "Get-NetTCPConnection -LocalPort 8080" in out
    assert "```" not in out
    assert r.text == "Run:\n\n```powershell\nGet-NetTCPConnection -LocalPort 8080\n```\n"


def test_plain_mode_streams_raw_and_ends_with_newline():
    r, buf = make(markdown=False)
    r.feed("**hi**")
    r.feed(" there")
    r.finish()
    assert buf.getvalue() == "**hi** there\n"


def test_pause_splits_blocks_and_keeps_full_text():
    r, buf = make(markdown=True)
    r.feed("Let me check.")
    r.pause()
    r.pause()  # idempotent
    r.feed("It is installed.")
    r.finish()
    out = buf.getvalue()
    assert "Let me check." in out and "It is installed." in out
    assert r.text == "Let me check.It is installed."


def test_finish_without_chunks_prints_nothing():
    r, buf = make(markdown=True)
    r.finish()
    assert buf.getvalue() == ""


def test_afeed_smooths_but_keeps_exact_text():
    import asyncio

    r, buf = make(markdown=True)
    chunk = "Rebasing replays your commits on top of another branch, " * 3

    async def run():
        await r.afeed(chunk)
        await r.afeed("```bash\ngit rebase main\n```\n")

    asyncio.run(run())
    r.finish()
    assert r.text == chunk + "```bash\ngit rebase main\n```\n"
    assert len(r._chunks) > 2  # revealed in several steps, not one
    assert "git rebase main" in buf.getvalue()


def test_afeed_plain_mode_is_unpaced():
    import asyncio

    r, buf = make(markdown=False)
    asyncio.run(r.afeed("hello world " * 20))
    assert r._chunks == ["hello world " * 20]


def test_status_spinner_then_answer():
    r, buf = make(markdown=True)
    r.status("checking git…")
    r.feed("All clean.")
    r.finish()
    out = buf.getvalue()
    assert "checking git" in out and "All clean." in out


def test_status_is_noop_in_plain_mode():
    r, buf = make(markdown=False)
    r.status("thinking…")
    r.finish()
    assert buf.getvalue() == ""


def test_instrument_reports_status(monkeypatch):
    from sage import agent, tools

    seen = []
    monkeypatch.setattr(tools, "show_status", seen.append)
    agent.instrument(tools.which)("python")
    assert seen == [tools.STATUS["which"], "thinking…"]


def test_plain_flag():
    assert cli.parse_args(["--plain", "hi"]).plain is True
    assert cli.parse_args(["hi"]).plain is False
