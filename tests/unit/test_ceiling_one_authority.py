"""One authority for the ceiling decision (#2536).

run-issue331-150920: eight honest converging rounds, then iteration 9's draft
failed completeness, the #2304 grace clause — which checked only the BASE cap
— granted a revision carrying iteration 10, and the review guard refused to
review it: 39m 49s ended in "the regeneration routing should have halted
earlier". The issue's label-vs-counter hypothesis was REFUTED against the run
log (the seeded counter worked; rounds 1–8 were grant-relative); the real
defect was a regeneration-granting path that never consulted the ceiling.

The law now: ``regeneration_allowed`` is the one predicate every path that
can send the graph back to N2 past the base cap consults, a genuine grant
ceiling always produces the clean ``[hard-ceiling]`` report, and the
incoherent guard message is retired from every path including the backstop.
"""

from __future__ import annotations

from assemblyzero.workflows.implementation_spec import lineage_seed as ls
from assemblyzero.workflows.implementation_spec.graph import (
    route_after_validation,
)
from assemblyzero.workflows.implementation_spec.review_progress import (
    EXIT_CEILING,
    decide,
    hard_ceiling,
    regeneration_allowed,
)

VERDICTS = [
    f"REVISE: round {n} raises `test_distinct_{n}` — a new objection.\n"
    for n in range(12)
]


class TestTheOneAuthority:
    def test_the_last_grantable_regeneration_produces_the_ceiling(self):
        """#1775: the draft generated AT the ceiling still gets its review,
        so iteration 8 may regenerate (producing 9 == ceiling) and 9 may not."""
        assert hard_ceiling(3) == 9
        assert regeneration_allowed(8, 3) is True
        assert regeneration_allowed(9, 3) is False
        assert regeneration_allowed(10, 3) is False

    def test_cross_grant_labels_never_reach_the_authority(self):
        """The issue's required fixture: history labels far beyond the
        ceiling while the grant counter is mid-cap — the loop continues.
        Whatever the cap regime counts is the variable checked; the history
        length (the cross-grant 'label') is not it."""
        assert regeneration_allowed(2, 3) is True  # counter mid-cap
        decision = decide(
            review_iteration=2,
            max_iterations=3,
            current_feedback="REVISE: `test_fresh_objection` is new.\n",
            prior_feedbacks=VERDICTS,  # 12 prior rounds across grants
        )
        assert decision.should_continue, decision.detail

    def test_a_grant_genuinely_at_its_ceiling_halts_clean(self):
        decision = decide(
            review_iteration=9,
            max_iterations=3,
            current_feedback="REVISE: `test_yet_another` — still converging.\n",
            prior_feedbacks=VERDICTS[:9],
        )
        assert not decision.should_continue
        assert decision.exit_name == EXIT_CEILING


class TestTheGraceClauseConsultsTheCeiling:
    """The observed defect path: a completeness failure at the ceiling."""

    def _validate(self, iteration: int, shown=()):
        from unittest.mock import patch

        from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
            validate_completeness,
        )

        state = {
            "spec_draft": "# Spec\n\n" + ("body line\n" * 40),
            "files_to_modify": [],
            "pattern_references": [],
            "repo_root": "",
            "lld_content": "",
            "review_iteration": iteration,
            "max_iterations": 3,
            "checks_shown_to_drafter": list(shown),
        }
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes."
            "validate_completeness.check_modify_files_have_excerpts",
            return_value={
                "check_name": "never_shown_check", "passed": False,
                "details": "missing excerpt for a.py",
            },
        ):
            return validate_completeness(state)

    def test_below_the_ceiling_the_grace_still_grants(self):
        out = self._validate(iteration=8)
        assert "never_shown_check" in out["grace_revision_for"]
        assert out["error_message"] == ""

    def test_at_the_ceiling_the_grace_is_refused_and_the_halt_is_clean(self):
        """run-issue331-150920's exact shape: an unshown check failing at
        iteration 9 must NOT earn a revision the guard would refuse to
        review — it must halt with the hard-ceiling report."""
        out = self._validate(iteration=9)
        assert out["grace_revision_for"] == []
        assert f"[{EXIT_CEILING}]" in out["error_message"]
        assert "hard ceiling" in out["error_message"]
        assert "should have halted earlier" not in out["error_message"]

    def test_the_ceiling_halt_names_the_unfixed_checks(self):
        out = self._validate(iteration=9)
        assert "missing excerpt" in out["error_message"]


