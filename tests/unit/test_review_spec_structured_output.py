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


def _make_mock_provider(response_content: str, success: bool = True, error_message: str = ""):
    """Create a mock provider whose invoke returns an LLMCallResult-shaped result.

    Issue #1868/#1843: the payload field is `.response` — the old mock set
    `.content`, which a MagicMock happily grew, so tests passed while
    production read a nonexistent field and stringified the dataclass.
    Explicit spec'd fields keep the mock honest.
    """
    mock_result = MagicMock(spec=["success", "response", "error_message"])
    mock_result.success = success
    mock_result.response = response_content
    mock_result.error_message = error_message
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

        result, _err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["verdict"] == "APPROVED"
        assert result["rationale"] == "Spec is complete"
        assert result["source"] == "structured"

    def test_failed_call_returns_error_not_verdict(self):
        """Issue #1868: LLM failure surfaces as (None, error) — never a verdict."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        provider = _make_mock_provider(
            "", success=False, error_message="agy exited 3221225794"
        )
        result, err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")
        assert result is None
        assert "3221225794" in err

    def test_empty_response_returns_error_not_verdict(self):
        """Issue #1868: an empty response is a failure, not a parseable verdict."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        provider = _make_mock_provider("   ", success=True)
        result, err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")
        assert result is None
        assert "empty" in err.lower()

    def test_payload_read_from_response_field(self):
        """Issue #1843: the payload is LLMCallResult.response — a result object
        without a `content` attribute must still parse structured."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = json.dumps({"verdict": "APPROVED", "rationale": "ok", "feedback_items": []})
        provider = _make_mock_provider(raw)
        # spec'd mock has no .content — the old code would stringify it
        assert not hasattr(provider.invoke.return_value, "content")
        result, err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")
        assert err == ""
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
        mock_result = MagicMock(spec=["success", "response", "error_message"])
        mock_result.success = True
        mock_result.response = raw
        mock_result.error_message = ""
        gemini_provider = MagicMock(spec=GeminiProvider)
        gemini_provider.invoke.return_value = mock_result

        _invoke_reviewer_with_spec_schema(gemini_provider, "prompt", "system")

        gemini_provider.invoke.assert_called_once()
        call_kwargs = gemini_provider.invoke.call_args[1]
        assert "response_schema" in call_kwargs
        assert call_kwargs["response_schema"] == REVIEW_SPEC_SCHEMA
        assert "json_schema" not in call_kwargs

    def test_markdown_response_rejects_via_error_path(self):
        """Standard 0028: a non-JSON response is rejected through the same
        (None, error) path as an infrastructure failure — never scraped."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = "[X] **APPROVED**\n\nRationale: Looks good"
        provider = _make_mock_provider(raw)

        result, err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result is None
        assert "review_spec" in err
        assert "contract" in err

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

        result, _err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

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

        result, _err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

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

    def test_plain_text_rejects_not_remapped(self):
        """Standard 0028: a failed parse raises — it is never remapped to a
        synthesized BLOCKED verdict."""
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            parse_review_verdict,
        )

        with pytest.raises(StructuredContractError):
            parse_review_verdict("This is just plain text with no verdict")

    def test_markdown_checkbox_rejects(self):
        """Standard 0028: legacy markdown checkboxes are contract
        violations, not scrapes."""
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            parse_review_verdict,
        )

        with pytest.raises(StructuredContractError):
            parse_review_verdict("[X] **REVISE**\n\nRationale: Needs more detail")

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

        result, _err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

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

        result, _err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["source"] == "structured"

    def test_markdown_yields_no_result_at_all(self):
        """Standard 0028: a markdown verdict is rejected (None, error) — the
        regex_fallback source no longer exists."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = "[X] **REVISE**\n\nRationale: missing tests"
        provider = _make_mock_provider(raw)

        result, err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result is None
        assert err != ""

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

        result, _err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["feedback_items"] == []


class TestFallbackBehavior:
    """Standard 0028: there is no fallback — violations reject."""

    def test_contract_violation_names_the_parser(self):
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = "[X] **REVISE**\n\n## Required Changes\n- Fix error handling"
        provider = _make_mock_provider(raw)

        result, err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result is None
        assert "review_spec" in err

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

        result, _err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result["source"] == "structured"

    def test_empty_response_is_an_error_not_a_verdict(self):
        """Issue #1868: an empty response no longer synthesizes a fallback
        verdict — it surfaces as an invoke error so routing halts honestly."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        provider = _make_mock_provider("")

        result, err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result is None
        assert err != ""

    def test_markdown_feedback_sections_are_not_scraped(self):
        """The old fallback scraped Required Changes / Feedback bullets out
        of markdown; those responses are rejections now — feedback arrives
        through the schema or not at all."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _invoke_reviewer_with_spec_schema,
        )

        raw = (
            "[X] **REVISE**\n\n"
            "## Required Changes\n"
            "- Fix error handling\n\n"
            "## Feedback\n"
            "- Update section 6\n"
        )
        provider = _make_mock_provider(raw)

        result, err = _invoke_reviewer_with_spec_schema(provider, "prompt", "system")

        assert result is None
        assert err != ""


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

    def test_missing_feedback_items_rejects(self):
        """Standard 0028: missing required keys is a contract violation."""
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError

        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "needs work",
        })
        with pytest.raises(StructuredContractError):
            parse_structured_review_spec(raw)

    def test_invalid_verdict_enum_rejects(self):
        """DISCUSS is outside REVIEW_SPEC_SCHEMA's enum — a violation."""
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError

        raw = json.dumps({
            "verdict": "DISCUSS",
            "rationale": "Let's talk",
            "feedback_items": [],
        })
        with pytest.raises(StructuredContractError):
            parse_structured_review_spec(raw)

    def test_malformed_json_rejects(self):
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError

        with pytest.raises(StructuredContractError):
            parse_structured_review_spec("not valid json {")

    def test_rejection_carries_parser_name(self):
        import pytest
        from assemblyzero.core.verdict_schema import StructuredContractError

        with pytest.raises(StructuredContractError) as exc_info:
            parse_structured_review_spec("[X] **APPROVED**")
        assert exc_info.value.parser == "review_spec"

    def test_structured_success_returns_structured_source(self):
        """Structured parse succeeds — source is 'structured'."""
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
        })
        result = parse_structured_review_spec(raw)
        assert result["source"] == "structured"