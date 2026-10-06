"""Renders streamed answer chunks: live markdown in a terminal, raw text otherwise."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

CODE_THEME = "monokai"


class StreamRenderer:
    """Feed it str chunks; it redraws them as markdown as they arrive.

    Call `pause()` before anything else writes to the terminal mid-stream (the y/N prompt,
    --debug tool traces): it freezes the current block, and later chunks start a new one.
    """

    def __init__(self, console: Console | None = None, markdown: bool | None = None):
        self.console = console or Console()
        self.markdown = self.console.is_terminal if markdown is None else markdown
        self._chunks: list[str] = []
        self._block = ""
        self._live: Live | None = None
        self._at_line_start = True

    @property
    def text(self) -> str:
        return "".join(self._chunks)

    def feed(self, chunk: str) -> None:
        if not chunk:
            return
        self._chunks.append(chunk)
        if not self.markdown:
            self.console.file.write(chunk)
            self.console.file.flush()
            self._at_line_start = chunk.endswith("\n")
            return
        self._block += chunk
        view = Markdown(self._block, code_theme=CODE_THEME)
        if self._live is None:
            self._live = Live(
                view,
                console=self.console,
                refresh_per_second=12,
                vertical_overflow="visible",
                redirect_stdout=False,
                redirect_stderr=False,
            )
            self._live.start()
        else:
            self._live.update(view)

    def pause(self) -> None:
        if self._live is not None:
            self._live.update(Markdown(self._block, code_theme=CODE_THEME), refresh=True)
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
