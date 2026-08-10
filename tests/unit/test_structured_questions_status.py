"""The reviewer's structured verdict governs open-questions status (#2199).

The regression these tests pin: ``audit_content`` is rendered from the parsed
verdict WITHOUT the open-questions field, and ``_check_open_questions_status``
re-parsed that rendering — so every question-bearing draft was ruled
UNANSWERED even when the reviewer APPROVED, and the forced revision (lossy,
tracked separately) turned approvals into dead rolls. Twelve approved LLDs
were discarded this way in the boostgauge campaign before the chain was
caught (run-issue1-122404: 321-line APPROVED draft regenerated into a
163-line invalid one).
"""
from __future__ import annotations

from assemblyzero.workflows.requirements.nodes.review import (
    _check_open_questions_status,
)

DRAFT_WITH_QUESTIONS = """# LLD-042: Test Document

## 1. Summary
Some design.

## Open Questions
- [ ] Should the collector support IPv6?
- [ ] Is 2s polling acceptable on battery?

## 11. Rollback
Revert the PR.
"""

DRAFT_WITHOUT_QUESTIONS = """# LLD-042: Test Document

## 1. Summary
Some design.

## Open Questions
- [ ] None

## 11. Rollback
Revert the PR.
"""

# What the caller actually passes: audit text re-rendered from the parsed
# verdict — no JSON, no "## Open Questions Resolved" section. This is the
# exact shape that made the legacy path rule UNANSWERED unconditionally.
AUDIT_APPROVED = "Verdict: APPROVED\n\nRationale: Solid, complete design.\n"


def structured(open_questions):
    return {
        "verdict": "APPROVED",
        "rationale": "Solid, complete design.",
        "feedback_items": [],
        "open_questions": open_questions,
        "resolved_issues": [],
        "source": "structured",
    }


# ---------------------------------------------------------------------------
# The regression: structured verdicts govern
# ---------------------------------------------------------------------------


def test_structured_empty_questions_is_resolved():
    """The 12-dead-runs case: APPROVED, reviewer lists nothing unresolved."""
    status = _check_open_questions_status(
        DRAFT_WITH_QUESTIONS, AUDIT_APPROVED, structured([])
    )
    assert status == "RESOLVED"


def test_structured_all_resolved_is_resolved():
    status = _check_open_questions_status(
        DRAFT_WITH_QUESTIONS,
        AUDIT_APPROVED,
        structured([
            {"text": "Should the collector support IPv6?", "resolved": True},
            {"text": "Is 2s polling acceptable on battery?", "resolved": True},
        ]),
    )
    assert status == "RESOLVED"


def test_structured_unresolved_item_is_unanswered():
    status = _check_open_questions_status(
        DRAFT_WITH_QUESTIONS,
        AUDIT_APPROVED,
        structured([
            {"text": "Should the collector support IPv6?", "resolved": True},
            {"text": "Is 2s polling acceptable on battery?", "resolved": False},
        ]),
    )
    assert status == "UNANSWERED"


def test_structured_item_without_resolved_flag_counts_unresolved():
    """An item the reviewer listed but did not mark resolved is unresolved."""
    status = _check_open_questions_status(
        DRAFT_WITH_QUESTIONS, AUDIT_APPROVED,
        structured([{"text": "Should the collector support IPv6?"}]),
    )
    assert status == "UNANSWERED"


def test_structured_non_dict_items_are_ignored():
    status = _check_open_questions_status(
        DRAFT_WITH_QUESTIONS, AUDIT_APPROVED, structured(["just a string"])
    )
    assert status == "RESOLVED"


# ---------------------------------------------------------------------------
# Precedence and fallbacks unchanged
# ---------------------------------------------------------------------------


def test_no_questions_in_draft_is_none_regardless_of_verdict():
    status = _check_open_questions_status(
        DRAFT_WITHOUT_QUESTIONS, AUDIT_APPROVED, structured([])
    )
    assert status == "NONE"


def test_human_required_beats_structured_resolution():
    audit = AUDIT_APPROVED + "\nHUMAN REQUIRED: licensing decision.\n"
    status = _check_open_questions_status(
        DRAFT_WITH_QUESTIONS, audit, structured([])
    )
    assert status == "HUMAN_REQUIRED"


def test_regex_fallback_source_uses_legacy_path():
    """A verdict that genuinely failed structured parsing keeps old behavior:
    a bare audit text answers nothing, so questions stay UNANSWERED."""
    fallback = dict(structured([]), source="regex_fallback")
    status = _check_open_questions_status(
        DRAFT_WITH_QUESTIONS, AUDIT_APPROVED, fallback
    )
    assert status == "UNANSWERED"


def test_no_feedback_result_uses_legacy_path():
    """Callers that pass nothing (older call sites, tests) are unchanged."""
    status = _check_open_questions_status(DRAFT_WITH_QUESTIONS, AUDIT_APPROVED)
    assert status == "UNANSWERED"


def test_legacy_resolved_section_still_wins_without_structured():
    verdict = (
        "Verdict: APPROVED\n\n## Open Questions Resolved\n"
        "- [x] ~~Should the collector support IPv6?~~ **RESOLVED:** No, v1 is local-only.\n"
        "- [x] ~~Is 2s polling acceptable on battery?~~ **RESOLVED:** Yes, measured.\n"
    )
    status = _check_open_questions_status(DRAFT_WITH_QUESTIONS, verdict)
    assert status == "RESOLVED"
