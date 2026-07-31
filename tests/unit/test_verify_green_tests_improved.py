"""The coverage guard must not halt the iteration that fixed the tests (#2023).

boostgauge #41, 2026-07-31:

    iteration 1  14 passed, 1 failed  coverage 94.0%
    iteration 2  15 passed, 0 failed  coverage 94.0%
    [STAGNANT] Coverage stagnant: 94.0% -> 94.0% (< 1% improvement). Halting.

Iteration 2 fixed the failing test and the run was halted for making no
progress, three of five iterations unspent, one point from target.

This branch is reached only when EVERY test passes, so the iteration that fixes
the last failing test always lands here -- and it had a single guard, on the one
metric that had not moved. The decisive fixture below therefore varies the test
counts while holding coverage flat; a fixture with both flat would pass against
the broken code too.
"""

from unittest.mock import patch

from assemblyzero.workflows.testing.nodes.verify_phases import verify_green_phase


def _state(**overrides):
    base = {
        "test_files": ["/tmp/test_example.py"],
        "repo_root": "/tmp/repo",
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 41,
        "iteration_count": 1,
        "max_iterations": 5,
        "coverage_target": 95,
        "implementation_files": [],
        "skip_e2e": True,
        "previous_coverage": -1.0,
        "previous_passed": -1,
    }
    base.update(overrides)
    return base


def _pytest(returncode, passed=0, failed=0, errors=0, coverage=0):
    return {
        "returncode": returncode,
        "stdout": f"{passed} passed, {failed} failed",
        "stderr": "",
        "parsed": {
            "passed": passed, "failed": failed,
            "errors": errors, "coverage": coverage,
        },
    }


class TestProgressTheGuardCouldNotSee:
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_iteration_that_went_green_is_not_stagnant(self, mock_pytest):
        """The live case, exactly: 14/15 -> 15/15, coverage flat under target."""
        mock_pytest.return_value = _pytest(1, passed=15, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=14, previous_coverage=94.0,
                   previous_green_failures=["test_decay"])
        )

        assert result["next_node"] == "N4_implement_code", result.get("error_message")
        assert "stagnant" not in result.get("error_message", "").lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_more_passing_tests_alone_is_progress(self, mock_pytest):
        """No recorded prior failures, but the passing count rose."""
        mock_pytest.return_value = _pytest(1, passed=15, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=12, previous_coverage=94.0)
        )
        assert result["next_node"] == "N4_implement_code", result.get("error_message")

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_it_says_why_it_kept_going(self, mock_pytest, capsys):
        mock_pytest.return_value = _pytest(1, passed=15, failed=0, coverage=94)
        verify_green_phase(
            _state(previous_passed=14, previous_coverage=94.0,
                   previous_green_failures=["test_decay"])
        )
        assert "tests improved" in capsys.readouterr().out


class TestGenuineStagnationStillHalts:
    """The guard's purpose is intact: no progress of any kind still stops."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_flat_coverage_and_flat_tests_still_halts(self, mock_pytest):
        mock_pytest.return_value = _pytest(1, passed=15, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=15, previous_coverage=94.0)
        )

        assert result["next_node"] == "end"
        assert "stagnant" in result.get("error_message", "").lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_fewer_passing_tests_is_not_progress(self, mock_pytest):
        """Regression must never buy another iteration."""
        mock_pytest.return_value = _pytest(1, passed=13, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=15, previous_coverage=94.0)
        )

        assert result["next_node"] == "end"
        assert "stagnant" in result.get("error_message", "").lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_max_iterations_still_wins_over_test_progress(self, mock_pytest):
        """The iteration budget is the outer bound; improving tests must not
        let a run spend past it."""
        mock_pytest.return_value = _pytest(1, passed=15, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=14, previous_coverage=94.0, iteration_count=4,
                   max_iterations=5, previous_green_failures=["test_decay"])
        )

        assert result["next_node"] == "end"
        assert "Max iterations" in result.get("error_message", "") or \
               "after 5 iterations" in result.get("error_message", "")


class TestReachingTargetIsUnaffected:
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_hitting_the_target_still_finishes(self, mock_pytest):
        mock_pytest.return_value = _pytest(0, passed=15, failed=0, coverage=96)
        result = verify_green_phase(
            _state(previous_passed=14, previous_coverage=94.0)
        )
        assert result["next_node"] != "N4_implement_code"
        assert "stagnant" not in result.get("error_message", "").lower()
