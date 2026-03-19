"""Unit tests for assemblyzero/core/verdict_schema.py.

Issue #775: Structured output for LLM reviewer responses.
Tests schemas, parse helpers, regex fallbacks, and counter metrics.
"""

import json
import logging
from unittest.mock import patch

import pytest

from assemblyzero.core.verdict_schema import (
    DRAFT_QUESTIONS_SCHEMA,
    FEEDBACK_SCHEMA,
    FINALIZE_QUESTIONS_SCHEMA,
    REVIEW_SPEC_SCHEMA,
    VERDICT_SCHEMA,
    DraftQuestionsResult,
    FeedbackResult,
    FinalizeQuestionsResult,
    ReviewSpecResult,
    VerdictResult,
    _extract_section_from_markdown,
    _regex_fallback_draft_questions,
    _regex_fallback_feedback,
    _regex_fallback_finalize_questions,
    _regex_fallback_verdict,
    _validate_enum,
    _validate_required_keys,
    parse_structured_draft_questions,
    parse_structured_feedback,
    parse_structured_finalize_questions,
    parse_structured_review_spec,
    parse_structured_verdict,
)


# ---------------------------------------------------------------------------
# Schema shape tests
# ---------------------------------------------------------------------------

class TestSchemaConstants:
    def test_verdict_schema_has_verdict_and_rationale(self):
        assert "verdict" in VERDICT_SCHEMA["properties"]
        assert "rationale" in VERDICT_SCHEMA["properties"]

    def test_feedback_schema_required_fields(self):
        required = FEEDBACK_SCHEMA["required"]
        assert "verdict" in required
        assert "rationale" in required
        assert "feedback_items" in required
        assert "open_questions" in required

    def test_feedback_schema_verdict_enum(self):
        enum = FEEDBACK_SCHEMA["properties"]["verdict"]["enum"]
        assert set(enum) == {"APPROVED", "REVISE", "DISCUSS"}

    def test_review_spec_schema_required_fields(self):
        required = REVIEW_SPEC_SCHEMA["required"]
        assert "verdict" in required
        assert "rationale" in required
        assert "feedback_items" in required

    def test_review_spec_schema_verdict_enum(self):
        enum = REVIEW_SPEC_SCHEMA["properties"]["verdict"]["enum"]
        assert set(enum) == {"APPROVED", "REVISE", "BLOCKED"}

    def test_draft_questions_schema_required(self):
        assert "open_questions" in DRAFT_QUESTIONS_SCHEMA["required"]

    def test_finalize_questions_schema_required(self):
        required = FINALIZE_QUESTIONS_SCHEMA["required"]
        assert "has_open_questions" in required
        assert "question_count" in required
        assert "questions" in required


# ---------------------------------------------------------------------------
# _validate_required_keys
# ---------------------------------------------------------------------------

class TestValidateRequiredKeys:
    def test_all_present(self):
        assert _validate_required_keys({"a": 1, "b": 2}, ["a", "b"]) is True

    def test_missing_key(self):
        assert _validate_required_keys({"a": 1}, ["a", "b"]) is False

    def test_empty_required(self):
        assert _validate_required_keys({}, []) is True

    def test_extra_keys_ok(self):
        assert _validate_required_keys({"a": 1, "b": 2, "c": 3}, ["a"]) is True


# ---------------------------------------------------------------------------
# _validate_enum
# ---------------------------------------------------------------------------

class TestValidateEnum:
    def test_valid_list(self):
        assert _validate_enum("APPROVED", ["APPROVED", "REVISE"]) is True

    def test_invalid_list(self):
        assert _validate_enum("BLOCKED", ["APPROVED", "REVISE"]) is False

    def test_valid_set(self):
        assert _validate_enum("REVISE", {"APPROVED", "REVISE", "DISCUSS"}) is True

    def test_case_sensitive(self):
        assert _validate_enum("approved", {"APPROVED"}) is False


# ---------------------------------------------------------------------------
# parse_structured_verdict
# ---------------------------------------------------------------------------

class TestParseStructuredVerdict:
    def test_valid_json_returns_dict(self):
        raw = json.dumps({"verdict": "APPROVED", "rationale": "LGTM"})
        result = parse_structured_verdict(raw)
        assert result is not None
        assert result["verdict"] == "APPROVED"

    def test_invalid_json_returns_none(self):
        assert parse_structured_verdict("not json") is None

    def test_missing_verdict_key_returns_none(self):
        raw = json.dumps({"rationale": "ok"})
        assert parse_structured_verdict(raw) is None

    def test_empty_string_returns_none(self):
        assert parse_structured_verdict("") is None


