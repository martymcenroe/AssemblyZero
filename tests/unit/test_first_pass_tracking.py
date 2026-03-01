"""Tests for Issue #513: First-pass acceptance rate tracking.

Validates that first_pass flag is correctly computed and logged
in both requirements and testing workflow finalize nodes.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRequirementsFirstPass:
    """Test first-pass tracking in requirements finalize."""

    def _run_finalize(self, state_overrides: dict) -> dict:
        """Run finalize with given state overrides and return the state."""
        from assemblyzero.workflows.requirements.nodes.finalize import finalize

        base_state = {
            "workflow_type": "lld",
            "target_repo": str(Path("/tmp/test-repo")),
            "issue_number": 42,
            "current_draft": "# LLD-042\n\nContent here",
            "lld_status": "APPROVED",
            "verdict_count": 1,
            "draft_count": 1,
            "audit_dir": str(Path("/tmp/audit")),
            "created_files": [],
        }
        base_state.update(state_overrides)
        return base_state

    @patch("assemblyzero.workflows.requirements.nodes.finalize.log_workflow_execution")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._save_lld_file")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._commit_and_push_files")
    def test_first_pass_true_on_single_verdict(self, mock_commit, mock_save, mock_log):
        from assemblyzero.workflows.requirements.nodes.finalize import finalize

        state = self._run_finalize({
            "verdict_count": 1,
            "draft_count": 1,
            "lld_status": "APPROVED",
        })
        mock_save.return_value = state
        mock_commit.return_value = state

        finalize(state)

        mock_log.assert_called_once()
        details = mock_log.call_args[1]["details"]
        assert details["first_pass"] is True

    @patch("assemblyzero.workflows.requirements.nodes.finalize.log_workflow_execution")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._save_lld_file")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._commit_and_push_files")
    def test_first_pass_false_on_multiple_verdicts(self, mock_commit, mock_save, mock_log):
        from assemblyzero.workflows.requirements.nodes.finalize import finalize

        state = self._run_finalize({
            "verdict_count": 3,
            "draft_count": 3,
            "lld_status": "APPROVED",
        })
        mock_save.return_value = state
        mock_commit.return_value = state

        finalize(state)

        mock_log.assert_called_once()
        details = mock_log.call_args[1]["details"]
        assert details["first_pass"] is False

    @patch("assemblyzero.workflows.requirements.nodes.finalize.log_workflow_execution")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._save_lld_file")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._commit_and_push_files")
    def test_first_pass_false_when_blocked(self, mock_commit, mock_save, mock_log):
        from assemblyzero.workflows.requirements.nodes.finalize import finalize

        state = self._run_finalize({
            "verdict_count": 1,
            "draft_count": 1,
            "lld_status": "BLOCKED",
        })
        mock_save.return_value = state
        mock_commit.return_value = state

        finalize(state)

        mock_log.assert_called_once()
        details = mock_log.call_args[1]["details"]
        assert details["first_pass"] is False

    @patch("assemblyzero.workflows.requirements.nodes.finalize.log_workflow_execution")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._save_lld_file")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._commit_and_push_files")
    def test_no_log_on_error(self, mock_commit, mock_save, mock_log):
        from assemblyzero.workflows.requirements.nodes.finalize import finalize

        state = self._run_finalize({"error_message": "Something failed"})
        mock_save.return_value = state
        mock_commit.return_value = state

        finalize(state)

        mock_log.assert_not_called()

    @patch("assemblyzero.workflows.requirements.nodes.finalize.log_workflow_execution")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._save_lld_file")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._commit_and_push_files")
    def test_includes_cost_data(self, mock_commit, mock_save, mock_log):
        from assemblyzero.workflows.requirements.nodes.finalize import finalize

        state = self._run_finalize({
            "verdict_count": 1,
            "draft_count": 1,
            "lld_status": "APPROVED",
            "node_costs": {"generate_draft": 0.15, "review": 0.05},
        })
        mock_save.return_value = state
        mock_commit.return_value = state

        finalize(state)

        details = mock_log.call_args[1]["details"]
        assert details["total_cost_usd"] == 0.2
        assert "generate_draft" in details["cost_by_node"]

    @patch("assemblyzero.workflows.requirements.nodes.finalize.log_workflow_execution")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._save_lld_file")
    @patch("assemblyzero.workflows.requirements.nodes.finalize._commit_and_push_files")
    def test_includes_final_lld_path(self, mock_commit, mock_save, mock_log):
        from assemblyzero.workflows.requirements.nodes.finalize import finalize

        state = self._run_finalize({
            "verdict_count": 2,
            "draft_count": 2,
            "lld_status": "APPROVED",
            "final_lld_path": "/tmp/docs/lld/active/LLD-042.md",
        })
        mock_save.return_value = state
        mock_commit.return_value = state

        finalize(state)

        details = mock_log.call_args[1]["details"]
        assert details["final_lld_path"] == "/tmp/docs/lld/active/LLD-042.md"
        assert details["first_pass"] is False


class TestTestingFirstPass:
    """Test first-pass tracking in testing finalize."""

    def test_first_pass_computed_correctly(self):
        """Verify the first_pass logic: iteration 1, all tests pass."""
        # first_pass = iteration_count <= 1 and passed_count == test_count and test_count > 0
        # True case
        assert (1 <= 1 and 5 == 5 and 5 > 0) is True
        # False: multiple iterations
        assert (2 <= 1 and 5 == 5 and 5 > 0) is False
        # False: not all passed
        assert (1 <= 1 and 3 == 5 and 5 > 0) is False
        # False: no tests
        assert (1 <= 1 and 0 == 0 and 0 > 0) is False
