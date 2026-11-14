"""The requirements gate's budget, its one retry, and saying so out loud (#2290).

#2290 made a run that proceeded without a verdict say so, in the roll's verdict
block and in the orchestrator summary, because "requirements were not checked"
and "requirements were checked and were clean" used to look identical. #2474
and #3585 then closed every path that proceeded: a run without a verdict now
halts as REQUIREMENTS UNVERIFIED and reports itself through its halt. #4264
removed the "proceeded unverified" banner and its ledger, which nothing could
write any more.

The measured case is boostgauge #7 -- two decision tables, 21 acceptance
criteria -- which timed out at the old 300s bound on one attempt and returned a
real CONFLICT verdict in 294s on the next, minutes apart, transport healthy
throughout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import speedrun_roll as sr  # noqa: E402

from assemblyzero.core.llm_provider import LLMCallResult  # noqa: E402
from assemblyzero.workflows.requirements.nodes.analyze_requirements import (  # noqa: E402
    GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS,
    REQUIREMENTS_GATE_TIMEOUT_SECONDS,
    analyze_requirements,
)

#: Attempts before the gate gives up: the first call plus one per backoff entry.
#: Written as an expression rather than a literal so retuning the schedule
#: retunes the tests with it (#2474).
ATTEMPTS_BEFORE_HALT = 1 + len(GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS)

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


@pytest.fixture
def slept(gate_backoff_waits):
    """The backoff waits this case requested, recorded rather than served.

    The seam itself is autouse in tests/conftest.py, because tests in files
    that know nothing about the backoff drive the gate to a no-verdict outcome
    too and would otherwise sleep the real schedule. This is the local name for
    reading it.
    """
    return gate_backoff_waits


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
        self, tmp_path, provider, calm, slept
    ):
        p = provider(TIMEOUT, OK)

        result = analyze_requirements(_state(tmp_path))

        assert len(p.calls) == 2, "a healthy-transport timeout must be retried once"
        assert result == {}, "the retry succeeded, so the gate proceeds normally"
        assert slept == [], "the immediate #2375 retry does not wait"

    def test_the_immediate_retry_is_still_only_once(self, tmp_path, provider, calm):
        """#2375's retry is one extra call, not a loop.

        Measured as the difference from the no-immediate-retry cases below:
        a healthy-transport timeout costs exactly one call more than a failure
        that never earns the immediate retry.
        """
        p = provider(TIMEOUT)

        analyze_requirements(_state(tmp_path))

        assert len(p.calls) == ATTEMPTS_BEFORE_HALT + 1, (
            "one immediate retry on top of the backoff schedule, not a loop"
        )

    def test_a_storm_is_not_retried_into_immediately(self, tmp_path, provider, storm):
        """#2086: re-asking during a storm burns a second budget against the
        same wall, so the IMMEDIATE retry stays suppressed.

        #2474's waited retries are a different thing and deliberately DO run
        here -- waiting is the remedy for a storm, not an instance of what
        #2086 forbids. So the storm case costs exactly one call fewer than the
        calm case above, and that one call is the suppressed immediate retry.
        """
        p = provider(TIMEOUT)

        analyze_requirements(_state(tmp_path))

        assert len(p.calls) == ATTEMPTS_BEFORE_HALT

    def test_a_non_timeout_failure_gets_no_immediate_retry(
        self, tmp_path, provider, calm
    ):
        """Unchanged from #2290: an identical IMMEDIATE second call will not
        change why it failed. #2474's waited retries are what follow."""
        p = provider(OTHER_FAILURE)

        analyze_requirements(_state(tmp_path))

        assert len(p.calls) == ATTEMPTS_BEFORE_HALT


# ---------------------------------------------------------------------------
# Failing closed (#2474)
# ---------------------------------------------------------------------------


