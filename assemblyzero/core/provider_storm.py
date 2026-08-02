"""Detect a provider timeout storm and back off instead of burning redraws (#2086).

2026-08-01 afternoon, run 2 of the boostgauge campaign: `claude -p timed out
after 602s` **eighteen times in one roll**, killing rolls 4-5 of phase 5. The
launcher's redraw logic treats every failed attempt identically -- self-heal and
immediately redraw -- so during a storm it burns a fresh ~90-minute attempt
straight into the same wall, repeatedly. With `--attempts 8` a storm can legally
consume an entire day producing nothing.

This is the last unfixed mechanism in the "12 hours with nothing to show"
family: the degraded box is #1920, the identical-replay loop is #1941, and
ambiguous specs are #2072/#2073.

## Design decisions

**Consecutive, not cumulative.** Three timeouts scattered across a long roll are
a flaky afternoon; three in a row are a wall. A single success resets the
counter, because it proves the provider is answering.

**Only timeouts count.** Other provider errors keep their existing
classification -- a 400 is a bug in what we sent, and waiting 15 minutes would
not improve it.

**The counter is per process, which is per roll.** Each roll is its own child
process, so module state is exactly roll-scoped with no plumbing. A new roll
starts at zero by construction rather than by remembering to reset.

**Storm is transient-class.** The roll halts, but the failure is not the
target repo's fault and must not be classified as one.
"""

from __future__ import annotations

#: Consecutive timeouts before the roll is declared storm-bound.
STORM_THRESHOLD = 3

#: Child exit code the launcher reads. Distinct from 0 (success) and 91 (a gate
#: problem), so the launcher can tell a storm from every other outcome without
#: parsing text.
STORM_EXIT_CODE = 92

#: Minutes to wait before each successive storm-classified redraw. The last
#: value is the cap and repeats for every attempt beyond it.
BACKOFF_MINUTES = (15, 30, 60)

STORM_MARKER = "PROVIDER STORM"

_consecutive_timeouts = 0
_last_timeout_seconds = 0


def reset() -> None:
    """Clear the counter. Called on a successful provider call."""
    global _consecutive_timeouts, _last_timeout_seconds
    _consecutive_timeouts = 0
    _last_timeout_seconds = 0


def record_timeout(timeout_seconds: int = 0) -> int:
    """Count one provider timeout. Returns the new consecutive count."""
    global _consecutive_timeouts, _last_timeout_seconds
    _consecutive_timeouts += 1
    _last_timeout_seconds = timeout_seconds or _last_timeout_seconds
    return _consecutive_timeouts


def record_success() -> None:
    """A completed call proves the provider is answering."""
    reset()


def consecutive_timeouts() -> int:
    return _consecutive_timeouts


def last_timeout_seconds() -> int:
    return _last_timeout_seconds


def is_storm() -> bool:
    return _consecutive_timeouts >= STORM_THRESHOLD


def backoff_minutes(storm_attempt: int) -> int:
    """Wait before the Nth consecutive storm-classified redraw.

    1 -> 15, 2 -> 30, 3 -> 60, and 60 for everything after: the cap holds
    rather than doubling into a wait longer than the workday it is protecting.
    """
    if storm_attempt < 1:
        return 0
    index = min(storm_attempt, len(BACKOFF_MINUTES)) - 1
    return BACKOFF_MINUTES[index]


def storm_message(count: int | None = None, timeout_seconds: int | None = None) -> str:
    """Plain English for the halt. No stage names, no exit codes, no jargon."""
    count = _consecutive_timeouts if count is None else count
    seconds = _last_timeout_seconds if timeout_seconds is None else timeout_seconds
    duration = f"{seconds} seconds" if seconds else "its time limit"
    return (
        f"{STORM_MARKER}: the model provider stopped answering — "
        f"{count} requests in a row each ran past {duration} with no reply. "
        f"Continuing would spend a fresh attempt on the same wall, so this run "
        f"is stopping here. Nothing is wrong with the code being built."
    )
