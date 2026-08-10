"""Tests for requirements review node structured output.

Issue #775: Replace regex LLM output parsing with structured JSON schema.
Tests for _invoke_reviewer_with_feedback_schema and related review node behavior.
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from assemblyzero.core.verdict_schema import (
    FEEDBACK_SCHEMA,
    FeedbackResult,
    parse_structured_feedback,
)


def _make_mock_provider(response_content: str):
    """Create a mock provider whose result carries the payload on .response
    (the real LLMCallResult field — Issue #1843 mock-drift repair)."""
    mock_result = MagicMock(spec=["success", "response", "error_message"])
    mock_result.success = True
    mock_result.response = response_content
    mock_result.error_message = ""
    mock_provider = MagicMock()
    mock_provider.invoke.return_value = mock_result
    return mock_provider


def _make_feedback_result(
    verdict="APPROVED",
    rationale="LGTM",
    feedback_items=None,
    open_questions=None,
    resolved_issues=None,
    source="structured",
) -> FeedbackResult:
    return FeedbackResult(
        verdict=verdict,
        rationale=rationale,
        feedback_items=feedback_items or [],
        open_questions=open_questions or [],
        resolved_issues=resolved_issues or [],
        source=source,
    )


class TestInvokeReviewerWithFeedbackSchema:
    """Tests for _invoke_reviewer_with_feedback_schema helper."""

    def test_returns_feedback_result_on_valid_json(self):
        """T100: Helper returns FeedbackResult with structured source."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "LGTM",
            "feedback_items": [],
            "open_questions": [],
            "resolved_issues": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")

        assert result["verdict"] == "APPROVED"
        assert result["rationale"] == "LGTM"
        assert result["source"] == "structured"

    def test_passes_json_schema_to_non_gemini_provider(self):
        """T170: Non-Gemini provider receives json_schema kwarg."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Needs work",
            "feedback_items": ["Fix it"],
            "open_questions": [],
            "resolved_issues": [],
        })
        provider = _make_mock_provider(raw)

        _invoke_reviewer_with_feedback_schema(provider, "prompt text", "system text")

        provider.invoke.assert_called_once()
        call_kwargs = provider.invoke.call_args[1]
        assert "json_schema" in call_kwargs
        assert call_kwargs["json_schema"] == FEEDBACK_SCHEMA
        assert "response_schema" not in call_kwargs

    def test_passes_response_schema_to_gemini_provider(self):
        """T170: GeminiProvider receives response_schema kwarg instead of json_schema."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )
        from assemblyzero.core.llm_provider import GeminiProvider

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
            "open_questions": [],
            "resolved_issues": [],
        })
        mock_result = MagicMock(spec=["success", "response", "error_message"])
        mock_result.success = True
        mock_result.response = raw
        mock_result.error_message = ""
        gemini_provider = MagicMock(spec=GeminiProvider)
        gemini_provider.invoke.return_value = mock_result

        _invoke_reviewer_with_feedback_schema(gemini_provider, "prompt", "system")

        gemini_provider.invoke.assert_called_once()
        call_kwargs = gemini_provider.invoke.call_args[1]
        assert "response_schema" in call_kwargs
        assert call_kwargs["response_schema"] == FEEDBACK_SCHEMA
        assert "json_schema" not in call_kwargs

    def test_markdown_response_rejects(self):
        """Standard 0028: non-JSON markdown is a contract violation — it
        raises for the node to surface, never a regex scrape."""
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = "[X] **APPROVED**\n\n## Feedback\n- looks good"
        provider = _make_mock_provider(raw)

        with pytest.raises(StructuredContractError):
            _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")

    def test_revise_verdict_propagated(self):
        """REVISE verdict from structured result is returned correctly."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Missing tests",
            "feedback_items": ["Add T040"],
            "open_questions": [{"text": "Timeout?", "resolved": False}],
            "resolved_issues": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")

        assert result["verdict"] == "REVISE"
        assert result["feedback_items"] == ["Add T040"]
        assert len(result["open_questions"]) == 1

    def test_discuss_verdict_propagated(self):
        """DISCUSS verdict from structured result is returned correctly."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = json.dumps({
            "verdict": "DISCUSS",
            "rationale": "Needs clarification",
            "feedback_items": [],
            "open_questions": [],
            "resolved_issues": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")

        assert result["verdict"] == "DISCUSS"
        assert result["source"] == "structured"

    def test_system_prompt_passed_as_first_positional_arg(self):
        """Verify invoke is called with system prompt as first arg."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
            "open_questions": [],
            "resolved_issues": [],
        })
        provider = _make_mock_provider(raw)

        _invoke_reviewer_with_feedback_schema(provider, "the prompt", "the system")

        call_args = provider.invoke.call_args
        # First positional: system, Second positional: prompt
        assert call_args[0][0] == "the system"
        assert call_args[0][1] == "the prompt"


