"""The graph's step budget is derived, explicit, and halts by name (Closes #2245).

LangGraph bounds a run by super-steps, and running out raises
``GraphRecursionError`` -- which names no stage, no loop and no document. Before
this, ``run_lld_stage`` passed no config at all and every orchestrated roll took
the default of 25 by accident, while ``tools/run_requirements_workflow.py``
computed ``(max_iterations * 4) + 10``: 22 at the default cap, smaller than the
default it was raising.

The per-loop costs are measured here rather than asserted in a comment, because
a comment would rot the first time a node joined a loop. The technique is
``TestStepBudget``'s in ``test_finalize_repair_routing.py``: drive the real
compiled graph with every model call stubbed and count super-steps.
"""

import pytest

from assemblyzero.workflows.requirements.nodes.finalize import MAX_FINALIZE_REPAIRS
from assemblyzero.workflows.requirements.step_budget import (
    CLEAN_RUN_STEPS,
    FINALIZE_REPAIR_STEPS,
    HEADROOM_STEPS,
    REVISE_ROUND_STEPS,
    describe_budget_exhaustion,
    invoke_with_budget,
    recursion_limit,
)


def _drive(monkeypatch, *, repairs=0, revisions=0, max_iterations=3, limit=500):
    """The real compiled graph, every model call stubbed. Returns super-steps."""
    import assemblyzero.workflows.requirements.graph as gr

    blocked = {"n": 0}
    revised = {"n": 0}

    def passthrough(state):
        return {}

    def fake_mechanical(state):
        # The real node clears the reviewer's stale BLOCKED (#302,
        # validate_mechanical.py:1597). A passthrough leaves it set and the
        # router bounces every revise round back to the drafter forever, which
        # measures the stub instead of the graph.
        return {"lld_status": "PENDING", "validation_errors": []}

    def fake_review(state):
        n = state.get("verdict_count", 0) + 1
        if revised["n"] < revisions:
            revised["n"] += 1
            return {
                "lld_status": "BLOCKED",
                "open_questions_status": "NONE",
                "verdict_count": n,
                # Distinct each round, so two-strike stagnation does not fire
                # and the loop itself is what is being measured.
                "current_verdict": f"blocking issue number {revised['n']} " * 3,
                "previous_review_feedback": "",
            }
        return {
            "lld_status": "APPROVED",
            "open_questions_status": "NONE",
            "verdict_count": n,
        }

    def fake_draft(state):
        return {
            "current_draft": "# doc\n\n## 1. A\n\nbody\n",
            "draft_count": state.get("draft_count", 0) + 1,
            "validation_errors": [],
            "finalize_repair_pending": False,
            "error_message": "",
        }

    def fake_finalize(state):
        if blocked["n"] < repairs:
            blocked["n"] += 1
            return {
                "finalize_repair_pending": True,
                "finalize_repair_count": blocked["n"],
                "validation_errors": ["forced"],
                "error_message": "",
            }
        return {"finalize_repair_pending": False, "final_lld_path": "x.md"}

    for name in (
        "load_input", "analyze_codebase", "analyze_requirements",
        "ponder_stibbons_node", "validate_test_plan_node",
        "human_gate_draft", "human_gate_verdict",
    ):
        monkeypatch.setattr(gr, name, passthrough)
    monkeypatch.setattr(gr, "validate_lld_mechanical", fake_mechanical)
    monkeypatch.setattr(gr, "review", fake_review)
    monkeypatch.setattr(gr, "generate_draft", fake_draft)
    monkeypatch.setattr(gr, "finalize", fake_finalize)

    app = gr.create_requirements_graph().compile()
    steps = 0
    for _ in app.stream(
        _state(max_iterations), config={"recursion_limit": limit}
    ):
        steps += 1
    return steps


def _state(max_iterations=3):
    return {
        "workflow_type": "lld",
        "config_gates_draft": False,
        "config_gates_verdict": False,
        "max_iterations": max_iterations,
        "issue_number": 7,
        "target_repo": "repo",
        "audit_dir": "audit",
    }


