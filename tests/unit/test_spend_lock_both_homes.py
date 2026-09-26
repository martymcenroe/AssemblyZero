"""The spend lock binds on both sides of a Windows + WSL machine (#3647)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import claude_spend_lock as csl  # noqa: E402
from assemblyzero.core import seats  # noqa: E402

SETTINGS = {"permissions": {"deny": ["Read(.env)"]}}


@pytest.fixture
def two_homes(tmp_path, monkeypatch):
    """A running home and an other-side home, each with a settings.json."""
    running = tmp_path / "running"
    other = tmp_path / "other" / ".claude"
    for home in (running / ".claude", other):
        home.mkdir(parents=True)
        (home / "settings.json").write_text(csl.render(SETTINGS), encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: running))
    monkeypatch.setattr(seats, "other_side_claude_home", lambda: other)
    monkeypatch.setattr(seats, "CLAUDE_SPEND_LOCK", running / ".claude" / "claude-spend.lock")
    return running / ".claude", other


def test_claude_homes_lists_both(two_homes):
    assert seats.claude_homes() == list(two_homes)


def test_a_lock_on_the_other_side_only_binds_here(two_homes):
    _, other = two_homes
    assert not seats.spend_locked()
    (other / "claude-spend.lock").write_text("x", encoding="utf-8")
    assert seats.spend_locked()
    assert str(other) in seats.spend_lock_message("a seat")


def test_a_lock_on_the_running_side_binds(two_homes):
    running, _ = two_homes
    (running / "claude-spend.lock").write_text("x", encoding="utf-8")
    assert seats.spend_locked()


def test_no_other_side_means_the_running_home_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(seats, "other_side_claude_home", lambda: None)
    assert seats.claude_homes() == [tmp_path / ".claude"]
    monkeypatch.setattr(seats, "other_side_claude_home", lambda: tmp_path / "absent")
    assert seats.claude_homes() == [tmp_path / ".claude"]


def test_lock_and_unlock_write_both_homes(two_homes, capsys):
    running, other = two_homes
    assert csl.main(["--lock", "--apply"]) == 0
    for home in (running, other):
        assert (home / "claude-spend.lock").is_file()
        assert all(e in csl.load(home / "settings.json")[0]["permissions"]["deny"] for e in csl.DENY_ENTRIES)
    assert csl.main(["--status"]) == 0
    assert capsys.readouterr().out.count("lock file: present") == 2
    assert csl.main(["--unlock", "--apply"]) == 0
    for home in (running, other):
        assert not (home / "claude-spend.lock").exists()
        assert csl.load(home / "settings.json")[0]["permissions"]["deny"] == ["Read(.env)"]


def test_explicit_homes_are_used_as_given(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for home in (a, b):
        home.mkdir()
        (home / "settings.json").write_text(csl.render(SETTINGS), encoding="utf-8")
    assert csl.main(["--lock", "--apply", "--claude-home", str(a), "--claude-home", str(b)]) == 0
    assert (a / "claude-spend.lock").is_file() and (b / "claude-spend.lock").is_file()
