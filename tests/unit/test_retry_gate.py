"""Classify before retrying, not after failing (#2423).

The operator's words are the requirement: a cock-up done three times is just an
expensive cock-up.

The replay at the bottom of this file is the acceptance evidence. It takes the
measured failure shape from run-issue1-090001 and drives the real gate with it,
asserting one payment and a named halt where the old behaviour paid seven
times.
"""

from __future__ import annotations

import pytest

from assemblyzero.core import retry_gate as g


@pytest.fixture(autouse=True)
def _no_ambient_fail_fast(monkeypatch):
    """The env var is process-wide; a stray one would make every test pass."""
    monkeypatch.delenv(g.ENV_FAIL_FAST, raising=False)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class TestClassification:
    def test_structured_wall_kind_is_a_ceiling(self):
        assert g.classify_failure("", timeout_kind="wall") == g.CEILING_TIMEOUT

    def test_structured_idle_kind_is_an_idle_timeout(self):
        assert g.classify_failure("", timeout_kind="idle") == g.IDLE_TIMEOUT

    def test_the_transports_wall_message_reads_as_a_ceiling(self):
        """The exact #2405 wall text, which is a contract with the transport."""
        message = (
            "claude -p timed out after 600s while still producing output "
            "(1421 events); raise AZ_FILE_TIMEOUT_FLOOR rather than treating "
            "this as a provider failure"
        )
        assert g.classify_failure(message) == g.CEILING_TIMEOUT

    def test_the_transports_idle_message_reads_as_an_idle_timeout(self):
        message = (
            "claude -p timed out after 120s with no output (idle limit 120s, "
            "37 events received before it went quiet)"
        )
        assert g.classify_failure(message) == g.IDLE_TIMEOUT

    def test_a_bare_timeout_is_treated_as_idle_not_as_a_ceiling(self):
        """The pre-#2405 shape, and every non-Claude provider. One retry --
        not none, which would be a bigger behaviour change than asked for."""
        assert g.classify_failure("claude -p timed out after 602s") == g.IDLE_TIMEOUT

    def test_a_non_retryable_error_is_permanent(self):
        assert g.classify_failure("401 unauthorized", retryable=False) == g.PERMANENT

    def test_a_5xx_is_transient(self):
        assert g.classify_failure("503 capacity exhausted") == g.TRANSIENT

    def test_a_connection_drop_is_transient(self):
        assert g.classify_failure("connection reset by peer") == g.TRANSIENT

    def test_structured_kind_beats_the_message(self):
        """The transport KNOWS which wall it hit; prose is only the fallback."""
        assert g.classify_failure(
            "503 capacity exhausted", timeout_kind="wall"
        ) == g.CEILING_TIMEOUT


# ---------------------------------------------------------------------------
# The decision -- the three rules the issue names
# ---------------------------------------------------------------------------


class TestTransientRetriesWithBackoff:
    def test_transient_retries(self):
        d = g.should_retry(g.TRANSIENT, attempts_made=1, max_attempts=3)
        assert d.retry is True
        assert d.backoff is True

    def test_transient_respects_the_callers_budget(self):
        d = g.should_retry(g.TRANSIENT, attempts_made=3, max_attempts=3)
        assert d.retry is False


class TestIdleRetriesAtMostOnce:
    def test_the_first_idle_kill_gets_one_more_attempt(self):
        d = g.should_retry(g.IDLE_TIMEOUT, attempts_made=1, max_attempts=3)
        assert d.retry is True

    def test_the_second_idle_kill_halts_even_with_budget_left(self):
        """'an idle-kill retries at most once (the hang may be flukish)'."""
        d = g.should_retry(g.IDLE_TIMEOUT, attempts_made=2, max_attempts=3)
        assert d.retry is False
        assert "one retry" in d.reason

    def test_a_class_can_lower_a_limit_but_never_raise_one(self):
        d = g.should_retry(g.IDLE_TIMEOUT, attempts_made=1, max_attempts=1)
        assert d.retry is False


class TestCeilingHaltsWithoutASecondPayment:
    def test_a_ceiling_kill_never_gets_a_second_attempt(self):
        """'a ceiling kill with the stream alive is deterministic ... do not
        re-pay it; halt with the named reason and the resume hint'."""
        d = g.should_retry(g.CEILING_TIMEOUT, attempts_made=1, max_attempts=3)
        assert d.retry is False

    def test_the_halt_names_the_reason(self):
        d = g.should_retry(g.CEILING_TIMEOUT, attempts_made=1, max_attempts=3)
        assert "STILL ANSWERING" in d.reason
        assert "same call will run just as long again" in d.reason

    def test_the_halt_carries_the_resume_hint(self):
        d = g.should_retry(g.CEILING_TIMEOUT, attempts_made=1, max_attempts=3)
        assert "AZ_FILE_TIMEOUT_FLOOR" in d.reason
        assert "resume" in d.reason

    def test_a_ceiling_halts_even_on_a_generous_budget(self):
        d = g.should_retry(g.CEILING_TIMEOUT, attempts_made=1, max_attempts=99)
        assert d.retry is False


class TestPermanent:
    def test_permanent_never_retries(self):
        d = g.should_retry(g.PERMANENT, attempts_made=1, max_attempts=5)
        assert d.retry is False


# ---------------------------------------------------------------------------
# Fail-fast
# ---------------------------------------------------------------------------


