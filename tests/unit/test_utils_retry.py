"""Tests for assemblyzero.utils.retry (#1071)."""

from __future__ import annotations

from typing import List

import pytest

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.utils.retry import RetryPolicy, get_policy, with_retry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_result(provider: str = "claude") -> LLMCallResult:
    """LLMCallResult representing a successful call."""
    return LLMCallResult(
        success=True,
        response="ok",
        raw_response="ok",
        error_message=None,
        provider=provider,
        model_used="opus-4-7",
        duration_ms=100,
        attempts=1,
        retryable=True,
    )


def _transient_result(
    status_code: int = 503,
    retry_after: float | None = None,
    provider: str = "anthropic",
) -> LLMCallResult:
    """LLMCallResult representing a retryable transient failure."""
    return LLMCallResult(
        success=False,
        response=None,
        raw_response=None,
        error_message=f"HTTP {status_code} transient",
        provider=provider,
        model_used="opus-4-7",
        duration_ms=100,
        attempts=1,
        status_code=status_code,
        retryable=True,
        retry_after=retry_after,
    )


def _permanent_result(
    status_code: int = 401,
    provider: str = "anthropic",
) -> LLMCallResult:
    """LLMCallResult representing a non-retryable permanent failure."""
    return LLMCallResult(
        success=False,
        response=None,
        raw_response=None,
        error_message=f"HTTP {status_code} auth",
        provider=provider,
        model_used="opus-4-7",
        duration_ms=100,
        attempts=1,
        status_code=status_code,
        retryable=False,
    )


class _FakeFn:
    """Replays a scripted sequence of LLMCallResults."""

    def __init__(self, results: list[LLMCallResult]):
        self.results = list(results)
        self.calls = 0

    def __call__(self) -> LLMCallResult:
        self.calls += 1
        if self.results:
            return self.results.pop(0)
        # Default to last result if scripted list is exhausted
        raise AssertionError("FakeFn called more times than scripted")


# ---------------------------------------------------------------------------
# RetryPolicy / get_policy
# ---------------------------------------------------------------------------


def test_default_policy_values():
    p = RetryPolicy.default()
    assert p.max_retries == 5
    assert p.initial_backoff_s == 2.0
    assert p.max_backoff_s == 32.0
    assert p.backoff_multiplier == 2.0


def test_aggressive_policy_values():
    p = RetryPolicy.aggressive()
    assert p.max_retries == 8
    assert p.max_backoff_s == 60.0


def test_none_policy_disables_retry():
    p = RetryPolicy.none()
    assert p.max_retries == 0


def test_get_policy_default():
    p = get_policy("default")
    assert p.max_retries == 5


def test_get_policy_aggressive():
    p = get_policy("aggressive")
    assert p.max_retries == 8


def test_get_policy_none():
    p = get_policy("none")
    assert p.max_retries == 0


def test_get_policy_unknown_raises():
    with pytest.raises(ValueError, match="Unknown retry policy"):
        get_policy("turbo")


# ---------------------------------------------------------------------------
# with_retry — happy paths
# ---------------------------------------------------------------------------


def test_with_retry_succeeds_immediately():
    """Success on first try → no retry, no sleep."""
    fn = _FakeFn([_ok_result()])
    sleeps: List[float] = []
    result = with_retry(fn, sleep_fn=sleeps.append)
    assert result.success is True
    assert fn.calls == 1
    assert sleeps == []


def test_with_retry_recovers_after_one_transient():
    """One 503 then success → 2 calls, 1 sleep."""
    fn = _FakeFn([_transient_result(503), _ok_result()])
    sleeps: List[float] = []
    result = with_retry(fn, sleep_fn=sleeps.append)
    assert result.success is True
    assert fn.calls == 2
    assert sleeps == [2.0]  # default initial_backoff


def test_with_retry_recovers_after_three_transients():
    """503, 503, 503, success → 4 calls, exponential backoff."""
    fn = _FakeFn([
        _transient_result(503),
        _transient_result(503),
        _transient_result(503),
        _ok_result(),
    ])
    sleeps: List[float] = []
    result = with_retry(fn, sleep_fn=sleeps.append)
    assert result.success is True
    assert fn.calls == 4
    assert sleeps == [2.0, 4.0, 8.0]


# ---------------------------------------------------------------------------
# with_retry — retry-after handling
# ---------------------------------------------------------------------------


