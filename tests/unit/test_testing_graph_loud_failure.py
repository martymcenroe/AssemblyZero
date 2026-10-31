"""Every stop the testing graph decides is loud and reaches HALT (#3585, ADR 0236).

Ledger 0908 rows for ``assemblyzero/workflows/testing/graph.py``. Each test is
named for the ledger line it settles (line numbers from commit 79e18ad1).

The routers used to end the run at ``END`` for an iteration cap, a spent
budget, a BLOCKED test plan or a route nobody named, printing at most a line on
stdout. ``END`` writes no halt bundle and alerts no one, and the stage read the
empty ``error_message`` as a pass. Every such stop now routes to ``HALT``, which
alerts. A router's own state writes are discarded at the graph boundary, so the
node in front of it records the reason (``_records_its_stop``), and the alert
carries it.
"""

from __future__ import annotations

import pytest

import assemblyzero.core.halt_node as hn
import assemblyzero.core.state_persistence as sp
from assemblyzero.workflows.testing import graph
from assemblyzero.workflows.testing.nodes.revise_test_plan import MAX_REVISION_CYCLES
from assemblyzero.workflows.testing.state import DEFAULT_MAX_ITERATIONS


def _node_fn(name: str):
    """The callable the built graph runs for ``name``, narration included."""
    spec = graph.build_testing_workflow().nodes[name]
    runnable = getattr(spec, "runnable", spec)
    return getattr(runnable, "func", runnable)


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    """Keep the halt's snapshot out of the real state directory."""
    target = tmp_path / "state"
    target.mkdir()
    monkeypatch.setattr(hn, "STATE_DIR", target, raising=False)
    monkeypatch.setattr(sp, "STATE_DIR", target, raising=False)
    return target


# ---------------------------------------------------------------- line 128


def test_128_a_failed_checkpoint_stops_the_run_and_says_so(
    tmp_path, monkeypatch, capsys, operator_alerts
):
    """A checkpoint that fails is no longer printed and swallowed."""

    def broken(worktree, issue, name):
        raise OSError("disk full")

    monkeypatch.setattr(graph, "commit_checkpoint", broken)

    def node(state):
        return {"error_message": ""}

    wrapped = graph._wrap_with_checkpoint(node, "post-green")
    with pytest.raises(graph.CheckpointFailed) as caught:
        wrapped({"worktree_path": str(tmp_path), "issue_number": 77})

    message = str(caught.value)
    assert "post-green" in message
    assert str(tmp_path) in message
    assert "77" in message
    assert "OSError: disk full" in message
    assert isinstance(caught.value.__cause__, OSError)
    err = capsys.readouterr().err
    assert "ERROR [CP:post-green]" in err
    assert "disk full" in err
    # One alert, from the run's caller (the entry point or the orchestrator's
    # stage, whose failed result routes to HALT), never a second one here.
    assert operator_alerts == []


