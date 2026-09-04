"""The implementation stage spends a derived step budget (#2790).

It passed none, so its ceiling was LangGraph's default. That default is
**10007**, read from the installed package rather than from memory:

    langgraph/_internal/_config.py:32
    DEFAULT_RECURSION_LIMIT = int(getenv("LANGGRAPH_DEFAULT_RECURSION_LIMIT", "10007"))

#2790 was filed saying 25 and argued a converging run had zero margin at its
iteration cap. That was wrong, and this suite pins the corrected claim
instead: 10007 is far above anything a converging run needs, and the cost is
a diverging one. A loop that escapes every internal cap runs ten thousand
super-steps -- in this stage a super-step can be a model call -- and then
dies on `GraphRecursionError`, which carries no gate key, matches no registry
row, and lands in the report as `unclassified`.

The budget is sized so every capped loop reaches its OWN named halt first,
which is the principle the implementation-spec stage's helper states.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.step_budget import (
    HEADROOM_STEPS,
    recursion_limit,
)

#: What the installed LangGraph falls back to when nothing is passed.
LANGGRAPH_DEFAULT = 10007


class TestTheDefaultThisReplaces:
    def test_the_default_is_read_from_the_package_not_from_memory(self):
        """The number #2790 was filed on was wrong. This is where the right
        one comes from, so the next reader does not have to trust prose."""
        from langgraph._internal._config import DEFAULT_RECURSION_LIMIT

        assert DEFAULT_RECURSION_LIMIT == LANGGRAPH_DEFAULT


class TestTheBudgetIsDerived:
    def test_it_is_far_below_the_default_it_replaces(self):
        """The whole value: a runaway costs dozens of super-steps, not ten
        thousand."""
        assert recursion_limit() < LANGGRAPH_DEFAULT / 10

    def test_raising_the_green_iteration_cap_raises_the_budget(self):
        """Derived, not typed. A cap and the budget that has to accommodate it
        cannot drift apart, because one is computed from the other."""
        base = recursion_limit(5)
        assert recursion_limit(6) > base
        assert recursion_limit(6) - base == 7, (
            "one more green iteration is 3 super-steps and one more e2e "
            "iteration is 4; if that shape changed, the budget must follow"
        )

    def test_raising_the_scaffold_cap_raises_the_budget(self):
        import assemblyzero.workflows.testing.nodes.validate_tests_mechanical as vtm

        base = recursion_limit()
        with patch.object(vtm, "MAX_SCAFFOLD_ATTEMPTS", vtm.MAX_SCAFFOLD_ATTEMPTS + 1):
            raised = recursion_limit()
        assert raised - base == 3, (
            "one more re-scaffold is N3 -> N2 -> N2.5 -> N3"
        )

    def test_every_cap_the_stage_owns_is_accounted_for(self):
        """A loop whose cap is missing from the sum is a loop that can be cut
        short by the budget instead of stopped by its own gate -- the exact
        failure this module exists to prevent."""
        from assemblyzero.workflows.testing.atlas import TOTAL_STEPS
        from assemblyzero.workflows.testing.graph import (
            MAX_COVERAGE_AUGMENT_ATTEMPTS,
        )
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            MAX_COMPLETENESS_ITERATIONS,
        )
        from assemblyzero.workflows.testing.nodes.revise_test_plan import (
            MAX_REVISION_CYCLES,
        )
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            MAX_SCAFFOLD_ATTEMPTS,
        )

        expected = (
            TOTAL_STEPS
            + MAX_REVISION_CYCLES * 2
            + (MAX_SCAFFOLD_ATTEMPTS + 1) * 3
            + MAX_COMPLETENESS_ITERATIONS * 2
            + 5 * 3
            + MAX_COVERAGE_AUGMENT_ATTEMPTS * 2
            + 5 * 4
            + HEADROOM_STEPS
        )
        assert recursion_limit(5) == expected


class TestTheStageActuallySpendsIt:
    def test_the_orchestrator_passes_the_derived_limit(self):
        """A budget nobody passes is a comment. This is the assertion that
        would have caught the original defect."""
        import inspect

        from assemblyzero.workflows.orchestrator import stages

        source = inspect.getsource(stages)
        assert "impl_recursion_limit(" in source, (
            "the implementation stage does not pass a recursion_limit; its "
            "ceiling is LangGraph's default again (#2790)"
        )
        assert 'config={"recursion_limit": impl_recursion_limit(' in source


class TestACappedLoopStillReachesItsOwnHalt:
    """The budget must not cut short a loop that has a gate waiting for it.

    This drives the #2767 re-scaffold loop -- the longest capped loop in the
    stage -- under the derived budget, and asserts it still ends on
    `impl.scaffold_suite_invalid` rather than on the budget.
    """

    VALID_SUITE = (
        "import pytest\n\n"
        "from widget.core import combine\n\n\n"
        "def test_combine_adds():\n"
        "    assert combine(1, 2) == 3\n"
    )

    @pytest.fixture
    def rolled(self, monkeypatch, tmp_path):
        import assemblyzero.workflows.testing.graph as g

        entries = {"scaffold": 0}

        def fake_scaffold(state):
            entries["scaffold"] += 1
            return {
                "generated_tests": self.VALID_SUITE + (
                    f"\n\ndef test_extra_{entries['scaffold']}():\n"
                    f"    assert combine({entries['scaffold']}, 0) "
                    f"== {entries['scaffold']}\n"
                ),
                "parsed_scenarios": {"scenarios": [
                    {"id": "S1", "description": "combine adds"},
                ]},
                "test_files": [str(tmp_path / "test_example.py")],
                "error_message": "",
            }

        monkeypatch.setattr(g, "load_lld", lambda s: {
            "lld_content": "# LLD\n", "spec_path": "spec.md", "error_message": ""})
        monkeypatch.setattr(g, "review_test_plan", lambda s: {
            "test_plan_status": "APPROVED", "error_message": ""})
        monkeypatch.setattr(g, "scaffold_tests", fake_scaffold)
        monkeypatch.setattr(
            "assemblyzero.workflows.testing.nodes.verify_phases.run_pytest",
            lambda *a, **k: {
                "returncode": 1, "stdout": "0 passed", "stderr": "",
                "parsed": {"passed": 0, "failed": 0, "errors": 0, "coverage": 0},
            },
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
        final = app.invoke(
            {
                "issue_number": 4242,
                "repo_root": str(tmp_path),
                "worktree_path": str(tmp_path),
                "audit_dir": "",
                "max_iterations": 5,
            },
            config={"recursion_limit": recursion_limit(5)},
        )
        return final, entries

    def test_it_ends_on_the_named_gate_not_the_budget(self, rolled):
        final, _ = rolled
        message = final.get("error_message", "")
        assert "scaffold budget is spent" in message, message

    def test_the_derived_budget_left_room_for_the_whole_loop(self, rolled):
        """If the budget were too tight the fixture would have raised
        GraphRecursionError before any assertion ran."""
        _, entries = rolled
        assert entries["scaffold"] >= 1
