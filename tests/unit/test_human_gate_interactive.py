"""Unit tests for human gate interactive mode.

Issue #160: Human gates in requirements workflow don't actually gate

Problem: When gates are enabled (--gates draft,verdict), the workflow runs
straight through without pausing for human input.

Fix: Implement actual input() prompts in interactive mode.
"""

from unittest.mock import patch, MagicMock
import pytest

from assemblyzero.workflows.requirements.state import create_initial_state, HumanDecision


class TestDraftGateInteractive:
    """Test that draft gate actually pauses for human input when enabled."""

    @patch("builtins.input", return_value="S")
    def test_draft_gate_prompts_for_input(self, mock_input, tmp_path):
        """Draft gate should prompt user for input when gate is enabled."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_draft

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_draft=True,  # Gate enabled
            auto_mode=False,   # Not auto mode
        )
        state["current_draft"] = "# Test Draft"

        result = human_gate_draft(state)

        # input() should have been called
        assert mock_input.called, "Draft gate should prompt for user input"

    @patch("builtins.input", return_value="S")
    def test_draft_gate_send_routes_to_review(self, mock_input, tmp_path):
        """User choosing 'S' (Send) should route to review."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_draft

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_draft=True,
            auto_mode=False,
        )
        state["current_draft"] = "# Test Draft"

        result = human_gate_draft(state)

        assert result["next_node"] == "N3_review"

    @patch("builtins.input", return_value="R")
    def test_draft_gate_revise_routes_to_generate(self, mock_input, tmp_path):
        """User choosing 'R' (Revise) should route back to draft generation."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_draft

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_draft=True,
            auto_mode=False,
        )
        state["current_draft"] = "# Test Draft"

        result = human_gate_draft(state)

        assert result["next_node"] == "N1_generate_draft"

    @patch("builtins.input", return_value="M")
    def test_draft_gate_manual_routes_to_end(self, mock_input, tmp_path):
        """User choosing 'M' (Manual) should end workflow."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_draft

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_draft=True,
            auto_mode=False,
        )
        state["current_draft"] = "# Test Draft"

        result = human_gate_draft(state)

        assert result["next_node"] == "END"

    def test_draft_gate_no_prompt_when_disabled(self, tmp_path):
        """Draft gate should NOT prompt when gate is disabled."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_draft

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_draft=False,  # Gate disabled
            auto_mode=False,
        )

        # Should not call input() when gate is disabled
        with patch("builtins.input") as mock_input:
            result = human_gate_draft(state)
            assert not mock_input.called, "Should not prompt when gate is disabled"

    def test_draft_gate_no_prompt_in_auto_mode(self, tmp_path):
        """Draft gate should NOT prompt when in auto mode."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_draft

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_draft=True,
            auto_mode=True,  # Auto mode
        )

        with patch("builtins.input") as mock_input:
            result = human_gate_draft(state)
            assert not mock_input.called, "Should not prompt in auto mode"


class TestVerdictGateInteractive:
    """Test that verdict gate actually pauses for human input when enabled."""

    @patch("builtins.input", return_value="A")
    def test_verdict_gate_prompts_for_input(self, mock_input, tmp_path):
        """Verdict gate should prompt user for input when gate is enabled."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_verdict

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_verdict=True,  # Gate enabled
            auto_mode=False,     # Not auto mode
        )
        state["lld_status"] = "APPROVED"
        state["current_verdict"] = "APPROVED - looks good"

        result = human_gate_verdict(state)

        assert mock_input.called, "Verdict gate should prompt for user input"

    @patch("builtins.input", return_value="A")
    def test_verdict_gate_approve_routes_to_finalize(self, mock_input, tmp_path):
        """User choosing 'A' (Approve) should route to finalize."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_verdict

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_verdict=True,
            auto_mode=False,
        )
        state["lld_status"] = "APPROVED"
        state["current_verdict"] = "APPROVED"

        result = human_gate_verdict(state)

        assert result["next_node"] == "N5_finalize"

    @patch("builtins.input", return_value="R")
    def test_verdict_gate_revise_routes_to_generate(self, mock_input, tmp_path):
        """User choosing 'R' (Revise) should route back to draft generation."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_verdict

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_verdict=True,
            auto_mode=False,
        )
        state["lld_status"] = "BLOCKED"
        state["current_verdict"] = "BLOCKED - issues found"

        result = human_gate_verdict(state)

        assert result["next_node"] == "N1_generate_draft"

    @patch("builtins.input", return_value="M")
    def test_verdict_gate_manual_routes_to_end(self, mock_input, tmp_path):
        """User choosing 'M' (Manual) should end workflow."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_verdict

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_verdict=True,
            auto_mode=False,
        )
        state["lld_status"] = "APPROVED"

        result = human_gate_verdict(state)

        assert result["next_node"] == "END"

    def test_verdict_gate_no_prompt_when_disabled(self, tmp_path):
        """Verdict gate should NOT prompt when gate is disabled."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_verdict

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_verdict=False,  # Gate disabled
            auto_mode=False,
        )
        state["lld_status"] = "APPROVED"

        with patch("builtins.input") as mock_input:
            result = human_gate_verdict(state)
            assert not mock_input.called, "Should not prompt when gate is disabled"

    def test_verdict_gate_no_prompt_in_auto_mode(self, tmp_path):
        """Verdict gate should NOT prompt when in auto mode."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_verdict

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_verdict=True,
            auto_mode=True,  # Auto mode
        )
        state["lld_status"] = "APPROVED"

        with patch("builtins.input") as mock_input:
            result = human_gate_verdict(state)
            assert not mock_input.called, "Should not prompt in auto mode"


class TestInvalidInputHandling:
    """Test that invalid input is handled gracefully."""

    @patch("builtins.input", side_effect=["X", "invalid", "S"])
    def test_draft_gate_reprompts_on_invalid_input(self, mock_input, tmp_path):
        """Draft gate should reprompt when user enters invalid choice."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_draft

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_draft=True,
            auto_mode=False,
        )
        state["current_draft"] = "# Test"

        result = human_gate_draft(state)

        # Should have been called 3 times (2 invalid + 1 valid)
        assert mock_input.call_count == 3
        assert result["next_node"] == "N3_review"

    @patch("builtins.input", side_effect=["invalid", "A"])
    def test_verdict_gate_reprompts_on_invalid_input(self, mock_input, tmp_path):
        """Verdict gate should reprompt when user enters invalid choice."""
        from assemblyzero.workflows.requirements.nodes.human_gate import human_gate_verdict

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_verdict=True,
            auto_mode=False,
        )
        state["lld_status"] = "APPROVED"

        result = human_gate_verdict(state)

        assert mock_input.call_count == 2
        assert result["next_node"] == "N5_finalize"
