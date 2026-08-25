"""A spec resume continues the loop it paid for (#2383).

run-issue1-152716 died at the review cap with draft 4 on disk and a four-item
worklist in its third verdict. The printed resume restarted at iteration 0 with
a fresh draft, because every run claims a NEW run-scoped lineage directory and
`generate_spec` recovers a draft by globbing the directory it was handed -- a
fresh one holds nothing.

The lineage layout here is that run's, exactly: drafts at 001/004/007/010 and
verdicts at 006/009/012. Two drafts precede the first verdict (a validation
loop-back regenerates without a review round), which is precisely the shape
that makes "the last draft" and "the last verdict" different index arithmetic
and worth testing rather than assuming.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.workflows.implementation_spec import lineage_seed as ls  # noqa: E402

VERDICTS = ROOT / "tests" / "fixtures" / "spec_review"


def real_verdict(n: str) -> str:
    return (VERDICTS / f"run-issue1-152716-{n}-readiness-verdict.md").read_text(
        encoding="utf-8"
    )


def build_run(run_dir: Path, drafts: int = 4, verdicts=("006", "009", "012")):
    """The real run's file layout, with identifiable draft bodies."""
    run_dir.mkdir(parents=True, exist_ok=True)
    for index, seq in enumerate(("001", "004", "007", "010")[:drafts], start=1):
        (run_dir / f"{seq}-spec-draft.md").write_text(
            f"# Implementation Spec\n\nDRAFT {index}\n", encoding="utf-8"
        )
    for seq in verdicts:
        (run_dir / f"{seq}-readiness-verdict.md").write_text(
            real_verdict(seq), encoding="utf-8"
        )
    return run_dir


@pytest.fixture
def lineage(tmp_path) -> Path:
    """An issue's spec lineage holding the dead run, plus this run's empty dir."""
    root = tmp_path / "docs" / "lineage" / "active" / "1-implspec"
    build_run(root / "2026-08-14T20-34-14Z")
    (root / "2026-08-14T22-00-00Z").mkdir(parents=True)  # the resumed run
    return root


class TestItStartsFromTheLastDraftNotTheFirst:
    """#2383's acceptance, stated in its own terms."""

    def test_the_seed_is_draft_four(self, lineage):
        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        assert seed is not None
        assert "DRAFT 4" in seed.draft
        assert seed.draft_path.endswith("010-spec-draft.md")

    def test_it_is_emphatically_not_draft_one(self, lineage):
        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        assert "DRAFT 1" not in seed.draft
        assert not seed.draft_path.endswith("001-spec-draft.md")

    def test_the_feedback_is_the_last_verdict(self, lineage):
        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        assert seed.feedback_path.endswith("012-readiness-verdict.md")
        assert "unregistered" in seed.feedback or "pytest_addoption" in seed.feedback

    def test_every_verdict_is_carried_as_history(self, lineage):
        """#2382 judges convergence against every prior round. A resumed run
        without this history cannot tell its first new verdict from a repeat of
        one it never saw, so it would read as converging whatever it said."""
        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        assert seed.rounds_completed == 3
        assert seed.prior_feedbacks[0] == real_verdict("006")
        assert seed.prior_feedbacks[-1] == real_verdict("012")

    def test_the_seeded_history_makes_a_repeat_detectable(self, lineage):
        """The point of carrying it: a resumed round that re-raises round one's
        objections is stagnation, and must be seen as such."""
        from assemblyzero.workflows.implementation_spec import review_progress as rp

        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        assert (
            rp.classify(real_verdict("006"), seed.prior_feedbacks) == rp.STAGNATING
        )