# ---------------------------------------------------------------------------
# parse_structured_feedback — T010 / test_010
# ---------------------------------------------------------------------------

class TestParseStructuredFeedback:
    """T010 / test_010: Happy path and fallback for feedback parsing."""

    def test_valid_json_structured_source(self):
        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Missing tests",
            "feedback_items": ["Add T040"],
            "open_questions": [{"text": "Timeout?", "resolved": False}],
            "resolved_issues": [],
        })
        result = parse_structured_feedback(raw)
        assert result["verdict"] == "REVISE"
        assert result["rationale"] == "Missing tests"
        assert result["feedback_items"] == ["Add T040"]
        assert result["open_questions"] == [{"text": "Timeout?", "resolved": False}]
        assert result["source"] == "structured"

    def test_valid_json_all_required_fields_present(self):
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "LGTM",
            "feedback_items": [],
            "open_questions": [],
        })
        result = parse_structured_feedback(raw)
        assert result["source"] == "structured"
        assert "resolved_issues" in result

    def test_missing_verdict_falls_back(self):
        raw = json.dumps({"rationale": "ok", "feedback_items": [], "open_questions": []})
        result = parse_structured_feedback(raw)
        assert result["source"] == "regex_fallback"

    def test_invalid_verdict_enum_falls_back(self):
        raw = json.dumps({
            "verdict": "NOTAVERDICT",
            "rationale": "x",
            "feedback_items": [],
            "open_questions": [],
        })
        result = parse_structured_feedback(raw)
        assert result["source"] == "regex_fallback"

    def test_malformed_json_falls_back(self):
        raw = "[X] **REVISE**\n\n## Feedback\n- Fix something\n"
        result = parse_structured_feedback(raw)
        assert result["source"] == "regex_fallback"
        assert result["verdict"] == "REVISE"

    def test_empty_string_returns_unknown(self):
        result = parse_structured_feedback("")
        assert result["verdict"] == "UNKNOWN"
        assert result["source"] == "regex_fallback"

    def test_blocked_verdict_remapped_to_unknown(self):
        # BLOCKED is valid in REVIEW_SPEC but not FEEDBACK schema
        raw = "[X] **BLOCKED**\n"
        result = parse_structured_feedback(raw)
        assert result["verdict"] == "UNKNOWN"
        assert result["source"] == "regex_fallback"

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_fallback_logs_debug(self, mock_logger):
        raw = "[X] **APPROVED**\n\n## Feedback\n- looks good"
        result = parse_structured_feedback(raw)
        assert result["source"] == "regex_fallback"
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=feedback")

    def test_structured_parse_returns_structured_source(self):
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "LGTM",
            "feedback_items": [],
            "open_questions": [],
        })
        result = parse_structured_feedback(raw)
        assert result["source"] == "structured"

    def test_missing_open_questions_falls_back(self):
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
        })
        result = parse_structured_feedback(raw)
        assert result["source"] == "regex_fallback"

    def test_logs_warning_on_fallback(self, caplog):
        raw = "not json at all"
        with caplog.at_level(logging.WARNING, logger="assemblyzero.core.verdict_schema"):
            parse_structured_feedback(raw)
        assert any("fallback" in r.message.lower() or "parse" in r.message.lower()
                   for r in caplog.records)


# ---------------------------------------------------------------------------
# parse_structured_review_spec — T030 / T040 / test_040 / test_050
# ---------------------------------------------------------------------------

class TestParseStructuredReviewSpec:
    """T030 / test_040: Happy path and fallback for spec review."""

    def test_valid_json_structured_source(self):
        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Missing diffs",
            "feedback_items": ["Add diff for section 6"],
        })
        result = parse_structured_review_spec(raw)
        assert result["verdict"] == "REVISE"
        assert result["rationale"] == "Missing diffs"
        assert result["feedback_items"] == ["Add diff for section 6"]
        assert result["source"] == "structured"

    def test_blocked_verdict_valid(self):
        raw = json.dumps({
            "verdict": "BLOCKED",
            "rationale": "Cannot proceed",
            "feedback_items": [],
        })
        result = parse_structured_review_spec(raw)
        assert result["verdict"] == "BLOCKED"
        assert result["source"] == "structured"

    def test_missing_feedback_items_falls_back(self):
        # test_050: missing required key
        raw = json.dumps({"verdict": "REVISE", "rationale": "ok"})
        result = parse_structured_review_spec(raw)
        assert result["source"] == "regex_fallback"

    def test_invalid_verdict_enum_falls_back(self):
        raw = json.dumps({
            "verdict": "DISCUSS",  # not valid in REVIEW_SPEC_SCHEMA
            "rationale": "x",
            "feedback_items": [],
        })
        result = parse_structured_review_spec(raw)
        assert result["source"] == "regex_fallback"

    def test_malformed_json_falls_back(self):
        raw = "[X] **APPROVED**\n"
        result = parse_structured_review_spec(raw)
        assert result["source"] == "regex_fallback"

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_fallback_logs_debug(self, mock_logger):
        parse_structured_review_spec("bad json")
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=review_spec")

    def test_structured_returns_structured_source(self):
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
        })
        result = parse_structured_review_spec(raw)
        assert result["source"] == "structured"


