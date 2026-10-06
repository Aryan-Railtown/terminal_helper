"""Renders streamed answer chunks: live markdown in a terminal, raw text otherwise."""

from __future__ import annotations

import asyncio
import re
import sys

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.text import Text

CODE_THEME = "monokai"
# Typewriter pacing: providers send big chunks (Gemini ~130 chars), which looks like the
# answer "pops in". Reveal each chunk word by word, at most MAX_CHUNK_SECONDS per chunk.
CHARS_PER_SECOND = 900
MAX_CHUNK_SECONDS = 0.15
MIN_STEP_SECONDS = 1 / 40

_PIECES = re.compile(r"\s*\S+\s*|\s+")


class StreamRenderer:
    """Feed it str chunks; it redraws them as markdown as they arrive.

    `status(label)` shows a spinner line (e.g. "checking git…") until the next chunk.
    Call `pause()` before anything else writes to the terminal mid-stream (the y/N prompt,
    --debug tool traces): it freezes the current block, and later chunks start a new one.
    """

    def __init__(
        self,
        console: Console | None = None,
        markdown: bool | None = None,
        chars_per_second: float = CHARS_PER_SECOND,
    ):
        self.console = console or Console()
        self.markdown = self.console.is_terminal if markdown is None else markdown
        self.chars_per_second = chars_per_second
        self._chunks: list[str] = []
        self._block = ""
        self._status: str | None = None
        self._live: Live | None = None
        self._at_line_start = True

    @property
    def text(self) -> str:
        return "".join(self._chunks)

    def _renderable(self):
        parts = []
        if self._block:
            parts.append(Markdown(self._block, code_theme=CODE_THEME))
        if self._status:
            parts.append(Spinner("dots", Text(self._status, style="dim"), style="cyan"))
        return Group(*parts)

    def _show(self) -> None:
        if self._live is None:
            self._live = Live(
                self._renderable(),
                console=self.console,
                refresh_per_second=30,
                vertical_overflow="visible",
                redirect_stdout=False,
                redirect_stderr=False,
            )
            self._live.start()
        else:
            self._live.update(self._renderable())

    def status(self, label: str | None) -> None:
        """Show (or with None, clear) a spinner line under the answer."""
        if not self.markdown or label == self._status:
            return
        self._status = label
        if label or self._live is not None:
            self._show()
            self._live.refresh()

    def feed(self, chunk: str) -> None:
        if not chunk:
            return
        self._chunks.append(chunk)
        if not self.markdown:
            self.console.file.write(chunk)
            self.console.file.flush()
            self._at_line_start = chunk.endswith("\n")
            return
        self._status = None
        self._block += chunk
        self._show()

    async def afeed(self, chunk: str) -> None:
        """Like feed(), but reveals a large chunk word by word (terminal only)."""
        if not self.markdown or self.chars_per_second <= 0 or len(chunk) < 8:
            self.feed(chunk)
            return
        pieces = _PIECES.findall(chunk)
        total = min(len(chunk) / self.chars_per_second, MAX_CHUNK_SECONDS)
        steps = max(1, min(len(pieces), int(total / MIN_STEP_SECONDS)))
        per_step = -(-len(pieces) // steps)  # ceil
        for i in range(0, len(pieces), per_step):
            self.feed("".join(pieces[i : i + per_step]))
            if i + per_step < len(pieces):
                await asyncio.sleep(total / steps)

    def pause(self) -> None:
        if self._live is not None:
            self._status = None
            self._live.update(self._renderable(), refresh=True)
            self._live.stop()
            self._live = None
            self._block = ""
        elif not self.markdown and not self._at_line_start:
            self.console.file.write("\n")
            self._at_line_start = True

    def finish(self) -> None:
        self.pause()


def make_renderer(plain: bool = False) -> StreamRenderer:
    return StreamRenderer(markdown=False if plain or not sys.stdout.isatty() else None)