class TestFailFast:
    def test_fail_fast_stops_even_a_transient_retry(self):
        d = g.should_retry(
            g.TRANSIENT, attempts_made=1, max_attempts=5, fail_fast=True
        )
        assert d.retry is False
        assert "--fail-fast" in d.reason

    def test_off_by_default(self):
        assert g.fail_fast_enabled() is False

    def test_set_and_clear_round_trip(self, monkeypatch):
        g.set_fail_fast(True)
        assert g.fail_fast_enabled() is True
        g.set_fail_fast(False)
        assert g.fail_fast_enabled() is False

    @pytest.mark.parametrize("word", ["0", "false", "no", "off", "FALSE", "Off"])
    def test_explicit_falsey_words_mean_off(self, monkeypatch, word):
        monkeypatch.setenv(g.ENV_FAIL_FAST, word)
        assert g.fail_fast_enabled() is False

    @pytest.mark.parametrize("word", ["1", "true", "yes", "on", "anything"])
    def test_anything_else_means_on(self, monkeypatch, word):
        """An operator who typed the flag meant it. A mode that silently
        disengages on an unexpected value is worse than one that never was."""
        monkeypatch.setenv(g.ENV_FAIL_FAST, word)
        assert g.fail_fast_enabled() is True


# ---------------------------------------------------------------------------
# Spend reporting (requirement 3)
# ---------------------------------------------------------------------------


class TestSpendIsReportedAsSpend:
    def test_the_retry_line_carries_the_running_total(self):
        line = g.retry_spend_line(
            "N4 implementer", attempts_made=1, budget=3,
            failure_class=g.TRANSIENT, cumulative_cost=4.17,
        )
        assert "cumulative=$4.17" in line
        assert "class=transient" in line

    def test_the_retry_line_shows_the_backoff_when_there_is_one(self):
        line = g.retry_spend_line(
            "N4", attempts_made=1, budget=3, failure_class=g.TRANSIENT,
            cumulative_cost=1.0, sleeping=8.0,
        )
        assert "backoff=8.0s" in line

    def test_the_halt_line_carries_the_running_total(self):
        d = g.should_retry(g.CEILING_TIMEOUT, attempts_made=1, max_attempts=3)
        line = g.halt_line("N4 implementer", d, 12.34)
        assert "cumulative=$12.34" in line
        assert "ceiling_timeout" in line
        assert "will NOT be retried" in line


# ---------------------------------------------------------------------------
# THE REPLAY -- the acceptance evidence the issue asks for
# ---------------------------------------------------------------------------


class TestReplayOfTheMeasuredRun:
    """run-issue1-090001, 2026-08-15, replayed against the new gate.

    Counted from the log rather than estimated:

        7 payments of ~602s = 4213.5s = 70.2 minutes, zero artifacts.

    The shape is a wall-clock kill on a call that was still streaming -- the
    provider was answering the whole time, so the same call runs just as long
    on every attempt. The cost was multiplicative because a per-file loop
    (MAX_FILE_RETRIES=2) sat inside a stage loop (max_retries=3).
    """

    #: The seven measured durations, in order, from the log.
    MEASURED = [600.2, 602.2, 602.2, 602.2, 602.2, 602.2, 602.3]

    def _drive(self, gate_max_attempts, *, fail_fast=False):
        """Pay for calls until the gate says stop. Returns what was spent."""
        paid = []
        for i, duration in enumerate(self.MEASURED, start=1):
            paid.append(duration)
            decision = g.should_retry(
                g.classify_failure(
                    "claude -p timed out after 600s while still producing "
                    "output (1421 events); raise AZ_FILE_TIMEOUT_FLOOR rather "
                    "than treating this as a provider failure"
                ),
                attempts_made=i,
                max_attempts=gate_max_attempts,
                fail_fast=fail_fast,
            )
            if not decision.retry:
                return paid, decision
        raise AssertionError("the gate never halted")  # pragma: no cover

    def test_the_old_shape_cost_seven_payments_and_seventy_minutes(self):
        """The baseline this is measured against, stated as arithmetic."""
        assert len(self.MEASURED) == 7
        assert round(sum(self.MEASURED), 1) == 4213.5
        assert round(sum(self.MEASURED) / 60, 1) == 70.2

    def test_the_new_gate_pays_once(self):
        paid, _decision = self._drive(gate_max_attempts=3)
        assert len(paid) == 1, f"expected one payment, got {len(paid)}"

    def test_the_halt_is_named(self):
        _paid, decision = self._drive(gate_max_attempts=3)
        assert decision.failure_class == g.CEILING_TIMEOUT
        assert "STILL ANSWERING" in decision.reason
        assert "AZ_FILE_TIMEOUT_FLOOR" in decision.reason

    def test_the_saving_is_six_payments_and_an_hour(self):
        paid, _ = self._drive(gate_max_attempts=3)
        saved = sum(self.MEASURED) - sum(paid)
        assert len(self.MEASURED) - len(paid) == 6
        assert round(saved / 60, 1) == 60.2

    def test_the_nested_budget_cannot_multiply_it_back(self):
        """The real cost was 2 file attempts x 3 stage attempts. A ceiling
        halt is budget-independent, so neither loop can re-pay it."""
        for budget in (1, 2, 3, 6, 99):
            paid, decision = self._drive(gate_max_attempts=budget)
            assert len(paid) == 1, f"budget {budget} paid {len(paid)} times"
            assert decision.retry is False

    def test_fail_fast_also_pays_once(self):
        paid, decision = self._drive(gate_max_attempts=3, fail_fast=True)
        assert len(paid) == 1
        assert "--fail-fast" in decision.reason

    def test_a_genuine_provider_outage_still_retries(self):
        """The gate must not have turned into 'never retry anything'. The
        503 burst on line 42 of the same log is the counter-example, and it
        SHOULD be retried with backoff."""
        decision = g.should_retry(
            g.classify_failure("503 capacity exhausted"),
            attempts_made=1, max_attempts=3,
        )
        assert decision.retry is True
        assert decision.backoff is True
