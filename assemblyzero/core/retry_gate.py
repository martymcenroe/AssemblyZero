"""Classify a failure BEFORE paying for it again (#2423).

The operator's words are the requirement: a cock-up done three times is just an
expensive cock-up.

Every retry gate in the pipeline decided from one bit -- "is this failure
retryable" -- which is a property of the error TYPE and says nothing about
whether a second attempt can plausibly succeed. A wall-clock timeout on a call
that was still streaming is retryable in that sense and hopeless in every
sense that matters: the same prompt will run just as long the second time,
because what ran out was our own limit, not the provider's patience.

## The measurement

run-issue1-090001, 2026-08-15, counted from the log rather than estimated:

    7 payments of ~602s each = 4213.5s = 70.2 minutes, for zero artifacts.

That is worse than the shape #2423 was filed with (three payments, ~30
minutes), and it is worse for a structural reason worth stating: **the retries
were nested.** A per-file loop (`MAX_FILE_RETRIES = 2`) sat inside a stage loop
(`max_retries = 3`), so the cost was multiplicative, not additive. Fixing one
gate would have left the product in place. Every gate has to ask the same
question, which is why the question lives here.

## The four classes

``TRANSIENT``
    5xx, a connection drop, capacity. The provider had a bad moment. Retrying
    with backoff is correct and is the existing behavior.

``IDLE_TIMEOUT``
    The call went silent and was killed (#2405). A hang may be flukish, so one
    retry is allowed -- but only one.

``CEILING_TIMEOUT``
    The wall-clock backstop fired while the stream was still alive. The
    provider was answering the whole time; our own limit is simply shorter than
    the work. This is DETERMINISTIC: the same call will run long again. It
    halts with a named reason and the lever to pull, and is never re-paid.

``PERMANENT``
    Auth, billing, a malformed request. Retrying is guaranteed to fail.

## Fail-fast

`--fail-fast` sets attempts to one everywhere at once, for diagnosis sessions.
It travels to child processes by environment variable rather than by argument,
because the pipeline is three processes deep and a flag would have to be
threaded through every one of them -- which is how a mode ends up honoured in
some transports and silently ignored in others.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: A bad moment at the provider. Retry with backoff.
TRANSIENT = "transient"

#: The call went silent and was killed (#2405). One retry, no more.
IDLE_TIMEOUT = "idle_timeout"

#: The wall fired while the stream was alive. Deterministic. Never re-paid.
CEILING_TIMEOUT = "ceiling_timeout"

#: Auth, billing, malformed request. Retrying cannot help.
PERMANENT = "permanent"

#: Set by `--fail-fast`; read by every transport in every process.
ENV_FAIL_FAST = "AZ_FAIL_FAST"

#: Substrings the transport writes into a timeout message. These are a
#: contract with `llm_provider._invoke_claude_cli`, not prose scraping -- the
#: same reason `analyze_requirements._is_timeout` matches on "timed out".
_CEILING_HINTS = (
    "while still producing output",  # #2405's wall message
    "timeout ceiling",
)
_IDLE_HINTS = (
    "with no output",  # #2405's idle message
    "idle limit",
)


def fail_fast_enabled() -> bool:
    """Is this a diagnosis session, where every defect is paid for once?

    Anything other than an explicit falsey word counts as on: an operator who
    typed the flag meant it, and a mode that silently disengages on an
    unexpected value is worse than one that never existed.
    """
    raw = os.environ.get(ENV_FAIL_FAST, "").strip().lower()
    if not raw:
        return False
    return raw not in ("0", "false", "no", "off")


def set_fail_fast(enabled: bool) -> None:
    """Turn fail-fast on or off for this process and everything it spawns."""
    if enabled:
        os.environ[ENV_FAIL_FAST] = "1"
    else:
        os.environ.pop(ENV_FAIL_FAST, None)


def classify_failure(
    error_message: str | None,
    *,
    retryable: bool = True,
    timeout_kind: str = "",
) -> str:
    """Which of the four classes this failure belongs to.

    `timeout_kind` is the transport's own structured answer ("idle" or "wall")
    and is trusted first when present. The message is consulted only as the
    fallback, for results that crossed a process or predate the field.
    """
    if timeout_kind == "idle":
        return IDLE_TIMEOUT
    if timeout_kind == "wall":
        return CEILING_TIMEOUT

    message = (error_message or "").lower()
    if any(hint in message for hint in _CEILING_HINTS):
        return CEILING_TIMEOUT
    if any(hint in message for hint in _IDLE_HINTS):
        return IDLE_TIMEOUT
    if not retryable:
        return PERMANENT
    if "timed out" in message:
        # A timeout with no discriminating detail. Treated as the idle case --
        # one retry, not none and not three -- because the pre-#2405 transports
        # and every non-Claude provider produce this shape, and refusing to
        # retry any of them would be a larger behavior change than this issue
        # asked for.
        return IDLE_TIMEOUT
    return TRANSIENT


#: How many TOTAL attempts each class is ever worth, before any policy the
#: caller adds on top. The gate takes the minimum of this and the caller's own
#: budget, so a class can lower a limit but never raise one.
_ATTEMPT_CEILING = {
    TRANSIENT: None,      # the caller's policy governs; backoff is correct here
    IDLE_TIMEOUT: 2,      # the first try plus one more
    CEILING_TIMEOUT: 1,   # deterministic: never re-paid
    PERMANENT: 1,
}


@dataclass(frozen=True)
class RetryDecision:
    """Whether to pay again, and the sentence explaining why not."""

    retry: bool
    failure_class: str
    reason: str
    backoff: bool = False

    def __bool__(self) -> bool:  # pragma: no cover - convenience only
        return self.retry


def should_retry(
    failure_class: str,
    attempts_made: int,
    *,
    max_attempts: int,
    fail_fast: bool | None = None,
) -> RetryDecision:
    """Decide retry-versus-halt from the failure SHAPE, before spending.

    Args:
        failure_class: one of the four constants above.
        attempts_made: how many attempts have already been paid for (>= 1).
        max_attempts: the caller's own total-attempt budget.
        fail_fast: override the environment, for tests.
    """
    if fail_fast is None:
        fail_fast = fail_fast_enabled()

    if fail_fast:
        return RetryDecision(
            False, failure_class,
            "fail-fast is on, so each defect is paid for exactly once "
            "(--fail-fast). Fix the cause and relaunch.",
        )

    if failure_class == CEILING_TIMEOUT:
        return RetryDecision(
            False, failure_class,
            "this call ran past our own time limit while the provider was "
            "STILL ANSWERING, so the limit is too short for the work rather "
            "than the provider being down. The same call will run just as "
            "long again -- retrying spends the same money for the same "
            "result. Raise AZ_FILE_TIMEOUT_FLOOR (or shrink the ask) and "
            "relaunch; the passed stages resume rather than re-run.",
        )

    if failure_class == PERMANENT:
        return RetryDecision(
            False, failure_class,
            "this failure cannot succeed on a retry (auth, billing, or a "
            "malformed request). Fix the cause and relaunch.",
        )

    ceiling = _ATTEMPT_CEILING.get(failure_class)
    budget = max_attempts if ceiling is None else min(max_attempts, ceiling)

    if attempts_made >= budget:
        if failure_class == IDLE_TIMEOUT and budget < max_attempts:
            return RetryDecision(
                False, failure_class,
                "the call went silent and was killed once already. A hang "
                "gets one retry, not a third payment -- a repeat is a wall, "
                "not bad luck. Diagnose and relaunch.",
            )
        return RetryDecision(
            False, failure_class,
            f"all {budget} attempt(s) are spent.",
        )

    return RetryDecision(
        True, failure_class,
        f"attempt {attempts_made + 1} of {budget}",
        backoff=(failure_class == TRANSIENT),
    )


def retry_spend_line(
    description: str,
    attempts_made: int,
    budget: int,
    failure_class: str,
    cumulative_cost: float,
    *,
    sleeping: float | None = None,
) -> str:
    """The retry line, carrying the running total (#2423 requirement 3).

    The price of a retry policy belongs in the log the operator is watching,
    not on a bill discovered later.
    """
    parts = [
        f"    [RETRY] {description}: attempt {attempts_made + 1}/{budget}",
        f"class={failure_class}",
    ]
    if sleeping is not None:
        parts.append(f"backoff={sleeping:.1f}s")
    parts.append(f"cumulative=${cumulative_cost:.2f}")
    return " ".join(parts)


def halt_line(
    description: str, decision: RetryDecision, cumulative_cost: float
) -> str:
    """The halt line, naming the class and the total already spent."""
    return (
        f"    [HALT] {description} will NOT be retried "
        f"({decision.failure_class}): {decision.reason} "
        f"[cumulative=${cumulative_cost:.2f}]"
    )
