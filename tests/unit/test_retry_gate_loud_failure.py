"""retry_gate.py under standard 0034, the one sweep site (#3790).

``should_retry`` looked an unknown failure class up with ``dict.get``, found
nothing, and gave it the caller's whole budget, the same answer as a
transient failure. A class nobody defined is a fault in the caller, and the
gate now raises on it, naming it. Line numbers in the names are ledger 0908's,
at its base ``79e18ad1``.
"""
from __future__ import annotations

import pytest

from assemblyzero.core import retry_gate


class TestAnUnknownClass:
    def test_209_an_unknown_class_raises(self):
        with pytest.raises(ValueError, match="'capacity'") as raised:
            retry_gate.should_retry("capacity", 1, max_attempts=3, fail_fast=False)
        for known in (retry_gate.TRANSIENT, retry_gate.IDLE_TIMEOUT,
                      retry_gate.CEILING_TIMEOUT, retry_gate.PERMANENT):
            assert known in str(raised.value)

    def test_209_an_unknown_class_raises_under_fail_fast_too(self):
        """Fail-fast answers "no retry" for every class; it must not hide a
        class that is not one."""
        with pytest.raises(ValueError, match="'capacity'"):
            retry_gate.should_retry("capacity", 1, max_attempts=3, fail_fast=True)


class TestTheKnownClassesAreUnchanged:
    @pytest.mark.parametrize("message, retryable", [
        ("HTTP 529 overloaded", True),
        ("timed out after 600s while still producing output", True),
        ("timed out after 300s with no output", True),
        ("timed out", True),
        ("invalid api key", False),
    ])
    def test_every_class_classify_failure_returns_is_accepted(self, message, retryable):
        """Kept: every class the classifier produces is one the gate knows."""
        failure_class = retry_gate.classify_failure(message, retryable=retryable)
        decision = retry_gate.should_retry(failure_class, 1, max_attempts=3, fail_fast=False)
        assert decision.failure_class == failure_class

    def test_a_transient_failure_keeps_the_callers_budget(self):
        """Kept: the caller's policy governs a transient failure."""
        decision = retry_gate.should_retry(
            retry_gate.TRANSIENT, 2, max_attempts=3, fail_fast=False,
        )
        assert decision.retry is True
        assert decision.backoff is True
