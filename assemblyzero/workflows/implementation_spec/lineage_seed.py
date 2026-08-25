"""Resume the spec review loop where it died, not from zero (#2383).

The spec stage died at the review cap after three rounds of measurably
converging feedback. Draft 4 existed, the third verdict carried a four-item
worklist, and every artifact was persisted. The printed resume --
``orchestrate --issue 1 --resume-from spec`` -- restarted the stage from
iteration 0 with a fresh draft, because each run claims a NEW run-scoped
lineage directory and `generate_spec` recovers a draft by globbing the
directory it was handed. A fresh directory holds nothing, so the glob finds
nothing, so the run draws again.

Three rounds of paid convergence discarded, the same first-round defect classes
likely to recur, and a fresh cap likely to die the same way.

The #2233 principle -- repair the artifact, never regenerate the attempt --
stops one level short of this: it governs the finalize step inside a run, while
stage RESUME regenerates everything.

What gets seeded, and why each piece
------------------------------------

``generate_spec`` treats a call as a revision when it has BOTH a draft and
feedback (``is_revision = existing_draft and (review_feedback or
completeness_issues)``). Seeding both is therefore not two conveniences but the
one condition that makes the resumed round a revision rather than a redraw.

``review_feedback_history`` is seeded too, and it matters more than it looks:
#2382 judges convergence against every prior round. A resumed run without that
history is a run that cannot tell its first new verdict from a repeat of one it
never saw, so it would read as converging no matter what it said.

What this does NOT decide
-------------------------

Whether resuming is appropriate at all. That judgement already exists upstream
and is deliberately left there: ``speedrun_roll.resume_plan`` refuses a resume
whose draft predates an issue edit or a binding-doc change, and ``--fresh``
skips planning entirely. Both express themselves the same way -- no
``--resume-from`` reaches the orchestrator -- so seeding keyed on an actual
resume inherits both rules instead of duplicating them into a second copy that
can drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DRAFT_GLOB = "*-spec-draft.md"
VERDICT_GLOB = "*-readiness-verdict.md"


@dataclass(frozen=True)
class Seed:
    """One prior run's resumable state."""

    run_dir: str
    draft: str
    draft_path: str
    feedback: str
    feedback_path: str
    #: Every verdict the prior run produced, oldest first, so #2382's
    #: convergence check is not blind on the resumed round.
    prior_feedbacks: list[str] = field(default_factory=list)

    @property
    def rounds_completed(self) -> int:
        return len(self.prior_feedbacks)


def prior_run_dirs(spec_lineage: Path, exclude: Path | None = None) -> list[Path]:
    """Run directories under an issue's spec lineage, oldest first.

    Named by ``make_run_id()``, which is a zero-padded UTC timestamp, so name
    order is time order. A collision suffix (``-1``, ``-2``) sorts after the
    directory it collided with, which is also its real order.
    """
    if not spec_lineage.is_dir():
        return []
    resolved_exclude = exclude.resolve() if exclude else None
    found = []
    for path in sorted(spec_lineage.iterdir()):
        if not path.is_dir():
            continue
        if resolved_exclude and path.resolve() == resolved_exclude:
            continue
        found.append(path)
    return found


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def seed_from_lineage(
    spec_lineage: Path, exclude: Path | None = None
) -> Seed | None:
    """The most recent prior run's resumable state, or None.

    None means there is nothing to resume onto and the caller should draw
    fresh -- which is always safe, and is what every failure path here returns
    rather than a half-seed. A draft with no verdict is such a failure: without
    feedback the seeded round is not a revision, so it would redraw anyway while
    reporting that it resumed.

    ``exclude`` is the current run's own directory, which the caller has already
    created and which must never be read as a prior run.
    """
    for run_dir in reversed(prior_run_dirs(spec_lineage, exclude)):
        drafts = sorted(run_dir.glob(DRAFT_GLOB))
        verdicts = sorted(run_dir.glob(VERDICT_GLOB))
        if not drafts or not verdicts:
            continue

        draft_text = _read(drafts[-1])
        feedback_text = _read(verdicts[-1])
        if not draft_text.strip() or not feedback_text.strip():
            continue

        return Seed(
            run_dir=str(run_dir),
            draft=draft_text,
            draft_path=str(drafts[-1]),
            feedback=feedback_text,
            feedback_path=str(verdicts[-1]),
            prior_feedbacks=[
                text
                for text in (_read(v) for v in verdicts)
                if text.strip()
            ],
        )
    return None


def resume_payload(seed: Seed) -> dict:
    """The graph-state seed for a resumed spec grant (#2516).

    ``spec_draft`` + ``review_feedback`` are the pair that makes the first
    resumed round a REVISION of the paid draft -- the halted run's final
    readiness verdict reaches the first regeneration verbatim, so no round
    is respent rediscovering the reviewer's last word.

    ``review_iteration`` is **0**, not ``seed.rounds_completed``. The #2514
    ruling: the cap regime is per LAUNCH, not per issue lifetime -- the
    operator's explicit relaunch is the spend grant, worth exactly one more
    normal regime (base cap 3, the still-converging continuation rules
    unchanged, ceiling 3x). Restoring the prior grant's counter made the
    first resumed round iteration 10 against a ceiling of 9: BLOCKED before
    any model call, three instant outer attempts, 56.8 seconds
    (run-issue331-102255) -- and the review guard's "exceeds the hard
    ceiling" state is unreachable from a resume precisely because nothing
    seeds an exhausted counter any more.

    ``review_feedback_history`` still carries EVERY prior grant's verdict:
    #2382's stagnation check stays sighted across grants, so an objection
    from the old grant coming back halts as a repeat rather than reading as
    convergence. History is memory; the counter is budget. They separate
    here deliberately.
    """
    return {
        "spec_draft": seed.draft,
        "review_feedback": seed.feedback,
        "review_feedback_history": list(seed.prior_feedbacks),
        "review_iteration": 0,
    }


def describe(seed: Seed) -> str:
    """What the operator should see when a resume reuses paid work."""
    return (
        f"    [spec] resuming from lineage: {Path(seed.draft_path).name} "
        f"({len(seed.draft.splitlines())} lines) with "
        f"{Path(seed.feedback_path).name}'s items as feedback, after "
        f"{seed.rounds_completed} completed review round(s) in "
        f"{Path(seed.run_dir).name}; the review cap regime starts fresh for "
        f"this grant (#2514)."
    )
