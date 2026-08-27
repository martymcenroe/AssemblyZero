"""When the spec review loop should stop, and which stop it was (#2382).

The exit condition counted iterations. A loop whose feedback repeats and a loop
whose feedback resolves-and-deepens are opposite processes, and a fixed cap of
three ended both with the same verdict.

Measured on run-issue1-152716 (boostgauge #1's first roll after conversion),
three REVISE verdicts persisted at ``006|009|012-readiness-verdict.md``:

- **Iteration 1** -- empty type-check assertions, an invented ``ValueError``
  behaviour, a mathematically inverted redline arc.
- **Iteration 2** -- *"All other assertions trace correctly ... successfully
  incorporates baseline-independent property assertions"*, then catches a band
  pixel sampled on the needle's own occluding axis.
- **Iteration 3** -- an unregistered pytest flag that crashes collection, five
  of six static elements missing, a literal-translation trap in the file
  instructions.

Each round resolved the previous round's list and surfaced a distinct, deeper
one. The loop was converging linearly on a first-contact visual domain, and the
cap killed it with exactly the verdict three rounds of identical failure earn.

What "converging" means here
----------------------------

Distinctness against **every** prior round, not just the last one. That is a
mechanical test, and it carries the substance of "prior items were resolved"
without asking a model to attest to it: an unresolved item comes back, because
the reviewer re-reads the whole document each round, and coming back is exactly
what the distinctness test catches.

The limit is worth stating plainly: a reviewer that silently *drops* an item it
should still be raising reads as convergence here. Nothing in the loop can tell
that from a fix, so the hard ceiling exists to bound what that costs rather than
to pretend it cannot happen.

The stagnation comparison itself is `same_blocking_issues` -- the identity check
the freeze protocol already uses (#503). This module widens what it is compared
against; it does not invent a second notion of sameness.
"""

from __future__ import annotations

from dataclasses import dataclass

#: A converging loop earns at most twice as many extra rounds as the base cap
#: allowed. Three is the base, so nine is the ceiling.
#:
#: The worst case is only reachable while every single round both resolves the
#: last one's list and finds something new -- which is the case worth paying
#: for. A loop that repeats itself halts at the first repeat, at any round, so
#: this multiplier never buys rounds of the failure it exists to end.
CEILING_MULTIPLIER = 3

#: Exit names. The halt says which one fired, because "the loop stopped" and
#: "the loop stopped WHILE STILL MAKING PROGRESS" are the two facts #2382 is
#: about and they used to print identically.
CONTINUE = "continue"
EXIT_STAGNATION = "stagnation"
EXIT_BASE_CAP = "base-cap-without-convergence"
EXIT_CEILING = "hard-ceiling"
EXIT_EMPTY = "empty-feedback"

CONVERGING = "converging"
STAGNATING = "stagnating"
EMPTY = "empty"


def hard_ceiling(max_iterations: int) -> int:
    """The most rounds a converging loop may run to."""
    try:
        base = max(0, int(max_iterations))
    except (TypeError, ValueError):
        base = 3
    return base * CEILING_MULTIPLIER


def regeneration_allowed(review_iteration: int, max_iterations: int) -> bool:
    """May a regeneration be granted at this counter? The ONE authority (#2536).

    The next revision will carry ``review_iteration + 1``, and #1775
    guarantees the draft generated AT the ceiling still gets its review — so
    the last grantable regeneration is the one that produces the ceiling
    itself. Every path that can send the graph back to N2 past the base cap
    consults this predicate; nothing else compares anything to the ceiling.

    The defect this retires (run-issue331-150920, 2026-08-26): the #2304
    grace clause checked only the BASE cap, so a completeness failure at
    iteration 9 — the ceiling, reached by honest converging rounds — was
    granted a grace revision carrying iteration 10, which the review guard
    then refused to review. 39m 49s of real work ended in the incoherent
    "the regeneration routing should have halted earlier" instead of the
    clean hard-ceiling report, and the grace draft was pure spend with
    unreviewable output.
    """
    return review_iteration < hard_ceiling(max_iterations)


@dataclass(frozen=True)
class Decision:
    """Whether to run another round, and the name of the exit if not."""

    should_continue: bool
    exit_name: str
    detail: str


def classify(current_feedback: str, prior_feedbacks: list[str]) -> str:
    """CONVERGING, STAGNATING or EMPTY for this round's feedback.

    Compared against every prior round rather than only the last, because a
    loop that alternates between two objections repeats without ever repeating
    consecutively -- and that is stagnation wearing motion.
    """
    from assemblyzero.core.verdict_schema import same_blocking_issues

    if not (current_feedback or "").strip():
        return EMPTY

    for prior in prior_feedbacks or []:
        if not (prior or "").strip():
            continue
        if same_blocking_issues(current_feedback, prior):
            return STAGNATING

    return CONVERGING


def decide(
    *,
    review_iteration: int,
    max_iterations: int,
    current_feedback: str,
    prior_feedbacks: list[str],
) -> Decision:
    """Whether a REVISE verdict earns another round.

    Only ever called for REVISE. APPROVED finalizes and BLOCKED halts; neither
    is a progress question.
    """
    ceiling = hard_ceiling(max_iterations)
    progress = classify(current_feedback, prior_feedbacks)
    rounds_seen = len(prior_feedbacks or []) + 1
    # #2516: on a resumed grant the counter restarts at zero while the
    # feedback history carries every prior grant's verdict (#2514 -- history
    # is memory, the counter is budget). The cap clauses must therefore count
    # in GRANT rounds, or the first resumed round prints "round 10 is within
    # the base cap of 3". In a single-grant run the two counts are equal, so
    # nothing changes for the ordinary case. `rounds_seen` stays the total
    # across grants and keeps naming the stagnation and ceiling rounds, where
    # the true total is the honest number.
    round_this_grant = review_iteration + 1

    if progress == EMPTY:
        return Decision(
            False,
            EXIT_EMPTY,
            "the reviewer returned REVISE with no feedback items, so there is "
            "nothing for another round to act on.",
        )

    if progress == STAGNATING:
        return Decision(
            False,
            EXIT_STAGNATION,
            f"round {rounds_seen} raises objections a previous round already "
            f"raised. Another round would re-read the same document and reach "
            f"the same wall.",
        )

    # Converging from here on.
    if review_iteration < max_iterations:
        return Decision(
            True,
            CONTINUE,
            f"round {round_this_grant} of this grant is within the base cap "
            f"of {max_iterations}.",
        )

    if review_iteration >= ceiling:
        return Decision(
            False,
            EXIT_CEILING,
            f"the loop was still converging at round {rounds_seen}, and stopped "
            f"only because it reached the hard ceiling of {ceiling} "
            f"({CEILING_MULTIPLIER}x the base cap of {max_iterations}). The last "
            f"verdict's items are outstanding and its draft is in lineage: a "
            f"resume continues from there rather than starting over (#2383).",
        )

    return Decision(
        True,
        CONTINUE,
        f"round {round_this_grant} of this grant resolved the previous "
        f"round's items and raised distinct ones, so the loop continues past "
        f"the base cap of {max_iterations} toward the ceiling of {ceiling}.",
    )


def describe_exit(decision: Decision, max_iterations: int) -> str:
    """The halt message, naming the exit rather than only the count."""
    return (
        f"Spec review stopped [{decision.exit_name}]: {decision.detail}"
        if not decision.should_continue
        else f"Spec review continues [{decision.exit_name}]: {decision.detail}"
    )
