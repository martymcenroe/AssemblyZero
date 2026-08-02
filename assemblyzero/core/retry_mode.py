"""Choose resume-in-place or clean-slate regeneration on a stage retry (#1941).

`run11b-issue4-234552`, attempt 2: every generated file logged
`Skipped (already exists)`. The stage retry re-entered the testing sub-workflow
against the same live worktree, resumed attempt 1's artifacts verbatim, and
reproduced its exact outcome -- 50/50 tests, 86.0% coverage, the same stagnation
halt.

For a **transient** failure -- a capacity storm mid-implementation -- resuming
in place is exactly right: do not redo paid work. For a **deterministic**
failure the replay converts `max_stage_retries` into a no-op loop where every
attempt is the same attempt. That is the mechanism behind runs that burn hours
producing identical results.

## The unknown case fails toward regeneration, deliberately

Replaying an attempt that cannot succeed costs a full stage and produces no new
information. Regenerating unnecessarily costs one stage and might. So anything
not positively identified as transient regenerates.

Note this differs from the retry-*eligibility* default, which treats an unmarked
failure as transient so that ordinary flakes still retry (#1463). Eligibility
asks "should we try again?"; this asks "should the next try be allowed to reuse
the last one's output?". The safe answer differs in each direction, so the two
defaults deliberately disagree.
"""

from __future__ import annotations

RESUMED = "RESUMED"
REGENERATED = "REGENERATED"


def retry_mode_for(stage_result: dict | None) -> str:
    """`RESUMED` only for a failure positively classified transient.

    Everything else -- deterministic, unclassified, missing, malformed --
    regenerates.
    """
    if not isinstance(stage_result, dict):
        return REGENERATED
    return RESUMED if stage_result.get("transient") is True else REGENERATED


def is_regeneration(retry_mode: str | None) -> bool:
    """True when generated artifacts from a prior attempt must not be reused."""
    return retry_mode == REGENERATED
