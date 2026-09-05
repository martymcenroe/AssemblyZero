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
    """#2637: the stdout carries a real coverage TABLE, not just counts.

    These fixtures used to set `parsed["coverage"]` while leaving stdout as
    `"15 passed, 0 failed"` -- a decoupling production never has, because
    `parsed["coverage"]` is itself regex-extracted from that stdout. Under the
    absence law a report with no TOTAL row is a measurement failure, and these
    tests are about stagnation rather than about measurement failing, so the
    fixture now emits what pytest-cov actually emits.
    """
    return {
        "returncode": returncode,
        "stdout": (
            f"{passed} passed, {failed} failed\n"
            "Name                      Stmts   Miss  Cover   Missing\n"
            "---------------------------------------------------------\n"
            f"assemblyzero/example.py      10      1    {coverage}%   7\n"
            "---------------------------------------------------------\n"
            f"TOTAL                        10      1    {coverage}%\n"
        ),
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

        # #2327: all tests pass and coverage is under target, so the loop
        # continues to TEST additions rather than implementation revision.
        # What this test guards is that it continues at all -- that the
        # stagnation check does not fire on a run that is making progress.
        assert result["next_node"] == "N4c_augment_tests", result.get("error_message")
        assert "stagnant" not in result.get("error_message", "").lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_more_passing_tests_alone_is_progress(self, mock_pytest):
        """No recorded prior failures, but the passing count rose."""
        mock_pytest.return_value = _pytest(1, passed=15, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=12, previous_coverage=94.0)
        )
        # #2327: green-but-under-covered continues to test additions.
        assert result["next_node"] == "N4c_augment_tests", result.get("error_message")

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_it_says_why_it_kept_going(self, mock_pytest, capsys):
        mock_pytest.return_value = _pytest(1, passed=15, failed=0, coverage=94)
        verify_green_phase(
            _state(previous_passed=14, previous_coverage=94.0,
                   previous_green_failures=["test_decay"])
        )
        assert "tests improved" in capsys.readouterr().out


class TestGenuineStagnationIsStillDetected:
    """The guard's judgement is intact: no progress of any kind is still called
    stagnation. #2723 changed only what follows from that — it is said, and the
    iteration cap decides when to stop paying."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_flat_coverage_and_flat_tests_is_still_stagnation(
        self, mock_pytest, capsys
    ):
        """#2711: on the second consecutive strike; the state carries the first."""
        mock_pytest.return_value = _pytest(1, passed=15, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=15, previous_coverage=94.0,
                   coverage_plateau_strikes=1)
        )

        assert result.get("error_message", "") == ""
        assert "stagnant" in capsys.readouterr().out.lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_fewer_passing_tests_is_not_progress(self, mock_pytest, capsys):
        """A regression is a strike, never progress; the second strike is
        reported (#2711 -- the first buys exactly one revision to revert it)."""
        mock_pytest.return_value = _pytest(1, passed=13, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=15, previous_coverage=94.0,
                   coverage_plateau_strikes=1)
        )

        assert result.get("error_message", "") == ""
        assert "stagnant" in capsys.readouterr().out.lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_a_regression_buys_one_revision_and_no_more(self, mock_pytest):
        """The control for #2711: with no strike on the board, the same
        regression routes onward with the strike recorded."""
        mock_pytest.return_value = _pytest(1, passed=13, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=15, previous_coverage=94.0)
        )

        assert result["next_node"] != "end", result.get("error_message")
        assert result["coverage_plateau_strikes"] == 1

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_base_cap_grants_one_more_to_test_progress(self, mock_pytest):
        """#2841: at the base cap, an iteration that passed more tests than the
        last earns one more iteration; the cap in state grows by one."""
        mock_pytest.return_value = _pytest(1, passed=15, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=14, previous_coverage=94.0, iteration_count=4,
                   max_iterations=5, previous_green_failures=["test_decay"])
        )

        assert result["next_node"] != "end", result.get("error_message")
        assert result["max_iterations"] == 6

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_ceiling_still_wins_over_test_progress(self, mock_pytest):
        """The ceiling is the outer bound; improving tests must not let a run
        spend past it (#2841)."""
        from assemblyzero.workflows.testing.state import GREEN_ITERATION_CEILING

        mock_pytest.return_value = _pytest(1, passed=15, failed=0, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=14, previous_coverage=94.0,
                   iteration_count=GREEN_ITERATION_CEILING - 1,
                   max_iterations=GREEN_ITERATION_CEILING,
                   previous_green_failures=["test_decay"])
        )

        assert result["next_node"] == "end"
        assert "Max iterations" in result.get("error_message", "") or \
               f"after {GREEN_ITERATION_CEILING} iterations" in result.get("error_message", "")


class TestReachingTargetIsUnaffected:
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_hitting_the_target_still_finishes(self, mock_pytest):
        mock_pytest.return_value = _pytest(0, passed=15, failed=0, coverage=96)
        result = verify_green_phase(
            _state(previous_passed=14, previous_coverage=94.0)
        )
        assert result["next_node"] != "N4_implement_code"
        assert "stagnant" not in result.get("error_message", "").lower()
