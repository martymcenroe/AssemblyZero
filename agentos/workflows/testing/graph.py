"""StateGraph definition for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node

Defines the compiled graph with:
- N0-N8 nodes
- Conditional edges for routing
- Checkpoint support via SqliteSaver

Graph structure:
    N0_load_lld -> N1_review_test_plan -> N2_scaffold_tests -> N3_verify_red
           |              |                     |                   |
           v              v                     v                   v
         error         BLOCKED              scaffold_only      unexpected
           |              |                     |               passes
           v              v                     v                   |
          END     loop back to LLD             END               error
                  (outside workflow)                               |
                                                                   v
                                                                  END

    N3_verify_red -> N4_implement_code -> N5_verify_green -> N6_e2e_validation
           |                |                   |                   |
           v                v                   v                   v
        red OK          iteration           green OK              e2e OK
           |            loop back              |                    |
           v                |                  v                    v
          N4               N4                  N6                  N7

    N6_e2e_validation -> N7_finalize -> N8_document -> END
           |                  |               |
           v                  v               v
       skip_e2e           complete       skip_docs
           |                                  |
           v                                  v
          N7                                 END
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from agentos.workflows.testing.nodes import (
    document,
    e2e_validation,
    finalize,
    implement_code,
    load_lld,
    review_test_plan,
    scaffold_tests,
    verify_green_phase,
    verify_red_phase,
)
from agentos.workflows.testing.state import TestingWorkflowState


def route_after_load(
    state: TestingWorkflowState,
) -> Literal["N1_review_test_plan", "end"]:
    """Route after N0 (load_lld).

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    if error:
        return "end"
    return "N1_review_test_plan"


def route_after_review(
    state: TestingWorkflowState,
) -> Literal["N2_scaffold_tests", "end"]:
    """Route after N1 (review_test_plan).

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    test_plan_status = state.get("test_plan_status", "")

    if error:
        return "end"

    # BLOCKED means test plan needs revision - this requires returning
    # to the LLD workflow (outside scope of this workflow)
    if test_plan_status == "BLOCKED":
        return "end"

    return "N2_scaffold_tests"


def route_after_scaffold(
    state: TestingWorkflowState,
) -> Literal["N3_verify_red", "end"]:
    """Route after N2 (scaffold_tests).

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    if error:
        return "end"

    # scaffold_only mode - stop after scaffolding
    if state.get("scaffold_only"):
        return "end"

    return "N3_verify_red"


def route_after_red(
    state: TestingWorkflowState,
) -> Literal["N4_implement_code", "end"]:
    """Route after N3 (verify_red_phase).

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    next_node = state.get("next_node", "")

    if error:
        return "end"

    if next_node == "N4_implement_code":
        return "N4_implement_code"

    return "end"


def route_after_implement(
    state: TestingWorkflowState,
) -> Literal["N5_verify_green", "end"]:
    """Route after N4 (implement_code).

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    if error:
        return "end"
    return "N5_verify_green"


def route_after_green(
    state: TestingWorkflowState,
) -> Literal["N6_e2e_validation", "N4_implement_code", "end"]:
    """Route after N5 (verify_green_phase).

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    next_node = state.get("next_node", "")

    if error:
        return "end"

    # Check for iteration loop back to implement
    if next_node == "N4_implement_code":
        # Check max iterations
        iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 10)
        if iteration >= max_iterations:
            return "end"
        return "N4_implement_code"

    if next_node == "N6_e2e_validation":
        return "N6_e2e_validation"

    return "end"


def route_after_e2e(
    state: TestingWorkflowState,
) -> Literal["N7_finalize", "N4_implement_code", "end"]:
    """Route after N6 (e2e_validation).

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    next_node = state.get("next_node", "")

    if error:
        return "end"

    # E2E failure may loop back to implement
    if next_node == "N4_implement_code":
        iteration = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 10)
        if iteration >= max_iterations:
            return "end"
        return "N4_implement_code"

    return "N7_finalize"


def route_after_finalize(
    state: TestingWorkflowState,
) -> Literal["N8_document", "end"]:
    """Route after N7 (finalize).

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    if error:
        return "end"

    # Skip documentation if flag is set
    if state.get("skip_docs"):
        return "end"

    return "N8_document"


def build_testing_workflow() -> StateGraph:
    """Build the TDD testing workflow StateGraph.

    Returns:
        StateGraph ready for compilation.
    """
    # Create graph with state type
    workflow = StateGraph(TestingWorkflowState)

    # Add nodes
    workflow.add_node("N0_load_lld", load_lld)
    workflow.add_node("N1_review_test_plan", review_test_plan)
    workflow.add_node("N2_scaffold_tests", scaffold_tests)
    workflow.add_node("N3_verify_red", verify_red_phase)
    workflow.add_node("N4_implement_code", implement_code)
    workflow.add_node("N5_verify_green", verify_green_phase)
    workflow.add_node("N6_e2e_validation", e2e_validation)
    workflow.add_node("N7_finalize", finalize)
    workflow.add_node("N8_document", document)

    # Set entry point
    workflow.set_entry_point("N0_load_lld")

    # Add edges: N0 -> N1 (with error check)
    workflow.add_conditional_edges(
        "N0_load_lld",
        route_after_load,
        {
            "N1_review_test_plan": "N1_review_test_plan",
            "end": END,
        },
    )

    # N1 -> N2 (with error/blocked check)
    workflow.add_conditional_edges(
        "N1_review_test_plan",
        route_after_review,
        {
            "N2_scaffold_tests": "N2_scaffold_tests",
            "end": END,
        },
    )

    # N2 -> N3 (with scaffold_only check)
    workflow.add_conditional_edges(
        "N2_scaffold_tests",
        route_after_scaffold,
        {
            "N3_verify_red": "N3_verify_red",
            "end": END,
        },
    )

    # N3 -> N4 (with error check)
    workflow.add_conditional_edges(
        "N3_verify_red",
        route_after_red,
        {
            "N4_implement_code": "N4_implement_code",
            "end": END,
        },
    )

    # N4 -> N5 (with error check)
    workflow.add_conditional_edges(
        "N4_implement_code",
        route_after_implement,
        {
            "N5_verify_green": "N5_verify_green",
            "end": END,
        },
    )

    # N5 -> N6 or N4 (iteration loop)
    workflow.add_conditional_edges(
        "N5_verify_green",
        route_after_green,
        {
            "N6_e2e_validation": "N6_e2e_validation",
            "N4_implement_code": "N4_implement_code",
            "end": END,
        },
    )

    # N6 -> N7 or N4 (iteration loop)
    workflow.add_conditional_edges(
        "N6_e2e_validation",
        route_after_e2e,
        {
            "N7_finalize": "N7_finalize",
            "N4_implement_code": "N4_implement_code",
            "end": END,
        },
    )

    # N7 -> N8 (with skip_docs check)
    workflow.add_conditional_edges(
        "N7_finalize",
        route_after_finalize,
        {
            "N8_document": "N8_document",
            "end": END,
        },
    )

    # N8 -> END
    workflow.add_edge("N8_document", END)

    return workflow
