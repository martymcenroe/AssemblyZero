"""Retry utility for LLM-calling workflow nodes (#1071).

Wraps any callable that returns an `LLMCallResult` and retries on
retryable failures (5xx, 429, capacity, timeout) with exponential
backoff. The retryability decision is delegated to the call site via
the `retryable` flag on `LLMCallResult` — populated by the providers
in `assemblyzero/core/llm_provider.py` based on the typed exception
hierarchy in `assemblyzero/core/errors.py`. This module does NOT do
its own error classification; it trusts what the provider reports.

Why a wrapper rather than a decorator: most LLM-calling nodes already
build the call inline with closure over local context (system prompt,
schema kwargs, audit-trail callbacks). A `with_retry(lambda: ...)`
form keeps that ergonomics; a decorator would force the call to be
factored into a separate function.

Three policies ship: `default` (5 retries, 2s→32s backoff), `aggressive`
(8 retries, 60s cap), and `none` (no retry — preserves the current
fail-fast behavior). The policy name flows through workflow state via
`config_retry_policy`, set by the entry-point script's `--retry-policy`
flag.

Usage:

    from assemblyzero.utils.retry import with_retry, get_policy

    policy = get_policy(state.get("config_retry_policy", "default"))
    result = with_retry(
        lambda: reviewer.invoke(
            system_prompt=sys_prompt,
            content=user_prompt,
            response_schema=VERDICT_SCHEMA,
        ),
        policy=policy,
        description="N1 testing reviewer",
    )

    if result.success:
        ...

`with_retry` ALWAYS returns an `LLMCallResult` — the caller's existing
`if result.success: ...` branch handles both first-try success and
retry-exhaustion failure paths uniformly.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from assemblyzero.core.llm_provider import LLMCallResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetryPolicy:
    """How retries are scheduled for transient LLM failures.

    Attributes:
        max_retries: Number of retry attempts AFTER the first call. So
            max_retries=5 means up to 6 total invocations of fn (one
            initial + five retries). max_retries=0 disables retry.
        initial_backoff_s: Sleep before the FIRST retry. Subsequent
            retries multiply by `backoff_multiplier`, capped at
            `max_backoff_s`.
        max_backoff_s: Ceiling on backoff duration. Prevents the
            sequence from growing unboundedly with high max_retries.
        backoff_multiplier: Per-retry multiplier on the backoff. 2.0
            yields 2s → 4s → 8s → 16s → 32s for default policy.
    """
    max_retries: int
    initial_backoff_s: float
    max_backoff_s: float
    backoff_multiplier: float

    @classmethod
    def default(cls) -> "RetryPolicy":
        """Default — 5 retries, 2s → 4s → 8s → 16s → 32s.

        Tuned for the boostgauge speed-run: covers most Gemini 503
        bursts (typically 10-30s) without crossing into recording
        dead-air territory (>2 minutes total).
        """
        return cls(
            max_retries=5,
            initial_backoff_s=2.0,
            max_backoff_s=32.0,
            backoff_multiplier=2.0,
        )

    @classmethod
    def aggressive(cls) -> "RetryPolicy":
        """Aggressive — 8 retries, 60s cap. For longer outages."""
        return cls(
            max_retries=8,
            initial_backoff_s=2.0,
            max_backoff_s=60.0,
            backoff_multiplier=2.0,
        )

    @classmethod
    def none(cls) -> "RetryPolicy":
        """None — no retry. Preserves pre-#1071 fail-fast behavior."""
        return cls(
            max_retries=0,
            initial_backoff_s=0.0,
            max_backoff_s=0.0,
            backoff_multiplier=1.0,
        )


def get_policy(name: str) -> RetryPolicy:
    """Look up a named policy.

    Args:
        name: One of "default", "aggressive", "none".

    Returns:
        The matching RetryPolicy.

    Raises:
        ValueError: If name is unknown.
    """
    factories = {
        "default": RetryPolicy.default,
        "aggressive": RetryPolicy.aggressive,
        "none": RetryPolicy.none,
    }
    factory = factories.get(name)
    if factory is None:
        raise ValueError(
            f"Unknown retry policy: {name!r}. "
            f"Valid: {sorted(factories.keys())}"
        )
    return factory()


# ---------------------------------------------------------------------------
# with_retry
# ---------------------------------------------------------------------------


def with_retry(
    fn: Callable[[], LLMCallResult],
    policy: Optional[RetryPolicy] = None,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    description: str = "LLM call",
) -> LLMCallResult:
    """Call fn() and retry on retryable failures.

    Args:
        fn: A zero-argument callable that returns an LLMCallResult.
            Typically a lambda wrapping a provider's `.invoke()` call.
        policy: Retry schedule. Defaults to RetryPolicy.default().
        sleep_fn: Override for `time.sleep`. Tests inject a no-op.
        description: Used in log messages to identify the call site
            (e.g., "N3 LLD reviewer", "N4 implementer").

    Returns:
        The first successful LLMCallResult, OR the final failed
        LLMCallResult after retries are exhausted (whether the
        exhaustion is from max_retries or a non-retryable failure).
        Never raises; the caller's existing `if result.success` branch
        handles both cases uniformly.

    Behavior:
        - Success on first try → no retry, returns immediately.
        - Failure with `retryable=False` → no retry, returns immediately.
        - Failure with `retryable=True`, attempts left → sleep + retry.
        - All retries exhausted → returns the last failed result.

    Backoff calculation:
        - If the result has `retry_after` set (e.g., from a 429
          response with a Retry-After header), sleep for exactly that
          many seconds. The provider populates this from the typed
          RateLimitError's retry_after field.
        - Otherwise, use exponential backoff: initial_backoff_s,
          ×backoff_multiplier per retry, capped at max_backoff_s.
    """
    policy = policy or RetryPolicy.default()
    backoff = policy.initial_backoff_s
    last_result: Optional[LLMCallResult] = None

    for attempt in range(policy.max_retries + 1):
        result = fn()
        last_result = result

        # Success — return immediately.
        if result.success:
            if attempt > 0:
                logger.info(
                    "%s succeeded on retry %d/%d",
                    description, attempt, policy.max_retries,
                )
            return result

        # Permanent failure — don't retry.
        if not result.retryable:
            logger.info(
                "%s failed permanently (non-retryable, status=%s): %s",
                description, result.status_code, result.error_message,
            )
            return result

        # Transient failure — decide whether to retry.
        is_final_attempt = attempt >= policy.max_retries
        if is_final_attempt:
            logger.warning(
                "%s retries exhausted after %d attempt(s); last error: %s",
                description, attempt + 1, result.error_message,
            )
            return result

        # Compute sleep duration. Server-provided retry_after wins; else
        # fall back to exponential backoff capped at max_backoff_s.
        if result.retry_after is not None:
            sleep_for = float(result.retry_after)
        else:
            sleep_for = min(backoff, policy.max_backoff_s)
            backoff = min(
                backoff * policy.backoff_multiplier,
                policy.max_backoff_s,
            )

        logger.info(
            "%s transient failure (attempt %d/%d, status=%s); "
            "sleeping %.1fs then retrying: %s",
            description,
            attempt + 1,
            policy.max_retries + 1,
            result.status_code,
            sleep_for,
            result.error_message,
        )
        sleep_fn(sleep_for)

    # Unreachable — the loop body always returns or breaks. Defensive.
    assert last_result is not None
    return last_result