class TestItHaltsWhenItCannotRun:
    """The operator ruling of 2026-08-16.

    Before this, a gate that could not reach the governance model returned the
    same empty dict as a gate that checked and found the requirements clean.
    LangGraph routes on the return value, so both went to the drafter and the
    run kept spending with the pipeline's highest-value gate skipped.
    """

    def test_an_unreachable_gate_halts_instead_of_proceeding(
        self, tmp_path, provider, calm
    ):
        provider(_result(False, None, "All credentials failed: 503/529 storm"))

        update = analyze_requirements(_state(tmp_path))

        assert update.get("requirements_unverified"), (
            "the run must carry WHY it could not check, not an empty dict"
        )
        assert "503/529" in update["requirements_unverified"]

    def test_the_halt_is_distinguishable_from_a_clean_check(
        self, tmp_path, provider, calm
    ):
        """The whole defect in one assertion.

        'I checked and it is fine' and 'I could not check' must not be the same
        value, because the graph has nothing else to route on.
        """
        provider(OTHER_FAILURE)
        unreachable = analyze_requirements(_state(tmp_path))

        provider(OK)
        clean = analyze_requirements(_state(tmp_path))

        assert clean == {}
        assert unreachable != clean

    def test_the_halt_is_distinguishable_from_a_conflict(
        self, tmp_path, provider, calm
    ):
        """A conflict needs an operator ruling on the issue text; an
        unreachable gate needs a re-run. Sharing a signal sends the operator
        to rewrite requirements that were never read."""
        provider(OTHER_FAILURE)
        update = analyze_requirements(_state(tmp_path))

        assert "REQUIREMENTS CONFLICT:" not in update["error_message"]
        assert "REQUIREMENTS UNVERIFIED:" in update["error_message"]

    def test_an_unparseable_response_halts_too(self, tmp_path, provider, calm):
        provider(_result(True, "not json at all"))

        update = analyze_requirements(_state(tmp_path))

        # #4485: it says which failure, where it said "unparseable" for all three.
        assert "not JSON" in update.get("requirements_unverified", "")

    def test_an_invalid_provider_halts_without_waiting(
        self, tmp_path, monkeypatch, slept
    ):
        """No backoff outlasts a provider spec that names nothing real."""
        def _raise(spec, *a, **k):
            raise ValueError(f"unknown provider: {spec}")

        monkeypatch.setattr(
            "assemblyzero.core.llm_provider.get_provider", _raise
        )

        update = analyze_requirements(_state(tmp_path))

        assert "invalid provider" in update.get("requirements_unverified", "")
        assert slept == [], "a bad spec is not transient; waiting cannot fix it"

    def test_it_backs_off_on_the_declared_schedule_before_halting(
        self, tmp_path, provider, calm, slept
    ):
        """The observed outage cleared in minutes, so halting on the first
        storm would be brittle in the other direction."""
        p = provider(OTHER_FAILURE)

        analyze_requirements(_state(tmp_path))

        assert slept == list(GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS)
        assert len(p.calls) == ATTEMPTS_BEFORE_HALT

    def test_a_verdict_on_a_backoff_retry_proceeds_normally(
        self, tmp_path, provider, calm, slept
    ):
        """The point of the backoff: a storm that clears must not cost a halt."""
        p = provider(OTHER_FAILURE, OK)

        update = analyze_requirements(_state(tmp_path))

        assert update == {}, "the retry got a verdict, so the run proceeds"
        assert len(p.calls) == 2, "it stops retrying the moment it has an answer"
        assert slept == [GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS[0]], (
            "it waits once, not through the whole schedule"
        )

    def test_a_conflict_still_halts_the_old_way(self, tmp_path, provider, calm):
        """#1899's halt is untouched: it is a verdict, not a failure to reach
        one, and it must not acquire the unverified marker."""
        provider(_result(True, json.dumps({
            "is_consistent": False,
            "conflicts": [{
                "criterion_a": "the floor is the highest value in the window",
                "criterion_b": "the floor drifts toward the most recent value",
                "diverging_situation": "when the window max is not the latest sample",
            }],
        })))

        update = analyze_requirements(_state(tmp_path))

        assert "REQUIREMENTS CONFLICT:" in update["error_message"]
        assert not update.get("requirements_unverified")

    def test_the_halt_message_says_the_gate_did_not_run(
        self, tmp_path, provider, calm
    ):
        provider(OTHER_FAILURE)

        message = analyze_requirements(_state(tmp_path))["error_message"]

        assert "did not run" in message
        assert "NOT a clean requirements check" in message

    def test_the_halt_message_carries_the_resume_command(
        self, tmp_path, provider, calm
    ):
        """Read at the moment something has already failed, so the next action
        has to be in the message rather than in a runbook."""
        provider(OTHER_FAILURE)

        message = analyze_requirements(_state(tmp_path))["error_message"]

        assert "tools/check_requirements.py" in message
        assert str(tmp_path) in message and "--issue 7" in message


