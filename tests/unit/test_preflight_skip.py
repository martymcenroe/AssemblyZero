"""Tests for Issue #509: Pre-flight gates to skip Gemini review.

When mechanical gates pass AND coverage is 100%, Gemini call is skipped.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.nodes.review_test_plan import (
    check_requirement_coverage,
    review_test_plan,
)


def _make_full_state(**overrides) -> dict:
    """Create a fully populated state for review_test_plan."""
    base = {
        "test_scenarios": [
            {"name": "test_create", "type": "unit", "requirement_ref": "REQ-1"},
            {"name": "test_delete", "type": "unit", "requirement_ref": "REQ-2"},
        ],
        "requirements": ["REQ-1: Create", "REQ-2: Delete"],
        "lld_content": "Detailed LLD content with enough words to pass the minimum word count gate requirement. " * 5,
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


class TestCoverageCheck:
    """Verify check_requirement_coverage works for fast-path decisions."""

    def test_full_coverage_passes(self):
        result = check_requirement_coverage(
            ["REQ-1: Create", "REQ-2: Delete"],
            [
                {"requirement_ref": "REQ-1"},
                {"requirement_ref": "REQ-2"},
            ],
        )
        assert result["passed"] is True
        assert result["coverage_pct"] == 100.0

    def test_partial_coverage_fails(self):
        result = check_requirement_coverage(
            ["REQ-1: Create", "REQ-2: Delete"],
            [{"requirement_ref": "REQ-1"}],
        )
        assert result["passed"] is False
        assert result["missing"] == ["REQ-2"]

    def test_no_requirements_fails(self):
        result = check_requirement_coverage([], [])
        assert result["passed"] is False


class TestFastPath:
    """Test that 100% coverage triggers fast-path (skip Gemini)."""

    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
    def test_fast_path_approves_at_100_coverage(self, mock_root, mock_prompt, mock_log):
        mock_root.return_value = Path("/tmp/test-repo")
        mock_prompt.return_value = "review prompt"

        state = _make_full_state()
        result = review_test_plan(state)

        assert result["test_plan_status"] == "APPROVED"
        assert "mechanical" in result["test_plan_verdict"].lower()
        assert result["error_message"] == ""

        # Verify Gemini was NOT called (no import of GeminiClient)
        mock_log.assert_called_once()
        details = mock_log.call_args[1]["details"]
        assert details["method"] == "mechanical_fast_path"

    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
    @patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
    def test_partial_coverage_hits_guard_block(self, mock_root, mock_prompt, mock_log):
        """When coverage < 100%, mechanical gate blocks before Gemini."""
        mock_root.return_value = Path("/tmp/test-repo")
        mock_prompt.return_value = "review prompt"

        state = _make_full_state(
            test_scenarios=[
                {"name": "test_create", "type": "unit", "requirement_ref": "REQ-1"},
            ],
            requirements=["REQ-1: Create", "REQ-2: Delete"],
        )

        result = review_test_plan(state)

        # Should be blocked by mechanical gate (1 scenario < 2 requirements)
        assert result["test_plan_status"] == "BLOCKED"
        assert "coverage ratio" in result["error_message"].lower() or "GUARD" in result["error_message"]

        # Guard block event should have been logged
        assert mock_log.called
        call_details = mock_log.call_args[1].get("details", {})
        assert call_details.get("reason") == "mechanical_gate_failure"
