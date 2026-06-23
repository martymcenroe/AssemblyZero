"""Tests for Issue #492: Structured output for verdicts.

Verifies that:
1. GeminiClient passes response_schema to the API config
2. Structured verdict JSON is parsed correctly
3. Fallback to regex works when JSON is not returned
"""

import json
from unittest.mock import MagicMock

from assemblyzero.core.verdict_schema import (
    VERDICT_SCHEMA,
    parse_structured_verdict,
)


class TestVerdictSchema:
    """Verify the verdict schema structure."""

    def test_schema_has_required_fields(self):
        assert VERDICT_SCHEMA["required"] == ["verdict", "rationale"]

    def test_schema_verdict_enum(self):
        verdict_prop = VERDICT_SCHEMA["properties"]["verdict"]
        assert "APPROVED" in verdict_prop["enum"]
        assert "REVISE" in verdict_prop["enum"]
        assert "BLOCKED" in verdict_prop["enum"]


class TestParseStructuredVerdict:
    """Verify structured verdict parsing."""

    def test_valid_json_verdict(self):
        response = json.dumps({
            "verdict": "APPROVED",
            "rationale": "Looks good",
            "blocking_issues": [],
            "suggestions": ["Minor formatting"],
        })
        result = parse_structured_verdict(response)
        assert result is not None
        assert result["verdict"] == "APPROVED"
        assert result["rationale"] == "Looks good"

    def test_json_in_code_fence(self):
        response = '```json\n{"verdict": "REVISE", "rationale": "Needs work"}\n```'
        result = parse_structured_verdict(response)
        assert result is not None
        assert result["verdict"] == "REVISE"

    def test_non_json_returns_none(self):
        response = "[X] **APPROVED** - Ready for implementation"
        result = parse_structured_verdict(response)
        assert result is None

    def test_empty_returns_none(self):
        assert parse_structured_verdict("") is None
        assert parse_structured_verdict(None) is None

    def test_json_missing_required_fields(self):
        response = json.dumps({"rationale": "no verdict key"})  # missing verdict
        result = parse_structured_verdict(response)
        assert result is None

    def test_blocking_issues_parsed(self):
        response = json.dumps({
            "verdict": "BLOCKED",
            "rationale": "Issues found",
            "blocking_issues": [
                {"section": "2.1", "issue": "Missing file", "severity": "BLOCKING"},
            ],
        })
        result = parse_structured_verdict(response)
        assert result is not None
        assert len(result["blocking_issues"]) == 1
        assert result["blocking_issues"][0]["section"] == "2.1"


class TestGeminiPassesResponseSchema:
    """Verify GeminiClient/GeminiProvider wire response_schema correctly.

    test_gemini_passes_response_schema was deleted in #1605: the structured-output
    path relied on genai.Client (paid API-key SDK), which was removed when
    governance moved to subscription/OAuth-only transport.  GeminiProvider still
    accepts and forwards response_schema to the underlying client; that forwarding
    is tested below.
    """

    def test_gemini_provider_passes_schema(self):
        """GeminiProvider.invoke() should forward response_schema to client."""
        from assemblyzero.core.llm_provider import GeminiProvider

        provider = GeminiProvider(model="3.1-pro-preview")

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.response = '{"verdict": "APPROVED", "rationale": "OK"}'
        mock_result.raw_response = "raw"
        mock_result.error_type = None
        mock_result.error_message = None
        mock_result.credential_used = "test"
        mock_result.rotation_occurred = False
        mock_result.attempts = 1
        mock_result.duration_ms = 100
        mock_result.model_verified = "gemini-3.1-pro-preview"
        mock_client.invoke.return_value = mock_result
        provider._client = mock_client

        provider.invoke(
            system_prompt="Review",
            content="Content",
            response_schema=VERDICT_SCHEMA,
        )

        # Verify client.invoke was called with response_schema
        call_kwargs = mock_client.invoke.call_args
        assert call_kwargs.kwargs.get("response_schema") == VERDICT_SCHEMA


class TestFallbackToRegex:
    """Verify that non-JSON responses fall back to regex parsing."""

    def test_fallback_to_regex_on_non_json(self):
        """review.py's _parse_verdict_status should still work for non-JSON."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _parse_verdict_status,
        )

        # Standard checkbox format
        assert _parse_verdict_status("[X] **APPROVED** - Ready") == "APPROVED"
        assert _parse_verdict_status("[X] **REVISE** - Needs changes") == "BLOCKED"
        assert _parse_verdict_status("VERDICT: APPROVED") == "APPROVED"
        assert _parse_verdict_status("VERDICT: BLOCKED") == "BLOCKED"

    def test_review_spec_fallback(self):
        """review_spec.py's parse_review_verdict should still work for non-JSON."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            parse_review_verdict,
        )

        verdict, feedback = parse_review_verdict("[X] **APPROVED** - Spec ready")
        assert verdict == "APPROVED"

        verdict, feedback = parse_review_verdict("[X] **REVISE** - Fix issues")
        assert verdict == "REVISE"
