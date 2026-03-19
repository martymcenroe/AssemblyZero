"""Tests for finalize question detection structured output.

Issue #775: Verify _detect_open_questions and validate_lld_final use
structured JSON parse with regex fallback.
"""

import json
from unittest.mock import patch
import pytest

from assemblyzero.workflows.requirements.nodes.finalize import (
    _detect_open_questions,
    validate_lld_final,
)


class TestDetectOpenQuestionsStructured:
    """T060: Structured JSON content detection."""

    def test_structured_json_with_questions(self):
        content = json.dumps({
            "has_open_questions": True,
            "question_count": 1,
            "questions": ["What timeout value?"],
        })
        result = _detect_open_questions(content)
        assert result["source"] == "structured"
        assert result["has_open_questions"] is True
        assert result["question_count"] == 1
        assert "What timeout value?" in result["questions"]

    def test_structured_json_no_questions(self):
        content = json.dumps({
            "has_open_questions": False,
            "question_count": 0,
            "questions": [],
        })
        result = _detect_open_questions(content)
        assert result["source"] == "structured"
        assert result["has_open_questions"] is False
        assert result["question_count"] == 0
        assert result["questions"] == []

    def test_structured_json_multiple_questions(self):
        content = json.dumps({
            "has_open_questions": True,
            "question_count": 2,
            "questions": ["What timeout value?", "TODO: fix this"],
        })
        result = _detect_open_questions(content)
        assert result["source"] == "structured"
        assert result["question_count"] == 2
        assert len(result["questions"]) == 2


class TestDetectOpenQuestionsRegexFallback:
    """T070: Regex fallback for plain text content."""

    def test_markdown_content_with_question(self):
        content = "## Requirements\n\nWhat timeout value?\nThe system shall process requests.\n"
        result = _detect_open_questions(content)
        assert result["source"] == "regex_fallback"
        assert result["has_open_questions"] is True
        assert "What timeout value?" in result["questions"]

    def test_markdown_content_with_todo(self):
        content = "## Design\n\nTODO: determine rate limit\nImplement retry logic.\n"
        result = _detect_open_questions(content)
        assert result["source"] == "regex_fallback"
        assert result["has_open_questions"] is True
        assert any("TODO" in q for q in result["questions"])

    def test_markdown_content_with_both(self):
        content = "## Requirements\n\nThe system should TODO: determine rate limit\nWhat timeout value?\n"
        result = _detect_open_questions(content)
        assert result["source"] == "regex_fallback"
        assert result["has_open_questions"] is True
        assert result["question_count"] >= 2

    def test_clean_content_no_issues(self):
        content = "## Requirements\n\nThe system shall process requests within 200ms.\nAll responses are JSON.\n"
        result = _detect_open_questions(content)
        assert result["source"] == "regex_fallback"
        assert result["has_open_questions"] is False
        assert result["question_count"] == 0

    def test_empty_content(self):
        result = _detect_open_questions("")
        assert result["source"] == "regex_fallback"
        assert result["has_open_questions"] is False
        assert result["question_count"] == 0

    def test_short_question_mark_not_detected(self):
        # Lines ending with ? but very short (noise filtering)
        content = "Why?\n"
        result = _detect_open_questions(content)
        assert result["source"] == "regex_fallback"
        # "Why?" is only 4 chars, below the 5-char threshold
        assert result["has_open_questions"] is False

    def test_longer_question_detected(self):
        content = "Why is this?\n"
        result = _detect_open_questions(content)
        assert result["source"] == "regex_fallback"
        assert result["has_open_questions"] is True

    def test_todo_case_insensitive(self):
        content = "todo: fix the rate limiting logic\n"
        result = _detect_open_questions(content)
        assert result["source"] == "regex_fallback"
        assert result["has_open_questions"] is True

    def test_invalid_json_falls_back_to_regex(self):
        content = '{"has_open_questions": true, "invalid json'
        result = _detect_open_questions(content)
        assert result["source"] == "regex_fallback"


class TestValidateLldFinalStructured:
    """Integration with validate_lld_final using structured detection."""

    def test_questions_detected_when_not_resolved(self):
        content = "## Section\n\nWhat is the correct timeout value?\n"
        issues = validate_lld_final(content, open_questions_resolved=False)
        assert any("unresolved questions" in i for i in issues)

    def test_no_questions_when_resolved(self):
        content = "## Section\n\nWhat is the correct timeout value?\n"
        issues = validate_lld_final(content, open_questions_resolved=True)
        assert not any("unresolved questions" in i for i in issues)

    def test_todos_detected_even_when_questions_resolved(self):
        content = "## Section\n\nTODO: finalize this section\n"
        issues = validate_lld_final(content, open_questions_resolved=True)
        assert any("TODO" in i for i in issues)

    def test_todos_detected_when_not_resolved(self):
        content = "## Section\n\nTODO: finalize this section\n"
        issues = validate_lld_final(content, open_questions_resolved=False)
        assert any("TODO" in i for i in issues)

    def test_clean_content_no_issues(self):
        content = "## Section\n\nThe system shall process requests within 200ms.\n"
        issues = validate_lld_final(content, open_questions_resolved=False)
        assert not any("unresolved questions" in i for i in issues)
        assert not any("TODO" in i for i in issues)

    def test_both_question_and_todo(self):
        content = "## Section\n\nWhat timeout value?\nTODO: fix this\n"
        issues = validate_lld_final(content, open_questions_resolved=False)
        assert any("unresolved questions" in i for i in issues)
        assert any("TODO" in i for i in issues)

    def test_returns_list(self):
        content = "## Section\n\nThe system processes requests.\n"
        issues = validate_lld_final(content)
        assert isinstance(issues, list)


class TestDetectOpenQuestionsReturnType:
    """Verify FinalizeQuestionsResult TypedDict structure."""

    def test_has_required_keys(self):
        result = _detect_open_questions("some content with a question?")
        assert "has_open_questions" in result
        assert "question_count" in result
        assert "questions" in result
        assert "source" in result

    def test_source_is_string(self):
        result = _detect_open_questions("content")
        assert isinstance(result["source"], str)
        assert result["source"] in ("structured", "regex_fallback")

    def test_has_open_questions_is_bool(self):
        result = _detect_open_questions("content")
        assert isinstance(result["has_open_questions"], bool)

    def test_question_count_is_int(self):
        result = _detect_open_questions("content")
        assert isinstance(result["question_count"], int)

    def test_questions_is_list(self):
        result = _detect_open_questions("content")
        assert isinstance(result["questions"], list)

    def test_question_count_matches_questions_length(self):
        content = "## Section\n\nWhat timeout value?\nTODO: fix this\n"
        result = _detect_open_questions(content)
        assert result["question_count"] == len(result["questions"])