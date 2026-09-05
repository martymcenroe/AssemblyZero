"""#2841: the green loop's cap grants one more iteration to a loop that improved.

Run 15 resumed (`run-issue4-040403`, 2026-09-05) climbed 29, 35, 45, 47
passing across four green iterations and met the base cap of 5 with four
tests still failing. A fixed cap ending a converging loop is the coverage
guard that killed run 9 wearing a budget's clothes. The base cap stays; an
iteration that improved on the last earns one more, up to a ceiling of 10.
"""

from __future__ import annotations

from unittest.mock import patch

from assemblyzero.workflows.testing.nodes.verify_phases import (
    _cap_grace,
    verify_green_phase,
)
from assemblyzero.workflows.testing.state import (
    DEFAULT_MAX_ITERATIONS,
    GREEN_ITERATION_CEILING,
)
from assemblyzero.workflows.testing.step_budget import recursion_limit


class TestTheGraceRule:
    def test_more_tests_passing_at_the_cap_earns_one_more(self, capsys):
        state = {"previous_passed": 45, "previous_coverage": 92.0}
        assert _cap_grace(state, 4, 5, 47, 93.0) == 6
        out = capsys.readouterr().out
        assert "cap grace" in out and "45 -> 47" in out and "ceiling of 10" in out

    def test_same_tests_at_higher_coverage_earns_one_more(self):
        state = {"previous_passed": 47, "previous_coverage": 92.0}
        assert _cap_grace(state, 4, 5, 47, 93.0) == 6

    def test_no_improvement_earns_nothing(self):
        state = {"previous_passed": 47, "previous_coverage": 93.0}
        assert _cap_grace(state, 4, 5, 47, 93.0) is None
        assert _cap_grace(state, 4, 5, 46, 99.0) is None

    def test_the_ceiling_is_the_ceiling(self, capsys):
        state = {"previous_passed": 1, "previous_coverage": 1.0}
        assert _cap_grace(state, 9, GREEN_ITERATION_CEILING, 50, 99.0) is None
        assert "ceiling" in capsys.readouterr().out

    def test_the_first_iteration_counts_as_improvement(self):
        assert _cap_grace({}, 4, 5, 1, 1.0) == 6


def _state(**overrides):
    base = {
        "test_files": ["/tmp/test_example.py"],
        "repo_root": "/tmp/repo",
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 4,
        "iteration_count": 4,
        "max_iterations": DEFAULT_MAX_ITERATIONS,
        "coverage_target": 95,
        "implementation_files": [],
        "skip_e2e": True,
        "previous_coverage": 92.0,
        "previous_passed": 45,
    }
    base.update(overrides)
    return base


def _pytest(returncode, passed, failed, coverage):
    return {
        "returncode": returncode,
        "stdout": f"{passed} passed, {failed} failed",
        "stderr": "",
        "parsed": {"passed": passed, "failed": failed, "errors": 0, "coverage": coverage},
    }


@patch("assemblyzero.workflows.testing.nodes.verify_phases.check_circuit_breaker", return_value=(False, ""))
@patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
class TestTheNodeAtTheCap:
    def test_run_15s_fifth_iteration_is_granted_a_sixth(self, mock_pytest, _log, _cb):
        """47 of 51 at iteration 5 of 5, up from 45: one more, cap now 6."""
        mock_pytest.return_value = _pytest(1, passed=47, failed=4, coverage=93.0)
        result = verify_green_phase(_state())
        assert result["error_message"] == ""
        assert result["next_node"] != "end"
        assert result["max_iterations"] == DEFAULT_MAX_ITERATIONS + 1
        assert result["iteration_count"] == 5

    def test_a_fifth_iteration_that_did_not_improve_halts_as_before(self, mock_pytest, _log, _cb):
        mock_pytest.return_value = _pytest(1, passed=45, failed=6, coverage=92.0)
        result = verify_green_phase(_state())
        assert result["next_node"] == "end"
        assert "Max iterations" in result["error_message"] or "iterations" in result["error_message"]
        assert "max_iterations" not in result

    def test_the_ceiling_halts_even_an_improving_loop(self, mock_pytest, _log, _cb):
        mock_pytest.return_value = _pytest(1, passed=50, failed=1, coverage=94.0)
        result = verify_green_phase(_state(
            iteration_count=GREEN_ITERATION_CEILING - 1,
            max_iterations=GREEN_ITERATION_CEILING,
        ))
        assert result["next_node"] == "end"
        assert "iterations" in result["error_message"]



class TestTheStepBudgetCoversTheCeiling:
    def test_headroom_for_every_grantable_iteration(self):
        """Five more iterations of three super-steps each are budgeted whether
        or not they are granted, so a granted iteration never meets the
        recursion limit."""
        with_grace = recursion_limit(max_iterations=DEFAULT_MAX_ITERATIONS)
        assert with_grace >= GREEN_ITERATION_CEILING * 3
        # The grace term is constant: asking for the ceiling outright adds the
        # five iterations again, which is the budget being conservative, never
        # short.
        assert recursion_limit(max_iterations=GREEN_ITERATION_CEILING) > with_grace