class TestTheMeasuredCosts:
    """The constants must equal what the graph actually spends. A node added to
    a loop fails one of these rather than quietly eating headroom."""

    def test_a_clean_pass_costs_what_the_constant_says(self, monkeypatch, capsys):
        steps = _drive(monkeypatch)
        capsys.readouterr()
        assert steps == CLEAN_RUN_STEPS

    @pytest.mark.parametrize("repairs", [1, 2, 3])
    def test_each_repair_costs_what_the_constant_says(
        self, monkeypatch, capsys, repairs
    ):
        steps = _drive(monkeypatch, repairs=repairs)
        capsys.readouterr()
        assert steps == CLEAN_RUN_STEPS + repairs * FINALIZE_REPAIR_STEPS

    @pytest.mark.parametrize("revisions", [1, 2, 3, 4])
    def test_each_revise_round_costs_what_the_constant_says(
        self, monkeypatch, capsys, revisions
    ):
        steps = _drive(monkeypatch, revisions=revisions, max_iterations=99)
        capsys.readouterr()
        assert steps == CLEAN_RUN_STEPS + revisions * REVISE_ROUND_STEPS

    def test_the_costs_are_additive(self, monkeypatch, capsys):
        """The derivation sums the loops, so it is only right if they add."""
        steps = _drive(monkeypatch, revisions=2, repairs=2, max_iterations=99)
        capsys.readouterr()
        assert steps == CLEAN_RUN_STEPS + 2 * REVISE_ROUND_STEPS + 2 * FINALIZE_REPAIR_STEPS


class TestTheDerivedLimit:
    def test_it_covers_every_loop_run_to_its_cap(self, monkeypatch, capsys):
        """The binding property: a run that spends everything must still fit."""
        limit = recursion_limit(max_iterations=3)
        steps = _drive(monkeypatch, revisions=3, repairs=MAX_FINALIZE_REPAIRS,
                       max_iterations=99, limit=limit)
        capsys.readouterr()
        assert steps <= limit

    def test_it_is_bigger_than_both_limits_it_replaces(self):
        """25 by accident, and 22 from a formula smaller than the default it
        was raising."""
        assert recursion_limit(max_iterations=3) > 25
        assert recursion_limit(max_iterations=3) > (3 * 4) + 10

    def test_it_grows_with_each_cap(self):
        base = recursion_limit(max_iterations=3, max_finalize_repairs=2)
        assert recursion_limit(max_iterations=4, max_finalize_repairs=2) == (
            base + REVISE_ROUND_STEPS
        )
        assert recursion_limit(max_iterations=3, max_finalize_repairs=3) == (
            base + FINALIZE_REPAIR_STEPS
        )

    def test_it_carries_the_stated_headroom(self):
        assert recursion_limit(max_iterations=0, max_finalize_repairs=0) == (
            CLEAN_RUN_STEPS + HEADROOM_STEPS
        )

    def test_a_junk_cap_falls_back_rather_than_raising(self):
        assert recursion_limit("not a number") == recursion_limit(3)

    def test_the_repair_cap_is_a_judgment_not_a_constraint(self, monkeypatch, capsys):
        """#2245's last criterion. MAX_FINALIZE_REPAIRS was 2 partly because a
        third did not fit. It fits now, so the value stands on its own."""
        limit = recursion_limit(max_iterations=3)
        steps = _drive(monkeypatch, repairs=MAX_FINALIZE_REPAIRS + 1, limit=limit)
        capsys.readouterr()
        assert steps <= limit, (
            "a repair past the cap still does not fit the derived budget, so "
            "the cap is being set by the step budget rather than by what a "
            "repair loop should try"
        )


class TestExhaustionHaltsByName:
    """#2245's third criterion: a spent budget must name the stage and the loop."""

    def test_a_spent_budget_returns_a_halt_not_an_exception(self, monkeypatch, capsys):
        import assemblyzero.workflows.requirements.graph as gr

        # A cap far above the budget, so the revise loop outruns the steps.
        monkeypatch.setattr(
            "assemblyzero.workflows.requirements.step_budget.recursion_limit",
            lambda *a, **k: 20,
        )
        _stub_graph(monkeypatch, revisions=50)
        app = gr.create_requirements_graph().compile()

        result = invoke_with_budget(app, _state(max_iterations=99), stage="lld")
        capsys.readouterr()

        assert result["error_message"], "a spent budget must produce a halt"
        assert "GraphRecursionError" not in result["error_message"]

    def test_the_halt_names_the_stage_and_the_loop(self, monkeypatch, capsys):
        import assemblyzero.workflows.requirements.graph as gr

        monkeypatch.setattr(
            "assemblyzero.workflows.requirements.step_budget.recursion_limit",
            lambda *a, **k: 20,
        )
        _stub_graph(monkeypatch, revisions=50)
        app = gr.create_requirements_graph().compile()

        message = invoke_with_budget(
            app, _state(max_iterations=99), stage="lld"
        )["error_message"]
        capsys.readouterr()

        assert "lld" in message
        assert "revise loop" in message
        assert "ran out of graph steps" in message

    def test_the_halt_reports_the_counters(self):
        message = describe_budget_exhaustion(
            {"verdict_count": 4, "finalize_repair_count": 2, "draft_count": 6},
            limit=40, steps=40, stage="lld",
        )
        assert "4" in message and "2" in message and "6" in message
        assert "40" in message

    def test_a_repair_only_exhaustion_names_the_repair_loop(self):
        message = describe_budget_exhaustion(
            {"verdict_count": 1, "finalize_repair_count": 5}, 40, 40, "lld"
        )
        assert "finalize repair loop" in message
        assert "revise loop and" not in message


