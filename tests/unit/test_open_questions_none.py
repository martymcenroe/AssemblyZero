"""The "- [ ] None" empty state, end to end (#2232).

The template scaffolds Open Questions as an unchecked checkbox, so a drafter
with nothing to ask fills the scaffold rather than deleting it. In
run-issue7-234943 four drafts out of four wrote `- [ ] None`. The reviewer read
the meaning and returned APPROVED; finalize read the form and blocked. The
draft it killed had already passed mechanical validation, passed test-plan
validation at 22/22, and been approved.

The root cause was two detectors disagreeing about one document: review.py
filtered none-placeholders, finalize.py did not, and the escape hatch #259
built for exactly this was wired to RESOLVED while review reports NONE.

`boostgauge-7-005-approved-draft.md` is that killed draft, byte-verbatim.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.core.verdict_schema import is_none_placeholder
from assemblyzero.workflows.requirements.nodes.finalize import (
    open_questions_settled,
    validate_lld_final,
)
from assemblyzero.workflows.requirements.nodes.ponder_rules import (
    PONDER_RULES,
    apply_all_rules,
    fix_none_open_questions,
)
from assemblyzero.workflows.requirements.nodes.review import (
    _check_open_questions_status,
    _draft_has_open_questions,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "open_questions"
    / "boostgauge-7-005-approved-draft.md"
)

REAL_QUESTION = "- [ ] Should the config live in APPDATA?"


@pytest.fixture(scope="module")
def approved_draft() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def _doc(section_body: str) -> str:
    return f"# Issue #7 - Feature: thing\n\n### Open Questions\n{section_body}\n\n## 2. Proposed Changes\n\nbody\n"


# ---------------------------------------------------------------------------
# One predicate, shared
# ---------------------------------------------------------------------------


class TestNonePlaceholder:
    @pytest.mark.parametrize(
        "text",
        ["None", "none", "NONE", "None.", "N/A", "n/a", "na",
         "None at this time", "None at this time.", "  none  ",
         "**None**", "nothing",
         # A placeholder carrying an aside, which is how drafters write it.
         "None — scope is well-defined", "None - scope is well-defined",
         "None: the design is settled", "None, the design is settled",
         "N/A (nothing outstanding)"],
    )
    def test_placeholders(self, text):
        assert is_none_placeholder(text)

    @pytest.mark.parametrize(
        "text",
        ["Should the config live in APPDATA?",
         "None of the thresholds are specified",
         "no decision yet on the polling interval",
         "nothing has been decided about theme precedence",
         ""],
    )
    def test_real_questions_are_not_placeholders(self, text):
        assert not is_none_placeholder(text)

    def test_review_and_ponder_share_it(self):
        """The two detectors that disagreed now consume one predicate.

        Imported via importlib because the nodes package re-exports the
        `review` FUNCTION under its module's name, so a plain import binds
        the function instead of the module.
        """
        from importlib import import_module

        pr = import_module("assemblyzero.workflows.requirements.nodes.ponder_rules")
        rv = import_module("assemblyzero.workflows.requirements.nodes.review")

        assert pr.is_none_placeholder is is_none_placeholder
        assert rv.is_none_placeholder is is_none_placeholder


# ---------------------------------------------------------------------------
# Ponder normalization
# ---------------------------------------------------------------------------


class TestPonderNormalization:
    def test_registered(self):
        assert fix_none_open_questions in PONDER_RULES

    def test_normalizes_the_placeholder(self):
        fixed, fixes = fix_none_open_questions(_doc("- [ ] None"), {})

        assert "- [ ] None" not in fixed
        assert "None." in fixed
        assert len(fixes) == 1
        assert fixes[0].section == "Open Questions"

    def test_normalizes_several_placeholders_to_one_line(self):
        fixed, _ = fix_none_open_questions(_doc("- [ ] None\n- [ ] N/A"), {})

        assert "- [ ]" not in fixed
        assert fixed.count("None.") == 1

    def test_a_real_question_is_left_completely_alone(self):
        """The binding negative: this rule must never check off a question."""
        doc = _doc(REAL_QUESTION)

        fixed, fixes = fix_none_open_questions(doc, {})

        assert fixed == doc
        assert fixes == []
        assert "- [x]" not in fixed

    def test_a_mixed_section_is_left_alone(self):
        """"None" beside a real question is not an empty state."""
        doc = _doc(f"- [ ] None\n{REAL_QUESTION}")

        fixed, fixes = fix_none_open_questions(doc, {})

        assert fixed == doc
        assert fixes == []

    def test_no_section_is_a_noop(self):
        doc = "# Title\n\n## 2. Proposed Changes\n\nbody\n"
        assert fix_none_open_questions(doc, {}) == (doc, [])

    def test_already_plain_none_is_a_noop(self):
        doc = _doc("None.")
        assert fix_none_open_questions(doc, {}) == (doc, [])

    def test_it_runs_in_the_full_ponder_pass(self):
        fixed, fixes = apply_all_rules(_doc("- [ ] None"), {"issue_number": 7})

        assert "- [ ]" not in fixed
        assert any(f.rule == "none_open_questions" for f in fixes)

    def test_the_killed_draft_survives_ponder_and_then_finalize(
        self, approved_draft
    ):
        """Defence in depth: the repair alone is enough, flag aside."""
        fixed, fixes = fix_none_open_questions(approved_draft, {})

        assert any(f.rule == "none_open_questions" for f in fixes)
        assert "Unresolved open questions remain" not in validate_lld_final(
            fixed, False
        )


# ---------------------------------------------------------------------------
# finalize, and the #259 flag
# ---------------------------------------------------------------------------


class TestFinalizeGate:
    def test_the_killed_draft_passes_byte_verbatim_when_review_said_none(
        self, approved_draft
    ):
        """Acceptance 1. The exhibit, unmodified, with the real NONE status."""
        errors = validate_lld_final(approved_draft, True)

        assert "Unresolved open questions remain" not in errors

    def test_the_same_draft_still_blocks_with_no_review_status(
        self, approved_draft
    ):
        """An absent status is not NONE: a path that never reviewed is gated."""
        errors = validate_lld_final(approved_draft, False)

        assert "Unresolved open questions remain" in errors

    def test_a_real_unchecked_question_still_blocks(self):
        """Acceptance 2. Unchanged behavior for a genuine question."""
        errors = validate_lld_final(_doc(REAL_QUESTION), False)

        assert "Unresolved open questions remain" in errors


class TestTwoSixtyNineFlag:
    """Why the escape hatch did not fire, pinned as behavior."""

    def test_review_reports_none_for_the_placeholder_draft(self, approved_draft):
        """The review detector already read the draft correctly."""
        assert not _draft_has_open_questions(approved_draft)
        assert _check_open_questions_status(approved_draft, "Verdict: APPROVED") == "NONE"

    def test_review_does_not_report_none_for_a_real_question(self):
        doc = _doc(REAL_QUESTION)

        assert _draft_has_open_questions(doc)
        assert _check_open_questions_status(doc, "Verdict: APPROVED") != "NONE"

    @pytest.mark.parametrize(
        "status,settled",
        [("RESOLVED", True), ("NONE", True), ("UNANSWERED", False),
         ("HUMAN_REQUIRED", False), ("", False), ("resolved", False)],
    )
    def test_which_statuses_are_settled(self, status, settled):
        """Calls the real decision, so a change to it fails here.

        RESOLVED was the only skip; NONE now joins it and nothing else does.
        An absent status stays unsettled on purpose.
        """
        assert open_questions_settled(status) is settled

        errors = validate_lld_final(
            _doc("- [ ] None"), open_questions_settled(status)
        )
        assert ("Unresolved open questions remain" in errors) is not settled

    def test_the_exhibit_end_to_end_through_the_real_decision(
        self, approved_draft
    ):
        """The killed draft, the real status it got, the real gate."""
        status = _check_open_questions_status(approved_draft, "Verdict: APPROVED")

        errors = validate_lld_final(
            approved_draft, open_questions_settled(status)
        )

        assert status == "NONE"
        assert "Unresolved open questions remain" not in errors


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


def test_the_template_tells_the_drafter_the_accepted_empty_state():
    """Acceptance 4: template instruction and finalize scan must agree."""
    template = (
        Path(__file__).resolve().parents[2]
        / "docs" / "templates" / "0102-feature-lld-template.md"
    ).read_text(encoding="utf-8")

    assert "`None.`" in template
    assert "Do NOT write `- [ ] None`" in template
