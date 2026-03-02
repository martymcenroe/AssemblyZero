"""Unified retry contract for API calls.

Issue #542: Replaces 4 different retry implementations scattered across the
codebase with a single ``with_retry`` function that respects the typed error
hierarchy from ``assemblyzero.core.errors``.

Key behaviours:
- Non-retryable errors (billing, auth, 404) raise immediately — zero retries.
- ``TimeoutError_`` gets at most 1 retry regardless of ``max_retries``.
- ``RateLimitError`` with ``retry_after`` overrides computed backoff.
- Exponential backoff with jitter: ``min(base * 2^attempt * (1 +/- jitter), max_delay)``.
- Every attempt is logged to stdout for observability.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from assemblyzero.core.errors import APIError, RateLimitError, TimeoutError_

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for ``with_retry``."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: float = 0.2  # +/- 20%


def with_retry(
    fn: Callable[[], T],
    config: RetryConfig | None = None,
) -> T:
    """Call *fn* with automatic retry on retryable errors.

    Args:
        fn: Zero-argument callable that performs the API call.
        config: Retry parameters.  Defaults to ``RetryConfig()``.

    Returns:
        The return value of *fn* on success.

    Raises:
        APIError: The last error if all retries are exhausted, or immediately
                  if the error is non-retryable.
    """
    if config is None:
        config = RetryConfig()

    last_error: APIError | None = None

    for attempt in range(1 + config.max_retries):
        try:
            return fn()
        except APIError as exc:
            last_error = exc

            # Non-retryable → raise immediately
            if not exc.retryable:
                print(
                    f"    [RETRY] non-retryable {exc.__class__.__name__}: {exc}"
                )
                raise

            # TimeoutError_ → max 1 retry
            if isinstance(exc, TimeoutError_) and attempt >= 1:
                print(
                    f"    [RETRY] {exc.__class__.__name__} already retried once, "
                    f"giving up"
                )
                raise

            # Last attempt — don't sleep, just raise
            if attempt == config.max_retries:
                break

            # Compute delay
            delay = _compute_delay(exc, attempt, config)
            print(
                f"    [RETRY] attempt {attempt + 1}/{config.max_retries + 1} "
                f"for {exc.__class__.__name__}: {exc} — "
                f"retrying in {delay:.1f}s"
            )
            time.sleep(delay)

    # All retries exhausted
    assert last_error is not None
    raise last_error


def _compute_delay(
    exc: APIError,
    attempt: int,
    config: RetryConfig,
) -> float:
    """Compute backoff delay for a given attempt.

    ``RateLimitError.retry_after`` takes priority over computed backoff.
    """
    # Honour Retry-After header from 429
    if isinstance(exc, RateLimitError) and exc.retry_after is not None:
        return max(exc.retry_after, 0.0)

    # Exponential backoff with jitter
    base = config.base_delay * (2**attempt)
    jitter = random.uniform(-config.jitter, config.jitter)  # noqa: S311
    delay = base * (1 + jitter)
    return min(delay, config.max_delay)
