"""A suite that collects nothing is rewritten, and the loop is bounded (#2767).

Two halves of one operator ruling, 2026-09-04.

**The budget counts every regeneration.** It used to count only the passes
that failed validation: `new_attempts = scaffold_attempts + 1 if not is_valid
else scaffold_attempts`, and the exhaustion check sat inside `if not
is_valid:`. So a regenerated suite that passed validation incremented nothing
and consulted nothing, and the `N3 -> N2` reroute shipped under #292 had no
bound of its own. The only thing holding it up was LangGraph's default of 25
super-steps, which raises an error with no gate key, no registry row, and no
halt bundle -- the artifact a stopped run leaves behind.

**So the red phase can now send a suite back.** "No tests were collected"
used to end the run. It routes to the scaffolder instead, and the cap that
already existed stops it: `impl.scaffold_suite_invalid`, registered, halting,
`upstream_artifact`.

The acceptance is the one the ruling names: a roll whose scaffolder keeps
producing a valid suite that collects nothing halts **at the cap**, not at the
recursion limit.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    MAX_SCAFFOLD_ATTEMPTS,
    validate_tests_mechanical_node,
)
from assemblyzero.workflows.testing.nodes.verify_phases import verify_red_phase

#: A suite that passes mechanical validation: real imports, real test
#: functions, real assertions. Nothing here is a stub.
VALID_SUITE = '''\
import pytest

from widget.core import combine


def test_combine_adds():
    assert combine(1, 2) == 3


def test_combine_rejects_none():
    with pytest.raises(TypeError):
        combine(None, 1)
'''


def _validation_state(attempts: int, previous_hash: str = "") -> dict:
    return {
        "generated_tests": VALID_SUITE,
        "parsed_scenarios": {"scenarios": [
            {"id": "S1", "description": "combine adds"},
            {"id": "S2", "description": "combine rejects None"},
        ]},
        "scaffold_attempts": attempts,
        "previous_scaffold_hash": previous_hash,
        "issue_number": 4242,
    }


def _pytest_result(returncode: int, passed=0, failed=0, errors=0):
    return {
        "returncode": returncode,
        "stdout": f"{passed} passed, {failed} failed",
        "stderr": "",
        "parsed": {
            "passed": passed, "failed": failed,
            "errors": errors, "coverage": 0,
        },
    }


def _red_state(**overrides) -> dict:
    base = {
        "test_files": ["/tmp/test_example.py"],
        "repo_root": "/tmp/repo",
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 4242,
        "iteration_count": 0,
        "max_iterations": 10,
        "coverage_target": 90,
        "implementation_files": [],
        "skip_e2e": True,
    }
    base.update(overrides)
    return base


class TestTheBudgetCountsEveryRegeneration:
    def test_a_valid_pass_now_spends_budget(self):
        """The half-sentence the whole ruling turns on."""
        result = validate_tests_mechanical_node(_validation_state(0))
        assert result["validation_result"]["is_valid"], result
        assert result["scaffold_attempts"] == 1, (
            "a pass that validated spent nothing, so nothing bounds a reroute"
        )
        assert result["scaffold_route"] == "continue"

    def test_the_cap_stops_a_valid_suite_once_the_allowance_is_exceeded(self):
        """Each pass a DIFFERENT valid suite, so the byte-identical guard is
        not what stops it -- the cap has to be.

        It stops on the pass after the allowance, not on the pass that
        reaches it: a suite that validates exactly at the cap is the one a
        run's last permitted retry produced, and killing that would make the
        budget punish the retry it exists to allow.
        """
        attempts = 0
        previous = ""
        routes = []
        for pass_number in range(1, MAX_SCAFFOLD_ATTEMPTS + 2):
            state = _validation_state(attempts, previous)
            # A different suite each time: same shape, one more test.
            state["generated_tests"] = VALID_SUITE + (
                f"\n\ndef test_extra_{pass_number}():\n"
                f"    assert combine({pass_number}, 0) == {pass_number}\n"
            )
            result = validate_tests_mechanical_node(state)
            assert result["validation_result"]["is_valid"], result
            attempts = result["scaffold_attempts"]
            previous = result.get("previous_scaffold_hash", "")
            routes.append(result["scaffold_route"])

        assert attempts == MAX_SCAFFOLD_ATTEMPTS + 1
        assert routes[-1] == "escalate", (
            f"the cap did not stop it: {routes}"
        )
        assert routes[:-1] == ["continue"] * MAX_SCAFFOLD_ATTEMPTS, routes

    def test_the_halt_does_not_claim_a_validated_suite_failed_validation(self):
        """The message a human reads to diagnose the halt has to be true.

        The exhaustion message said "the generated test suite cannot be
        validated", which is false of a suite that passed every check this
        node makes. What ran out is the budget.
        """
        attempts = 0
        previous = ""
        result: dict = {}
        for pass_number in range(1, MAX_SCAFFOLD_ATTEMPTS + 2):
            state = _validation_state(attempts, previous)
            state["generated_tests"] = VALID_SUITE + (
                f"\n\ndef test_extra_{pass_number}():\n"
                f"    assert combine({pass_number}, 0) == {pass_number}\n"
            )
            result = validate_tests_mechanical_node(state)
            attempts = result["scaffold_attempts"]
            previous = result.get("previous_scaffold_hash", "")

        message = result.get("error_message", "")
        assert message, "the cap fired but named no reason"
        assert "the scaffold budget is spent" in message, message
        assert "cannot be validated" not in message, (
            "the halt says a suite that validated could not be validated"
        )

    def test_an_invalid_pass_still_escalates_at_the_same_cap(self):
        """The invalid path's budget is unchanged: this ruling widened what
        counts, it did not move the line."""
        attempts = 0
        result: dict = {}
        for _ in range(MAX_SCAFFOLD_ATTEMPTS):
            state = _validation_state(attempts)
            state["generated_tests"] = "def test_nothing():\n    pass\n"
            result = validate_tests_mechanical_node(state)
            attempts = result["scaffold_attempts"]
        assert result["scaffold_route"] == "escalate"
        assert "cannot be validated" in result.get("error_message", "")


class TestTheRedPhaseSendsAnEmptySuiteBack:
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.Path.exists",
           return_value=True)
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution")
    def test_no_tests_collected_reroutes_instead_of_halting(
        self, _log, mock_pytest, _exists
    ):
        """Exit 1 with nothing collected: the run used to end here.

        Distinct from the exit-5 route already covered by #292 -- this is the
        path where pytest returns a normal code and simply ran nothing.
        """
        mock_pytest.return_value = _pytest_result(1, passed=0, failed=0, errors=0)
        result = verify_red_phase(_red_state())

        assert result["next_node"] == "N2_scaffold_tests"
        assert result["error_message"] == "", (
            "a reroute that records a reason routes to HALT instead (#2756)"
        )


class TestTheLoopEndsAtTheCapNotTheRecursionLimit:
    """The claim the ruling actually cares about, on the real compiled graph."""

    @pytest.fixture
    def rolled(self, monkeypatch, tmp_path):
        import assemblyzero.workflows.testing.graph as g

        entries = {"scaffold": 0}

        def fake_load(state):
            return {"lld_content": "# LLD\n", "spec_path": "spec.md",
                    "error_message": ""}

        def fake_review(state):
            return {"test_plan_status": "APPROVED", "error_message": ""}

        def fake_scaffold(state):
            entries["scaffold"] += 1
            # A different valid suite every time, so the byte-identical guard
            # is not what ends this -- the cap must be.
            return {
                "generated_tests": VALID_SUITE + (
                    f"\n\ndef test_extra_{entries['scaffold']}():\n"
                    f"    assert combine({entries['scaffold']}, 0) "
                    f"== {entries['scaffold']}\n"
                ),
                "parsed_scenarios": {"scenarios": [
                    {"id": "S1", "description": "combine adds"},
                    {"id": "S2", "description": "combine rejects None"},
                ]},
                "test_files": [str(tmp_path / "test_example.py")],
                "error_message": "",
            }

        monkeypatch.setattr(g, "load_lld", fake_load)
        monkeypatch.setattr(g, "review_test_plan", fake_review)
        monkeypatch.setattr(g, "scaffold_tests", fake_scaffold)
        monkeypatch.setattr(
            "assemblyzero.workflows.testing.nodes.verify_phases.run_pytest",
            lambda *a, **k: _pytest_result(1, passed=0, failed=0, errors=0),
        )
        monkeypatch.setattr(
            "assemblyzero.workflows.testing.nodes.verify_phases.log_workflow_execution",
            lambda **k: None,
        )
        monkeypatch.setattr(
            "assemblyzero.workflows.testing.nodes.verify_phases.Path.exists",
            lambda self: True,
        )

        app = g.build_testing_workflow().compile()
        final = app.invoke({
            "issue_number": 4242,
            "repo_root": str(tmp_path),
            "worktree_path": str(tmp_path),
            "audit_dir": "",
            "max_iterations": 5,
        })
        return final, entries

    def test_it_terminates_rather_than_running_out_of_super_steps(self, rolled):
        """If this raised, the loop was never bounded and the fixture would
        have failed with GraphRecursionError before reaching any assertion."""
        final, _ = rolled
        assert final is not None

    def test_it_halts_on_the_cap_that_already_existed(self, rolled):
        final, _ = rolled
        message = final.get("error_message", "")
        assert "scaffold budget is spent" in message, message

    def test_the_scaffolder_ran_exactly_the_budget(self, rolled):
        """Bounded at the documented number, not merely finite.

        The allowance is `MAX_SCAFFOLD_ATTEMPTS` regenerations; the pass that
        exceeds it is the one refused, so the scaffolder runs one more time
        than the cap and the last of those produces the suite nobody gets to
        use. That off-by-one is the deliberate asymmetry in
        `exhausted_reason`, not slack in the bound.
        """
        _, entries = rolled
        assert entries["scaffold"] == MAX_SCAFFOLD_ATTEMPTS + 1, entries
