"""Tests for implementation spec review node structured output.

Issue #775: Replace regex LLM output parsing with structured JSON schema.
Tests for _invoke_reviewer_with_spec_schema and related review_spec node behavior.
"""

import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core.verdict_schema import (
    REVIEW_SPEC_SCHEMA,
    ReviewSpecResult,
    parse_structured_review_spec,
)


def _make_mock_provider(response_content: str):
    """Create a mock provider that returns the given content."""
    mock_result = MagicMock()
    mock_result.content = response_content
    mock_provider = MagicMock()
    mock_provider.invoke.return_value = mock_result
    return mock_provider


def _make_spec_result(
    verdict="APPROVED",
    rationale="LGTM",
    feedback_items=None,
    source="structured",
) -> ReviewSpecResult:
    return ReviewSpecResult(
        verdict=verdict,
        rationale=rationale,
        feedback_items=feedback_items or [],
        source=source,
    )


class TestInvokeReviewerWithSpecSchema:
    """Tests for _invoke_reviewer_with_spec_schema helper."""

    def test_returns_review_spec_result_on_valid_json(self):
        """T120: Helper returns ReviewSpecResult with structured source."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "Spec is complete",
            "feedback_items": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["verdict"] == "APPROVED"
        assert result["rationale"] == "Spec is complete"
        assert result["source"] == "structured"

    def test_passes_json_schema_to_non_gemini_provider(self):
        """T170: Non-Gemini provider receives json_schema kwarg."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Missing diffs",
            "feedback_items": ["Add diff for section 6"],
        })
        provider = _make_mock_provider(raw)

        _invoke_reviewer_with_spec_schema(provider, "prompt text", "system text")

        provider.invoke.assert_called_once()
        call_kwargs = provider.invoke.call_args[1]
        assert "json_schema" in call_kwargs
        assert call_kwargs["json_schema"] == REVIEW_SPEC_SCHEMA
        assert "response_schema" not in call_kwargs

    def test_passes_response_schema_to_gemini_provider(self):
        """T170: GeminiProvider receives response_schema kwarg instead of json_schema."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )
        from assemblyzero.core.llm_provider import GeminiProvider

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
        })
        mock_result = MagicMock()
        mock_result.content = raw
        gemini_provider = MagicMock(spec=GeminiProvider)
        gemini_provider.invoke.return_value = mock_result

        _invoke_reviewer_with_spec_schema(gemini_provider, "prompt", "system")

        gemini_provider.invoke.assert_called_once()
        call_kwargs = gemini_provider.invoke.call_args[1]
        assert "response_schema" in call_kwargs
        assert call_kwargs["response_schema"] == REVIEW_SPEC_SCHEMA
        assert "json_schema" not in call_kwargs

    def test_falls_back_to_regex_on_malformed_json(self):
        """Fallback path triggered when provider returns non-JSON markdown."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = "[X] **APPROVED**\n\nRationale: Looks good"
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["verdict"] == "APPROVED"
        assert result["source"] == "regex_fallback"

    def test_revise_verdict_propagated(self):
        """REVISE verdict from structured result is returned correctly."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Missing diffs",
            "feedback_items": ["Add diff for section 6"],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["verdict"] == "REVISE"
        assert result["feedback_items"] == ["Add diff for section 6"]

    def test_blocked_verdict_propagated(self):
        """BLOCKED verdict from structured result is returned correctly."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = json.dumps({
            "verdict": "BLOCKED",
            "rationale": "Fundamental design issue",
            "feedback_items": ["Rethink architecture"],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["verdict"] == "BLOCKED"
        assert result["source"] == "structured"

    def test_system_prompt_passed_as_first_positional_arg(self):
        """Verify invoke is called with system prompt as first arg."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
        })
        provider = _make_mock_provider(raw)

        _invoke_reviewer_with_spec_schema(provider, "the prompt", "the system")

        call_args = provider.invoke.call_args
        assert call_args[0][0] == "the system"
        assert call_args[0][1] == "the prompt"


class TestParseReviewVerdict:
    """Tests for parse_review_verdict function."""

    def test_valid_json_returns_approved(self):
        """T030/test_040: parse_review_verdict returns APPROVED from JSON."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            parse_review_verdict,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "Spec is implementable",
            "feedback_items": [],
        })

        verdict, feedback = parse_review_verdict(raw)

        assert verdict == "APPROVED"
        assert feedback == "Spec is implementable"

    def test_valid_json_returns_revise_with_feedback(self):
        """parse_review_verdict returns REVISE with feedback from JSON."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            parse_review_verdict,
        )

        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Missing error handling",
            "feedback_items": ["Add try/except in node.py line 145"],
        })

        verdict, feedback = parse_review_verdict(raw)

        assert verdict == "REVISE"
        assert "Missing error handling" in feedback

    def test_valid_json_returns_blocked(self):
        """parse_review_verdict returns BLOCKED from valid JSON."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            parse_review_verdict,
        )

        raw = json.dumps({
            "verdict": "BLOCKED",
            "rationale": "Fundamental design conflict",
            "feedback_items": [],
        })

        verdict, feedback = parse_review_verdict(raw)

        assert verdict == "BLOCKED"

    def test_unknown_verdict_remapped_to_blocked(self):
        """UNKNOWN verdict from failed parse is remapped to BLOCKED."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            parse_review_verdict,
        )

        raw = "This is just plain text with no verdict"

        verdict, feedback = parse_review_verdict(raw)

        assert verdict == "BLOCKED"

    def test_fallback_markdown_returns_verdict(self):
        """Legacy markdown checkbox returns correct verdict via fallback."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            parse_review_verdict,
        )

        raw = "[X] **REVISE**\n\nRationale: Needs more detail"

        verdict, feedback = parse_review_verdict(raw)

        assert verdict == "REVISE"

    def test_feedback_from_items_when_no_rationale(self):
        """feedback_items used as feedback when rationale is empty."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            parse_review_verdict,
        )

        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "",
            "feedback_items": ["Add diff for section 6", "Fix example in T030"],
        })

        verdict, feedback = parse_review_verdict(raw)

        assert verdict == "REVISE"
        assert "Add diff for section 6" in feedback


class TestSchemaPassedToProvider:
    """T170: Verify REVIEW_SPEC_SCHEMA is passed to provider.invoke()."""

    def test_review_spec_schema_has_required_fields(self):
        """REVIEW_SPEC_SCHEMA contains verdict, rationale, feedback_items."""
        required = REVIEW_SPEC_SCHEMA.get("required", [])
        assert "verdict" in required
        assert "rationale" in required
        assert "feedback_items" in required

    def test_review_spec_schema_verdict_enum_values(self):
        """REVIEW_SPEC_SCHEMA verdict enum contains APPROVED, REVISE, BLOCKED."""
        verdict_prop = REVIEW_SPEC_SCHEMA["properties"]["verdict"]
        assert "enum" in verdict_prop
        assert set(verdict_prop["enum"]) == {"APPROVED", "REVISE", "BLOCKED"}

    def test_review_spec_schema_no_discuss(self):
        """REVIEW_SPEC_SCHEMA does not contain DISCUSS (unlike FEEDBACK_SCHEMA)."""
        verdict_prop = REVIEW_SPEC_SCHEMA["properties"]["verdict"]
        assert "DISCUSS" not in verdict_prop["enum"]

    def test_review_spec_schema_has_blocked_not_feedback(self):
        """REVIEW_SPEC_SCHEMA has BLOCKED; FEEDBACK_SCHEMA does not."""
        from assemblyzero.core.verdict_schema import FEEDBACK_SCHEMA

        spec_enum = set(REVIEW_SPEC_SCHEMA["properties"]["verdict"]["enum"])
        feedback_enum = set(FEEDBACK_SCHEMA["properties"]["verdict"]["enum"])

        assert "BLOCKED" in spec_enum
        assert "BLOCKED" not in feedback_enum
        assert "DISCUSS" in feedback_enum
        assert "DISCUSS" not in spec_enum


class TestReviewSpecResultPropagation:
    """T120: Structured result fields propagate correctly."""

    def test_feedback_items_populated_from_structured(self):
        """feedback_items from structured result are accessible."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        items = ["Add diff for section 6", "Fix example in T030", "Update test T040"]
        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Several issues",
            "feedback_items": items,
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["feedback_items"] == items

    def test_source_is_structured_on_valid_json(self):
        """source field is 'structured' when JSON parse succeeds."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["source"] == "structured"

    def test_source_is_regex_fallback_on_markdown(self):
        """source field is 'regex_fallback' when JSON parse fails."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = "[X] **REVISE**\n\nRationale: missing tests"
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["source"] == "regex_fallback"

    def test_empty_feedback_items_when_approved(self):
        """feedback_items is empty list for APPROVED verdict."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "All good",
            "feedback_items": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["feedback_items"] == []


class TestFallbackBehavior:
    """Tests for regex fallback path in review_spec node."""

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_fallback_logs_debug_metric(self, mock_logger):
        """T150: logger.debug called when fallback fires in review_spec parse."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = "[X] **REVISE**\n\n## Required Changes\n- Fix error handling"
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["source"] == "regex_fallback"
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=review_spec")

    def test_no_fallback_on_structured_success(self):
        """Structured parse succeeds — source is 'structured'."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "LGTM",
            "feedback_items": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["source"] == "structured"

    def test_empty_response_returns_unknown_or_revise(self):
        """Empty provider response returns fallback result."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        provider = _make_mock_provider("")

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["source"] == "regex_fallback"
        assert result["verdict"] in {"UNKNOWN", "REVISE"}

    def test_feedback_items_extracted_via_fallback(self):
        """Feedback items extracted from markdown via regex fallback."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = (
            "[X] **REVISE**\n\n"
            "## Required Changes\n"
            "- Fix error handling\n"
            "- Add missing tests\n"
        )
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["source"] == "regex_fallback"
        assert "Fix error handling" in result["feedback_items"]
        assert "Add missing tests" in result["feedback_items"]

    def test_feedback_section_also_extracted(self):
        """Feedback items extracted from ## Feedback section via regex fallback."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = (
            "[X] **REVISE**\n\n"
            "## Feedback\n"
            "- Update section 6\n"
            "- Add concrete examples\n"
        )
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["source"] == "regex_fallback"
        assert "Update section 6" in result["feedback_items"]