class TestTheStreamContract:
    """invoke_with_budget streams so it can name the loop on exhaustion. That is
    only safe if the last streamed value is what invoke would have returned."""

    def test_the_last_streamed_value_equals_invoke(self, monkeypatch, capsys):
        import assemblyzero.workflows.requirements.graph as gr

        _stub_graph(monkeypatch, revisions=0)
        app = gr.create_requirements_graph().compile()

        direct = app.invoke(_state(), config={"recursion_limit": 100})
        streamed = invoke_with_budget(app, _state(), stage="lld")
        capsys.readouterr()

        assert streamed.get("final_lld_path") == direct.get("final_lld_path")
        assert streamed.get("lld_status") == direct.get("lld_status")
        assert set(direct) <= set(streamed), (
            "streaming dropped keys invoke returns; every caller reads this dict"
        )

    def test_a_clean_run_carries_no_error_message(self, monkeypatch, capsys):
        import assemblyzero.workflows.requirements.graph as gr

        _stub_graph(monkeypatch, revisions=0)
        app = gr.create_requirements_graph().compile()
        result = invoke_with_budget(app, _state(), stage="lld")
        capsys.readouterr()

        assert not result.get("error_message")
        assert result.get("final_lld_path") == "x.md"


class TestBothCallersPassAnExplicitLimit:
    """#2245's second criterion: no caller inherits the default silently."""

    def test_the_orchestrator_uses_the_derived_budget(self):
        import inspect

        from assemblyzero.workflows.orchestrator.stages import run_lld_stage

        source = inspect.getsource(run_lld_stage)
        assert "invoke_with_budget" in source, (
            "run_lld_stage invokes the graph without a derived budget, so an "
            "orchestrated roll silently takes LangGraph's default of 25"
        )

    def test_the_standalone_runner_uses_the_derived_budget(self):
        from pathlib import Path

        import assemblyzero  # noqa: F401  (anchor the repo root)

        runner = (
            Path(__file__).resolve().parents[2] / "tools" / "run_requirements_workflow.py"
        )
        source = runner.read_text(encoding="utf-8")
        assert "invoke_with_budget" in source

        # Comments quote the old formula deliberately, to say what changed.
        # Only live code counts.
        code = [
            line for line in source.splitlines()
            if not line.lstrip().startswith("#")
        ]
        offenders = [line for line in code if "* 4) + 10" in line]
        assert not offenders, (
            f"the undersized formula is still live in the runner: {offenders}"
        )
        assert not [
            line for line in code
            if "recursion_limit" in line and "=" in line and "step_budget" not in line
        ], "the runner still computes a recursion limit of its own"


def _stub_graph(monkeypatch, *, revisions=0, repairs=0):
    """Shared stubbing for the invoke-level tests."""
    import assemblyzero.workflows.requirements.graph as gr

    state_counters = {"revised": 0, "blocked": 0}

    def passthrough(state):
        return {}

    def fake_mechanical(state):
        return {"lld_status": "PENDING", "validation_errors": []}

    def fake_review(state):
        n = state.get("verdict_count", 0) + 1
        if state_counters["revised"] < revisions:
            state_counters["revised"] += 1
            return {
                "lld_status": "BLOCKED",
                "open_questions_status": "NONE",
                "verdict_count": n,
                "current_verdict": f"blocking issue {state_counters['revised']} " * 3,
                "previous_review_feedback": "",
            }
        return {
            "lld_status": "APPROVED",
            "open_questions_status": "NONE",
            "verdict_count": n,
        }

    def fake_draft(state):
        return {
            "current_draft": "# doc\n\n## 1. A\n\nbody\n",
            "draft_count": state.get("draft_count", 0) + 1,
            "validation_errors": [],
            "finalize_repair_pending": False,
            "error_message": "",
        }

    def fake_finalize(state):
        if state_counters["blocked"] < repairs:
            state_counters["blocked"] += 1
            return {
                "finalize_repair_pending": True,
                "finalize_repair_count": state_counters["blocked"],
                "validation_errors": ["forced"],
                "error_message": "",
            }
        return {"finalize_repair_pending": False, "final_lld_path": "x.md"}

    for name in (
        "load_input", "analyze_codebase", "analyze_requirements",
        "ponder_stibbons_node", "validate_test_plan_node",
        "human_gate_draft", "human_gate_verdict",
    ):
        monkeypatch.setattr(gr, name, passthrough)
    monkeypatch.setattr(gr, "validate_lld_mechanical", fake_mechanical)
    monkeypatch.setattr(gr, "review", fake_review)
    monkeypatch.setattr(gr, "generate_draft", fake_draft)
    monkeypatch.setattr(gr, "finalize", fake_finalize)
