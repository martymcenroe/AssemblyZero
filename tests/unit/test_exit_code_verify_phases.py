"""Tests for exit code routing in verify_phases.

Issue #292: Verify that verify_red_phase and verify_green_phase correctly
use pytest exit codes for routing decisions.

Tests cover:
- Red phase routes to N2_scaffold_tests on exit codes 4/5
- Red phase stops workflow on exit codes 2/3
- Red phase stores pytest_exit_code in state
- Green phase routes to N2_scaffold_tests on exit codes 4/5
- Green phase stops workflow on exit codes 2/3
- Green phase stores pytest_exit_code in state
- Graph routing functions handle new N2_scaffold_tests target
"""

from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.exit_code_router import (
    EXIT_INTERNALERROR,
    EXIT_INTERRUPTED,
    EXIT_NOTESTSCOLLECTED,
    EXIT_USAGEERROR,
)
from assemblyzero.workflows.testing.graph import route_after_green, route_after_red
from assemblyzero.workflows.testing.nodes.verify_phases import (
    verify_green_phase,
    verify_red_phase,
)


def _make_state(**overrides):
    """Create a minimal TestingWorkflowState dict for testing."""
    base = {
        "test_files": ["/tmp/test_example.py"],
        "repo_root": "/tmp/repo",
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 42,
        "iteration_count": 0,
        "max_iterations": 10,
        "coverage_target": 90,
        "implementation_files": [],
        "skip_e2e": True,
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


class TestRedPhaseExitCodeRouting:
    """Test that verify_red_phase routes correctly based on exit codes."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.Path.exists", return_value=True)
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_exit_4_routes_to_scaffold(self, mock_log, mock_pytest, mock_exists):
        """Exit code 4 (syntax/collection error) routes to N2_scaffold_tests."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_USAGEERROR, passed=0, failed=0, errors=1,
        )
        state = _make_state()
        result = verify_red_phase(state)

        assert result["next_node"] == "N2_scaffold_tests"
        assert result["pytest_exit_code"] == EXIT_USAGEERROR
        assert result["error_message"] == ""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.Path.exists", return_value=True)
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_exit_5_routes_to_scaffold(self, mock_log, mock_pytest, mock_exists):
        """Exit code 5 (no tests collected) routes to N2_scaffold_tests."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_NOTESTSCOLLECTED, passed=0, failed=0, errors=0,
        )
        state = _make_state()
        result = verify_red_phase(state)

        assert result["next_node"] == "N2_scaffold_tests"
        assert result["pytest_exit_code"] == EXIT_NOTESTSCOLLECTED
        assert result["error_message"] == ""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.Path.exists", return_value=True)
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_exit_2_stops_workflow(self, mock_pytest, mock_exists):
        """Exit code 2 (interrupted) stops the workflow."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_INTERRUPTED, passed=0, failed=0, errors=0,
        )
        state = _make_state()
        result = verify_red_phase(state)

        assert result["next_node"] == "end"
        assert result["pytest_exit_code"] == EXIT_INTERRUPTED
        assert "interrupted" in result["error_message"].lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.Path.exists", return_value=True)
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_exit_3_stops_workflow(self, mock_pytest, mock_exists):
        """Exit code 3 (internal error) stops the workflow."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_INTERNALERROR, passed=0, failed=0, errors=0,
        )
        state = _make_state()
        result = verify_red_phase(state)

        assert result["next_node"] == "end"
        assert result["pytest_exit_code"] == EXIT_INTERNALERROR
        assert "internal error" in result["error_message"].lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.Path.exists", return_value=True)
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_exit_1_valid_red_routes_to_implement(self, mock_log, mock_pytest, mock_exists):
        """Exit code 1 (tests failed) is valid RED, routes to N4."""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=0, failed=3, errors=0,
        )
        state = _make_state()
        result = verify_red_phase(state)

        assert result["next_node"] == "N4_implement_code"
        assert result["pytest_exit_code"] == 1
        assert result["error_message"] == ""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.Path.exists", return_value=True)
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_exit_code_stored_in_state(self, mock_log, mock_pytest, mock_exists):
        """Pytest exit code is always stored in returned state."""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=0, failed=5, errors=0,
        )
        state = _make_state()
        result = verify_red_phase(state)

        assert "pytest_exit_code" in result
        assert result["pytest_exit_code"] == 1

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.Path.exists", return_value=True)
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_exit_4_logs_scaffold_error(self, mock_log, mock_pytest, mock_exists):
        """Exit code 4 logs a scaffold_error event."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_USAGEERROR, passed=0, failed=0, errors=1,
        )
        state = _make_state()
        verify_red_phase(state)

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        assert call_kwargs["event"] == "red_phase_scaffold_error"
        assert call_kwargs["details"]["exit_code"] == EXIT_USAGEERROR