class TestNoInlineSchemasInReviewSpecNode:
    """T180: No inline schema dict literals in review_spec.py."""

    def test_no_inline_schema_literals(self):
        """review_spec.py should not define REVIEW_SPEC_SCHEMA inline."""
        review_path = pathlib.Path(
            "assemblyzero/workflows/implementation_spec/nodes/review_spec.py"
        )
        if not review_path.exists():
            pytest.skip("review_spec.py not found")

        content = review_path.read_text()

        lines = content.splitlines()
        inline_schema_lines = [
            line for line in lines
            if '"enum"' in line and '"verdict"' in line and "verdict_schema" not in line
        ]
        assert len(inline_schema_lines) == 0, (
            f"Found potential inline schema in review_spec.py: {inline_schema_lines}"
        )

    def test_imports_review_spec_schema_from_verdict_schema(self):
        """review_spec.py imports REVIEW_SPEC_SCHEMA from verdict_schema module."""
        review_path = pathlib.Path(
            "assemblyzero/workflows/implementation_spec/nodes/review_spec.py"
        )
        if not review_path.exists():
            pytest.skip("review_spec.py not found")

        content = review_path.read_text()
        assert "from assemblyzero.core.verdict_schema" in content
        assert "REVIEW_SPEC_SCHEMA" in content

    def test_imports_invoke_helper(self):
        """review_spec.py defines or imports _invoke_reviewer_with_spec_schema."""
        review_path = pathlib.Path(
            "assemblyzero/workflows/implementation_spec/nodes/review_spec.py"
        )
        if not review_path.exists():
            pytest.skip("review_spec.py not found")

        content = review_path.read_text()
        assert "_invoke_reviewer_with_spec_schema" in content


