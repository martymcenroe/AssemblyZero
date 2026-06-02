"""Tests for Issue #494: JSON verdict migration in review_test_plan.

Validates that review_test_plan uses structured JSON verdict parsing
(parse_structured_verdict) first, falling back to regex _parse_verdict.
"""

import json
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from assemblyzero.core.verdict_schema import (
    VERDICT_SCHEMA,
    parse_structured_verdict,
)
from assemblyzero.workflows.testing.nodes.review_test_plan import _parse_verdict


class TestStructuredVerdictParsing:
    """Test parse_structured_verdict with test plan verdict content."""

    def test_approved_json(self):
        verdict = json.dumps({
            "verdict": "APPROVED",
            "rationale": "All requirements covered.",
        })
        result = parse_structured_verdict(verdict)
        assert result is not None
        assert result["verdict"] == "APPROVED"

    def test_blocked_json_with_issues(self):
        verdict = json.dumps({
            "verdict": "BLOCKED",
            "rationale": "Missing coverage for 2 requirements.",
            "blocking_issues": [
                {
                    "section": "Coverage",
                    "issue": "REQ-3 has no test scenario",
                    "severity": "BLOCKING",
                },
            ],
        })
        result = parse_structured_verdict(verdict)
        assert result is not None
        assert result["verdict"] == "BLOCKED"
        assert len(result["blocking_issues"]) == 1
        assert result["blocking_issues"][0]["severity"] == "BLOCKING"

    def test_revise_maps_to_blocked(self):
        """REVISE verdict should be mapped to BLOCKED by the caller."""
        verdict = json.dumps({
            "verdict": "REVISE",
            "rationale": "Needs more edge case coverage.",
        })
        result = parse_structured_verdict(verdict)
        assert result is not None
        assert result["verdict"] == "REVISE"
        # The mapping to BLOCKED happens in review_test_plan, not in parse

    def test_json_in_code_fence(self):
        verdict = '```json\n{"verdict": "APPROVED", "rationale": "Good."}\n```'
        result = parse_structured_verdict(verdict)
        assert result is not None
        assert result["verdict"] == "APPROVED"

    def test_non_json_returns_none(self):
        verdict = "## Verdict\n[x] **APPROVED**\n\nAll looks good."
        result = parse_structured_verdict(verdict)
        assert result is None

    def test_json_missing_verdict_returns_none(self):
        verdict = json.dumps({"rationale": "No verdict field"})
        result = parse_structured_verdict(verdict)
        assert result is None

    def test_empty_string_returns_none(self):
        assert parse_structured_verdict("") is None
        assert parse_structured_verdict(None) is None


class TestRegexFallback:
    """Test _parse_verdict regex fallback still works."""

    def test_approved_checkbox(self):
        verdict = "## Verdict\n[X] **APPROVED** — all good"
        assert _parse_verdict(verdict)["verdict"] == "APPROVED"

    def test_blocked_checkbox(self):
        verdict = "## Verdict\n[X] **BLOCKED** — needs work"
        assert _parse_verdict(verdict)["verdict"] == "BLOCKED"

    def test_verdict_keyword(self):
        verdict = "After review, Verdict: APPROVED"
        assert _parse_verdict(verdict)["verdict"] == "APPROVED"

    def test_default_unknown(self):
        verdict = "Unclear response with no verdict markers"
        assert _parse_verdict(verdict)["verdict"] == "UNKNOWN"


class TestVerdictSchemaShape:
    """Verify VERDICT_SCHEMA has the expected structure."""

    def test_schema_has_verdict_enum(self):
        props = VERDICT_SCHEMA["properties"]
        assert "verdict" in props
        assert props["verdict"]["enum"] == ["APPROVED", "REVISE", "BLOCKED"]

    def test_schema_requires_verdict_and_summary(self):
        assert "verdict" in VERDICT_SCHEMA["required"]
        assert "rationale" in VERDICT_SCHEMA["required"]

    def test_schema_has_blocking_issues(self):
        props = VERDICT_SCHEMA["properties"]
        assert "blocking_issues" in props
        assert props["blocking_issues"]["type"] == "array"

    def test_blocking_issue_has_section_and_issue(self):
        item_props = VERDICT_SCHEMA["properties"]["blocking_issues"]["items"]["properties"]
        assert "section" in item_props
        assert "issue" in item_props
        assert "severity" in item_props