class TestTheSeedIsAValidRevisionInput:
    """`generate_spec` treats a call as a revision only when it has BOTH a draft
    and feedback. Seeding both is the one condition that makes the resumed round
    a revision rather than a redraw."""

    def test_both_halves_are_present_and_non_empty(self, lineage):
        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        is_revision = bool(seed.draft and seed.feedback)
        assert is_revision

    def test_a_draft_with_no_verdict_is_no_seed_at_all(self, tmp_path):
        """Half a seed is worse than none: without feedback the round is not a
        revision, so it would redraw anyway while reporting that it resumed."""
        root = tmp_path / "1-implspec"
        build_run(root / "2026-08-14T20-34-14Z", drafts=4, verdicts=())
        assert ls.seed_from_lineage(root) is None

    def test_an_empty_draft_file_is_not_seeded(self, tmp_path):
        root = tmp_path / "1-implspec"
        run = build_run(root / "2026-08-14T20-34-14Z")
        for draft in run.glob(ls.DRAFT_GLOB):
            draft.write_text("   \n", encoding="utf-8")
        assert ls.seed_from_lineage(root) is None


class TestWhichRunItReadsFrom:
    def test_the_current_run_is_never_read_as_a_prior_one(self, lineage):
        current = lineage / "2026-08-14T22-00-00Z"
        assert current not in ls.prior_run_dirs(lineage, exclude=current)

    def test_the_most_recent_prior_run_wins(self, tmp_path):
        root = tmp_path / "1-implspec"
        build_run(root / "2026-08-13T10-00-00Z")
        newer = build_run(root / "2026-08-14T20-34-14Z")
        for draft in newer.glob(ls.DRAFT_GLOB):
            draft.write_text("NEWER RUN\n", encoding="utf-8")

        seed = ls.seed_from_lineage(root)
        assert "NEWER RUN" in seed.draft

    def test_a_collision_suffixed_run_sorts_after_the_one_it_collided_with(
        self, tmp_path
    ):
        """make_run_id is second-resolution, so two attempts in one second get
        a `-1` suffix. That suffix IS the later run."""
        root = tmp_path / "1-implspec"
        build_run(root / "2026-08-14T20-34-14Z")
        later = build_run(root / "2026-08-14T20-34-14Z-1")
        for draft in later.glob(ls.DRAFT_GLOB):
            draft.write_text("SUFFIXED RUN\n", encoding="utf-8")

        seed = ls.seed_from_lineage(root)
        assert "SUFFIXED RUN" in seed.draft

    def test_it_skips_a_barren_newer_run_for_a_usable_older_one(self, tmp_path):
        """A run that died before producing a verdict has nothing to resume;
        the round that DID converge is the one worth continuing."""
        root = tmp_path / "1-implspec"
        build_run(root / "2026-08-13T10-00-00Z")
        (root / "2026-08-14T20-34-14Z").mkdir(parents=True)

        assert ls.seed_from_lineage(root) is not None

    def test_no_lineage_at_all_is_none_not_an_error(self, tmp_path):
        assert ls.seed_from_lineage(tmp_path / "nope") is None
        assert ls.prior_run_dirs(tmp_path / "nope") == []


