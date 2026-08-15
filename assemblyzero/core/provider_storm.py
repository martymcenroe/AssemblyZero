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

from collections.abc import Callable

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

#: #2405: the other diagnosis. Consecutive timeouts can mean the provider
#: stopped answering, or they can mean our own limit sits inside the call's
#: duration. Counting timeouts cannot tell these apart, because a timeout is
#: the one failure the caller times rather than the provider reports.
CEILING_MARKER = "TIMEOUT CEILING"

#: What the probe asks. Trivial by design: it is testing whether anyone is
#: home, not whether the model is any good.
PROBE_PROMPT = "Reply with the single word ok."

#: Probe budget. The measurement this was built from answered in 5.867s, and
#: the in-band evidence on #2405 showed a 16.9s success immediately after a
#: storm was declared, so a minute is generous without being a second wall.
PROBE_TIMEOUT_SECONDS = 60

_consecutive_timeouts = 0
_last_timeout_seconds = 0

#: What the last "ceiling" verdict was about. Deliberately NOT cleared by
#: reset(), because diagnose() calls reset() as part of reaching that verdict.
_last_ceiling_count = 0
_last_ceiling_seconds = 0


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


def diagnose(probe: Callable[[], bool]) -> str:
    """Decide whether a run of timeouts is weather or a wall (#2405).

    `probe` makes one trivial provider call and returns True if it answered.

    Returns ``"none"`` when no storm is pending, ``"ceiling"`` when the provider
    answered and the timeouts are therefore our own limit saturating, and
    ``"storm"`` when the provider did not answer.

    A ``"ceiling"`` verdict CLEARS the counter, and that is the point rather than
    a side effect: a provider that just answered has proven it is up, which is
    the same thing ``record_success`` means. Leaving the counter set would halt
    the roll as storm-bound on the strength of evidence we just refuted, and the
    launcher reads ``is_storm()`` rather than this return value.

    A probe that raises counts as a failed probe. If we cannot reach the
    provider to ask, we are not entitled to overturn the storm reading.

    The evidence this exists for: boostgauge #1's run declared PROVIDER STORM on
    three consecutive timeouts, and the very next call succeeded in 16.9s, with
    ten Claude calls completing in 6.3-31.6s interleaved through the same
    window. The provider was answering the entire time.
    """
    global _last_ceiling_count, _last_ceiling_seconds

    if not is_storm():
        return "none"
    try:
        answered = bool(probe())
    except Exception:
        answered = False
    if answered:
        # Preserve what the verdict was about before clearing it. reset() wipes
        # both counters, so a ceiling_message() called afterwards would
        # otherwise report "0 requests in a row", which is worse than useless
        # in the one message whose job is to explain what just happened.
        _last_ceiling_count = _consecutive_timeouts
        _last_ceiling_seconds = _last_timeout_seconds
        reset()
        return "ceiling"
    return "storm"


def ceiling_message(count: int | None = None, timeout_seconds: int | None = None) -> str:
    """Plain English for the cap-saturation verdict. No jargon, no exit codes.

    Defaults describe the most recent ``diagnose`` ceiling verdict, because by
    the time anyone asks for this message the live counter has been cleared.
    """
    count = _last_ceiling_count if count is None else count
    seconds = _last_ceiling_seconds if timeout_seconds is None else timeout_seconds
    duration = f"{seconds} seconds" if seconds else "its time limit"
    return (
        f"{CEILING_MARKER}: {count} requests in a row each ran past {duration}, "
        f"but a test request sent straight afterwards was answered normally. "
        f"The model provider is up, so this is our own time limit being too "
        f"short for the work rather than a provider outage. Raising "
        f"AZ_FILE_TIMEOUT_FLOOR is the lever; waiting will not help."
    )


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
