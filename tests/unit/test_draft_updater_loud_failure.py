"""The draft updater under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/parsers/draft_updater.py``. A reviewer's
resolution that cannot be applied to the approved draft is lost from it, so it
raises naming the resolution, where it used to become a warning string the
caller only printed. An empty draft raises, and a suggestions heading the
section pattern cannot read raises a named error instead of an AttributeError.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.requirements.parsers.draft_updater import update_draft
from assemblyzero.workflows.requirements.parsers.verdict_parser import (
    ResolvedQuestion,
    Tier3Suggestion,
    VerdictParseResult,
)

DRAFT = (
    "# 42 - Feature: x\n\n"
    "## Open Questions\n\n"
    "- [ ] Should the cache expire after an hour?\n\n"
    "## Definition of Done\n\n- done\n"
)


def _verdict(resolutions=(), suggestions=()):
    return VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=list(resolutions),
        suggestions=list(suggestions),
    )


def test_35_an_empty_draft_raises():
    with pytest.raises(ValueError, match="empty draft"):
        update_draft("", _verdict())


def test_84_a_resolution_with_no_open_questions_section_raises():
    resolution = ResolvedQuestion("Should the cache expire?", "Yes, after an hour.")
    with pytest.raises(ValueError, match="no Open Questions section") as raised:
        update_draft("# 42 - Feature: x\n\n## Design\n\nprose\n", _verdict([resolution]))
    assert "Should the cache expire?" in str(raised.value)


def test_105_a_question_the_draft_does_not_carry_raises():
    resolution = ResolvedQuestion("Which database engine is used?", "SQLite.")
    with pytest.raises(ValueError, match="no question in the draft") as raised:
        update_draft(DRAFT, _verdict([resolution]))
    assert "Which database engine is used?" in str(raised.value)


def test_271_a_suggestions_heading_the_section_pattern_cannot_read_raises():
    """`^##\\s*Reviewer Suggestions` finds the heading; the section pattern needs
    a newline after it, and a heading that ends the file has none."""
    draft = DRAFT + "\n## Reviewer Suggestions"
    suggestion = Tier3Suggestion("Add a metrics hook for cache hits")
    with pytest.raises(ValueError, match="Reviewer Suggestions"):
        update_draft(draft, _verdict(suggestions=[suggestion]))


def test_a_matching_resolution_is_applied():
    """Kept: the update the module exists for."""
    resolution = ResolvedQuestion("Should the cache expire after an hour?", "Yes.")
    updated, warnings = update_draft(DRAFT, _verdict([resolution]))
    assert "- [x] Should the cache expire after an hour? **RESOLVED:** Yes." in updated
    assert warnings == []


def test_a_verdict_with_nothing_to_apply_leaves_the_draft_alone():
    """Kept: no resolutions and no suggestions is an answer, not a failure."""
    assert update_draft(DRAFT, _verdict()) == (DRAFT, [])