class TestReviewSpecResultTypeDict:
    """Tests for ReviewSpecResult TypedDict structure."""

    def test_review_spec_result_has_required_fields(self):
        """ReviewSpecResult TypedDict has verdict, rationale, feedback_items, source."""
        result = ReviewSpecResult(
            verdict="APPROVED",
            rationale="ok",
            feedback_items=[],
            source="structured",
        )
        assert result["verdict"] == "APPROVED"
        assert result["rationale"] == "ok"
        assert result["feedback_items"] == []
        assert result["source"] == "structured"

    def test_review_spec_result_with_blocked(self):
        """ReviewSpecResult supports BLOCKED verdict."""
        result = ReviewSpecResult(
            verdict="BLOCKED",
            rationale="Design conflict",
            feedback_items=["Rethink approach"],
            source="structured",
        )
        assert result["verdict"] == "BLOCKED"

    def test_review_spec_result_regex_fallback_source(self):
        """ReviewSpecResult supports regex_fallback source."""
        result = ReviewSpecResult(
            verdict="REVISE",
            rationale="",
            feedback_items=[],
            source="regex_fallback",
        )
        assert result["source"] == "regex_fallback"


class TestParseStructuredReviewSpecDirect:
    """Direct tests for parse_structured_review_spec function."""

    def test_valid_json_approved(self):
        """parse_structured_review_spec returns structured result for APPROVED."""
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "All good",
            "feedback_items": [],
        })
        result = parse_structured_review_spec(raw)
        assert result["verdict"] == "APPROVED"
        assert result["source"] == "structured"

    def test_valid_json_blocked(self):
        """parse_structured_review_spec accepts BLOCKED verdict."""
        raw = json.dumps({
            "verdict": "BLOCKED",
            "rationale": "Fundamental issue",
            "feedback_items": ["Redesign required"],
        })
        result = parse_structured_review_spec(raw)
        assert result["verdict"] == "BLOCKED"
        assert result["source"] == "structured"

    def test_missing_feedback_items_falls_back(self):
        """Missing feedback_items triggers fallback."""
        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "needs work",
        })
        result = parse_structured_review_spec(raw)
        assert result["source"] == "regex_fallback"

    def test_invalid_verdict_enum_falls_back(self):
        """Invalid verdict (e.g. DISCUSS) triggers fallback for review_spec."""
        raw = json.dumps({
            "verdict": "DISCUSS",
            "rationale": "Let's talk",
            "feedback_items": [],
        })
        result = parse_structured_review_spec(raw)
        assert result["source"] == "regex_fallback"

    def test_malformed_json_falls_back(self):
        """Malformed JSON triggers fallback."""
        raw = "not valid json {"
        result = parse_structured_review_spec(raw)
        assert result["source"] == "regex_fallback"

    @patch("assemblyzero.core.verdict_schema.logger")
    def test_fallback_logs_debug_with_review_spec_tag(self, mock_logger):
        """logger.debug called with parser=review_spec on fallback."""
        raw = "[X] **APPROVED**"
        result = parse_structured_review_spec(raw)
        assert result["source"] == "regex_fallback"
        mock_logger.debug.assert_any_call("verdict_schema.regex_fallback parser=review_spec")

    def test_structured_success_returns_structured_source(self):
        """Structured parse succeeds — source is 'structured'."""
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
        })
        result = parse_structured_review_spec(raw)
        assert result["source"] == "structured"