"""Tests for test-count stagnation detection in verify_green_phase.

Issue #457: When passed_count == 0 across consecutive iterations, the existing
coverage stagnation check was skipped (guarded by passed_count > 0). This caused
TDD loops to burn all max_iterations with zero progress. The fix adds a
test-count stagnation check that fires when passed_count is unchanged from the
previous iteration.
"""

from unittest.mock import patch

from assemblyzero.workflows.testing.nodes.verify_phases import verify_green_phase


def _make_state(**overrides):
    """Create a minimal TestingWorkflowState dict for testing."""
    base = {
        "test_files": ["/tmp/test_example.py"],
        "repo_root": "/tmp/repo",
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 42,
        "iteration_count": 1,
        "max_iterations": 10,
        "coverage_target": 90,
        "implementation_files": [],
        "skip_e2e": True,
        "previous_coverage": -1.0,
        "previous_passed": -1,
    }
    base.update(overrides)
    return base


def _make_pytest_result(returncode, passed=0, failed=0, errors=0, coverage=0):
    """Create a mock pytest result dict."""
    return {
        "returncode": returncode,
        "stdout": f"{passed} passed, {failed} failed",
        "stderr": "",
        "parsed": {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "coverage": coverage,
        },
    }


class TestGreenPhaseTestCountStagnation:
    """Test that verify_green_phase detects test-count stagnation."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_zero_to_zero_is_stagnant(self, mock_pytest):
        """previous_passed=0, current passed=0 -> STAGNANT, next_node=end."""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=0, failed=24, errors=0, coverage=26,
        )
        state = _make_state(previous_passed=0, previous_coverage=26.0)
        result = verify_green_phase(state)

        assert result["next_node"] == "end"
        assert "stagnant" in result["error_message"].lower()
        assert "Test count stagnant" in result["error_message"]
        assert result["previous_passed"] == 0

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.check_circuit_breaker")
    def test_zero_to_five_continues(self, mock_cb, mock_log, mock_pytest):
        """previous_passed=0, current passed=5 -> no stagnation, continues."""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=5, failed=19, errors=0, coverage=40,
        )
        mock_cb.return_value = (False, "")
        state = _make_state(previous_passed=0, previous_coverage=26.0)
        result = verify_green_phase(state)

        assert result["next_node"] == "N4_implement_code"
        assert result["error_message"] == ""
        assert result["previous_passed"] == 5

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.check_circuit_breaker")
    def test_first_iteration_no_stagnation(self, mock_cb, mock_log, mock_pytest):
        """previous_passed=-1 (first iteration) -> no stagnation check."""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=0, failed=24, errors=0, coverage=26,
        )
        mock_cb.return_value = (False, "")
        state = _make_state(previous_passed=-1, previous_coverage=-1.0)
        result = verify_green_phase(state)

        assert result["next_node"] == "N4_implement_code"
        assert result["error_message"] == ""
        assert result["previous_passed"] == 0

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_nonzero_stagnation(self, mock_pytest):
        """previous_passed=10, current passed=10 -> STAGNANT (non-zero case)."""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=10, failed=14, errors=0, coverage=50,
        )
        state = _make_state(previous_passed=10, previous_coverage=50.0)
        result = verify_green_phase(state)

        assert result["next_node"] == "end"
        assert "stagnant" in result["error_message"].lower()
        assert result["previous_passed"] == 10

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_previous_passed_propagated_in_success(self, mock_log, mock_pytest):
        """Success path includes previous_passed in return dict."""
        mock_pytest.return_value = _make_pytest_result(
            0, passed=24, failed=0, errors=0, coverage=95,
        )
        state = _make_state(previous_passed=20)
        result = verify_green_phase(state)

        assert result["next_node"] == "N7_finalize"
        assert result["previous_passed"] == 24
