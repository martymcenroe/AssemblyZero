"""A repeated failing set freezes the tests and rewrites only the impl (#2064).

Six boostgauge #2 runs repeated their pass counts to the digit (33/74, 106/208,
27/68, 44/94, 37/82...). Tests and implementation are both regenerated from the
same spec, so when they disagree, a deterministic drafter reproduces the exact
failure set every iteration -- a fixed point no amount of re-rolling escapes.

The break: on the first repeat the tests become a frozen contract (the passing
ones prove they can run) and N4 rewrites only the implementation to satisfy
them. The identity guard halts on the THIRD identical set, after the break has
had its chance -- it used to halt on the first repeat, before anything new
could happen.
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


def _pytest(passed, failed, failing_names):
    lines = "\n".join(
        f"FAILED tests/unit/test_m.py::{n} - AssertionError: x" for n in failing_names
    )
    return {
        "returncode": 1,
        "stdout": f"===== short test summary info =====\n{lines}\n=====\n"
                  f"{passed} passed, {failed} failed",
        "stderr": "",
        "parsed": {"passed": passed, "failed": failed, "errors": 0, "coverage": 40},
    }


def _run(state, passed, failed, names):
    from assemblyzero.workflows.testing.nodes import verify_phases

    with patch.object(verify_phases, "run_pytest",
                      return_value=_pytest(passed, failed, names)):
        return verify_green_phase(state)


FAILS = ["t_a", "t_b"]
PREV = [f"tests/unit/test_m.py::{n}" for n in FAILS]


class TestTheFirstRepeatBreaksSymmetryInsteadOfHalting:
    def test_it_loops_back_with_tests_frozen(self):
        out = _run(
            _state(previous_passed=5, previous_green_failures=PREV,
                   count_plateau_strikes=0),
            5, 2, FAILS,
        )
        assert out["next_node"] == "N4_implement_code", out.get("error_message")
        assert out["freeze_tests"] is True
        assert out["identity_plateau_strikes"] == 1

    def test_the_third_identical_set_is_reported(self, capsys):
        """count_plateau_strikes seeded 0 so the count guard (strike 1 of 2)
        defers and the IDENTITY path is what speaks here.

        #2723: it says the tests were frozen and the set repeated anyway, and
        the loop carries on to its iteration cap instead of ending."""
        out = _run(
            _state(previous_passed=5, previous_green_failures=PREV,
                   identity_plateau_strikes=2, count_plateau_strikes=0),
            5, 2, FAILS,
        )
        assert out["error_message"] == ""
        assert "frozen" in capsys.readouterr().out

    def test_a_changed_failing_set_resets_the_strikes_and_unfreezes(self):
        out = _run(
            _state(previous_passed=4, previous_green_failures=PREV,
                   identity_plateau_strikes=1, freeze_tests=True),
            5, 2, ["t_c", "t_d"],
        )
        assert out["next_node"] == "N4_implement_code"
        assert out["identity_plateau_strikes"] == 0
        assert out["freeze_tests"] is False


class TestN4HonorsTheFreeze:
    def test_frozen_test_files_are_not_rewritten(self, tmp_path):
        from assemblyzero.workflows.testing.nodes.implementation import orchestrator

        repo = tmp_path / "wt"
        (repo / "tests").mkdir(parents=True)
        test_file = repo / "tests" / "test_m.py"
        test_file.write_text("# the contract\n", encoding="utf-8")

        calls = []
        state = {
            "files_to_modify": [
                {"path": "tests/test_m.py", "change_type": "Modify",
                 "description": "d"},
            ],
            "repo_root": str(repo),
            "audit_dir": "",
            "issue_number": 2,
            "iteration_count": 1,
            "freeze_tests": True,
            "test_failure_summary": "2 test(s): AssertionError",
            "lld_content": "x", "spec_path": "", "mock_mode": False,
        }
        with patch.object(orchestrator, "call_claude_for_file",
                          side_effect=lambda *a, **k: calls.append(1) or ("code", "")), \
             patch.object(orchestrator, "get_repo_structure", return_value=""), \
             patch.object(orchestrator, "extract_paths_from_lld",
                          return_value=None):
            try:
                orchestrator.implement_code(state)
            except Exception:
                pass  # downstream needs more state; the freeze check runs first

        assert test_file.read_text(encoding="utf-8") == "# the contract\n"
        assert calls == [], "no model call may target a frozen test file"

    def test_the_prompt_names_the_contract(self):
        """The instruction must reach the impl rewrite, or the model keeps
        assuming the tests will move to meet it."""
        import inspect

        from assemblyzero.workflows.testing.nodes.implementation import orchestrator

        source = inspect.getsource(orchestrator.implement_code)
        assert "FROZEN CONTRACT" in source
        assert "revision_error_context" in source


class TestTheArmedBreakOutranksOtherGuards:
    def test_flat_coverage_does_not_steal_the_frozen_iteration(self):
        """The live failure of the first version: identity armed the freeze,
        fell through, and the coverage guard halted on the same flat numbers
        before the frozen iteration ever executed (run-issue2-015725:
        40/74 twice, 'Coverage stagnant: 45.0% -> 45.0%')."""
        out = _run(
            _state(previous_passed=5, previous_coverage=45.0,
                   previous_green_failures=PREV, count_plateau_strikes=0),
            5, 2, FAILS,
        )
        assert out["next_node"] == "N4_implement_code", out.get("error_message")
        assert out["freeze_tests"] is True