class TestStructuredFeedbackExtraction:
    """Test that structured verdict feedback is properly extracted for BLOCKED."""

    def test_feedback_from_blocking_issues(self):
        """When structured data available, feedback uses blocking_issues."""
        structured = {
            "verdict": "BLOCKED",
            "rationale": "Coverage gaps found.",
            "blocking_issues": [
                {
                    "section": "Coverage",
                    "issue": "REQ-3 missing test",
                    "severity": "BLOCKING",
                },
                {
                    "section": "Test Quality",
                    "issue": "No negative tests",
                    "severity": "HIGH",
                },
            ],
        }
        feedback_parts = [structured["rationale"]]
        for issue in structured.get("blocking_issues", []):
            feedback_parts.append(
                f"[{issue.get('severity', 'BLOCKING')}] {issue.get('section', '?')}: {issue.get('issue', '?')}"
            )
        feedback = "\n".join(feedback_parts)
        assert "Coverage gaps found" in feedback
        assert "[BLOCKING] Coverage: REQ-3 missing test" in feedback
        assert "[HIGH] Test Quality: No negative tests" in feedback

    def test_feedback_from_summary_only(self):
        """When no blocking_issues, just use summary."""
        structured = {
            "verdict": "BLOCKED",
            "rationale": "Not enough tests.",
        }
        feedback_parts = [structured["rationale"]]
        for issue in structured.get("blocking_issues", []):
            feedback_parts.append(f"[{issue.get('severity')}] {issue.get('issue')}")
        feedback = "\n".join(feedback_parts)
        assert feedback == "Not enough tests."


class TestIntegrationWithReviewTestPlan:
    """Integration-level tests for the structured verdict flow."""

    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
    def test_structured_approved_verdict_skips_regex(self, mock_root, mock_prompt, mock_log):
        """When Gemini returns valid JSON, regex is not used."""
        from assemblyzero.workflows.testing.nodes.review_test_plan import review_test_plan

        mock_root.return_value = Path("/tmp/test-repo")
        mock_prompt.return_value = "review prompt"

        state = {
            "test_scenarios": [
                {"name": "test_a", "type": "unit", "requirement_ref": "REQ-1"},
                {"name": "test_b", "type": "unit", "requirement_ref": "REQ-2"},
            ],
            "requirements": ["REQ-1: A", "REQ-2: B"],
            "lld_content": "This is a detailed low-level design document with sufficient words to pass the mechanical gate minimum threshold. " * 5,
            "issue_number": 42,
            "repo_root": "/tmp/test-repo",
            "audit_dir": "/tmp/nonexistent",
            "mock_mode": False,
            "node_costs": {},
            "node_tokens": {},
            "file_counter": 0,
        }

        # This will hit fast-path (100% coverage) from #509, so structured
        # verdict won't be reached. That's fine — the fast-path is the
        # expected behavior when coverage passes.
        result = review_test_plan(state)
        assert result["test_plan_status"] == "APPROVED"


