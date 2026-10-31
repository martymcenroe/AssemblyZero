"""verdict_schema.py under standard 0034, one test per sweep site (#3802).

Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import json

import pytest

from assemblyzero.core.verdict_schema import (
    parse_structured_verdict,
    same_blocking_issues,
    scan_residual_questions,
)


class TestAVerdictWithoutItsReasonIsNotAVerdict:
    def test_196_json_with_no_rationale_is_not_schema_valid(self):
        assert parse_structured_verdict(json.dumps({"verdict": "APPROVED"})) is None

    def test_208_fenced_json_with_no_rationale_is_not_schema_valid(self):
        text = "Here it is:\n```json\n" + json.dumps({"verdict": "BLOCKED"}) + "\n```\n"
        assert parse_structured_verdict(text) is None

    def test_a_verdict_with_its_reason_still_parses(self):
        data = parse_structured_verdict(json.dumps({"verdict": "APPROVED", "rationale": "Sound."}))
        assert data == {"verdict": "APPROVED", "rationale": "Sound."}


class TestNothingIsReadAsNothingFound:
    def test_651_an_empty_document_raises(self):
        with pytest.raises(ValueError, match="cannot be shown to have none"):
            scan_residual_questions("")

    def test_703_an_empty_verdict_cannot_be_compared(self):
        with pytest.raises(ValueError, match="the current verdict text is empty"):
            same_blocking_issues("", "- [Section 2] The data model is missing")


class TestRenderedFeedbackIsComparedByItsLines:
    """716: a won't-do, recorded on #3802. The requirements workflow stores
    rendered feedback in ``current_verdict`` by design (#506), so the line
    comparison is the comparison, not a fallback from a failed parse. Raising
    there would end two-strike stagnation detection for every blocked round."""

    FEEDBACK = (
        "- [Section 2.1] The files-changed table omits the migration script\n"
        "- [Section 10] Test T030 has no expected output\n"
    )

    def test_716_the_same_rendered_feedback_twice_is_stagnant(self):
        assert same_blocking_issues(self.FEEDBACK, self.FEEDBACK) is True

    def test_716_different_rendered_feedback_is_not(self):
        other = "- [Section 11] The rollback plan names no command\n"
        assert same_blocking_issues(self.FEEDBACK, other) is False