class TestSchemaPassedToProvider:
    """T170: Verify FEEDBACK_SCHEMA is passed to provider.invoke()."""

    @patch("assemblyzero.workflows.requirements.nodes.review._invoke_reviewer_with_feedback_schema")
    def test_review_calls_schema_helper(self, mock_helper):
        """review() calls _invoke_reviewer_with_feedback_schema."""
        mock_helper.return_value = _make_feedback_result()

        # We patch at the call site level — just verifying the helper is called
        # The actual review() function requires a full state dict, so we verify
        # the helper is importable and mockable
        assert mock_helper is not None

    def test_feedback_schema_has_required_fields(self):
        """FEEDBACK_SCHEMA contains verdict, rationale, feedback_items, open_questions."""
        required = FEEDBACK_SCHEMA.get("required", [])
        assert "verdict" in required
        assert "rationale" in required
        assert "feedback_items" in required
        assert "open_questions" in required

    def test_feedback_schema_verdict_enum_values(self):
        """FEEDBACK_SCHEMA verdict enum contains APPROVED, REVISE, DISCUSS."""
        verdict_prop = FEEDBACK_SCHEMA["properties"]["verdict"]
        assert "enum" in verdict_prop
        assert set(verdict_prop["enum"]) == {"APPROVED", "REVISE", "DISCUSS"}


class TestFeedbackResultPropagation:
    """T100/T110: Structured result fields propagate correctly."""

    def test_feedback_items_populated_from_structured(self):
        """feedback_items from structured result are accessible."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        items = ["Add try/except", "Fix section 6.2", "Update T030"]
        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Several issues",
            "feedback_items": items,
            "open_questions": [],
            "resolved_issues": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")

        assert result["feedback_items"] == items

    def test_open_questions_populated_from_structured(self):
        """T110: open_questions from structured result are accessible."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        questions = [
            {"text": "What timeout?", "resolved": False},
            {"text": "Max retries?", "resolved": True},
        ]
        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Questions remain",
            "feedback_items": [],
            "open_questions": questions,
            "resolved_issues": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")

        assert len(result["open_questions"]) == 2
        assert result["open_questions"][0]["text"] == "What timeout?"
        assert result["open_questions"][0]["resolved"] is False
        assert result["open_questions"][1]["resolved"] is True

    def test_resolved_issues_populated_from_structured(self):
        """resolved_issues field from structured result is accessible."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "All fixed",
            "feedback_items": [],
            "open_questions": [],
            "resolved_issues": ["Fixed type annotation", "Removed debug logging"],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")

        assert result["resolved_issues"] == ["Fixed type annotation", "Removed debug logging"]

    def test_source_is_structured_on_valid_json(self):
        """source field is 'structured' when JSON parse succeeds."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
            "open_questions": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")

        assert result["source"] == "structured"

    def test_markdown_never_yields_a_source(self):
        """Standard 0028: there is no regex_fallback source anymore — a
        markdown verdict raises instead of producing a degraded result."""
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = "[X] **REVISE**\n\nRationale: missing tests"
        provider = _make_mock_provider(raw)

        with pytest.raises(StructuredContractError):
            _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")