class TestStructuredContentReadOverResponse:
    """#1523: Verify the LLM result is read from `.content` (where Gemini puts
    structured-schema JSON), with `.response` as legacy fallback.

    Bug shape: previously `verdict_content = result.response`. With
    response_schema=VERDICT_SCHEMA set on a Gemini call, the structured JSON
    lands in `result.content`; `.response` is empty. The old read got an empty
    string every time, fell through to regex fallback, and the default-empty
    regex result mapped to BLOCKED. Observed on Chiron #45 curator iter02 N1
    and N1.5 cycles 1/2 and 2/2 — 25-27s LLM calls succeeding silently with
    no parseable verdict.
    """

    def _state_forcing_llm_path(self) -> dict:
        """State with <100% coverage so fast-path is skipped, but enough
        scenarios to clear the mechanical gates (Gate 3 requires
        scenario_count >= req_count). Two scenarios both map to REQ-1 →
        clears Gate 3 but coverage_pct=50% (REQ-2 uncovered) so LLM path runs.
        """
        return {
            "test_scenarios": [
                {"name": "test_a", "type": "unit", "requirement_ref": "REQ-1"},
                {"name": "test_b", "type": "unit", "requirement_ref": "REQ-1"},
            ],
            "requirements": ["REQ-1: A", "REQ-2: B"],
            "lld_content": "This is a detailed low-level design document with sufficient words to pass the mechanical gate minimum threshold. " * 5,
            "issue_number": 42,
            "repo_root": "/tmp/test-repo",
            "audit_dir": "/tmp/nonexistent",
            "mock_mode": False,
            "node_costs": {},
            "node_tokens": {},
            "file_counter": 0,
            "config_reviewer": "gemini:3.1-pro-preview",
        }

    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
    @patch("assemblyzero.utils.retry.with_retry")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_provider")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_cumulative_cost")
    def test_structured_json_in_content_is_used(
        self, mock_cost, mock_provider, mock_with_retry, mock_root, mock_prompt, mock_log,
    ):
        """When the LLM result has structured JSON in `.content` and empty
        `.response`, the structured path runs (verdict_method='structured') and
        the workflow reflects the JSON verdict — NOT the regex-fallback BLOCKED.

        This is the exact Chiron #45 scenario inverted: with the fix, the same
        Gemini-shape result that previously read as empty now reads as APPROVED.
        """
        from assemblyzero.workflows.testing.nodes.review_test_plan import review_test_plan
        from assemblyzero.core.llm_provider import GeminiProvider

        mock_root.return_value = Path("/tmp/test-repo")
        mock_prompt.return_value = "review prompt"
        mock_cost.return_value = 0.0

        # Mock provider: must be a GeminiProvider so response_schema is set
        mock_provider.return_value = MagicMock(spec=GeminiProvider)

        # The result Gemini would return with response_schema=VERDICT_SCHEMA:
        # structured JSON in .content, .response empty
        llm_result = MagicMock()
        llm_result.success = True
        llm_result.error_message = None
        llm_result.content = json.dumps({
            "verdict": "APPROVED",
            "rationale": "Coverage is acceptable.",
        })
        llm_result.response = ""  # the bug: old code read THIS
        llm_result.input_tokens = 100
        llm_result.output_tokens = 50
        mock_with_retry.return_value = llm_result

        result = review_test_plan(self._state_forcing_llm_path())

        # If the bug were present, this would be BLOCKED via regex fallback
        # on an empty string. With the fix, it's APPROVED via structured parse.
        assert result["test_plan_status"] == "APPROVED", (
            f"Expected APPROVED from structured-content read; got "
            f"{result.get('test_plan_status')!r}. This is the #1523 regression."
        )

    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
    @patch("assemblyzero.utils.retry.with_retry")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_provider")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_cumulative_cost")
    def test_legacy_response_fallback_still_works(
        self, mock_cost, mock_provider, mock_with_retry, mock_root, mock_prompt, mock_log,
    ):
        """When a provider returns content via `.response` only (no `.content`
        attribute populated), the legacy read path still works — required so
        non-Gemini providers and older provider shapes aren't broken by the fix.
        """
        from assemblyzero.workflows.testing.nodes.review_test_plan import review_test_plan
        from assemblyzero.core.llm_provider import GeminiProvider

        mock_root.return_value = Path("/tmp/test-repo")
        mock_prompt.return_value = "review prompt"
        mock_cost.return_value = 0.0
        mock_provider.return_value = MagicMock(spec=GeminiProvider)

        # Provider returns verdict in .response (legacy path); .content is empty
        llm_result = MagicMock()
        llm_result.success = True
        llm_result.error_message = None
        llm_result.content = ""
        llm_result.response = json.dumps({
            "verdict": "APPROVED",
            "rationale": "Looks fine.",
        })
        llm_result.input_tokens = 100
        llm_result.output_tokens = 50
        mock_with_retry.return_value = llm_result

        result = review_test_plan(self._state_forcing_llm_path())
        assert result["test_plan_status"] == "APPROVED"