def test_128_a_checkpoint_that_works_still_returns_the_result(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(
        graph, "commit_checkpoint", lambda w, i, n: seen.append((w, i, n)) or True
    )
    result = {"error_message": "", "x": 1}
    wrapped = graph._wrap_with_checkpoint(lambda state: result, "post-impl")
    assert wrapped({"worktree_path": str(tmp_path), "issue_number": 5}) is result
    assert seen == [(str(tmp_path), 5, "post-impl")]


# ---------------------------------------------------------------- line 217


def test_217_an_n1_error_halts_under_auto_mode():
    """auto_mode is the default (--review none); it no longer hides N1 errors."""
    state = {"error_message": "Review error: boom", "auto_mode": True}
    assert graph.route_after_review(state) == "HALT"


def test_217_an_n1_error_halts_without_auto_mode():
    assert graph.route_after_review({"error_message": "boom"}) == "HALT"


# ---------------------------------------------------------------- line 227


@pytest.mark.parametrize(
    "state",
    [
        {"auto_mode": True},
        {"test_plan_policy": "auto"},
        {"auto_mode": True, "test_plan_policy": "auto"},
    ],
    ids=["auto_mode", "policy_auto", "both"],
)
def test_227_a_blocked_plan_under_auto_is_revised_not_passed(state):
    """A BLOCKED verdict is a failed gate; auto no longer walks past it."""
    state = {
        **state,
        "error_message": "",
        "test_plan_status": "BLOCKED",
        "test_plan_revision_count": 0,
    }
    assert graph.route_after_review(state) == "N1_5_revise_test_plan"


def test_227_a_blocked_plan_under_auto_halts_when_revisions_are_spent(capsys):
    state = {
        "error_message": "",
        "auto_mode": True,
        "test_plan_status": "BLOCKED",
        "test_plan_revision_count": MAX_REVISION_CYCLES,
    }
    assert graph.route_after_review(state) == "HALT"
    assert "ERROR [N1]" in capsys.readouterr().err


# ---------------------------------------------------------------- line 232


def test_232_a_strict_blocked_plan_halts():
    state = {
        "error_message": "",
        "test_plan_policy": "strict",
        "test_plan_status": "BLOCKED",
        "test_plan_revision_count": 0,
    }
    assert graph.route_after_review(state) == "HALT"


def test_232_the_strict_halt_is_recorded_by_n1(monkeypatch, capsys):
    """The node records the reason the router halts on, so HALT's alert has it."""
    monkeypatch.setattr(
        graph,
        "review_test_plan",
        lambda state: {
            "test_plan_status": "BLOCKED",
            "test_plan_verdict": "BLOCKED: scenario 3 tests nothing",
            "error_message": "",
        },
    )
    result = _node_fn("N1_review_test_plan")(
        {"issue_number": 9, "test_plan_policy": "strict"}
    )
    message = result["error_message"]
    assert message.startswith("Test plan revision budget spent")
    assert "strict" in message
    assert "scenario 3 tests nothing" in message
    assert "issue 9" in message
    assert "ERROR [N1] Test plan revision budget spent" in capsys.readouterr().err


def test_232_a_strict_halt_reaches_halt_and_alerts(
    monkeypatch, state_dir, operator_alerts
):
    """The whole graph, N0 to HALT: the alert carries N1's recorded reason."""
    monkeypatch.setattr(graph, "load_lld", lambda state: {"error_message": ""})
    monkeypatch.setattr(
        graph,
        "review_test_plan",
        lambda state: {
            "test_plan_status": "BLOCKED",
            "test_plan_verdict": "BLOCKED: no edge cases",
            "error_message": "",
        },
    )
    app = graph.build_testing_workflow().compile()
    final = app.invoke({"issue_number": 31, "test_plan_policy": "strict"})

    assert final.get("workflow_status") == "halted"
    assert final.get("recovery_plan_path")
    assert len(operator_alerts) == 1
    assert "Test plan revision budget spent" in operator_alerts[0]["cause"]
    assert "no edge cases" in operator_alerts[0]["cause"]


# ---------------------------------------------------------------- line 245


def test_245_still_blocked_after_the_revision_cap_halts(capsys):
    state = {
        "error_message": "",
        "test_plan_status": "BLOCKED",
        "test_plan_revision_count": MAX_REVISION_CYCLES,
    }
    assert graph.route_after_review(state) == "HALT"
    err = capsys.readouterr().err
    assert "ERROR [N1] Test plan revision budget spent" in err
    assert f"{MAX_REVISION_CYCLES} revision cycle" in err


def test_245_the_cap_halt_is_recorded_by_n1(monkeypatch):
    monkeypatch.setattr(
        graph,
        "review_test_plan",
        lambda state: {"test_plan_status": "BLOCKED", "error_message": ""},
    )
    result = _node_fn("N1_review_test_plan")(
        {"issue_number": 4, "test_plan_revision_count": MAX_REVISION_CYCLES}
    )
    assert result["error_message"].startswith("Test plan revision budget spent")


def test_245_a_blocked_plan_under_the_cap_is_still_revised(monkeypatch):
    """The revision loop is unchanged: under the cap nothing is recorded."""
    monkeypatch.setattr(
        graph,
        "review_test_plan",
        lambda state: {"test_plan_status": "BLOCKED", "error_message": ""},
    )
    result = _node_fn("N1_review_test_plan")({"test_plan_revision_count": 1})
    assert result["error_message"] == ""
    assert graph.route_after_review({**result, "test_plan_revision_count": 1}) == (
        "N1_5_revise_test_plan"
    )


def test_245_n1_has_no_edge_to_end():
    compiled = graph.build_testing_workflow().compile().get_graph()
    targets = {e.target for e in compiled.edges if e.source == "N1_review_test_plan"}
    assert "__end__" not in targets
    assert "HALT" in targets


# ---------------------------------------------------------------- line 318


def test_318_an_escalation_with_no_reason_halts(capsys):
    """The carried route says escalate and nothing named the halt."""
    state = {"error_message": "", "scaffold_route": "escalate"}
    assert graph.route_after_validate(state) == "HALT"
    assert "ERROR [N2.5]" in capsys.readouterr().err


def test_318_the_escalation_is_recorded_by_n2_5(monkeypatch):
    monkeypatch.setattr(
        graph,
        "validate_tests_mechanical_node",
        lambda state: {"scaffold_route": "escalate", "error_message": ""},
    )
    result = _node_fn("N2_5_validate_tests")({"issue_number": 12})
    assert "the generated test suite cannot be used" in result["error_message"]
    assert "issue 12" in result["error_message"]


def test_318_an_unrecognised_carried_route_is_recorded(monkeypatch):
    monkeypatch.setattr(
        graph,
        "validate_tests_mechanical_node",
        lambda state: {"scaffold_route": "sideways", "error_message": ""},
    )
    result = _node_fn("N2_5_validate_tests")({"issue_number": 12})
    assert result["error_message"].startswith("Unrecognised route after N2.5")
    assert "sideways" in result["error_message"]


def test_318_n2_5_has_no_edge_to_end():
    compiled = graph.build_testing_workflow().compile().get_graph()
    targets = {e.target for e in compiled.edges if e.source == "N2_5_validate_tests"}
    assert "__end__" not in targets


# ---------------------------------------------------------------- line 355


def test_355_an_unrecognised_route_after_n3_halts(capsys):
    state = {"error_message": "", "next_node": "N9_somewhere"}
    assert graph.route_after_red(state) == "HALT"
    err = capsys.readouterr().err
    assert "ERROR [N3] Unrecognised route after N3" in err
    assert "N9_somewhere" in err


def test_355_the_unrecognised_route_is_recorded_by_n3(monkeypatch):
    monkeypatch.setattr(
        graph, "verify_red_phase", lambda state: {"next_node": "", "error_message": ""}
    )
    result = _node_fn("N3_verify_red")({"issue_number": 3})
    assert result["error_message"].startswith("Unrecognised route after N3")


def test_355_n3_has_no_edge_to_end():
    compiled = graph.build_testing_workflow().compile().get_graph()
    targets = {e.target for e in compiled.edges if e.source == "N3_verify_red"}
    assert "__end__" not in targets


# ------------------------------------------------- lines 438, 447, 451 (N4c)


def test_438_the_iteration_cap_on_the_augment_path_halts(capsys):
    state = {
        "error_message": "",
        "next_node": "N4c_augment_tests",
        "iteration_count": 4,
        "max_iterations": 4,
    }
    assert graph.route_after_green(state) == "HALT"
    assert "ERROR [N5] Green phase failed after 4 iteration(s)" in (
        capsys.readouterr().err
    )


def test_447_spent_augment_attempts_halt(capsys):
    state = {
        "error_message": "",
        "next_node": "N4c_augment_tests",
        "iteration_count": 1,
        "max_iterations": 5,
        "coverage_augment_attempts": graph.MAX_COVERAGE_AUGMENT_ATTEMPTS,
    }
    assert graph.route_after_green(state) == "HALT"
    assert "ERROR [N5] Coverage test additions spent" in capsys.readouterr().err


def test_451_the_cost_budget_on_the_augment_path_halts(monkeypatch, capsys):
    monkeypatch.setattr(graph, "get_cumulative_cost", lambda: 9.5)
    state = {
        "error_message": "",
        "next_node": "N4c_augment_tests",
        "iteration_count": 1,
        "max_iterations": 5,
        "cost_budget_usd": 2.0,
    }
    assert graph.route_after_green(state) == "HALT"
    err = capsys.readouterr().err
    assert "ERROR [N5] [BUDGET]" in err
    assert "$9.50" in err and "$2.00" in err


def test_451_under_budget_the_augment_path_still_runs(monkeypatch):
    monkeypatch.setattr(graph, "get_cumulative_cost", lambda: 1.0)
    state = {
        "error_message": "",
        "next_node": "N4c_augment_tests",
        "iteration_count": 1,
        "max_iterations": 5,
        "cost_budget_usd": 2.0,
    }
    assert graph.route_after_green(state) == "N4c_augment_tests"


# ------------------------------------------------- lines 471, 478, 488 (N4)


def test_471_the_iteration_cap_on_a_revision_halts(capsys):
    state = {
        "error_message": "",
        "next_node": "N4_implement_code",
        "iteration_count": DEFAULT_MAX_ITERATIONS,
        "max_iterations": DEFAULT_MAX_ITERATIONS,
    }
    assert graph.route_after_green(state) == "HALT"
    err = capsys.readouterr().err
    assert f"ERROR [N5] Green phase failed after {DEFAULT_MAX_ITERATIONS}" in err
    assert "not a pass" in err


def test_478_the_cost_budget_before_n4_halts(monkeypatch, capsys):
    monkeypatch.setattr(graph, "get_cumulative_cost", lambda: 3.0)
    state = {
        "error_message": "",
        "next_node": "N4_implement_code",
        "iteration_count": 1,
        "max_iterations": 5,
        "cost_budget_usd": 2.5,
    }
    assert graph.route_after_green(state) == "HALT"
    assert "ERROR [N5] [BUDGET]" in capsys.readouterr().err


def test_488_an_unrecognised_route_after_n5_halts(capsys):
    state = {"error_message": "", "next_node": "end"}
    assert graph.route_after_green(state) == "HALT"
    assert "ERROR [N5] Unrecognised route after N5" in capsys.readouterr().err


def test_488_n5_records_its_stop(monkeypatch):
    """The halt reaches HALT's alert because N5 records it."""
    monkeypatch.setattr(graph, "commit_checkpoint", lambda w, i, n: False)
    monkeypatch.setattr(
        graph,
        "verify_green_phase",
        lambda state: {
            "next_node": "N4_implement_code",
            "iteration_count": 5,
            "error_message": "",
        },
    )
    result = _node_fn("N5_verify_green")({"issue_number": 8, "max_iterations": 5})
    assert result["error_message"].startswith("Green phase failed after 5 iteration(s)")
    assert "issue 8" in result["error_message"]


def test_488_n5_has_no_edge_to_end():
    compiled = graph.build_testing_workflow().compile().get_graph()
    targets = {e.target for e in compiled.edges if e.source == "N5_verify_green"}
    assert "__end__" not in targets


# ---------------------------------------------------------------- line 513


def test_513_the_e2e_iteration_cap_halts(capsys):
    state = {
        "error_message": "",
        "next_node": "N4_implement_code",
        "iteration_count": 3,
        "max_iterations": 3,
    }
    assert graph.route_after_e2e(state) == "HALT"
    assert "ERROR [N6] E2E failed after 3 iteration(s)" in capsys.readouterr().err


def test_513_the_e2e_cap_is_recorded_by_n6(monkeypatch):
    monkeypatch.setattr(
        graph,
        "e2e_validation",
        lambda state: {"next_node": "N4_implement_code", "error_message": ""},
    )
    result = _node_fn("N6_e2e_validation")(
        {"issue_number": 6, "iteration_count": 2, "max_iterations": 2}
    )
    assert result["error_message"].startswith("E2E failed after 2 iteration(s)")


def test_513_n6_has_no_edge_to_end():
    compiled = graph.build_testing_workflow().compile().get_graph()
    targets = {e.target for e in compiled.edges if e.source == "N6_e2e_validation"}
    assert "__end__" not in targets


# ---------------------------------------------------------------- line 557


def test_557_an_adversarial_failure_halts():
    """Pinned: #3725 already routes N7.5's recorded reason to HALT."""
    assert graph.route_after_adversarial({"error_message": "review failed"}) == "HALT"
    assert graph.route_after_adversarial({}) == "N8_document"


# ------------------------------------------------- the wrapper itself


def test_the_stop_wrapper_carries_identity():
    def fake_node(state):
        return {}

    wrapped = graph._records_its_stop(fake_node, lambda state: {}, "N0")
    assert wrapped.__module__ == fake_node.__module__
    assert wrapped.__wrapped__ is fake_node
    assert wrapped.__name__ == "fake_node"


def test_the_stop_wrapper_leaves_a_recorded_reason_alone():
    def node(state):
        return {"error_message": "the node's own reason"}

    wrapped = graph._records_its_stop(
        node, lambda state: {"error_message": "not this"}, "N0"
    )
    assert wrapped({})["error_message"] == "the node's own reason"