def test_with_retry_honors_server_retry_after():
    """retry_after on the result overrides exponential backoff."""
    fn = _FakeFn([
        _transient_result(429, retry_after=15.0),
        _ok_result(),
    ])
    sleeps: List[float] = []
    result = with_retry(fn, sleep_fn=sleeps.append)
    assert result.success is True
    assert sleeps == [15.0]


def test_with_retry_mixes_retry_after_and_backoff():
    """When some attempts have retry_after and others don't, both honored."""
    fn = _FakeFn([
        _transient_result(429, retry_after=10.0),  # explicit retry_after
        _transient_result(503),  # no retry_after — use backoff
        _ok_result(),
    ])
    sleeps: List[float] = []
    result = with_retry(fn, sleep_fn=sleeps.append)
    assert result.success is True
    # First sleep: 10s from retry_after. Second: starts from initial_backoff
    # (the backoff variable hasn't been advanced because retry_after won).
    assert sleeps == [10.0, 2.0]


# ---------------------------------------------------------------------------
# with_retry — exhaustion
# ---------------------------------------------------------------------------


def test_with_retry_exhausts_after_max_retries():
    """All transient → returns last failed result, no exception."""
    # max_retries=5 → 6 total invocations (1 initial + 5 retries).
    fn = _FakeFn([_transient_result(503)] * 6)
    sleeps: List[float] = []
    result = with_retry(fn, sleep_fn=sleeps.append)
    assert result.success is False
    assert result.retryable is True
    assert result.status_code == 503
    assert fn.calls == 6
    # 5 sleeps (one per retry); last attempt is the 6th call but no
    # sleep follows it (loop returns).
    assert len(sleeps) == 5
    assert sleeps == [2.0, 4.0, 8.0, 16.0, 32.0]


def test_with_retry_caps_backoff_at_max_backoff_s():
    """Backoff is capped at max_backoff_s even with many retries."""
    # Aggressive policy: max_retries=8, max_backoff_s=60.0
    # Sequence: 2, 4, 8, 16, 32, 60, 60, 60 (capped at 60)
    fn = _FakeFn([_transient_result(503)] * 9)
    sleeps: List[float] = []
    with_retry(fn, policy=RetryPolicy.aggressive(), sleep_fn=sleeps.append)
    assert sleeps == [2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0, 60.0]


# ---------------------------------------------------------------------------
# with_retry — non-retryable
# ---------------------------------------------------------------------------


def test_with_retry_does_not_retry_non_retryable():
    """retryable=False (e.g., 401 auth) → returns after one call."""
    fn = _FakeFn([_permanent_result(401)])
    sleeps: List[float] = []
    result = with_retry(fn, sleep_fn=sleeps.append)
    assert result.success is False
    assert result.retryable is False
    assert fn.calls == 1
    assert sleeps == []


def test_with_retry_with_none_policy_does_not_retry():
    """get_policy('none') → max_retries=0 → no retry even on transient."""
    fn = _FakeFn([_transient_result(503)])
    sleeps: List[float] = []
    result = with_retry(fn, policy=get_policy("none"), sleep_fn=sleeps.append)
    assert result.success is False
    assert fn.calls == 1
    assert sleeps == []


# ---------------------------------------------------------------------------
# with_retry — integration semantics
# ---------------------------------------------------------------------------


def test_with_retry_default_policy_is_used_when_none_passed():
    """Passing policy=None falls back to RetryPolicy.default()."""
    # Five 503s then success — default policy allows up to 5 retries.
    fn = _FakeFn([_transient_result(503)] * 5 + [_ok_result()])
    sleeps: List[float] = []
    result = with_retry(fn, policy=None, sleep_fn=sleeps.append)
    assert result.success is True
    assert fn.calls == 6


def test_with_retry_preserves_last_failure_attributes():
    """When retries exhaust, the returned result is the LAST failed call."""
    last_failure = _transient_result(503)
    last_failure.error_message = "final error"
    fn = _FakeFn([_transient_result(503)] * 5 + [last_failure])
    sleeps: List[float] = []
    result = with_retry(fn, sleep_fn=sleeps.append)
    assert result.error_message == "final error"


def test_with_retry_log_description_in_messages(caplog: pytest.LogCaptureFixture):
    """The `description` arg appears in log records."""
    import logging
    caplog.set_level(logging.INFO, logger="assemblyzero.utils.retry")
    fn = _FakeFn([_transient_result(503), _ok_result()])
    with_retry(fn, description="N3 LLD reviewer", sleep_fn=lambda s: None)
    # Both the failure log and success log mention the description.
    descriptions_seen = [r.getMessage() for r in caplog.records]
    assert any("N3 LLD reviewer" in m for m in descriptions_seen)