# ---------------------------------------------------------------------------
# Saying so
# ---------------------------------------------------------------------------


class TestItSaysSoWhenItDidNotRun:
    """Every path without a verdict halts and says so (#2474, #3585).

    #2290's ledger and end-of-run banner said "the run proceeded anyway". Once
    no path proceeded, nothing wrote the ledger, and #4264 removed both. A
    halted run is reported by its halt message and recovery plan.
    """

    def test_an_exhausted_retry_halts(self, tmp_path, provider, calm):
        provider(TIMEOUT)

        update = analyze_requirements(_state(tmp_path))

        assert update.get("requirements_unverified"), "it halted"

    def test_an_unparseable_response_halts(self, tmp_path, provider, calm):
        provider(_result(True, "not json at all"))

        update = analyze_requirements(_state(tmp_path))

        assert update.get("requirements_unverified"), "it halted"

    def test_the_last_fail_open_path_now_halts(self, tmp_path, provider, calm):
        """#2462's path: the model answered, but every conflict it reported
        lacked a divergence condition. It used to proceed and record the
        unverified state; #3585 (ADR 0236) halts it as REQUIREMENTS UNVERIFIED,
        and a halt reports itself.
        """
        provider(_result(True, json.dumps({
            "is_consistent": False,
            "conflicts": [{
                "criterion_a": "A",
                "criterion_b": "B",
                "diverging_situation": "?",
            }],
        })))

        update = analyze_requirements(_state(tmp_path))

        assert update.get("requirements_unverified"), "it halted"

    def test_the_precheck_reports_no_verdict_as_error_not_conflict(
        self, tmp_path, provider, calm
    ):
        """#2474: the node now sets error_message on the unreachable path so
        the HALT node has something to classify. The pre-check reads
        requirements_unverified first, or it would tell the operator to rule on
        a contradiction in requirements nothing ever read."""
        from assemblyzero.workflows.requirements import precheck

        provider(OTHER_FAILURE)
        result = precheck.run_gate(tmp_path, 7, "t", "The app shall persist state.")

        assert result.status == "error"
        assert "no verdict" in result.detail


class TestTheVerdictBlock:
    """The roll's verdict block carries no "proceeded unverified" banner (#4264).

    No roll proceeds without a requirements verdict since #3585, so the banner
    could never print; it went with its ledger.
    """

    def _verdict(self, capsys, repo, **over):
        kwargs = dict(
            requested=[7], rolled=[7], blocked=[], stopped_at=None, code=0, since="",
        )
        kwargs.update(over)
        sr._render_verdict(repo, **kwargs)
        return capsys.readouterr().out

    def test_a_clean_roll_says_nothing_extra(self, tmp_path, capsys):
        out = self._verdict(capsys, tmp_path)

        assert "ROLL SUCCEEDED" in out
        assert "REQUIREMENTS UNVERIFIED" not in out

    def test_a_failed_roll_reads_as_failed(self, tmp_path, capsys):
        out = self._verdict(capsys, tmp_path, rolled=[], stopped_at=7, code=1)

        assert "ROLL FAILED" in out
        assert "REQUIREMENTS UNVERIFIED" not in out
