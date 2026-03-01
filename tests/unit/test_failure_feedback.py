"""Tests for Issue #498 (test failure feedback to N4) and #501 (green phase identity stagnation).

Issue #498: N4 receives structured failure summaries instead of raw pytest output.
Issue #501: Green phase detects when the same tests fail across iterations (identity stagnation).
"""

from unittest.mock import patch

from assemblyzero.workflows.testing.nodes.verify_phases import (
    _build_failure_summary,
    verify_green_phase,
)


# ===========================================================================
# Issue #498: _build_failure_summary
# ===========================================================================


class TestBuildFailureSummary:
    """Tests for extracting concise failure summaries from pytest output."""

    def test_extracts_short_summary_section(self):
        """Extracts FAILED lines from 'short test summary info' section."""
        output = """============================= test session starts ==============================
collected 5 items

tests/test_foo.py::test_a PASSED
tests/test_foo.py::test_b FAILED
tests/test_foo.py::test_c FAILED

=========================== short test summary info ============================
FAILED tests/test_foo.py::test_b - AssertionError: 446 != 143
FAILED tests/test_foo.py::test_c - TypeError: unsupported operand
============================== 2 failed, 1 passed in 0.15s ====================
"""
        result = _build_failure_summary(output)
        assert "AssertionError: 446 != 143" in result
        assert "TypeError: unsupported operand" in result
        assert "test_b" in result
        assert "test_c" in result

    def test_includes_final_count_line(self):
        """Includes the '2 failed, 1 passed' line from separator."""
        output = """=========================== short test summary info ============================
FAILED tests/test_foo.py::test_b - AssertionError
============================== 1 failed, 2 passed in 0.15s ====================
"""
        result = _build_failure_summary(output)
        assert "1 failed" in result

    def test_fallback_to_failed_lines(self):
        """Falls back to FAILED lines when no summary section exists."""
        output = """FAILED tests/test_foo.py::test_a - Error: something broke
FAILED tests/test_foo.py::test_b - ValueError: bad input
3 failed in 1.00s
"""
        result = _build_failure_summary(output)
        assert "test_a" in result
        assert "test_b" in result

    def test_returns_empty_for_no_failures(self):
        """Returns empty string when no failures detected."""
        output = """============================= test session starts ==============================
collected 3 items

tests/test_foo.py::test_a PASSED
tests/test_foo.py::test_b PASSED

============================== 2 passed in 0.12s ===============================
"""
        result = _build_failure_summary(output)
        assert result == ""

    def test_truncates_long_output(self):
        """Truncates output exceeding MAX_FAILURE_SUMMARY_CHARS."""
        # Build output with many FAILED lines
        lines = ["=========================== short test summary info ============================"]
        for i in range(200):
            lines.append(f"FAILED tests/test_x.py::test_{i:04d} - AssertionError: value mismatch")
        lines.append("=" * 50 + " 200 failed " + "=" * 50)
        output = "\n".join(lines)

        result = _build_failure_summary(output)
        assert len(result) <= 2100  # 2000 + truncation message
        assert "truncated" in result

    def test_empty_input(self):
        """Empty input returns empty string."""
        assert _build_failure_summary("") == ""


# ===========================================================================
# Issue #498: verify_green_phase returns test_failure_summary
# ===========================================================================


def _make_state(**overrides):
    """Create a minimal TestingWorkflowState for testing."""
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
        "previous_green_failures": [],
    }
    base.update(overrides)
    return base


def _make_pytest_result(returncode, passed=0, failed=0, errors=0, coverage=0, summary_section=""):
    """Create a mock pytest result dict with optional summary section."""
    stdout = f"{passed} passed, {failed} failed"
    if summary_section:
        stdout = summary_section
    return {
        "returncode": returncode,
        "stdout": stdout,
        "stderr": "",
        "parsed": {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "coverage": coverage,
        },
    }


class TestFailureSummaryInGreenPhase:
    """Tests that verify_green_phase includes test_failure_summary in results."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.check_circuit_breaker")
    def test_failure_summary_populated_on_loop(self, mock_cb, mock_log, mock_pytest):
        """When tests fail and we loop back, test_failure_summary is set."""
        summary = """=========================== short test summary info ============================
FAILED tests/test_foo.py::test_bar - AssertionError: 446 != 143
============================== 1 failed, 2 passed in 0.15s ===================="""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=2, failed=1, errors=0, coverage=50, summary_section=summary,
        )
        mock_cb.return_value = (False, "")
        state = _make_state(previous_passed=-1, previous_coverage=-1.0)
        result = verify_green_phase(state)

        assert result["next_node"] == "N4_implement_code"
        assert "test_failure_summary" in result
        assert "AssertionError: 446 != 143" in result["test_failure_summary"]

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_failure_summary_empty_on_success(self, mock_log, mock_pytest):
        """When tests pass, test_failure_summary is empty."""
        mock_pytest.return_value = _make_pytest_result(
            0, passed=5, failed=0, errors=0, coverage=95,
        )
        state = _make_state()
        result = verify_green_phase(state)

        assert result["next_node"] == "N7_finalize"
        assert result["test_failure_summary"] == ""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_failure_summary_on_stagnation_halt(self, mock_pytest):
        """Even on stagnation halt, failure summary is populated."""
        summary = """=========================== short test summary info ============================
