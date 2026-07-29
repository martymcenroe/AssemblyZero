"""Cross-provider capacity state (#1883).

A run needs Gemini for design/review and Claude for implementation. Starting
one while either is exhausted spends the healthy provider's quota to discover
the dry one. Gemini already recorded its exhaustion with reset times; Claude
detected usage limits and threw the knowledge away.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from assemblyzero.core import capacity
from assemblyzero.core.capacity import (
    UNKNOWN_RESET_COOLDOWN,
    ProviderCapacity,
    check_capacity,
    clear_exhaustion,
    parse_reset_time,
    record_exhaustion,
)

NOW = datetime(2026, 7, 29, 17, 0, tzinfo=timezone.utc)


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "provider-capacity.json"


class TestParseResetTime:
    """The Claude message format has never been captured, so parse the shapes
    seen in the wild and return None rather than guess."""

    def test_trailing_unix_timestamp(self):
        stamp = int(datetime(2026, 7, 29, 22, 0, tzinfo=timezone.utc).timestamp())
        parsed = parse_reset_time(f"Claude AI usage limit reached|{stamp}")
        assert parsed == datetime(2026, 7, 29, 22, 0, tzinfo=timezone.utc)

    def test_iso_timestamp(self):
        parsed = parse_reset_time("limit resets 2026-07-29T22:30:00")
        assert parsed.hour == 22 and parsed.minute == 30

    def test_relative_hours_and_minutes(self):
        parsed = parse_reset_time("Your quota will reset in 2h30m", now=NOW)
        assert parsed == NOW + timedelta(hours=2, minutes=30)

    def test_relative_minutes_only(self):
        parsed = parse_reset_time("try again in 45 minutes", now=NOW)
        assert parsed == NOW + timedelta(minutes=45)

    def test_clock_time_with_meridiem(self):
        parsed = parse_reset_time("Your limit will reset at 5pm", now=NOW)
        assert parsed is not None
        assert parsed.astimezone().hour == 17

    def test_unparseable_returns_none_rather_than_guessing(self):
        assert parse_reset_time("Claude usage limit reached.") is None

    def test_empty_returns_none(self):
        assert parse_reset_time("") is None


class TestRecordAndClear:
    def test_record_persists_reset_and_raw_message(self, state_file):
        message = "Claude usage limit reached. Your limit will reset in 1h0m"
        result = record_exhaustion("claude", message, state_file=state_file, now=NOW)

        assert result.available is False
        assert result.resets_at == NOW + timedelta(hours=1)

        stored = json.loads(state_file.read_text(encoding="utf-8"))["claude"]
        # the raw message survives so an unparseable format is diagnosable
        assert stored["source_message"] == message
        assert stored["resets_at"] is not None

    def test_record_keeps_raw_message_even_when_unparseable(self, state_file):
        record_exhaustion("claude", "some new wording", state_file=state_file, now=NOW)
        stored = json.loads(state_file.read_text(encoding="utf-8"))["claude"]
        assert stored["resets_at"] is None
        assert stored["source_message"] == "some new wording"

    def test_clear_removes_the_record(self, state_file):
        record_exhaustion("claude", "usage limit", state_file=state_file, now=NOW)
        clear_exhaustion("claude", state_file=state_file)
        status = check_capacity(["claude"], state_file=state_file, now=NOW)["claude"]
        assert status.available is True


class TestClaudeCapacityWindow:
    def test_exhausted_before_reset(self, state_file):
        record_exhaustion(
            "claude", "reset in 0h30m", state_file=state_file, now=NOW
        )
        status = check_capacity(["claude"], state_file=state_file, now=NOW)["claude"]
        assert status.available is False

    def test_available_after_reset_passes(self, state_file):
        record_exhaustion(
            "claude", "reset in 0h30m", state_file=state_file, now=NOW
        )
        later = NOW + timedelta(hours=1)
        status = check_capacity(["claude"], state_file=state_file, now=later)["claude"]
        assert status.available is True

    def test_unparseable_record_expires_on_its_own(self, state_file):
        """A block that never lifts would wedge the pipeline harder than the
        quota did."""
        record_exhaustion("claude", "no time here", state_file=state_file, now=NOW)

        during = check_capacity(["claude"], state_file=state_file, now=NOW)["claude"]
        assert during.available is False

        after = NOW + UNKNOWN_RESET_COOLDOWN + timedelta(minutes=1)
        assert check_capacity(["claude"], state_file=state_file, now=after)[
            "claude"
        ].available is True

    def test_missing_state_file_means_available(self, tmp_path):
        status = check_capacity(
            ["claude"], state_file=tmp_path / "nope.json", now=NOW
        )["claude"]
        assert status.available is True

    def test_corrupt_state_file_does_not_block_work(self, state_file):
        state_file.write_text("{ not json", encoding="utf-8")
        status = check_capacity(["claude"], state_file=state_file, now=NOW)["claude"]
        assert status.available is True


class TestCapacityMessageDetection:
    """Narrower than is_non_retryable_error: billing and auth failures must
    NOT be recorded as 'exhausted until', since waiting never fixes them."""

    def test_usage_limit_is_capacity(self):
        from assemblyzero.core.llm_provider import _is_capacity_message

        assert _is_capacity_message("Claude usage limit reached") is True

    def test_billing_failure_is_not_capacity(self):
        from assemblyzero.core.llm_provider import _is_capacity_message

        assert _is_capacity_message("Your credit balance is too low") is False

    def test_auth_failure_is_not_capacity(self):
        from assemblyzero.core.llm_provider import _is_capacity_message

        assert _is_capacity_message("invalid api key") is False

    def test_empty_is_not_capacity(self):
        from assemblyzero.core.llm_provider import _is_capacity_message

        assert _is_capacity_message(None) is False


class TestWaitSummary:
    def test_available_summary(self):
        assert "available" in ProviderCapacity("claude", True).wait_summary()

    def test_exhausted_summary_is_platform_portable(self):
        """Formatted by hand — %-I is glibc-only, %#I is Windows-only."""
        status = ProviderCapacity(
            provider="claude",
            available=False,
            resets_at=NOW + timedelta(minutes=45),
        )
        summary = status.wait_summary(now=NOW)
        assert "45 min" in summary
        assert "AM" in summary or "PM" in summary

    def test_unknown_reset_summary_says_so(self):
        status = ProviderCapacity("claude", False, detail="reset time unknown")
        assert "unknown" in status.wait_summary()


class TestBlockedProviders:
    def test_lists_only_the_dry_ones(self, state_file, monkeypatch):
        monkeypatch.setattr(
            capacity,
            "_gemini_capacity",
            lambda now=None: ProviderCapacity("gemini", True),
        )
        record_exhaustion("claude", "reset in 0h30m", state_file=state_file, now=NOW)

        blocked = capacity.blocked_providers(state_file=state_file, now=NOW)
        assert [status.provider for status in blocked] == ["claude"]

    def test_empty_when_both_healthy(self, state_file, monkeypatch):
        monkeypatch.setattr(
            capacity,
            "_gemini_capacity",
            lambda now=None: ProviderCapacity("gemini", True),
        )
        assert capacity.blocked_providers(state_file=state_file, now=NOW) == []
