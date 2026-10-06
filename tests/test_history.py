from datetime import datetime, timedelta

from sage import history


def test_round_trip_and_rolling_truncation(tmp_path):
    path = tmp_path / "history.json"
    now = datetime(2026, 10, 6, 12, 0)
    for i in range(10):
        history.save_turn(path, f"q{i}", f"a{i}", "C:\\", max_turns=3, now=now)
    turns = history.load_turns(path, ttl_minutes=30, now=now)
    assert [t["question"] for t in turns] == ["q7", "q8", "q9"]


def test_expired_turns_dropped(tmp_path):
    path = tmp_path / "history.json"
    old = datetime(2026, 10, 6, 12, 0)
    history.save_turn(path, "old", "a", "C:\\", max_turns=6, now=old)
    history.save_turn(path, "new", "a", "C:\\", max_turns=6, now=old + timedelta(minutes=40))
    turns = history.load_turns(path, ttl_minutes=30, now=old + timedelta(minutes=45))
    assert [t["question"] for t in turns] == ["new"]


def test_clear(tmp_path):
    path = tmp_path / "history.json"
    history.save_turn(path, "q", "a", "C:\\", max_turns=6)
    history.clear(path)
    assert history.load_turns(path, ttl_minutes=30) == []


def test_missing_or_corrupt_file(tmp_path):
    path = tmp_path / "history.json"
    assert history.load_turns(path, ttl_minutes=30) == []
    path.write_text("{not json")
    assert history.load_turns(path, ttl_minutes=30) == []
