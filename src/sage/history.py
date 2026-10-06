"""Short rolling Q&A history so follow-up questions have context."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


def load_turns(path: Path, ttl_minutes: int, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    try:
        turns = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(turns, list):
        return []
    cutoff = now - timedelta(minutes=ttl_minutes)
    fresh = []
    for t in turns:
        try:
            if datetime.fromisoformat(t["ts"]) >= cutoff:
                fresh.append(t)
        except (KeyError, TypeError, ValueError):
            continue
    return fresh


def save_turn(
    path: Path, question: str, answer: str, cwd: str, max_turns: int, now: datetime | None = None
) -> None:
    now = now or datetime.now()
    path = Path(path)
    try:
        turns = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(turns, list):
            turns = []
    except (OSError, ValueError):
        turns = []
    turns.append({"question": question, "answer": answer, "cwd": cwd, "ts": now.isoformat()})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(turns[-max_turns:], indent=2), encoding="utf-8")


def clear(path: Path) -> None:
    Path(path).unlink(missing_ok=True)