class TestTheRouterBackstop:
    def test_a_hand_built_grace_at_the_ceiling_routes_to_halt(self):
        assert route_after_validation({
            "validation_passed": False,
            "review_iteration": 9,
            "max_iterations": 3,
            "grace_revision_for": ["some_check"],
        }) == "HALT"

    def test_a_grace_below_the_ceiling_still_routes_to_n2(self):
        assert route_after_validation({
            "validation_passed": False,
            "review_iteration": 5,
            "max_iterations": 3,
            "grace_revision_for": ["some_check"],
        }) == "N2_generate_spec"


class TestTheGuardBackstopSpeaksTheCleanVocabulary:
    def test_beyond_the_ceiling_the_report_is_the_ceiling_report(self):
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            review_spec,
        )

        out = review_spec({
            "spec_draft": "# Spec\n\nbody\n",
            "review_iteration": 10,
            "max_iterations": 3,
        })
        assert out["review_verdict"] == "BLOCKED"
        assert out["review_exit"] == EXIT_CEILING
        assert f"[{EXIT_CEILING}]" in out["error_message"]
        assert "preserved in lineage unreviewed" in out["review_feedback"]
        # The incoherence is retired from its last home.
        assert "should have halted earlier" not in out["review_feedback"]

    def test_at_the_ceiling_the_review_still_happens(self):
        """#1775 stands: iteration == ceiling is reviewable; only beyond it
        is refused. A mock review at 9 must reach the reviewer, not the
        guard."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            review_spec,
        )

        out = review_spec({
            "spec_draft": "# Spec\n\n" + ("body\n" * 30),
            "lld_content": "# LLD\n",
            "review_iteration": 9,
            "max_iterations": 3,
            "config_mock_mode": True,
        })
        assert "beyond the grant's hard ceiling" not in (
            out.get("review_feedback") or ""
        )


class TestTheUnreviewedDraftResume:
    """The acceptance's second observation: 150920's final draft was never
    reviewed, so the resumed grant's first action is reviewing it."""

    def _run_dir(self, tmp_path, *, last_draft_reviewed: bool):
        run = tmp_path / "lineage" / "2026-08-26T20-09-22Z"
        run.mkdir(parents=True)
        (run / "001-spec-draft.md").write_text(
            "# Spec\n\nDRAFT ONE\n", encoding="utf-8"
        )
        (run / "003-readiness-verdict.md").write_text(
            "REVISE: `test_x` is wrong.\n", encoding="utf-8"
        )
        if not last_draft_reviewed:
            (run / "005-spec-draft.md").write_text(
                "# Spec\n\nDRAFT TWO — never reviewed\n", encoding="utf-8"
            )
        return run.parent

    def test_an_unreviewed_final_draft_is_detected(self, tmp_path):
        seed = ls.seed_from_lineage(
            self._run_dir(tmp_path, last_draft_reviewed=False)
        )
        assert seed.draft_unreviewed is True
        assert "DRAFT TWO" in seed.draft

    def test_its_payload_seeds_no_outstanding_feedback(self, tmp_path):
        """The verdict's items already fed the revision that produced the
        draft; seeding them again would spend a regeneration re-applying
        landed fixes. The first action is the review."""
        seed = ls.seed_from_lineage(
            self._run_dir(tmp_path, last_draft_reviewed=False)
        )
        payload = ls.resume_payload(seed)
        assert payload["review_feedback"] == ""
        assert payload["review_iteration"] == 0
        assert payload["review_feedback_history"], "history still travels"

    def test_a_reviewed_final_draft_keeps_the_old_behaviour(self, tmp_path):
        seed = ls.seed_from_lineage(
            self._run_dir(tmp_path, last_draft_reviewed=True)
        )
        assert seed.draft_unreviewed is False
        assert ls.resume_payload(seed)["review_feedback"].startswith("REVISE")

    def test_the_description_says_review_first(self, tmp_path):
        seed = ls.seed_from_lineage(
            self._run_dir(tmp_path, last_draft_reviewed=False)
        )
        assert "never reviewed" in ls.describe(seed)

    def test_n2_passes_the_unreviewed_draft_through_untouched(self):
        """No LLM call, no redraw, counter unchanged: the seeded draft goes
        to review as-is."""
        from unittest.mock import patch

        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            generate_spec,
        )

        state = {
            "config_mock_mode": True,
            "lld_content": "# LLD\n",
            "current_state_snapshots": {},
            "pattern_references": [],
            "assemblyzero_root": "",
            "repo_root": "",
            "spec_draft": "# Spec\n\nPAID, UNREVIEWED DRAFT\n",
            "review_feedback": "",
            "review_iteration": 0,
        }
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes."
            "generate_spec.get_provider",
        ) as provider:
            out = generate_spec(state)
        provider.assert_not_called()
        assert out["spec_draft"] == "# Spec\n\nPAID, UNREVIEWED DRAFT\n"
        assert out["review_iteration"] == 0
        assert out["error_message"] == ""