# ---------------------------------------------------------------------------
# parse_structured_draft_questions — T050 / test_060
# ---------------------------------------------------------------------------

class TestParseStructuredDraftQuestions:
    """T050 / test_060: Happy path and fallback for draft questions."""

    def test_valid_json_structured_source(self):
        raw = json.dumps({
            "open_questions": [
                {"text": "What is the timeout?", "resolved": False},
                {"text": "Rate limit decided", "resolved": True},
            ]
        })
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "structured"
        assert len(result["open_questions"]) == 2
        assert result["open_questions"][0]["text"] == "What is the timeout?"
        assert result["open_questions"][0]["resolved"] is False

    def test_empty_questions_list(self):
        raw = json.dumps({"open_questions": []})
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "structured"
        assert result["open_questions"] == []

    def test_missing_open_questions_key_falls_back(self):
        raw = json.dumps({"something_else": []})
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "regex_fallback"

    def test_malformed_json_falls_back(self):
        raw = "## Open Questions\n- [ ] What is the timeout?\n- [X] Rate limit decided\n"
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "regex_fallback"
        assert len(result["open_questions"]) == 2

    def test_empty_string_returns_regex_fallback(self):
        result = parse_structured_draft_questions("")
        assert result["source"] == "regex_fallback"
        assert result["open_questions"] == []

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_fallback_logs_debug(self, mock_logger):
        parse_structured_draft_questions("not json")
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=draft_questions")

    def test_structured_returns_structured_source(self):
        raw = json.dumps({"open_questions": []})
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "structured"


# ---------------------------------------------------------------------------
# parse_structured_finalize_questions — T060 / test_070
# ---------------------------------------------------------------------------

class TestParseStructuredFinalizeQuestions:
    """T060 / test_070: Happy path and fallback for finalize questions."""

    def test_valid_json_with_questions(self):
        raw = json.dumps({
            "has_open_questions": True,
            "question_count": 1,
            "questions": ["What timeout value?"],
        })
        result = parse_structured_finalize_questions(raw)
        assert result["source"] == "structured"
        assert result["has_open_questions"] is True
        assert result["question_count"] == 1
        assert "What timeout value?" in result["questions"]

    def test_valid_json_no_questions(self):
        raw = json.dumps({
            "has_open_questions": False,
            "question_count": 0,
            "questions": [],
        })
        result = parse_structured_finalize_questions(raw)
        assert result["source"] == "structured"
        assert result["has_open_questions"] is False
        assert result["question_count"] == 0

    def test_missing_required_key_falls_back(self):
        raw = json.dumps({"has_open_questions": True})
        result = parse_structured_finalize_questions(raw)
        assert result["source"] == "regex_fallback"

    def test_malformed_json_falls_back(self):
        raw = "## Section\nWhat is the timeout?\n"
        result = parse_structured_finalize_questions(raw)
        assert result["source"] == "regex_fallback"

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_fallback_logs_debug(self, mock_logger):
        parse_structured_finalize_questions("bad json")
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=finalize_questions")

    def test_structured_returns_structured_source(self):
        raw = json.dumps({
            "has_open_questions": False,
            "question_count": 0,
            "questions": [],
        })
        result = parse_structured_finalize_questions(raw)
        assert result["source"] == "structured"


# ---------------------------------------------------------------------------
# _regex_fallback_verdict
# ---------------------------------------------------------------------------