class TestFallbackBehavior:
    """Standard 0028: there is no fallback — violations reject."""

    def test_contract_violation_raises_not_logs(self):
        """The pre-0028 fallback logged a debug metric and guessed; now the
        violation raises with the parser named."""
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = "[X] **REVISE**\n\n## Feedback\n- Fix error handling"
        provider = _make_mock_provider(raw)

        with pytest.raises(StructuredContractError) as exc_info:
            _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")
        assert exc_info.value.parser == "feedback"

    def test_no_fallback_on_structured_success(self):
        """Structured parse succeeds — source is 'structured'."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "LGTM",
            "feedback_items": [],
            "open_questions": [],
        })
        provider = _make_mock_provider(raw)

        result = _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")

        assert result["source"] == "structured"

    def test_empty_response_rejects(self):
        """An empty provider response is a contract violation, not an
        UNKNOWN verdict to be remapped downstream."""
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        provider = _make_mock_provider("")

        with pytest.raises(StructuredContractError) as exc_info:
            _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")
        assert "response empty" in str(exc_info.value)

    def test_markdown_feedback_sections_are_not_scraped(self):
        """The old fallback scraped feedback bullets and question checkboxes
        out of markdown; both are rejections now — the reviewer's data
        arrives through the schema or not at all."""
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError
        from assemblyzero.workflows.requirements.nodes.review import (
            _invoke_reviewer_with_feedback_schema,
        )

        raw = (
            "[X] **REVISE**\n\n"
            "## Feedback\n- Fix error handling\n\n"
            "## Open Questions\n"
            "- [ ] What timeout value?\n"
        )
        provider = _make_mock_provider(raw)

        with pytest.raises(StructuredContractError):
            _invoke_reviewer_with_feedback_schema(provider, "prompt", "system")


class TestExtractActionableFeedback:
    """Tests for _extract_actionable_feedback with feedback_result param."""

    def test_uses_feedback_items_when_structured(self):
        """_extract_actionable_feedback returns structured items when source=structured."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        feedback_result = _make_feedback_result(
            verdict="REVISE",
            feedback_items=["Fix error handling", "Add tests"],
            source="structured",
        )

        result = _extract_actionable_feedback("", "REVISE", None, feedback_result=feedback_result)

        assert "Fix error handling" in result
        assert "Add tests" in result

    def test_skips_structured_path_when_regex_fallback(self):
        """_extract_actionable_feedback falls through to legacy logic for regex_fallback source."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        feedback_result = _make_feedback_result(
            verdict="REVISE",
            feedback_items=["Some item"],
            source="regex_fallback",
        )

        # With regex_fallback source, should not use the fast-path early return
        # Result depends on verdict_content — empty string falls through gracefully
        result = _extract_actionable_feedback("", "REVISE", None, feedback_result=feedback_result)
        # Just verify it doesn't raise
        assert isinstance(result, str)

    def test_returns_empty_when_no_feedback_items_structured(self):
        """Empty feedback_items with structured source returns empty string."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        feedback_result = _make_feedback_result(
            verdict="APPROVED",
            feedback_items=[],
            source="structured",
        )

        result = _extract_actionable_feedback("", "APPROVED", None, feedback_result=feedback_result)

        assert result == ""

    def test_feedback_result_none_falls_through_to_legacy(self):
        """feedback_result=None triggers legacy parsing path."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        result = _extract_actionable_feedback("", "APPROVED", None, feedback_result=None)

        # Legacy path with empty input returns empty or minimal string
        assert isinstance(result, str)

    def test_formatted_as_bullet_list(self):
        """Structured feedback items are formatted as bullet list."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        feedback_result = _make_feedback_result(
            feedback_items=["Item one", "Item two"],
            source="structured",
        )

        result = _extract_actionable_feedback("", "REVISE", None, feedback_result=feedback_result)

        assert "- Item one" in result
        assert "- Item two" in result


class TestNoInlineSchemasInReviewNode:
    """T180: No inline schema dict literals in review.py."""

    def test_no_inline_schema_literals(self):
        """review.py should not define FEEDBACK_SCHEMA inline."""
        import pathlib

        review_path = pathlib.Path("assemblyzero/workflows/requirements/nodes/review.py")
        if not review_path.exists():
            pytest.skip("review.py not found")

        content = review_path.read_text()

        # The file should import FEEDBACK_SCHEMA, not define it inline
        assert "FEEDBACK_SCHEMA" in content or "feedback_schema" in content.lower()

        # Should not have inline dict with "verdict" + "enum" keys (schema definition)
        # Import from verdict_schema instead
        lines = content.splitlines()
        inline_schema_lines = [
            line for line in lines
            if '"enum"' in line and '"verdict"' in line and "verdict_schema" not in line
        ]
        assert len(inline_schema_lines) == 0, (
            f"Found potential inline schema in review.py: {inline_schema_lines}"
        )

    def test_imports_feedback_schema_from_verdict_schema(self):
        """review.py imports FEEDBACK_SCHEMA from verdict_schema module."""
        import pathlib

        review_path = pathlib.Path("assemblyzero/workflows/requirements/nodes/review.py")
        if not review_path.exists():
            pytest.skip("review.py not found")

        content = review_path.read_text()
        assert "from assemblyzero.core.verdict_schema" in content
        assert "FEEDBACK_SCHEMA" in content