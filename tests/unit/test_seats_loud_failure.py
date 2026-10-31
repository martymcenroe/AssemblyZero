"""seats.py under standard 0034, one test per sweep site (#3793).

The spend-lock reads already failed closed (an unreadable lock counts as on,
so no Anthropic seat runs); what was missing is the reason. The WSL check and
the telemetry profile name no longer turn a failure into an answer. Line
numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import pytest

from assemblyzero.core import seats

# Captured at import, before tests/conftest.py replaces it for every test.
_REAL_OTHER_SIDE = seats.other_side_claude_home


class _Unreadable(type(seats.Path())):
    """A path whose reads fail the way an unreadable mount does."""

    def is_dir(self, **kwargs):
        raise PermissionError("permission denied")

    def is_file(self, **kwargs):
        return True

    def read_text(self, *args, **kwargs):
        raise PermissionError("permission denied")


class TestTheWslCheck:
    def test_128_an_unreadable_proc_version_on_linux_raises(self, monkeypatch):
        monkeypatch.setattr(seats.sys, "platform", "linux")
        real_read = seats.Path.read_text

        def read_text(self, *args, **kwargs):
            if str(self) == "/proc/version":
                raise PermissionError("permission denied")
            return real_read(self, *args, **kwargs)

        monkeypatch.setattr(seats.Path, "read_text", read_text)
        with pytest.raises(RuntimeError, match="cannot read /proc/version.*PermissionError"):
            _REAL_OTHER_SIDE()

    def test_128_off_linux_there_is_no_other_side_and_nothing_is_read(self, monkeypatch):
        monkeypatch.setattr(seats.sys, "platform", "darwin")

        def read_text(self, *args, **kwargs):
            raise AssertionError("nothing should be read off Linux")

        monkeypatch.setattr(seats.Path, "read_text", read_text)
        assert _REAL_OTHER_SIDE() is None


class TestTheLockFailsClosedAndAlerts:
    def test_149_an_unreadable_home_is_kept_and_alerts(self, operator_alerts):
        assert seats._present(_Unreadable("/mnt/c/Users/x/.claude")) is True
        assert len(operator_alerts) == 1
        assert "cannot tell whether" in operator_alerts[0]["what"]
        assert "PermissionError" in operator_alerts[0]["cause"]

    def test_173_an_unreadable_lock_counts_as_on_and_alerts(self, operator_alerts):
        assert seats._lock_on(_Unreadable("/home/x/.claude/claude-spend.lock")) is True
        assert len(operator_alerts) == 1
        assert "cannot read the spend lock" in operator_alerts[0]["what"]
        assert "no seat runs on an Anthropic model" in operator_alerts[0]["consequence"]

    def test_191_an_unreadable_lift_time_binds_and_alerts(self, operator_alerts):
        assert seats.lock_until("until: next tuesday\n") is None
        assert len(operator_alerts) == 1
        assert "next tuesday" in operator_alerts[0]["what"]

    def test_a_readable_lift_time_is_quiet(self, operator_alerts):
        assert seats.lock_until("until: 2026-10-10T09:00:00+00:00\n") is not None
        assert operator_alerts == []


class TestTheTelemetryProfileName:
    def test_776_a_profile_that_cannot_be_read_raises(self, monkeypatch):
        def broken():
            raise seats.ProfileError("models.toml: no [defaults] table")

        monkeypatch.setattr(seats, "active_profile", broken)
        with pytest.raises(seats.ProfileError, match="no \\[defaults\\] table"):
            seats.current_profile_name()

    def test_777_the_withdrawn_tag_is_gone(self):
        import inspect

        source = inspect.getsource(seats)
        assert "fail-open" not in source
