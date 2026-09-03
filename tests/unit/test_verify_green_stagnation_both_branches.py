"""Both branches must judge stagnation the same way (#2029, #2030).

#2023 fixed the coverage guard in the all-tests-pass branch, because that is
the branch boostgauge #41 died in. `verify_green_phase` carries the same check
twice, and the untouched copy halted the very next live arc:

    [N5] Results: 20 passed, 3 failed | Coverage: 97.0%
    [N5] Results: 22 passed, 1 failed | Coverage: 98.0%
    [STAGNANT] Coverage stagnant: 97.0% -> 98.0% (< 1% improvement). Halting.

Two more passing, two fewer failing, coverage up a point -- stopped for lack of
progress, at phase 3 of 6.

Every #2023 test enters through the all-tests-pass branch (failed=0) and passes
regardless of that defect. These enter with tests still failing, which is the
only way to reach the other copy.

#2030 is separate and fires even with flat tests: 97.0 -> 98.0 is a 1.0 point
gain, and `<= previous + 1.0` called it insufficient while printing
"< 1% improvement".
"""

from unittest.mock import patch

from assemblyzero.workflows.testing.nodes.verify_phases import (
    coverage_has_stagnated,
    verify_green_phase,
)


def _state(**overrides):
    base = {
        "test_files": ["/tmp/test_example.py"],
        "repo_root": "/tmp/repo",
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 1,
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


class TestTheTestsFailingBranch:
    """Reached only while tests are still failing -- the copy #2023 missed."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_live_case_is_not_stagnant(self, mock_pytest):
        """20/3 -> 22/1 with coverage 97.0 -> 98.0, exactly as it happened."""
        mock_pytest.return_value = _pytest(1, passed=22, failed=1, coverage=98)
        result = verify_green_phase(
            _state(previous_passed=20, previous_coverage=97.0,
                   previous_green_failures=["t_a", "t_b", "t_c"])
        )

        assert result["next_node"] == "N4_implement_code", result.get("error_message")
        assert "stagnant" not in result.get("error_message", "").lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_no_progress_at_all_is_still_reported(self, mock_pytest, capsys):
        """Same pass count, same failing set, flat coverage. The test-count
        guard reaches this one first, which is correct.

        #2723: a genuinely stuck loop still STOPS, but the iteration cap is
        what stops it -- this guard now only says what it sees. The stopping is
        covered by the cap's own tests; what is pinned here is that the
        observation is not lost when the guard stopped being terminal."""
        mock_pytest.return_value = _pytest(1, passed=20, failed=3, coverage=94)
        result = verify_green_phase(
            _state(previous_passed=20, previous_coverage=94.0,
                   previous_green_failures=["t_a", "t_b", "t_c"],
                   count_plateau_strikes=1)  # #2062: third identical count
        )
        assert result.get("error_message", "") == ""
        assert "stagnant" in capsys.readouterr().out.lower()


class TestTheThresholdBoundary:
    """#2030: reaching the stated bar must satisfy it."""

    def test_exactly_one_point_is_enough(self):
        assert coverage_has_stagnated(98.0, 97.0, 20, 20, [], []) is False

    def test_just_under_one_point_is_not(self):
        assert coverage_has_stagnated(97.9, 97.0, 20, 20, [], []) is True

    def test_flat_coverage_with_flat_tests_is_stagnant(self):
        assert coverage_has_stagnated(97.0, 97.0, 20, 20, [], []) is True

    def test_a_first_iteration_is_never_stagnant(self):
        """previous_coverage of -1 means nothing to compare against."""
        assert coverage_has_stagnated(50.0, -1.0, 5, -1, [], []) is False

    def test_a_drop_in_coverage_with_flat_tests_is_stagnant(self):
        assert coverage_has_stagnated(90.0, 97.0, 20, 20, [], []) is True

    def test_fewer_failures_is_progress_even_without_reaching_zero(self):
        """3 -> 1 failing counts. The #2023 form only recognised 'none failing
        now', which the tests-failing branch by definition never sees, so that
        signal was dead exactly where it was needed."""
        assert coverage_has_stagnated(
            94.0, 94.0, 21, 21, ["t_a"], ["t_a", "t_b", "t_c"]
        ) is False

    def test_the_same_failures_recurring_is_not_progress(self):
        assert coverage_has_stagnated(
            94.0, 94.0, 21, 21, ["t_a", "t_b"], ["t_a", "t_b"]
        ) is True


class TestBothBranchesAgree:
    def test_one_helper_backs_every_stagnation_decision(self):
        """The duplicated guard is what let #2023 land on one side only. If a
        raw inline comparison reappears, this catches it."""
        import inspect

        from assemblyzero.workflows.testing.nodes import verify_phases

        source = inspect.getsource(verify_phases.verify_green_phase)
        # #2711: the strike count wraps the decision, and BOTH branches go
        # through the wrapper; the wrapper is the only caller of the decision.
        assert source.count("coverage_plateau_verdict(") == 2, (
            "both branches must route their coverage-stagnation decision "
            "through the shared strike-counting helper"
        )
        assert source.count("coverage_has_stagnated(") == 0, (
            "a branch is calling the bare decision, bypassing the strike count"
        )
        wrapper = inspect.getsource(verify_phases.coverage_plateau_verdict)
        assert wrapper.count("coverage_has_stagnated(") == 1
        assert "previous_coverage + 1.0" not in source, (
            "an inline threshold comparison has reappeared; the two copies "
            "drift apart under exactly this kind of repair"
        )
