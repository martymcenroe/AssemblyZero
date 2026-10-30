"""capacity.py under standard 0034, one test per sweep site (#3773).

The capacity gate decides whether a run may start. A state file it cannot
read, or a record it cannot make sense of, used to read as "available", and a
write that failed was dropped, so the next run started blind. Each now raises,
naming the file and the cause. Gemini, which this machine does not track, is
reported as not checked rather than as available, and an unknown provider
raises. Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from assemblyzero.core import capacity

NOW = datetime(2026, 7, 29, 17, 0, tzinfo=UTC)


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "provider-capacity.json"


def _write(path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


class TestTheStateFileIsRead:
    def test_74_a_state_file_that_is_not_an_object_raises(self, state_file):
        _write(state_file, ["claude"])

        with pytest.raises(RuntimeError, match="not a JSON object") as raised:
            capacity.check_capacity(["claude"], state_file=state_file, now=NOW)
        assert str(state_file) in str(raised.value)

    def test_75_a_corrupt_state_file_raises(self, state_file):
        state_file.write_text("{ not json", encoding="utf-8")

        with pytest.raises(RuntimeError, match="cannot read the capacity state") as raised:
            capacity.check_capacity(["claude"], state_file=state_file, now=NOW)
        assert "JSONDecodeError" in str(raised.value)
        assert str(state_file) in str(raised.value)

    def test_75_an_unreadable_state_file_raises(self, state_file):
        state_file.mkdir()  # exists, and open() fails on it

        with pytest.raises(RuntimeError, match="cannot read the capacity state") as raised:
            capacity.check_capacity(["claude"], state_file=state_file, now=NOW)
        assert "IsADirectoryError" in str(raised.value)

    def test_a_missing_state_file_is_no_record_and_quiet(self, tmp_path):
        """Kept: no file means nothing was ever recorded, which is an answer."""
        status = capacity.check_capacity(
            ["claude"], state_file=tmp_path / "never-written.json", now=NOW
        )["claude"]
        assert status.available is True


class TestTheStateFileIsWritten:
    def test_89_an_unwritable_state_file_raises(self, tmp_path):
        blocker = tmp_path / "blocker"
        blocker.write_text("a file where the directory should be", encoding="utf-8")
        target = blocker / "provider-capacity.json"

        with pytest.raises(RuntimeError, match="cannot write the capacity state") as raised:
            capacity.record_exhaustion("claude", "usage limit", state_file=target, now=NOW)
        assert str(target) in str(raised.value)

    def test_89_the_raise_is_not_read_as_a_transport_failure(self, tmp_path):
        """ClaudeCLIProvider.invoke turns an OSError into a failed call
        ("claude -p could not be run"); a broken state file is not that."""
        blocker = tmp_path / "blocker"
        blocker.write_text("x", encoding="utf-8")

        with pytest.raises(RuntimeError) as raised:
            capacity.record_exhaustion(
                "claude", "usage limit", state_file=blocker / "c.json", now=NOW
            )
        assert not isinstance(raised.value, OSError)
        assert isinstance(raised.value.__cause__, OSError)


class TestTheClaudeRecord:
    def test_212_an_unparseable_stored_time_raises(self, state_file):
        _write(state_file, {"claude": {
            "exhausted_at": "yesterday", "resets_at": None, "source_message": "limit",
        }})

        with pytest.raises(RuntimeError, match="exhausted_at") as raised:
            capacity.check_capacity(["claude"], state_file=state_file, now=NOW)
        assert "'yesterday'" in str(raised.value)
        assert str(state_file) in str(raised.value)

    def test_223_a_record_with_no_time_at_all_raises(self, state_file):
        _write(state_file, {"claude": {"source_message": "limit"}})

        with pytest.raises(RuntimeError, match="no exhaustion time") as raised:
            capacity.check_capacity(["claude"], state_file=state_file, now=NOW)
        assert str(state_file) in str(raised.value)

    def test_a_record_without_a_reset_time_binds_for_the_cooldown(self, state_file):
        """Kept: an unparsed reset time is stored as null by design, and the
        record expires on its own after UNKNOWN_RESET_COOLDOWN."""
        capacity.record_exhaustion("claude", "no time here", state_file=state_file, now=NOW)

        during = capacity.check_capacity(["claude"], state_file=state_file, now=NOW)
        assert during["claude"].available is False
        later = NOW + capacity.UNKNOWN_RESET_COOLDOWN + timedelta(minutes=1)
        after = capacity.check_capacity(["claude"], state_file=state_file, now=later)
        assert after["claude"].available is True


class TestWhatTheGateCannotCheck:
    def test_237_gemini_is_not_checked_here_and_says_so(self, state_file):
        status = capacity.check_capacity(["gemini"], state_file=state_file, now=NOW)["gemini"]

        assert status.available is False
        assert status.checked is False
        summary = status.wait_summary(now=NOW)
        assert "not checked" in summary
        assert "preflight" in summary

    def test_an_unchecked_provider_is_not_listed_as_exhausted(self, state_file):
        """Kept: blocked_providers lists what is known to be exhausted. Gemini's
        transport preflight checks it, with a real call, before the first
        draft of every workflow that uses it."""
        assert capacity.blocked_providers(state_file=state_file, now=NOW) == []

    def test_264_an_unknown_provider_raises(self, state_file):
        with pytest.raises(ValueError, match="'openai'"):
            capacity.check_capacity(["openai"], state_file=state_file, now=NOW)
