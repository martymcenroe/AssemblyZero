"""The requirements graph sends every error and every exhausted loop to HALT (#3864).

Before this change an N0b error ran N0c's model calls first, a Ponder error and
a non-BLOCKED N1.5 error went on as passes, an unknown gate decision ended the
run as a manual exit, the review cap finalized a still-BLOCKED draft, the
open-questions cap handed unanswered questions to the verdict gate, and a
finalize error ended at END. None of them reached HALT, so none alerted.
"""

import pytest

from assemblyzero.workflows.requirements.graph import (
    create_requirements_graph,
    route_after_analyze_codebase,
    route_after_ponder,
    route_after_validate_mechanical,
)


def test_n0b_errors_halt_before_n0c_runs():
    assert route_after_analyze_codebase({"error_message": "cannot cut the arc worktree"}) == "HALT"
    assert route_after_analyze_codebase({"error_message": ""}) == "N0c_analyze_requirements"


def test_ponder_errors_halt():
    assert route_after_ponder({"error_message": "could not write the fixed draft"}) == "HALT"
    assert route_after_ponder({"error_message": ""}) == "N1_5_validate_mechanical"


def test_a_mechanical_error_that_is_not_a_failed_validation_halts():
    """It used to go on to N1b as if validation had passed."""
    assert route_after_validate_mechanical({"lld_status": "PENDING", "error_message": "boom"}) == "HALT"


def test_a_blocked_validation_still_loops_back_with_its_message():
    """The regression guard: BLOCKED carries its own error_message into the retry,
    and that must still redraft, not halt, while iterations remain."""
    state = {
        "lld_status": "BLOCKED",
        "error_message": "MECHANICAL VALIDATION FAILED:\n- missing section",
        "iteration_count": 1,
        "max_iterations": 3,
        "validation_errors": [],
    }
    assert route_after_validate_mechanical(state) == "N1_generate_draft"


def test_a_clean_mechanical_pass_proceeds():
    assert route_after_validate_mechanical({"lld_status": "PENDING", "error_message": ""}) == "N1b_validate_test_plan"


@pytest.mark.parametrize("node", [
    "N0b_analyze_codebase",
    "N_ponder_stibbons",
    "N2_human_gate_draft",
    "N4_human_gate_verdict",
    "N5_finalize",
])
def test_every_changed_node_can_reach_halt(node):
    """The compiled graph carries the HALT edge each router can now return."""
    graph = create_requirements_graph().compile().get_graph()
    successors = {edge.target for edge in graph.edges if edge.source == node}
    assert "HALT" in successors