class TestGreenPhaseExitCodeRouting:
    """Test that verify_green_phase routes correctly based on exit codes."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_exit_4_routes_to_scaffold(self, mock_log, mock_pytest):
        """Exit code 4 (syntax/collection error) routes to N2_scaffold_tests."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_USAGEERROR, passed=0, failed=0, errors=1,
        )
        state = _make_state()
        result = verify_green_phase(state)

        assert result["next_node"] == "N2_scaffold_tests"
        assert result["pytest_exit_code"] == EXIT_USAGEERROR
        assert result["error_message"] == ""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_exit_5_routes_to_scaffold(self, mock_log, mock_pytest):
        """Exit code 5 (no tests collected) routes to N2_scaffold_tests."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_NOTESTSCOLLECTED, passed=0, failed=0, errors=0,
        )
        state = _make_state()
        result = verify_green_phase(state)

        assert result["next_node"] == "N2_scaffold_tests"
        assert result["pytest_exit_code"] == EXIT_NOTESTSCOLLECTED

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_exit_2_stops_workflow(self, mock_pytest):
        """Exit code 2 (interrupted) stops the workflow."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_INTERRUPTED, passed=0, failed=0, errors=0,
        )
        state = _make_state()
        result = verify_green_phase(state)

        assert result["next_node"] == "end"
        assert result["pytest_exit_code"] == EXIT_INTERRUPTED
        assert "interrupted" in result["error_message"].lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_exit_3_stops_workflow(self, mock_pytest):
        """Exit code 3 (internal error) stops the workflow."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_INTERNALERROR, passed=0, failed=0, errors=0,
        )
        state = _make_state()
        result = verify_green_phase(state)

        assert result["next_node"] == "end"
        assert result["pytest_exit_code"] == EXIT_INTERNALERROR

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_exit_4_increments_iteration(self, mock_log, mock_pytest):
        """Exit code 4 increments iteration count for loop protection."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_USAGEERROR, passed=0, failed=0, errors=1,
        )
        state = _make_state(iteration_count=3)
        result = verify_green_phase(state)

        assert result["iteration_count"] == 4

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_exit_code_stored_in_green_state(self, mock_log, mock_pytest):
        """Pytest exit code is stored in green phase return state."""
        mock_pytest.return_value = _make_pytest_result(
            0, passed=10, failed=0, errors=0, coverage=95,
        )
        state = _make_state()
        result = verify_green_phase(state)

        assert "pytest_exit_code" in result
        assert result["pytest_exit_code"] == 0

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_exit_4_logs_scaffold_error(self, mock_log, mock_pytest):
        """Exit code 4 logs a green_phase_scaffold_error event."""
        mock_pytest.return_value = _make_pytest_result(
            EXIT_USAGEERROR, passed=0, failed=0, errors=1,
        )
        state = _make_state()
        verify_green_phase(state)

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        assert call_kwargs["event"] == "green_phase_scaffold_error"


class TestGraphRoutingWithExitCodes:
    """Test graph routing functions handle N2_scaffold_tests."""

    def test_route_after_red_scaffold(self):
        """route_after_red returns N2_scaffold_tests when next_node says so."""
        state = {"error_message": "", "next_node": "N2_scaffold_tests"}
        assert route_after_red(state) == "N2_scaffold_tests"

    def test_route_after_red_implement(self):
        """route_after_red still routes to N4 for normal red phase."""
        state = {"error_message": "", "next_node": "N4_implement_code"}
        assert route_after_red(state) == "N4_implement_code"

    def test_route_after_red_error(self):
        """route_after_red returns end on error."""
        state = {"error_message": "some error", "next_node": "N4_implement_code"}
        assert route_after_red(state) == "end"

    def test_route_after_green_scaffold(self):
        """route_after_green returns N2_scaffold_tests when next_node says so."""
        state = {"error_message": "", "next_node": "N2_scaffold_tests"}
        assert route_after_green(state) == "N2_scaffold_tests"

    def test_route_after_green_implement(self):
        """route_after_green still routes to N4 for test failures."""
        state = {
            "error_message": "",
            "next_node": "N4_implement_code",
            "iteration_count": 1,
            "max_iterations": 10,
        }
        assert route_after_green(state) == "N4_implement_code"

    def test_route_after_green_e2e(self):
        """route_after_green still routes to N6 on success."""
        state = {"error_message": "", "next_node": "N6_e2e_validation"}
        assert route_after_green(state) == "N6_e2e_validation"

    def test_route_after_green_finalize(self):
        """route_after_green still routes to N7 when skipping E2E."""
        state = {"error_message": "", "next_node": "N7_finalize"}
        assert route_after_green(state) == "N7_finalize"

    def test_route_after_green_error(self):
        """route_after_green returns end on error."""
        state = {"error_message": "boom", "next_node": "N4_implement_code"}
        assert route_after_green(state) == "end"
