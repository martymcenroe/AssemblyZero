"""When to stop polling a pull request (#2702).

Two backgrounded shell loops from the 2026-09-01 session were still running
twelve hours later, polling the GitHub API every thirty seconds for PRs that had
merged that night:

    until [ "$(gh api repos/.../pulls/2691 --jq '.mergeable_state')" = "clean" ]
    do sleep 30; done

**A merged PR reports `mergeable_state` as `unknown`, and never as `clean`.** So
the loop's only exit condition becomes unreachable at the moment its job is
done. It cannot notice that it has finished; it can only be killed. Both loops
surfaced as `2 shells still running` in a completion line, which the operator
read as two agents.

The documented merge sequence is where that loop comes from, so the same shape
is in every session that follows it and in twelve one-shot tools in `tools/`.

## The rule

A poll ends for one of three reasons, and only the first was ever checked:

* **ready** -- `clean`, or `unstable` when the caller accepts it. `unstable`
  means only non-required checks are failing and `gh pr merge` succeeds, which
  is what a PR that removes its own failing check looks like.
* **gone** -- `merged` or `closed`. The work is done or abandoned; there is
  nothing left to wait for, whatever `mergeable_state` says.
* **stuck** -- `dirty` (a conflict) or `behind` (needs a rebase). Neither
  resolves by waiting.

Anything else keeps polling, bounded. `blocked` is deliberately in that group:
it usually means the approving review has not landed yet, and it does resolve on
its own.

The decision is a pure function of one API payload so it can be tested against
the exact JSON shape a merged PR returns, which is what the twelve-hour loops
were never able to see.
"""

from __future__ import annotations

#: What one poll concluded.
VERDICT_READY = "ready"
VERDICT_GONE = "gone"
VERDICT_STUCK = "stuck"
VERDICT_WAIT = "wait"
VERDICTS: tuple[str, ...] = (
    VERDICT_READY, VERDICT_GONE, VERDICT_STUCK, VERDICT_WAIT,
)

#: Mergeable states a merge can proceed from. `unstable` is included by the
#: caller's choice, not by default: a PR that removes the very check making it
#: unstable can never reach `clean` (#2585's self-referential landings), while
#: an ordinary PR should wait for its checks.
STATE_CLEAN = "clean"
STATE_UNSTABLE = "unstable"

#: States that will not improve by waiting. Measured on the 2026-07-30 fleet
#: run: 328 polls sat in `behind` for about 55 minutes and four PRs burned the
#: whole budget without ever clearing.
STUCK_STATES: frozenset[str] = frozenset({"dirty", "behind"})

#: The three fields one `gh api repos/{repo}/pulls/{n}` call already returns.
#: Nothing extra is fetched to answer this; the old loop asked for one of them
#: and threw the other two away.
POLL_FIELDS: tuple[str, ...] = ("mergeable_state", "merged", "state")


def poll_verdict(payload: dict, *, accept_unstable: bool = False) -> str:
    """What this PR's current state says a poller should do.

    Terminal-first, deliberately. A merged PR's `mergeable_state` is `unknown`,
    so a reading that consulted the state before the terminal fields would put
    the finished case in the same bucket as "no information yet" -- which is
    exactly the bucket the twelve-hour loops sat in.
    """
    if payload.get("merged") is True:
        return VERDICT_GONE
    if str(payload.get("state") or "").lower() == "closed":
        return VERDICT_GONE
    state = str(payload.get("mergeable_state") or "").lower()
    if state == STATE_CLEAN or (accept_unstable and state == STATE_UNSTABLE):
        return VERDICT_READY
    if state in STUCK_STATES:
        return VERDICT_STUCK
    return VERDICT_WAIT


def describe(verdict: str, payload: dict) -> str:
    """One line a human can act on, naming the fields it read."""
    state = str(payload.get("mergeable_state") or "unknown")
    if verdict == VERDICT_GONE:
        how = "merged" if payload.get("merged") is True else "closed"
        return (
            f"the pull request is already {how}; nothing left to wait for "
            f"(mergeable_state reads {state!r}, which is what a merged PR "
            f"always reports)"
        )
    if verdict == VERDICT_READY:
        return f"mergeable_state is {state!r} -- ready to merge"
    if verdict == VERDICT_STUCK:
        return (
            f"mergeable_state is {state!r}, which does not resolve by waiting: "
            f"'dirty' is a conflict and 'behind' needs a rebase"
        )
    return f"mergeable_state is {state!r} -- still waiting"
