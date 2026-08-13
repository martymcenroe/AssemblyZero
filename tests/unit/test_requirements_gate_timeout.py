"""The requirements gate's budget, its one retry, and saying so out loud (#2290).

The gate fails open by design so a provider storm cannot brick a launch (#1899),
and that policy is unchanged. What changed is that failing open is no longer
silent: a run that proceeded without a verdict says so in the roll's verdict
block and in the orchestrator summary, because "requirements were not checked"
and "requirements were checked and were clean" used to look identical.

The measured case is boostgauge #7 -- two decision tables, 21 acceptance
criteria -- which timed out at the old 300s bound on one attempt and returned a
real CONFLICT verdict in 294s on the next, minutes apart, transport healthy
throughout.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import speedrun_roll as sr  # noqa: E402

from assemblyzero.core.llm_provider import LLMCallResult  # noqa: E402
from assemblyzero.speedrun.requirements_status import (  # noqa: E402
    format_banner,
    read_unverified,
    record_unverified,
    unverified_path,
)
from assemblyzero.workflows.requirements.nodes.analyze_requirements import (  # noqa: E402
    REQUIREMENTS_GATE_TIMEOUT_SECONDS,
    analyze_requirements,
)

#: What the gate's own call actually took on boostgauge #7, wall clock.
MEASURED_ISSUE_7_SECONDS = 294

CONSISTENT = '{"is_consistent": true, "conflicts": []}'


def _result(success, response, error=None):
    return LLMCallResult(
        success=success, response=response, raw_response=response,
        error_message=error, provider="fake", model_used="fake-model",
        duration_ms=1, attempts=1,
    )


class _Provider:
    """Returns a scripted sequence, one entry per call."""

    def __init__(self, *results):
        self._results = list(results)
        self.calls: list[dict] = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return self._results[min(len(self.calls) - 1, len(self._results) - 1)]


TIMEOUT = _result(False, None, "claude -p timed out after 600s")
OK = _result(True, CONSISTENT)
OTHER_FAILURE = _result(False, None, "400 invalid request")


@pytest.fixture
def provider(monkeypatch):
    def _install(*results):
        p = _Provider(*results)
        monkeypatch.setattr(
            "assemblyzero.core.llm_provider.get_provider",
            lambda spec, *a, **k: p,
        )
        return p

    return _install


@pytest.fixture
def calm(monkeypatch):
    """A healthy transport: no provider storm in progress."""
    monkeypatch.setattr("assemblyzero.core.provider_storm.is_storm", lambda: False)


@pytest.fixture
def storm(monkeypatch):
    monkeypatch.setattr("assemblyzero.core.provider_storm.is_storm", lambda: True)


def _state(tmp_path, **over):
    base = {
        "issue_title": "feat: config persistence",
        "issue_body": "The app shall persist window position on exit.",
        "issue_number": 7,
        "target_repo": str(tmp_path),
        "config_drafter": "fake:model",
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# The budget
# ---------------------------------------------------------------------------


class TestTheBudget:
    def test_the_measured_issue_7_call_fits_within_budget(self):
        """The regression fixture. 294s must not be near the bound again.

        This is the whole defect in one assertion: the old 300s bound sat six
        seconds above the real duration, so the same call landed on either side
        of it depending on the minute.
        """
        assert MEASURED_ISSUE_7_SECONDS < REQUIREMENTS_GATE_TIMEOUT_SECONDS
        margin = REQUIREMENTS_GATE_TIMEOUT_SECONDS - MEASURED_ISSUE_7_SECONDS
        assert margin >= MEASURED_ISSUE_7_SECONDS, (
            f"only {margin}s of headroom above the measured {MEASURED_ISSUE_7_SECONDS}s. "
            "Duration scales with issue size and the bound is a constant, so a "
            "margin thinner than the measurement itself will be spent by the "
            "next issue with three tables."
        )

    def test_the_gate_asks_for_its_own_bound_not_the_provider_default(
        self, tmp_path, provider, calm
    ):
        p = provider(OK)

        analyze_requirements(_state(tmp_path))

        assert p.calls[0]["timeout_seconds"] == REQUIREMENTS_GATE_TIMEOUT_SECONDS

    def test_the_standalone_precheck_measures_the_same_thing(self, tmp_path, provider, calm):
        """The offline pre-check runs the same node, so a clean pass there
        means what it means in a roll. Pinned because the two drifting apart
        is exactly what makes a pre-check worthless."""
        from assemblyzero.workflows.requirements import precheck

        p = provider(OK)
        precheck.run_gate(tmp_path, 7, "t", "The app shall persist state.")

        assert p.calls[0]["timeout_seconds"] == REQUIREMENTS_GATE_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# The one retry
# ---------------------------------------------------------------------------


class TestTheRetry:
    def test_a_timeout_on_a_healthy_transport_retries_once(
        self, tmp_path, provider, calm
    ):
        p = provider(TIMEOUT, OK)

        result = analyze_requirements(_state(tmp_path))

        assert len(p.calls) == 2, "a healthy-transport timeout must be retried once"
        assert result == {}, "the retry succeeded, so the gate proceeds normally"

    def test_it_retries_only_once(self, tmp_path, provider, calm):
        p = provider(TIMEOUT)

        analyze_requirements(_state(tmp_path))

        assert len(p.calls) == 2, "one retry, not a loop"

    def test_a_storm_is_not_retried_into(self, tmp_path, provider, storm):
        """The storm is the condition fail-open exists for. Retrying burns
        another full budget to reach the same wall (#2086)."""
        p = provider(TIMEOUT)

        analyze_requirements(_state(tmp_path))

        assert len(p.calls) == 1

    def test_a_non_timeout_failure_is_not_retried(self, tmp_path, provider, calm):
        p = provider(OTHER_FAILURE)

        analyze_requirements(_state(tmp_path))

        assert len(p.calls) == 1, (
            "it failed for a reason an identical second call will not change"
        )


# ---------------------------------------------------------------------------
# Saying so
# ---------------------------------------------------------------------------


class TestItSaysSoWhenItDidNotRun:
    def test_an_exhausted_retry_records_the_unverified_state(
        self, tmp_path, provider, calm
    ):
        provider(TIMEOUT)

        analyze_requirements(_state(tmp_path))

        records = read_unverified(tmp_path)
        assert len(records) == 1
        assert records[0]["issue"] == 7
        assert "timed out" in records[0]["reason"]

    def test_an_unparseable_response_records_it_too(self, tmp_path, provider, calm):
        provider(_result(True, "not json at all"))

        analyze_requirements(_state(tmp_path))

        records = read_unverified(tmp_path)
        assert len(records) == 1 and "unparseable" in records[0]["reason"]

    def test_a_verdict_records_nothing(self, tmp_path, provider, calm):
        provider(OK)

        analyze_requirements(_state(tmp_path))

        assert read_unverified(tmp_path) == []
        assert not unverified_path(tmp_path).exists()

    def test_the_standalone_precheck_does_not_write_roll_records(
        self, tmp_path, provider, calm
    ):
        """Its own exit code is the signal. A record here would sit in the
        ledger waiting to mislabel whichever roll runs next."""
        from assemblyzero.workflows.requirements import precheck

        provider(TIMEOUT)
        precheck.run_gate(tmp_path, 7, "t", "The app shall persist state.")

        assert read_unverified(tmp_path) == []

    def test_recording_never_raises(self, tmp_path):
        blocker = tmp_path / "data"
        blocker.write_text("not a directory", encoding="utf-8")
        assert record_unverified(tmp_path, issue=7, reason="x") is False

    def test_since_filters_older_records(self, tmp_path):
        record_unverified(tmp_path, issue=1, reason="old", ts="2026-08-01 00:00:00")
        record_unverified(tmp_path, issue=2, reason="new", ts="2026-08-13 00:00:00")

        recent = read_unverified(tmp_path, since="2026-08-12 00:00:00")

        assert [r["issue"] for r in recent] == [2]


class TestTheBanner:
    def test_no_records_says_nothing(self):
        assert format_banner([]) == []

    def test_the_banner_names_the_state_and_the_issue(self):
        lines = format_banner([{"issue": 7, "reason": "analysis unavailable: timed out"}])
        text = "\n".join(lines)

        assert "REQUIREMENTS UNVERIFIED" in text
        assert "#7" in text
        assert "timed out" in text
        assert "NOT the same as a clean requirements check" in text


class TestTheVerdictBlockCarriesIt:
    def _verdict(self, capsys, repo, **over):
        kwargs = dict(
            requested=[7], rolled=[7], blocked=[], stopped_at=None, code=0, since="",
        )
        kwargs.update(over)
        sr._render_verdict(repo, **kwargs)
        return capsys.readouterr().out

    def test_a_successful_roll_still_reports_unverified_requirements(
        self, tmp_path, capsys
    ):
        """The case that matters. A roll whose gate failed open used to print
        an unqualified ROLL SUCCEEDED and read exactly like a verified run."""
        record_unverified(tmp_path, issue=7, reason="analysis unavailable: timed out")

        out = self._verdict(capsys, tmp_path)

        assert "ROLL SUCCEEDED" in out
        assert "REQUIREMENTS UNVERIFIED" in out

    def test_a_clean_roll_says_nothing_extra(self, tmp_path, capsys):
        out = self._verdict(capsys, tmp_path)

        assert "ROLL SUCCEEDED" in out
        assert "REQUIREMENTS UNVERIFIED" not in out

    def test_a_failed_roll_carries_it_too(self, tmp_path, capsys):
        record_unverified(tmp_path, issue=7, reason="analysis unavailable: timed out")

        out = self._verdict(capsys, tmp_path, rolled=[], stopped_at=7, code=1)

        assert "ROLL FAILED" in out
        assert "REQUIREMENTS UNVERIFIED" in out

    def test_an_unreadable_ledger_never_costs_the_verdict(
        self, tmp_path, capsys, monkeypatch
    ):
        def _boom(*a, **k):
            raise OSError("ledger unreadable")

        monkeypatch.setattr(
            "assemblyzero.speedrun.requirements_status.read_unverified", _boom
        )

        out = self._verdict(capsys, tmp_path)

        assert "ROLL SUCCEEDED" in out
