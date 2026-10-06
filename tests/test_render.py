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


def test_plain_flag():
    assert cli.parse_args(["--plain", "hi"]).plain is True
    assert cli.parse_args(["hi"]).plain is False
