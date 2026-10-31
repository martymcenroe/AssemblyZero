"""The requirements graph under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (lines at 79e18ad1). Seven of
the nine rows were already routed to HALT by #3864 and two were compliant;
these tests pin them by line. What #3585 adds is the last router that read no
``error_message``: the two human gates routed on ``next_node`` alone, so a gate
that stopped with an error and named a successor would have gone on to it.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.requirements import graph as g

ERROR = {"error_message": "[N?] something failed"}


def test_182_a_drafter_error_halts():
    assert g.route_after_generate_draft({**ERROR, "workflow_type": "lld"}) == g.HALT


def test_230_the_mechanical_cap_halts():
    state = {"lld_status": "BLOCKED", "iteration_count": 3, "max_iterations": 3}
    assert g.route_after_validate_mechanical(state) == g.HALT


def test_235_a_mechanical_node_error_that_is_not_a_failed_validation_halts():
    assert g.route_after_validate_mechanical({**ERROR, "lld_status": "PENDING"}) == g.HALT


def test_235_kept_a_blocked_validation_loops_back_with_its_message():
    state = {**ERROR, "lld_status": "BLOCKED", "iteration_count": 1, "max_iterations": 3}
    assert g.route_after_validate_mechanical(state) == g.N1_GENERATE_DRAFT


def test_308_a_ponder_error_halts():
    assert g.route_after_ponder(ERROR) == g.HALT


@pytest.mark.parametrize("decision", ["", "N9_nowhere"])
def test_334_a_draft_gate_decision_it_never_makes_halts(decision):
    assert g.route_from_human_gate_draft({"next_node": decision}) == g.HALT


def test_380_the_open_questions_cap_halts():
    state = {"open_questions_status": "UNANSWERED", "verdict_count": 3, "max_iterations": 3}
    assert g.route_after_review(state) == g.HALT


def test_414_the_blocked_revise_cap_halts():
    state = {
        "config_gates_verdict": False, "lld_status": "BLOCKED",
        "verdict_count": 3, "max_iterations": 3,
    }
    assert g.route_after_review(state) == g.HALT


def test_505_a_finalize_error_halts():
    assert g.route_after_finalize(ERROR) == g.HALT


def test_578_an_n0b_error_halts_before_n0c():
    assert g.route_after_analyze_codebase(ERROR) == g.HALT


@pytest.mark.parametrize("next_node", ["N3_review", "N1_generate_draft", "END"])
def test_a_draft_gate_that_stops_with_an_error_halts_whatever_it_names(next_node):
    assert g.route_from_human_gate_draft({**ERROR, "next_node": next_node}) == g.HALT


@pytest.mark.parametrize("next_node", ["N5_finalize", "N1_generate_draft", "END"])
def test_a_verdict_gate_that_stops_with_an_error_halts_whatever_it_names(next_node):
    assert g.route_from_human_gate_verdict({**ERROR, "next_node": next_node}) == g.HALT


def test_kept_a_manual_exit_with_no_error_still_ends():
    assert g.route_from_human_gate_draft({"next_node": "END", "error_message": ""}) == "END"
    assert g.route_from_human_gate_verdict({"next_node": "END", "error_message": ""}) == "END"


#: Every router, and a state that would carry it on if the error were ignored.
ROUTERS = [
    (g.route_after_load_input, {"workflow_type": "lld"}),
    (g.route_after_analyze_codebase, {}),
    (g.route_after_analyze_requirements, {}),
    (g.route_after_generate_draft, {"workflow_type": "lld"}),
    (g.route_after_ponder, {}),
    (g.route_after_validate_mechanical, {"lld_status": "PENDING"}),
    (g.route_after_validate_test_plan, {"test_plan_validation_result": {"passed": True}}),
    (g.route_from_human_gate_draft, {"next_node": "N3_review"}),
    (g.route_after_review, {"lld_status": "APPROVED", "config_gates_verdict": False}),
    (g.route_from_human_gate_verdict, {"next_node": "N5_finalize"}),
    (g.route_after_finalize, {}),
]


@pytest.mark.parametrize("router,state", ROUTERS, ids=lambda x: getattr(x, "__name__", ""))
def test_no_router_lets_an_error_go_on(router, state):
    assert router({**state, **ERROR}) == g.HALT


def test_every_node_that_can_fail_has_halt_as_a_successor():
    compiled = g.create_requirements_graph().compile().get_graph()
    nodes = {edge.source for edge in compiled.edges} - {"__start__", g.HALT}
    for node in nodes:
        successors = {edge.target for edge in compiled.edges if edge.source == node}
        assert g.HALT in successors, f"{node} has no HALT edge: {sorted(successors)}"