class TestRegexFallbackVerdict:
    def test_approved_checkbox(self):
        raw = "[X] **APPROVED**\n\nRationale: Looks good"
        result = _regex_fallback_verdict(raw)
        assert result["verdict"] == "APPROVED"
        assert result["source"] == "regex_fallback"

    def test_revise_checkbox(self):
        raw = "[X] **REVISE**\n"
        result = _regex_fallback_verdict(raw)
        assert result["verdict"] == "REVISE"

    def test_discuss_checkbox(self):
        raw = "[X] **DISCUSS**\n"
        result = _regex_fallback_verdict(raw)
        assert result["verdict"] == "DISCUSS"

    def test_blocked_checkbox(self):
        raw = "[X] **BLOCKED**\n"
        result = _regex_fallback_verdict(raw)
        assert result["verdict"] == "BLOCKED"

    def test_case_insensitive(self):
        raw = "[x] **approved**"
        result = _regex_fallback_verdict(raw)
        assert result["verdict"] == "APPROVED"

    def test_no_match_returns_unknown(self):
        raw = "This is just plain text"
        result = _regex_fallback_verdict(raw)
        assert result["verdict"] == "UNKNOWN"
        assert result["rationale"] == ""

    def test_extracts_rationale(self):
        raw = "[X] **APPROVED**\n\nRationale: This is the reason\n\n## Section"
        result = _regex_fallback_verdict(raw)
        assert "reason" in result["rationale"].lower() or "rationale" in result["rationale"].lower() or result["rationale"] != ""

    def test_never_raises(self):
        # Should not raise on any input
        _regex_fallback_verdict(None)  # type: ignore
        _regex_fallback_verdict(123)   # type: ignore

    def test_regex_helper_does_not_log_fallback_metric(self):
        with patch("assemblyzero.core.verdict_schema.logger") as mock_logger:
            _regex_fallback_verdict("[X] **APPROVED**")
            # _regex_fallback_verdict logs warnings but NOT the debug metric line
            for c in mock_logger.debug.call_args_list:
                assert "regex_fallback" not in str(c)

    def test_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="assemblyzero.core.verdict_schema"):
            _regex_fallback_verdict("[X] **APPROVED**")
        assert any("regex fallback" in r.message.lower() or "fallback" in r.message.lower()
                   for r in caplog.records)


# ---------------------------------------------------------------------------
# _regex_fallback_feedback
# ---------------------------------------------------------------------------

class TestRegexFallbackFeedback:
    def test_extracts_verdict_and_feedback_items(self):
        raw = "[X] **REVISE**\n\n## Feedback\n- Fix error handling\n- Add missing tests\n"
        result = _regex_fallback_feedback(raw)
        assert result["verdict"] == "REVISE"
        assert "Fix error handling" in result["feedback_items"]
        assert "Add missing tests" in result["feedback_items"]
        assert result["source"] == "regex_fallback"

    def test_extracts_open_questions(self):
        raw = "[X] **REVISE**\n\n## Open Questions\n- [ ] What timeout value?\n- [X] Should we retry?\n"
        result = _regex_fallback_feedback(raw)
        assert any(q["text"] == "What timeout value?" and not q["resolved"]
                   for q in result["open_questions"])
        assert any(q["text"] == "Should we retry?" and q["resolved"]
                   for q in result["open_questions"])

    def test_empty_input_returns_unknown(self):
        result = _regex_fallback_feedback("")
        assert result["verdict"] == "UNKNOWN"
        assert result["feedback_items"] == []
        assert result["open_questions"] == []

    def test_regex_helper_does_not_log_fallback_metric(self):
        with patch("assemblyzero.core.verdict_schema.logger") as mock_logger:
            _regex_fallback_feedback("[X] **APPROVED**")
            # _regex_fallback_feedback logs warnings but NOT the debug metric line
            for c in mock_logger.debug.call_args_list:
                assert "regex_fallback" not in str(c)

    def test_extracts_resolved_issues(self):
        raw = "[X] **APPROVED**\n\n## Resolved Issues\n- Fixed missing type annotation\n"
        result = _regex_fallback_feedback(raw)
        assert "Fixed missing type annotation" in result["resolved_issues"]

    def test_required_changes_section_fallback(self):
        raw = "[X] **REVISE**\n\n## Required Changes\n- Update the spec\n"
        result = _regex_fallback_feedback(raw)
        assert "Update the spec" in result["feedback_items"]


# ---------------------------------------------------------------------------
# _regex_fallback_draft_questions
# ---------------------------------------------------------------------------

