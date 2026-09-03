"""A nonzero pass-count plateau gets three strikes, import-death still gets two (#2062).

Five boostgauge #2 runs halted on the SECOND identical count with three
iterations unspent -- and the first of each pair was judged while the revision
starved on a 2000-char feedback window (#2058). One identical count is one
revision that did not move the needle, not proof that none can.

The #457 case this guard was built for -- 0/N -> 0/N import-death loops --
keeps its fast halt: zero passing twice is structural, not variance.
"""

from unittest.mock import patch

from assemblyzero.workflows.testing.nodes.verify_phases import verify_green_phase


def _state(**overrides):
    base = {
        "test_files": ["/tmp/t.py"],
        "repo_root": "/tmp/repo",
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 2,
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


def _pytest(passed, failed, coverage=50):
    return {
        "returncode": 1,
        "stdout": f"{passed} passed, {failed} failed",
        "stderr": "",
        "parsed": {"passed": passed, "failed": failed, "errors": 0,
                   "coverage": coverage},
    }


def _run(state, passed, failed):
    from assemblyzero.workflows.testing.nodes import verify_phases

    with patch.object(verify_phases, "run_pytest",
                      return_value=_pytest(passed, failed)):
        return verify_green_phase(state)


class TestNonzeroPlateau:
    def test_the_first_identical_count_loops_back(self):
        """The five live halts all died here, three iterations unspent."""
        out = _run(_state(previous_passed=44), 44, 50)
        assert out["next_node"] == "N4_implement_code", out.get("error_message")
        assert out["count_plateau_strikes"] == 1

    def test_the_second_identical_count_is_reported(self, capsys):
        """#2723: the second strike used to end the run. The strike counting is
        unchanged and the sentence still says "3 iterations"; what changed is
        that saying it no longer stops the loop."""
        out = _run(_state(previous_passed=44, count_plateau_strikes=1), 44, 50)
        assert out["error_message"] == ""
        assert "3 iterations" in capsys.readouterr().out

    def test_progress_resets_the_strikes(self):
        out = _run(_state(previous_passed=44, count_plateau_strikes=1), 45, 49)
        assert out["next_node"] == "N4_implement_code"
        assert out["count_plateau_strikes"] == 0


class TestImportDeathIsStillCalledOutFast:
    def test_zero_to_zero_is_reported_at_two(self, capsys):
        """#2062's fast detection is intact -- zero passing twice is
        structural, not variance -- and #2723 made the consequence the
        iteration cap's rather than this guard's."""
        out = _run(_state(previous_passed=0), 0, 50)
        assert out["error_message"] == ""
        assert "stagnant" in capsys.readouterr().out.lower()


class TestTheFieldIsDeclared:
    def test_count_plateau_strikes_is_a_channel(self):
        """#2018: undeclared keys are dropped at the node boundary, and the
        strike counter would silently reset every iteration."""
        from assemblyzero.workflows.testing.state import TestingWorkflowState

        assert "count_plateau_strikes" in TestingWorkflowState.__annotations__
