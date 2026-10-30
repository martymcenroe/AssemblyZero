"""state_persistence.py under standard 0034 (#3797).

A snapshot that exists and cannot be read raises, naming it; it used to read
as "no snapshot". An absent one is still None. The other site, a value JSON
cannot hold being written as its ``str()``, is a won't-do: HALT writes the
snapshot before it alerts, so a raise there would cost the halt its recovery
plan and its alert, and nothing reads the snapshot back as state. Line
numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from assemblyzero.core import state_persistence as sp


@pytest.fixture
def state_dir(tmp_path, monkeypatch) -> Path:
    directory = tmp_path / "workflow_state"
    monkeypatch.setattr(sp, "STATE_DIR", directory)
    return directory


class TestLoadingASnapshot:
    def test_77_a_corrupt_snapshot_raises(self, state_dir):
        state_dir.mkdir()
        path = state_dir / "requirements-42.json"
        path.write_text("NOT VALID JSON {{{", encoding="utf-8")

        with pytest.raises(RuntimeError, match="cannot read the state snapshot") as raised:
            sp.load_state_snapshot("requirements", 42)
        assert str(path) in str(raised.value)
        assert "JSONDecodeError" in str(raised.value)

    def test_77_an_unreadable_snapshot_raises(self, state_dir):
        (state_dir / "requirements-42.json").mkdir(parents=True)

        with pytest.raises(RuntimeError, match="IsADirectoryError"):
            sp.load_state_snapshot("requirements", 42)

    def test_an_absent_snapshot_is_none(self, state_dir):
        """Kept: no snapshot was written, which is an answer."""
        assert sp.load_state_snapshot("requirements", 999) is None


class TestSavingASnapshot:
    def test_42_wont_do_a_value_json_cannot_hold_is_written_as_text(self, state_dir):
        """Won't do (#3797): the snapshot is HALT's record and is written
        before HALT alerts. A raise here would cost the halt its recovery plan
        and its alert; and nothing reads the snapshot back as state."""
        path = sp.save_state_snapshot(
            "testing", 7, {"worktree": Path("/work/tree"), "n": 1}, trigger="halt",
        )

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["worktree"] == str(Path("/work/tree"))
        assert payload["n"] == 1

    def test_42_the_reason_is_in_the_docstring(self):
        assert "#3797" in inspect.getdoc(sp.save_state_snapshot)