class TestRegexFallbackDraftQuestions:
    def test_extracts_unchecked_and_checked(self):
        raw = "## Open Questions\n- [ ] What is the timeout?\n- [X] Rate limit decided\n"
        result = _regex_fallback_draft_questions(raw)
        assert result["source"] == "regex_fallback"
        unchecked = [q for q in result["open_questions"] if not q["resolved"]]
        checked = [q for q in result["open_questions"] if q["resolved"]]
        assert len(unchecked) == 1
        assert unchecked[0]["text"] == "What is the timeout?"
        assert len(checked) == 1
        assert checked[0]["text"] == "Rate limit decided"

    def test_no_section_returns_empty(self):
        raw = "Some content without open questions section."
        result = _regex_fallback_draft_questions(raw)
        assert result["open_questions"] == []
        assert result["source"] == "regex_fallback"

    def test_regex_helper_does_not_log_fallback_metric(self):
        with patch("assemblyzero.core.verdict_schema.logger") as mock_logger:
            _regex_fallback_draft_questions("## Open Questions\n- [ ] Q1\n")
            # _regex_fallback_draft_questions logs warnings but NOT the debug metric line
            for c in mock_logger.debug.call_args_list:
                assert "regex_fallback" not in str(c)


# ---------------------------------------------------------------------------
# _regex_fallback_finalize_questions
# ---------------------------------------------------------------------------

class TestRegexFallbackFinalizeQuestions:
    def test_detects_question_lines(self):
        raw = "## Requirements\n\nWhat timeout value?\nThe system shall process requests.\n"
        result = _regex_fallback_finalize_questions(raw)
        assert result["source"] == "regex_fallback"
        assert result["has_open_questions"] is True
        assert "What timeout value?" in result["questions"]

    def test_detects_todo_markers(self):
        raw = "## Design\n\nTODO: determine rate limit\nImplement retry logic.\n"
        result = _regex_fallback_finalize_questions(raw)
        assert result["has_open_questions"] is True
        assert any("TODO" in q for q in result["questions"])

    def test_no_questions_or_todos(self):
        raw = "## Section\n\nThe system shall process requests within 200ms.\n"
        result = _regex_fallback_finalize_questions(raw)
        assert result["has_open_questions"] is False
        assert result["question_count"] == 0
        assert result["questions"] == []

    def test_short_question_mark_filtered(self):
        # Single "?" or very short lines should not be counted
        raw = "?\n"
        result = _regex_fallback_finalize_questions(raw)
        assert result["has_open_questions"] is False

    def test_regex_helper_does_not_log_fallback_metric(self):
        with patch("assemblyzero.core.verdict_schema.logger") as mock_logger:
            _regex_fallback_finalize_questions("What timeout?")
            # _regex_fallback_finalize_questions logs warnings but NOT the debug metric line
            for c in mock_logger.debug.call_args_list:
                assert "regex_fallback" not in str(c)

    def test_question_count_matches_questions_list(self):
        raw = "What is the timeout?\nWhat is the retry count?\nTODO: fix this\n"
        result = _regex_fallback_finalize_questions(raw)
        assert result["question_count"] == len(result["questions"])


# ---------------------------------------------------------------------------
# _extract_section_from_markdown
# ---------------------------------------------------------------------------

class TestExtractSectionFromMarkdown:
    def test_extracts_named_section(self):
        content = "## Intro\n\nIntro text.\n\n## Feedback\n\nFeedback text.\n\n## Next\n\nNext text."
        result = _extract_section_from_markdown(content, "Feedback")
        assert "Feedback text" in result

    def test_returns_empty_string_when_not_found(self):
        content = "## Intro\n\nIntro text.\n"
        result = _extract_section_from_markdown(content, "Missing Section")
        assert result == ""

    def test_handles_section_with_suffix(self):
        content = "## Open Questions (3 remaining)\n\n- [ ] Q1\n\n## Next\n"
        result = _extract_section_from_markdown(content, "Open Questions")
        assert "Q1" in result

    def test_case_insensitive(self):
        content = "## FEEDBACK\n\nSome feedback.\n"
        result = _extract_section_from_markdown(content, "Feedback")
        assert "feedback" in result.lower()

    def test_last_section_no_trailing_header(self):
        content = "## Feedback\n\nEnd content."
        result = _extract_section_from_markdown(content, "Feedback")
        assert "End content" in result


# ---------------------------------------------------------------------------
# TypedDict structure tests
# ---------------------------------------------------------------------------

