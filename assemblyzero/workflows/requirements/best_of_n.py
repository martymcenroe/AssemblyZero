"""Best-of-N drafts, judged by the mechanical gates (#2573).

The cap-halt pathology is a SERIAL-LOOP ARTIFACT. One drafter iterates
against one complaint stream until the cap, and an entire subsystem exists
to referee that loop: stagnation detection, grace clauses, ceiling regimes,
identical-complaint classifiers. Every one of those guards is correct. The
shape they guard is the problem.

## The breakeven, counted rather than assumed

The issue asked for the cost math to be verified before building. From
`tools/factory_report.py` over the boostgauge stores, 2026-08-01 onward:

* the spec loop reached **round 9** on #331 and **round 7** on #1;
* **five** cap grants fired, all on the spec stage;
* edit scripts applied 165 times against 14 fallbacks.

A revision round costs one drafter call plus one validation. N=3 costs
three drafter calls and three validations and zero revision rounds when any
candidate clears. Against loops that actually reached seven and nine
rounds, three is favourable. That is a counted comparison, not an estimate.

## What this does and does not replace

It replaces the MECHANICAL-GATE revision churn -- the rounds spent because
a draft failed a deterministic check, which is where the deadlocks lived.
It does not replace the reviewer's semantic revision loop: the winner
proceeds INTO review, never past it. Revisions remain edit-script only
(#2569).

## Scoring uses the real gates, never a proxy

A candidate is scored by running the actual mechanical validator and the
actual test-plan validator against a state carrying that candidate as its
draft. Re-implementing a cheaper approximation is how the score and the
gate drift apart, and a winner chosen by a proxy that the real gate then
rejects is worse than no selection at all.

## Ties are broken deterministically, and the reason matters

Equal failure counts fall back to candidate ORDER, so the first-generated
candidate wins. Not "longest", which rewards padding; not "shortest", which
rewards elision -- the exact behaviour #2559's eliding rewrite exhibited.
Order is arbitrary but it is stable, and stability is what makes a roll
replayable.

Default OFF. The serial path remains the default until live-roll data says
otherwise, which is the issue's own instruction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

#: `--draft-candidates 1` is the serial path exactly, not a degenerate
#: best-of-N: no scoring runs, no extra state is written, and the node
#: behaves byte-identically to the pre-#2573 code.
SERIAL = 1

#: A ceiling on candidates. Not a policy about what is useful -- a policy
#: about what a typo can cost. `--draft-candidates 30` on a live roll is
#: thirty drafter calls, and the flag is one keystroke from 3.
MAX_CANDIDATES = 5


@dataclass
class CandidateScore:
    """One candidate draft, judged by the full mechanical gate suite."""

    index: int
    draft: str
    #: Every gate failure, gate by gate. The COUNT decides the winner; the
    #: text is what makes the scored table worth reading.
    failures: dict[str, list[str]] = field(default_factory=dict)
    #: A candidate the drafter never produced (an LLM failure). It is
    #: scored as unusable rather than as perfect -- an empty draft trips no
    #: gate that reads content, so "no failures" would otherwise win.
    unusable: str = ""

    @property
    def failure_count(self) -> int:
        return sum(len(items) for items in self.failures.values())

    @property
    def clears(self) -> bool:
        return not self.unusable and self.failure_count == 0

    def summary(self) -> str:
        if self.unusable:
            return f"unusable: {self.unusable}"
        if not self.failures:
            return "clears every gate"
        return ", ".join(
            f"{gate} {len(items)}" for gate, items in sorted(self.failures.items())
        )


def score_candidate(
    index: int,
    draft: str,
    state: dict,
    *,
    mechanical: Callable[[dict], dict],
    test_plan: Callable[[dict], dict],
) -> CandidateScore:
    """Run the REAL gates against one candidate.

    The validators are injected rather than imported here so this module
    stays free of the node import cycle and so a test can drive it without
    standing up a workflow. Production passes the real ones.
    """
    score = CandidateScore(index=index, draft=draft)
    if not (draft or "").strip():
        score.unusable = "the drafter returned an empty draft"
        return score

    # A candidate is judged in ISOLATION: its own draft, and none of the
    # accumulated validation state from a sibling. Leaking `validation_errors`
    # between candidates would score candidate 3 for candidate 2's failures.
    probe = dict(state)
    probe["current_draft"] = draft
    probe["validation_errors"] = []
    probe["validation_warnings"] = []
    probe["test_plan_errors"] = []

    for gate_name, gate in (("mechanical", mechanical), ("test-plan", test_plan)):
        try:
            result = gate(probe) or {}
        except Exception as exc:  # noqa: BLE001
            # fail-open: a gate that CRASHES on a candidate must not kill the
            # roll, but the candidate is not thereby good. The crash is
            # recorded as a failure of that gate, so a candidate that breaks
            # a validator can never win by breaking it.
            score.failures[gate_name] = [f"gate raised {type(exc).__name__}: {exc}"]
            continue
        errors = [
            str(item)
            for key in ("validation_errors", "test_plan_errors")
            for item in (result.get(key) or [])
        ]
        if errors:
            score.failures[gate_name] = errors
    return score


def select_winner(scores: list[CandidateScore]) -> CandidateScore | None:
    """Fewest gate failures wins; ties go to the earlier candidate.

    Returns None only when every candidate is unusable, which is a halt
    condition for the caller rather than something to paper over with the
    least-bad empty draft.
    """
    usable = [score for score in scores if not score.unusable]
    if not usable:
        return None
    return min(usable, key=lambda s: (s.failure_count, s.index))


def render_score_table(scores: list[CandidateScore], winner_index: int) -> str:
    """The scored table the issue asks the log to carry."""
    lines = [
        f"    [BEST-OF-N] {len(scores)} candidate(s) scored by the mechanical "
        f"gates (#2573):"
    ]
    for score in scores:
        mark = "WINNER" if score.index == winner_index else "      "
        lines.append(
            f"      {mark} candidate {score.index}: "
            f"{score.failure_count} failure(s) -- {score.summary()}"
        )
    return "\n".join(lines)


def clamp_candidates(requested: Any) -> int:
    """A candidate count that cannot surprise the operator's wallet."""
    try:
        value = int(requested)
    except (TypeError, ValueError):
        # fail-open: toward the SERIAL path, which is the pre-#2573
        # behaviour and spends the fewest tokens. An unparseable candidate
        # count is a config typo, and the safe reading of a typo is "do the
        # cheap thing", never "do it five times". Falling closed here would
        # halt a roll over a malformed flag; falling open the other way
        # would let one spend the operator's quota.
        return SERIAL
    if value < SERIAL:
        return SERIAL
    return min(value, MAX_CANDIDATES)