class TestSeedingIsKeyedOnAnActualResume:
    """Whether resuming is appropriate is decided upstream -- resume_plan
    refuses a stale draft, --fresh skips planning -- and both express
    themselves as no --resume-from arriving. Seeding keyed on the resume
    inherits both rules instead of duplicating them."""

    def test_the_orchestrator_records_which_stage_it_resumed_into(self):
        source = (
            ROOT / "assemblyzero" / "workflows" / "orchestrator" / "graph.py"
        ).read_text(encoding="utf-8")
        assert 'state_dict["resumed_from"] = resume_stage' in source
        assert 'state["resumed_from"] = ""' in source, "explicit on the fresh path"

    def test_a_fresh_run_carries_no_resume_marker(self):
        from assemblyzero.workflows.orchestrator.config import get_default_config
        from assemblyzero.workflows.orchestrator.state import create_initial_state

        state = create_initial_state(1, get_default_config())
        assert state["resumed_from"] == ""

    def test_the_marker_is_not_current_stage(self):
        """current_stage reaches every stage in the normal course, so it cannot
        tell a resume from a pipeline arriving there."""
        source = (
            ROOT / "assemblyzero" / "workflows" / "orchestrator" / "stages.py"
        ).read_text(encoding="utf-8")
        spec_stage = source.split("def run_spec_stage", 1)[1].split("\ndef ", 1)[0]
        assert 'state.get("resumed_from") == "spec"' in spec_stage

    def test_the_stage_seeds_through_the_shared_payload(self):
        """#2516 moved the payload into lineage_seed.resume_payload so the
        counter ruling (#2514) has one home; the stage must use it rather
        than rebuilding the dict inline, where the two could drift."""
        source = (
            ROOT / "assemblyzero" / "workflows" / "orchestrator" / "stages.py"
        ).read_text(encoding="utf-8")
        spec_stage = source.split("def run_spec_stage", 1)[1].split("\ndef ", 1)[0]
        assert "resumed_payload = resume_payload(seed) if seed else {}" in spec_stage

    def test_the_payload_carries_the_four_fields_the_loop_needs(self, lineage):
        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        payload = ls.resume_payload(seed)
        assert payload["spec_draft"] == seed.draft
        assert payload["review_feedback"] == seed.feedback
        assert payload["review_feedback_history"] == seed.prior_feedbacks
        assert "review_iteration" in payload

    def test_the_stage_excludes_its_own_run_directory(self):
        source = (
            ROOT / "assemblyzero" / "workflows" / "orchestrator" / "stages.py"
        ).read_text(encoding="utf-8")
        assert "exclude=Path(audit_dir_str)" in source


class TestItSaysWhatItReused:
    def test_the_description_names_the_draft_the_verdict_and_the_rounds(
        self, lineage
    ):
        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        text = ls.describe(seed)
        assert "010-spec-draft.md" in text
        assert "012-readiness-verdict.md" in text
        assert "3 completed review round" in text

    def test_the_description_says_the_cap_regime_is_fresh(self, lineage):
        """#2515's operator followed a resume hint with no way to know what it
        carried. The narration now states the grant terms."""
        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        assert "cap regime starts fresh" in ls.describe(seed)


class TestTheResumedGrantStartsFresh:
    """#2516, implementing the #2514 ruling: per-launch cap regime.

    Restoring the prior grant's counter made the first resumed round
    iteration 10 against a ceiling of 9 -- BLOCKED before any model call,
    56.8 seconds, no work (run-issue331-102255).
    """

    def test_the_counter_is_zero_not_the_prior_grants_count(self, lineage):
        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        assert seed.rounds_completed == 3, "precondition: prior rounds exist"

        assert ls.resume_payload(seed)["review_iteration"] == 0

    def test_the_seeded_counter_cannot_trip_the_ceiling_guard(self, lineage):
        """The 'exceeds the hard ceiling' state must be unreachable from a
        resume: the guard fires on iteration > ceiling, and the grant's
        first review arrives at iteration 1 after the revision increment."""
        from assemblyzero.workflows.implementation_spec.review_progress import (
            hard_ceiling,
        )

        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        first_review_iteration = ls.resume_payload(seed)["review_iteration"] + 1

        assert first_review_iteration <= hard_ceiling(3)

    def test_history_still_carries_every_prior_grant_round(self, lineage):
        """History is memory, the counter is budget: #2382's stagnation check
        must stay sighted across grants, so an objection from the old grant
        coming back halts as a repeat instead of reading as convergence."""
        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        payload = ls.resume_payload(seed)

        assert len(payload["review_feedback_history"]) == 3
        assert payload["review_feedback_history"] == seed.prior_feedbacks

    def test_a_prior_grant_objection_returning_still_stagnates(self, lineage):
        from assemblyzero.workflows.implementation_spec.review_progress import (
            EXIT_STAGNATION,
            decide,
        )

        seed = ls.seed_from_lineage(lineage, exclude=lineage / "2026-08-14T22-00-00Z")
        payload = ls.resume_payload(seed)

        decision = decide(
            review_iteration=payload["review_iteration"] + 1,
            max_iterations=3,
            current_feedback=seed.prior_feedbacks[0],
            prior_feedbacks=payload["review_feedback_history"],
        )
        assert decision.should_continue is False
        assert decision.exit_name == EXIT_STAGNATION
