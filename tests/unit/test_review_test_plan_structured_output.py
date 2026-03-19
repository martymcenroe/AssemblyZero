"""Tests for test-plan review node structured output and fallback parsing.

Issue #775: Verify _parse_verdict returns VerdictResult with correct source field.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core.verdict_schema import VerdictResult
from assemblyzero.workflows.testing.nodes.review_test_plan import _parse_verdict


class TestParseVerdictStructuredPath:
    """T130: Structured JSON path returns VerdictResult(source='structured')."""

    def test_approved_structured(self):
        raw = json.dumps({"verdict": "APPROVED", "rationale": "All tests pass"})
        result = _parse_verdict(raw)
        assert result["verdict"] == "APPROVED"
        assert result["rationale"] == "All tests pass"
        assert result["source"] == "structured"

    def test_revise_structured(self):
        raw = json.dumps({"verdict": "REVISE", "rationale": "Missing edge case"})
        result = _parse_verdict(raw)
        assert result["verdict"] == "REVISE"
        assert result["source"] == "structured"

    def test_discuss_structured(self):
        raw = json.dumps({"verdict": "DISCUSS", "rationale": "Needs clarification"})
        result = _parse_verdict(raw)
        assert result["verdict"] == "DISCUSS"
        assert result["source"] == "structured"

    def test_structured_returns_typed_dict_keys(self):
        raw = json.dumps({"verdict": "APPROVED", "rationale": "LGTM"})
        result = _parse_verdict(raw)
        assert "verdict" in result
        assert "rationale" in result
        assert "source" in result

    def test_structured_missing_rationale_defaults_empty(self):
        raw = json.dumps({"verdict": "APPROVED"})
        result = _parse_verdict(raw)
        assert result["verdict"] == "APPROVED"
        assert result["rationale"] == ""
        assert result["source"] == "structured"

    def test_structured_with_extra_fields(self):
        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Needs work",
            "feedback_items": ["Fix test T042"],
        })
        result = _parse_verdict(raw)
        assert result["verdict"] == "REVISE"
        assert result["source"] == "structured"


class TestParseVerdictFallbackPath:
    """T140: Fallback path returns VerdictResult(source='regex_fallback'), emits WARNING."""

    def test_markdown_checkbox_approved_triggers_fallback(self):
        raw = "[X] **APPROVED**\n\nRationale: Looks good"
        result = _parse_verdict(raw)
        assert result["verdict"] == "APPROVED"
        assert result["source"] == "regex_fallback"

    def test_markdown_checkbox_revise_triggers_fallback(self):
        raw = "[X] **REVISE**\n\nRationale: Needs changes"
        result = _parse_verdict(raw)
        assert result["verdict"] == "REVISE"
        assert result["source"] == "regex_fallback"

    def test_markdown_checkbox_discuss_triggers_fallback(self):
        raw = "[X] **DISCUSS**\n\nRationale: Open questions remain"
        result = _parse_verdict(raw)
        assert result["verdict"] == "DISCUSS"
        assert result["source"] == "regex_fallback"

    def test_unparseable_returns_unknown(self):
        raw = "This is just plain text with no verdict"
        result = _parse_verdict(raw)
        assert result["verdict"] == "UNKNOWN"
        assert result["source"] == "regex_fallback"

    def test_empty_string_returns_unknown(self):
        result = _parse_verdict("")
        assert result["verdict"] == "UNKNOWN"
        assert result["source"] == "regex_fallback"

    def test_fallback_logs_warning(self, caplog):
        import logging
        raw = "[X] **APPROVED**\n\nRationale: LGTM"
        with caplog.at_level(logging.WARNING):
            result = _parse_verdict(raw)
        assert result["source"] == "regex_fallback"
        assert any("fallback" in record.message.lower() for record in caplog.records)

    def test_invalid_json_triggers_fallback(self):
        raw = '{"verdict": "APPROVED"'  # malformed JSON
        result = _parse_verdict(raw)
        assert result["source"] == "regex_fallback"

    def test_fallback_returns_typed_dict_keys(self):
        raw = "[X] **REVISE**"
        result = _parse_verdict(raw)
        assert "verdict" in result
        assert "rationale" in result
        assert "source" in result

    def test_case_insensitive_checkbox_match(self):
        raw = "[X] **approved**"
        result = _parse_verdict(raw)
        assert result["verdict"] == "APPROVED"
        assert result["source"] == "regex_fallback"

    def test_blocked_verdict_via_fallback(self):
        raw = "[X] **BLOCKED**\n\nRationale: Blocked by dependency"
        result = _parse_verdict(raw)
        assert result["verdict"] == "BLOCKED"
        assert result["source"] == "regex_fallback"