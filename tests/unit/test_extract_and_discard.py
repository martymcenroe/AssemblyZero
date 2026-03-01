"""Tests for Issue #507: Extract-and-discard pattern in review_test_plan.

Validates that test_plan_verdict stores concise extracted summaries,
not raw LLM prose. Full responses are saved to audit files only.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.nodes.review_test_plan import (
    review_test_plan,
    _mock_review_test_plan,
)


def _make_state(**overrides) -> dict:
    """Minimal state for review_test_plan."""
    base = {
        "test_scenarios": [
            {"name": "test_create", "type": "unit", "requirement_ref": "REQ-1"},
            {"name": "test_delete", "type": "unit", "requirement_ref": "REQ-2"},
        ],
        "requirements": ["REQ-1: Create", "REQ-2: Delete"],
        "lld_content": "Detailed LLD content with enough words to pass the gate. " * 5,
        "issue_number": 42,
        "repo_root": str(Path("/tmp/test-repo")),
        "audit_dir": str(Path("/tmp/nonexistent-audit")),
        "mock_mode": False,
        "node_costs": {},
        "node_tokens": {},
        "file_counter": 0,
    }
    base.update(overrides)
    return base


class TestBlockedVerdictExtraction:
    """BLOCKED path should store extracted feedback, not raw prose."""

    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
    def test_blocked_verdict_stores_summary_not_prose(self, mock_root, mock_prompt, mock_log):
        """Gemini BLOCKED → test_plan_verdict is short summary, not full response."""
        mock_root.return_value = Path("/tmp/test-repo")
        mock_prompt.return_value = "review prompt"

        raw_prose = "A" * 500  # Long raw prose that should NOT appear in state

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.response = json.dumps({
            "verdict": "BLOCKED",
            "summary": "Missing edge case coverage for REQ-2.",
            "blocking_issues": [
                {"section": "Coverage", "issue": "REQ-2 missing edge cases", "severity": "BLOCKING"},
            ],
        })
        mock_result.input_tokens = 100
        mock_result.output_tokens = 50

        with patch("assemblyzero.core.gemini_client.GeminiClient") as mock_cls, \
             patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_cumulative_cost", return_value=0.0), \
             patch("assemblyzero.workflows.testing.nodes.review_test_plan.check_requirement_coverage") as mock_cov:
            mock_cls.return_value.invoke.return_value = mock_result
            # Force past fast-path
            mock_cov.return_value = {"passed": False, "total": 2, "covered": 1, "coverage_pct": 50.0, "missing": ["REQ-2"]}

            state = _make_state()
            result = review_test_plan(state)

        assert result["test_plan_status"] == "BLOCKED"
        assert result["test_plan_verdict"].startswith("BLOCKED:")
        assert len(result["test_plan_verdict"]) <= 210  # "BLOCKED: " + 200 chars max


class TestApprovedVerdictExtraction:
    """APPROVED path should store concise summary, not raw prose."""

    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
    def test_approved_verdict_stores_summary_not_prose(self, mock_root, mock_prompt, mock_log):
        """Gemini APPROVED → test_plan_verdict is concise, not full response."""
        mock_root.return_value = Path("/tmp/test-repo")
        mock_prompt.return_value = "review prompt"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.response = json.dumps({
            "verdict": "APPROVED",
            "summary": "All requirements covered with good edge cases.",
        })
        mock_result.input_tokens = 100
        mock_result.output_tokens = 50

        with patch("assemblyzero.core.gemini_client.GeminiClient") as mock_cls, \
             patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_cumulative_cost", return_value=0.0), \
             patch("assemblyzero.workflows.testing.nodes.review_test_plan.check_requirement_coverage") as mock_cov:
            mock_cls.return_value.invoke.return_value = mock_result
            mock_cov.return_value = {"passed": False, "total": 2, "covered": 1, "coverage_pct": 50.0, "missing": ["REQ-2"]}

            state = _make_state()
            result = review_test_plan(state)

        assert result["test_plan_status"] == "APPROVED"
        assert result["test_plan_verdict"].startswith("APPROVED:")
        assert "All requirements covered" in result["test_plan_verdict"]
        assert len(result["test_plan_verdict"]) <= 210

    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
    def test_approved_regex_fallback_stores_bare_approved(self, mock_root, mock_prompt, mock_log):
        """Regex fallback (no structured JSON) → bare 'APPROVED' string."""
        mock_root.return_value = Path("/tmp/test-repo")
        mock_prompt.return_value = "review prompt"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.response = "## Verdict\n[x] **APPROVED** - Test plan is ready.\n\nLong explanation here..." + ("x" * 500)
        mock_result.input_tokens = 100
        mock_result.output_tokens = 50

        with patch("assemblyzero.core.gemini_client.GeminiClient") as mock_cls, \
             patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_cumulative_cost", return_value=0.0), \
             patch("assemblyzero.workflows.testing.nodes.review_test_plan.check_requirement_coverage") as mock_cov:
            mock_cls.return_value.invoke.return_value = mock_result
            mock_cov.return_value = {"passed": False, "total": 2, "covered": 1, "coverage_pct": 50.0, "missing": ["REQ-2"]}

            state = _make_state()
            result = review_test_plan(state)

        assert result["test_plan_status"] == "APPROVED"
        assert result["test_plan_verdict"] == "APPROVED"


class TestFastPathCompliance:
    """Fast-path (mechanical approval) already stores concise summary."""

    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
    def test_fast_path_stores_concise_verdict(self, mock_root, mock_prompt, mock_log):
        mock_root.return_value = Path("/tmp/test-repo")
        mock_prompt.return_value = "review prompt"

        state = _make_state()
        result = review_test_plan(state)

        assert result["test_plan_status"] == "APPROVED"
        assert "mechanical" in result["test_plan_verdict"].lower()
        # Fast-path verdict is a short formatted summary, not raw LLM prose
        assert len(result["test_plan_verdict"]) < 500


class TestMockModeCompliance:
    """Mock mode should store concise verdict, not raw prose."""

    def test_mock_approved_stores_concise_verdict(self):
        state = _make_state(mock_mode=True)
        result = _mock_review_test_plan(state)

        assert result["test_plan_status"] == "APPROVED"
        # Should be "APPROVED" (no feedback) — not the multi-line prose
        assert result["test_plan_verdict"] == "APPROVED"
        assert len(result["test_plan_verdict"]) < 200

    def test_mock_blocked_stores_concise_verdict(self):
        state = _make_state(
            mock_mode=True,
            test_scenarios=[
                {"name": "test_create", "type": "unit", "requirement_ref": "REQ-1"},
            ],
            requirements=["REQ-1: Create", "REQ-2: Delete"],
        )
        result = _mock_review_test_plan(state)

        assert result["test_plan_status"] == "BLOCKED"
        assert result["test_plan_verdict"].startswith("BLOCKED:")
        assert len(result["test_plan_verdict"]) <= 210


class TestAuditFilePreservation:
    """Raw response MUST be saved to audit file before extraction."""

    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.save_audit_file")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.next_file_number", return_value=5)
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
    def test_raw_prose_saved_to_audit_file(self, mock_root, mock_prompt, mock_log, mock_num, mock_save):
        """Full Gemini response written to audit file before extraction."""
        mock_root.return_value = Path("/tmp/test-repo")
        mock_prompt.return_value = "review prompt"

        raw_json = json.dumps({
            "verdict": "APPROVED",
            "summary": "All good.",
        })
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.response = raw_json
        mock_result.input_tokens = 100
        mock_result.output_tokens = 50

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("assemblyzero.core.gemini_client.GeminiClient") as mock_cls, \
                 patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_cumulative_cost", return_value=0.0), \
                 patch("assemblyzero.workflows.testing.nodes.review_test_plan.check_requirement_coverage") as mock_cov:
                mock_cls.return_value.invoke.return_value = mock_result
                mock_cov.return_value = {"passed": False, "total": 2, "covered": 1, "coverage_pct": 50.0, "missing": ["REQ-2"]}

                state = _make_state(audit_dir=tmpdir)
                result = review_test_plan(state)

            # Verify save_audit_file was called with the FULL raw response
            verdict_calls = [
                c for c in mock_save.call_args_list
                if "verdict.md" in str(c)
            ]
            assert len(verdict_calls) >= 1, "Raw verdict must be saved to audit file"
            # The saved content should be the full raw response
            saved_content = verdict_calls[0][0][3]  # 4th positional arg
            assert saved_content == raw_json
