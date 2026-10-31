"""A call ``with_retry`` gives up on is an ERROR on stderr and in the log (ADR 0236, #3585).

``assemblyzero.utils.retry.with_retry`` returns the last failed
``LLMCallResult`` when it stops: retries exhausted, or a failure not worth
retrying. That result is the declared contract, and every caller routes a
failure to HALT. What was wrong is how it said so: the halt line went to stdout
and the log record was INFO, so the moment the run gave up was not loud. It is
now an ERROR line on stderr and an ERROR log record naming the call, the
attempts, the failure class and the cause.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import logging

import pytest

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.utils.retry import RetryPolicy, with_retry


def _failed(message: str, *, retryable: bool, status: int) -> LLMCallResult:
    return LLMCallResult(
        success=False,
        response=None,
        raw_response=None,
        error_message=message,
        provider="anthropic",
        model_used="opus",
        duration_ms=10,
        attempts=1,
        status_code=status,
        retryable=retryable,
    )


def _ok() -> LLMCallResult:
    return LLMCallResult(
        success=True, response="ok", raw_response="ok", error_message=None,
        provider="anthropic", model_used="opus", duration_ms=10, attempts=1,
    )


def test_220_a_failure_not_worth_retrying_is_an_error_on_stderr(capsys, caplog, operator_alerts):
    caplog.set_level(logging.INFO, logger="assemblyzero.utils.retry")

    result = with_retry(
        lambda: _failed("HTTP 401 auth", retryable=False, status=401),
        policy=RetryPolicy.default(), sleep_fn=lambda _s: None,
        description="N1 testing reviewer",
    )

    assert result.success is False, "the failed result is still the contract"
    err = capsys.readouterr().err
    assert "ERROR" in err
    assert "N1 testing reviewer" in err
    assert "HTTP 401 auth" in err
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors and "N1 testing reviewer" in errors[0].getMessage()


def test_220_retries_exhausted_is_an_error_on_stderr(capsys, operator_alerts):
    calls = []

    def _transient():
        calls.append(1)
        return _failed("HTTP 503 transient", retryable=True, status=503)

    result = with_retry(
        _transient,
        policy=RetryPolicy(max_retries=2, initial_backoff_s=0, max_backoff_s=0, backoff_multiplier=1),
        sleep_fn=lambda _s: None,
        description="N3 LLD reviewer",
    )

    assert result.success is False
    err = capsys.readouterr().err
    assert "ERROR" in err and "N3 LLD reviewer" in err
    assert "HTTP 503 transient" in err


def test_a_success_is_quiet_on_stderr(capsys, operator_alerts):
    result = with_retry(_ok, sleep_fn=lambda _s: None, description="N1")

    assert result.success is True
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("retryable", [True, False])
def test_the_failed_result_is_returned_not_raised(retryable, operator_alerts, capsys):
    result = with_retry(
        lambda: _failed("boom", retryable=retryable, status=500),
        policy=RetryPolicy.none(), sleep_fn=lambda _s: None,
    )
    assert result.success is False