class TestTypedDictStructures:
    def test_verdict_result_fields(self):
        result = VerdictResult(verdict="APPROVED", rationale="ok", source="structured")
        assert result["verdict"] == "APPROVED"
        assert result["rationale"] == "ok"
        assert result["source"] == "structured"

    def test_feedback_result_fields(self):
        result = FeedbackResult(
            verdict="REVISE",
            rationale="needs work",
            feedback_items=["item1"],
            open_questions=[],
            resolved_issues=[],
            source="structured",
        )
        assert result["verdict"] == "REVISE"
        assert result["feedback_items"] == ["item1"]

    def test_review_spec_result_fields(self):
        result = ReviewSpecResult(
            verdict="BLOCKED",
            rationale="cannot proceed",
            feedback_items=[],
            source="regex_fallback",
        )
        assert result["verdict"] == "BLOCKED"
        assert result["source"] == "regex_fallback"

    def test_draft_questions_result_fields(self):
        result = DraftQuestionsResult(
            open_questions=[{"text": "Q?", "resolved": False}],
            source="structured",
        )
        assert len(result["open_questions"]) == 1

    def test_finalize_questions_result_fields(self):
        result = FinalizeQuestionsResult(
            has_open_questions=False,
            question_count=0,
            questions=[],
            source="structured",
        )
        assert result["has_open_questions"] is False


# ---------------------------------------------------------------------------
# Counter metric emission — T150 / test_150
# ---------------------------------------------------------------------------

class TestFallbackDebugLogging:
    """T150: logger.debug called on every fallback invocation."""

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_feedback_fallback_logs_debug(self, mock_logger):
        parse_structured_feedback("not json")
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=feedback")

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_review_spec_fallback_logs_debug(self, mock_logger):
        parse_structured_review_spec("not json")
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=review_spec")

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_draft_questions_fallback_logs_debug(self, mock_logger):
        parse_structured_draft_questions("not json")
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=draft_questions")

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_finalize_questions_fallback_logs_debug(self, mock_logger):
        parse_structured_finalize_questions("not json")
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=finalize_questions")

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_no_fallback_metric_from_regex_helpers(self, mock_logger):
        # _regex_fallback_feedback does NOT log the debug metric line itself
        _regex_fallback_feedback("[X] **APPROVE**")
        for c in mock_logger.debug.call_args_list:
            assert "regex_fallback" not in str(c)

    def test_structured_success_returns_structured_source(self):
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
            "open_questions": [],
        })
        result = parse_structured_feedback(raw)
        assert result["source"] == "structured"


# ---------------------------------------------------------------------------
# Edge cases and integration scenarios
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_parse_structured_feedback_none_input(self):
        result = parse_structured_feedback(None)  # type: ignore
        assert result["source"] == "regex_fallback"
        assert result["verdict"] == "UNKNOWN"

    def test_parse_structured_review_spec_none_input(self):
        result = parse_structured_review_spec(None)  # type: ignore
        assert result["source"] == "regex_fallback"

    def test_parse_structured_draft_questions_none_input(self):
        result = parse_structured_draft_questions(None)  # type: ignore
        assert result["source"] == "regex_fallback"

    def test_parse_structured_finalize_questions_none_input(self):
        result = parse_structured_finalize_questions(None)  # type: ignore
        assert result["source"] == "regex_fallback"

    def test_feedback_with_no_resolved_issues_key(self):
        # resolved_issues is optional in schema; missing => defaults to []
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
            "open_questions": [],
        })
        result = parse_structured_feedback(raw)
        assert result["resolved_issues"] == []
        assert result["source"] == "structured"

    def test_review_spec_fallback_extracts_feedback_items(self):
        raw = "[X] **REVISE**\n\n## Feedback\n- Fix section 6\n- Add diffs\n"
        result = parse_structured_review_spec(raw)
        assert result["source"] == "regex_fallback"
        assert "Fix section 6" in result["feedback_items"]

    def test_finalize_questions_both_question_and_todo(self):
        raw = "What is the timeout?\nTODO: fix this\n"
        result = parse_structured_finalize_questions(raw)
        assert result["source"] == "regex_fallback"
        assert result["has_open_questions"] is True
        assert result["question_count"] >= 2

    def test_draft_questions_stops_at_next_section(self):
        raw = "## Open Questions\n- [ ] Q1\n- [ ] Q2\n\n## Other Section\n- [ ] Not a question\n"
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "regex_fallback"
        # Should only find questions from the Open Questions section
        texts = [q["text"] for q in result["open_questions"]]
        assert "Q1" in texts
        assert "Q2" in texts
        assert "Not a question" not in texts