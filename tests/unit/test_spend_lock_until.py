"""The spend lock lifts itself at the time it was thrown with (#3646)."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import claude_spend_lock as csl  # noqa: E402
from assemblyzero.core import seats  # noqa: E402


def lock_file(tmp_path: Path, until: datetime | None) -> Path:
    path = tmp_path / "claude-spend.lock"
    path.write_text(csl.lock_text(until), encoding="utf-8")
    return path


def test_an_until_in_the_past_does_not_bind(tmp_path):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert not seats.spend_locked(lock_file(tmp_path, past))


def test_an_until_in_the_future_binds(tmp_path):
    future = datetime.now(timezone.utc) + timedelta(days=2)
    assert seats.spend_locked(lock_file(tmp_path, future))


def test_no_until_binds_until_lifted_by_hand(tmp_path):
    assert seats.spend_locked(lock_file(tmp_path, None))


def test_an_unreadable_until_binds(tmp_path):
    path = tmp_path / "claude-spend.lock"
    path.write_text(csl.LOCK_TEXT + "until: next tuesday-ish\n", encoding="utf-8")
    assert seats.spend_locked(path)


def test_lock_with_until_writes_it_and_status_names_it(tmp_path, capsys):
    home = tmp_path / "home"
    home.mkdir()
    (home / "settings.json").write_text(csl.render({"permissions": {"deny": []}}), encoding="utf-8")
    assert csl.main(["--lock", "--apply", "--until", "2030-01-06 13:00", "--claude-home", str(home)]) == 0
    text = (home / "claude-spend.lock").read_text(encoding="utf-8")
    assert "until: 2030-01-06T13:00:00" in text
    capsys.readouterr()
    assert csl.main(["--status", "--claude-home", str(home)]) == 0
    out = capsys.readouterr().out
    assert "lifts 2030-01-06 01:00 PM" in out and "now binding" in out
    # re-throwing with another lift time rewrites the file
    assert csl.main(["--lock", "--apply", "--until", "2030-01-13 13:00", "--claude-home", str(home)]) == 0
    assert "2030-01-13T13:00:00" in (home / "claude-spend.lock").read_text(encoding="utf-8")


def test_until_without_lock_is_a_usage_error(tmp_path):
    try:
        csl.main(["--unlock", "--until", "2030-01-06 13:00"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("--until without --lock was accepted")
