"""Tests for draft open-questions extraction in generate_draft node.

Issue #775: Replace regex LLM output parsing with structured JSON schema.
Tests for _extract_open_questions helper and related behavior.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core.verdict_schema import (
    DRAFT_QUESTIONS_SCHEMA,
    DraftQuestionsResult,
    parse_structured_draft_questions,
)
from assemblyzero.workflows.requirements.nodes.generate_draft import _extract_open_questions


def _make_mock_provider(response_content: str):
    """Create a mock provider that returns the given content."""
    provider = MagicMock()
    result = MagicMock()
    result.content = response_content
    provider.invoke.return_value = result
    return provider


class TestExtractOpenQuestionsStructuredPath:
    """Tests for _extract_open_questions with valid JSON input."""

    def test_valid_json_returns_structured_source(self):
        response = json.dumps({
            "open_questions": [
                {"text": "What is the timeout?", "resolved": False},
            ]
        })
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "structured"

    def test_valid_json_single_question(self):
        response = json.dumps({
            "open_questions": [
                {"text": "What is the timeout?", "resolved": False},
            ]
        })
        result = _extract_open_questions(MagicMock(), response, "")
        assert len(result["open_questions"]) == 1
        assert result["open_questions"][0]["text"] == "What is the timeout?"
        assert result["open_questions"][0]["resolved"] is False

    def test_valid_json_multiple_questions(self):
        response = json.dumps({
            "open_questions": [
                {"text": "What is the timeout?", "resolved": False},
                {"text": "Rate limit decided", "resolved": True},
            ]
        })
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "structured"
        assert len(result["open_questions"]) == 2

    def test_valid_json_resolved_question(self):
        response = json.dumps({
            "open_questions": [
                {"text": "Rate limit decided", "resolved": True},
            ]
        })
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["open_questions"][0]["resolved"] is True

    def test_valid_json_empty_questions_list(self):
        response = json.dumps({"open_questions": []})
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "structured"
        assert result["open_questions"] == []

    def test_valid_json_mixed_resolved_states(self):
        response = json.dumps({
            "open_questions": [
                {"text": "Unresolved question?", "resolved": False},
                {"text": "Resolved question", "resolved": True},
                {"text": "Another unresolved?", "resolved": False},
            ]
        })
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "structured"
        assert len(result["open_questions"]) == 3
        unresolved = [q for q in result["open_questions"] if not q["resolved"]]
        resolved = [q for q in result["open_questions"] if q["resolved"]]
        assert len(unresolved) == 2
        assert len(resolved) == 1

    def test_returns_draft_questions_result_type(self):
        response = json.dumps({
            "open_questions": [{"text": "Question?", "resolved": False}]
        })
        result = _extract_open_questions(MagicMock(), response, "")
        assert "open_questions" in result
        assert "source" in result

    def test_provider_not_called_when_json_parseable(self):
        """_extract_open_questions parses existing response directly, no LLM call needed."""
        provider = _make_mock_provider("")
        response = json.dumps({"open_questions": []})
        _extract_open_questions(provider, response, "system prompt")
        # Provider.invoke should NOT be called since response is already parseable
        provider.invoke.assert_not_called()


class TestExtractOpenQuestionsMarkdownFallback:
    """Tests for _extract_open_questions with markdown (regex fallback) input."""

    def test_markdown_fallback_returns_regex_fallback_source(self):
        response = "## Open Questions\n- [ ] What is the timeout?\n"
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "regex_fallback"

    def test_markdown_unchecked_question_extracted(self):
        response = "## Open Questions\n- [ ] What is the timeout?\n"
        result = _extract_open_questions(MagicMock(), response, "")
        assert len(result["open_questions"]) == 1
        assert result["open_questions"][0]["text"] == "What is the timeout?"
        assert result["open_questions"][0]["resolved"] is False

    def test_markdown_checked_question_extracted(self):
        response = "## Open Questions\n- [X] Rate limit decided\n"
        result = _extract_open_questions(MagicMock(), response, "")
        assert len(result["open_questions"]) == 1
        assert result["open_questions"][0]["text"] == "Rate limit decided"
        assert result["open_questions"][0]["resolved"] is True

    def test_markdown_mixed_questions(self):
        response = "## Open Questions\n- [ ] What is the timeout?\n- [X] Rate limit decided\n"
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "regex_fallback"
        assert len(result["open_questions"]) == 2

    def test_markdown_no_open_questions_section(self):
        response = "## Requirements\n\nThe system shall process requests.\n"
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "regex_fallback"
        assert result["open_questions"] == []

    def test_markdown_questions_stop_at_next_section(self):
        response = (
            "## Open Questions\n"
            "- [ ] What is the timeout?\n"
            "## Next Section\n"
            "- [ ] Not a question\n"
        )
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "regex_fallback"
        # Should only extract from Open Questions section
        assert len(result["open_questions"]) == 1
        assert result["open_questions"][0]["text"] == "What is the timeout?"

    def test_markdown_case_insensitive_checked_box(self):
        response = "## Open Questions\n- [x] resolved question\n"
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "regex_fallback"


class TestExtractOpenQuestionsEdgeCases:
    """Edge cases for _extract_open_questions."""

    def test_empty_response_returns_regex_fallback(self):
        result = _extract_open_questions(MagicMock(), "", "")
        assert result["source"] == "regex_fallback"
        assert result["open_questions"] == []

    def test_none_like_empty_string(self):
        result = _extract_open_questions(MagicMock(), "", "system")
        assert "open_questions" in result
        assert "source" in result

    def test_invalid_json_falls_back_to_regex(self):
        response = '{"open_questions": [{"text": "missing bracket"'
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "regex_fallback"

    def test_json_missing_open_questions_key_falls_back(self):
        response = json.dumps({"verdict": "APPROVED", "rationale": "OK"})
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "regex_fallback"

    def test_plain_text_returns_regex_fallback(self):
        response = "This is just plain text with no structure."
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "regex_fallback"
        assert result["open_questions"] == []

    def test_provider_param_accepted(self):
        """_extract_open_questions accepts provider param without error."""
        provider = _make_mock_provider("")
        response = json.dumps({"open_questions": []})
        # Should not raise
        result = _extract_open_questions(provider, response, "system prompt")
        assert result is not None

    def test_system_prompt_param_accepted(self):
        """_extract_open_questions accepts system_prompt param without error."""
        response = json.dumps({"open_questions": []})
        result = _extract_open_questions(MagicMock(), response, "system prompt text")
        assert result is not None


class TestExtractOpenQuestionsDebugLogging:
    """T150: logger.debug called on fallback invocation."""

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_fallback_logs_debug(self, mock_logger):
        response = "## Open Questions\n- [ ] What is the timeout?\n"
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "regex_fallback"
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=draft_questions")

    def test_structured_success_returns_structured_source(self):
        response = json.dumps({"open_questions": []})
        result = _extract_open_questions(MagicMock(), response, "")
        assert result["source"] == "structured"

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_empty_input_logs_debug(self, mock_logger):
        result = _extract_open_questions(MagicMock(), "", "")
        assert result["source"] == "regex_fallback"
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=draft_questions")


class TestParseStructuredDraftQuestionsDirect:
    """Direct tests for parse_structured_draft_questions function."""

    def test_valid_json_returns_structured(self):
        raw = json.dumps({
            "open_questions": [{"text": "What timeout?", "resolved": False}]
        })
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "structured"
        assert len(result["open_questions"]) == 1

    def test_empty_list_valid(self):
        raw = json.dumps({"open_questions": []})
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "structured"
        assert result["open_questions"] == []

    def test_missing_key_falls_back(self):
        raw = json.dumps({"verdict": "APPROVED"})
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "regex_fallback"

    def test_malformed_json_falls_back(self):
        raw = "{not valid json"
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "regex_fallback"

    def test_empty_string_falls_back(self):
        result = parse_structured_draft_questions("")
        assert result["source"] == "regex_fallback"

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_fallback_logs_debug_with_draft_questions_tag(self, mock_logger):
        result = parse_structured_draft_questions("not json")
        assert result["source"] == "regex_fallback"
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=draft_questions")

    def test_structured_returns_structured_source(self):
        raw = json.dumps({"open_questions": []})
        result = parse_structured_draft_questions(raw)
        assert result["source"] == "structured"

    def test_question_text_and_resolved_preserved(self):
        raw = json.dumps({
            "open_questions": [
                {"text": "Q1?", "resolved": False},
                {"text": "Q2?", "resolved": True},
            ]
        })
        result = parse_structured_draft_questions(raw)
        assert result["open_questions"][0]["text"] == "Q1?"
        assert result["open_questions"][0]["resolved"] is False
        assert result["open_questions"][1]["text"] == "Q2?"
        assert result["open_questions"][1]["resolved"] is True


class TestDraftQuestionsSchema:
    """Tests for DRAFT_QUESTIONS_SCHEMA structure."""

    def test_schema_has_open_questions_required(self):
        assert "open_questions" in DRAFT_QUESTIONS_SCHEMA.get("required", [])

    def test_schema_open_questions_is_array(self):
        props = DRAFT_QUESTIONS_SCHEMA["properties"]
        assert props["open_questions"]["type"] == "array"

    def test_schema_item_has_text_and_resolved(self):
        items = DRAFT_QUESTIONS_SCHEMA["properties"]["open_questions"]["items"]
        assert "text" in items["properties"]
        assert "resolved" in items["properties"]

    def test_schema_item_required_fields(self):
        items = DRAFT_QUESTIONS_SCHEMA["properties"]["open_questions"]["items"]
        assert "text" in items["required"]
        assert "resolved" in items["required"]


class TestNoInlineSchemasInGenerateDraftNode:
    """T180: No inline schema dict literals in generate_draft.py."""

    def test_no_inline_schema_literals(self):
        """generate_draft.py should not define DRAFT_QUESTIONS_SCHEMA inline."""
        import pathlib
        node_path = pathlib.Path("assemblyzero/workflows/requirements/nodes/generate_draft.py")
        if node_path.exists():
            content = node_path.read_text()
            # The schema should be imported, not defined inline
            assert "DRAFT_QUESTIONS_SCHEMA" not in content.split("from assemblyzero")[0] or \
                   "DRAFT_QUESTIONS_SCHEMA = {" not in content

    def test_imports_draft_questions_schema_from_verdict_schema(self):
        """generate_draft.py imports DRAFT_QUESTIONS_SCHEMA from verdict_schema module."""
        import pathlib
        node_path = pathlib.Path("assemblyzero/workflows/requirements/nodes/generate_draft.py")
        if node_path.exists():
            content = node_path.read_text()
            assert "DRAFT_QUESTIONS_SCHEMA" in content
            assert "verdict_schema" in content