FAILED tests/test_x.py::test_a - AssertionError
============================== 1 failed in 0.10s ==============================="""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=0, failed=1, errors=0, coverage=0, summary_section=summary,
        )
        state = _make_state(previous_passed=0, previous_coverage=0.0)
        result = verify_green_phase(state)

        assert result["next_node"] == "end"
        assert "stagnant" in result["error_message"].lower()
        assert "test_failure_summary" in result
        assert result["test_failure_summary"] != ""


# ===========================================================================
# Issue #501: Green phase identity-based stagnation
# ===========================================================================


class TestGreenPhaseIdentityStagnation:
    """Tests for identity-based stagnation detection in verify_green_phase."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_same_failures_triggers_identity_stagnation(self, mock_pytest):
        """Same test names failing across iterations → identity stagnant → halt."""
        summary = """=========================== short test summary info ============================
FAILED tests/test_foo.py::test_bar - AssertionError
FAILED tests/test_foo.py::test_baz - TypeError
============================== 2 failed, 3 passed in 0.20s ===================="""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=3, failed=2, errors=0, coverage=60, summary_section=summary,
        )
        # previous_passed=1 and current passed=3 → count check passes (improvement)
        # But same tests failing → identity stagnation triggers
        state = _make_state(
            previous_passed=1,
            previous_coverage=-1.0,
            previous_green_failures=[
                "tests/test_foo.py::test_bar",
                "tests/test_foo.py::test_baz",
            ],
        )
        result = verify_green_phase(state)

        assert result["next_node"] == "end"
        assert "identity stagnant" in result["error_message"].lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.check_circuit_breaker")
    def test_different_failures_not_stagnant(self, mock_cb, mock_log, mock_pytest):
        """Different test names failing → not identity stagnant → continue."""
        summary = """=========================== short test summary info ============================
FAILED tests/test_foo.py::test_new_failure - AssertionError
============================== 1 failed, 4 passed in 0.20s ===================="""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=4, failed=1, errors=0, coverage=70, summary_section=summary,
        )
        mock_cb.return_value = (False, "")
        state = _make_state(
            previous_passed=3,
            previous_coverage=50.0,
            previous_green_failures=["tests/test_foo.py::test_old_failure"],
        )
        result = verify_green_phase(state)

        assert result["next_node"] == "N4_implement_code"
        assert result["error_message"] == ""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.check_circuit_breaker")
    def test_first_iteration_no_identity_stagnation(self, mock_cb, mock_log, mock_pytest):
        """First iteration (no previous failures) → no identity stagnation."""
        summary = """=========================== short test summary info ============================
FAILED tests/test_foo.py::test_bar - AssertionError
============================== 1 failed, 2 passed in 0.15s ===================="""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=2, failed=1, errors=0, coverage=50, summary_section=summary,
        )
        mock_cb.return_value = (False, "")
        state = _make_state(
            previous_passed=-1,
            previous_coverage=-1.0,
            previous_green_failures=[],
        )
        result = verify_green_phase(state)

        assert result["next_node"] == "N4_implement_code"

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_previous_green_failures_propagated(self, mock_pytest):
        """Result always includes previous_green_failures for next iteration."""
        summary = """=========================== short test summary info ============================
FAILED tests/test_foo.py::test_x - Error
============================== 1 failed, 2 passed in 0.15s ===================="""
        mock_pytest.return_value = _make_pytest_result(
            1, passed=2, failed=1, errors=0, coverage=50, summary_section=summary,
        )
        # Will hit count stagnation (previous_passed=2, current=2)
        state = _make_state(previous_passed=2, previous_coverage=50.0)
        result = verify_green_phase(state)

        assert "previous_green_failures" in result
        assert "tests/test_foo.py::test_x" in result["previous_green_failures"]

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_success_clears_green_failures(self, mock_log, mock_pytest):
        """On success, previous_green_failures is cleared."""
        mock_pytest.return_value = _make_pytest_result(
            0, passed=5, failed=0, errors=0, coverage=95,
        )
        state = _make_state(previous_green_failures=["tests/test_foo.py::test_x"])
        result = verify_green_phase(state)

        assert result["next_node"] == "N7_finalize"
        assert result["previous_green_failures"] == []


# ===========================================================================
# Issue #498: E2E failure summary
# ===========================================================================


class TestE2EFailureSummary:
    """Tests for _build_e2e_failure_summary."""

    def test_extracts_e2e_failure_summary(self):
        """Extracts failure summary from E2E pytest output."""
        from assemblyzero.workflows.testing.nodes.e2e_validation import (
            _build_e2e_failure_summary,
        )

        output = """=========================== short test summary info ============================
FAILED tests/test_e2e.py::test_workflow - AssertionError: expected 200, got 500
============================== 1 failed in 5.23s ===============================
"""
        result = _build_e2e_failure_summary(output)
        assert "expected 200, got 500" in result

    def test_returns_empty_for_no_failures(self):
        """Returns empty string when no failures."""
        from assemblyzero.workflows.testing.nodes.e2e_validation import (
            _build_e2e_failure_summary,
        )

        output = "3 passed in 2.00s"
        assert _build_e2e_failure_summary(output) == ""
