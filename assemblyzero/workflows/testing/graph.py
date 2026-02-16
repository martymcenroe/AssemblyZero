"""StateGraph definition for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #335: Add mechanical test validation node (N2.5)
Issue #147: Add completeness gate node (N4b) between N4 and N5
Issue #292: Exit code routing — N3/N5 can route to N2 on syntax/collection errors

Defines the compiled graph with:
- N0-N8 nodes (plus N2.5 for test validation, N4b for completeness gate)
- Conditional edges for routing
- Checkpoint support via SqliteSaver

Graph structure:
    N0_load_lld -> N1_review_test_plan -> N2_scaffold_tests -> N2_5_validate_tests
           |              |                     |                      |
           v              v                     v                      v
         error         BLOCKED              scaffold_only         validation
           |              |                     |                   result
           v              v                     v                      |
          END     loop back to LLD             END                    / \\
                  (outside workflow)                                 /   \\
                                                                pass   fail
                                                                 |       |
                                                                 v       v
    N2_5 (pass) -> N3_verify_red -> N4_implement_code ------> N2 (retry)
           |                |                   |               or escalate
           v                v                   v               to N4
        red OK          iteration          N4b_completeness
           |            loop back              |
           v                |                 / \\
          N4               N4              PASS  BLOCK
                                            |      |
                                            v      v
                                           N5   N4 (iter<3)
                                                 or END (iter>=3)

    N5_verify_green -> N6_e2e_validation -> N7_finalize -> N8_document -> END
           |                  |                  |               |
           v                  v                  v               v
       iteration          skip_e2e           complete       skip_docs
       loop back              |                                  |
           |                  v                                  v
          N4                 N7                                 END
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.testing.nodes import (
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
from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
    route_after_completeness_gate,
)
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    validate_tests_mechanical_node,
    should_regenerate,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState


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
    auto_mode = state.get("auto_mode", False)

    if error and not auto_mode:
        return "end"

    # BLOCKED means test plan needs revision - this requires returning
    # to the LLD workflow (outside scope of this workflow)
    # In auto_mode, continue anyway (skip human gate)
    if test_plan_status == "BLOCKED":
        if auto_mode:
            print("    [AUTO] Continuing despite BLOCKED verdict - auto mode enabled")
            return "N2_scaffold_tests"
        return "end"

    return "N2_scaffold_tests"


def route_after_scaffold(
    state: TestingWorkflowState,
) -> Literal["N2_5_validate_tests", "end"]:
    """Route after N2 (scaffold_tests).

    Issue #335: Updated to route to validation node instead of verify_red.

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

    return "N2_5_validate_tests"


def route_after_validate(
    state: TestingWorkflowState,
) -> Literal["N3_verify_red", "N2_scaffold_tests", "N4_implement_code", "end"]:
    """Route after N2.5 (validate_tests_mechanical).

    Issue #335: Routes based on test validation results.

    Routes to:
    - N3_verify_red: Validation passed, continue normal flow
    - N2_scaffold_tests: Validation failed, attempts < 3, retry
    - N4_implement_code: Validation failed, attempts >= 3, escalate to Claude
    - END: Error

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    if error:
        return "end"

    # Use the should_regenerate function from validate_tests_mechanical
    decision = should_regenerate(state)

    if decision == "continue":
        return "N3_verify_red"
    elif decision == "regenerate":
        return "N2_scaffold_tests"
    elif decision == "escalate":
        # Escalate to Claude - skip verify_red and go to implement
        print("    [ESCALATE] Skipping verify_red, escalating to Claude implementation")
        return "N4_implement_code"

    return "end"


def route_after_red(
    state: TestingWorkflowState,
) -> Literal["N4_implement_code", "N2_scaffold_tests", "end"]:
    """Route after N3 (verify_red_phase).

    Issue #292: Added N2_scaffold_tests route for exit codes 4/5.

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

    # Issue #292: Exit code 4/5 routes back to scaffold
    if next_node == "N2_scaffold_tests":
        return "N2_scaffold_tests"

    return "end"


def route_after_implement(
    state: TestingWorkflowState,
) -> Literal["N4b_completeness_gate", "end"]:
    """Route after N4 (implement_code).

    Issue #147: Routes to N4b completeness gate instead of directly to N5.

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    if error:
        return "end"
    return "N4b_completeness_gate"


def route_after_green(
    state: TestingWorkflowState,
) -> Literal["N6_e2e_validation", "N7_finalize", "N4_implement_code", "N2_scaffold_tests", "end"]:
    """Route after N5 (verify_green_phase).

    Issue #292: Added N2_scaffold_tests route for exit codes 4/5.

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    next_node = state.get("next_node", "")

    if error:
        return "end"

    # Issue #292: Exit code 4/5 routes back to scaffold
    if next_node == "N2_scaffold_tests":
        return "N2_scaffold_tests"

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

    # Skip E2E - go directly to finalize
    if next_node == "N7_finalize":
        return "N7_finalize"

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

    Issue #147: Added N4b completeness gate between N4 and N5.

    Returns:
        StateGraph ready for compilation.
    """
    # Create graph with state type
    workflow = StateGraph(TestingWorkflowState)

    # Add nodes
    workflow.add_node("N0_load_lld", load_lld)
    workflow.add_node("N1_review_test_plan", review_test_plan)
    workflow.add_node("N2_scaffold_tests", scaffold_tests)
    workflow.add_node("N2_5_validate_tests", validate_tests_mechanical_node)  # Issue #335
    workflow.add_node("N3_verify_red", verify_red_phase)
    workflow.add_node("N4_implement_code", implement_code)
    workflow.add_node("N4b_completeness_gate", completeness_gate)  # Issue #147
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

    # N2 -> N2.5 (with scaffold_only check) - Issue #335
    workflow.add_conditional_edges(
        "N2_scaffold_tests",
        route_after_scaffold,
        {
            "N2_5_validate_tests": "N2_5_validate_tests",
            "end": END,
        },
    )

    # N2.5 -> N3 or N2 (retry) or N4 (escalate) - Issue #335
    workflow.add_conditional_edges(
        "N2_5_validate_tests",
        route_after_validate,
        {
            "N3_verify_red": "N3_verify_red",
            "N2_scaffold_tests": "N2_scaffold_tests",
            "N4_implement_code": "N4_implement_code",
            "end": END,
        },
    )

    # N3 -> N4 or N2 (exit code routing) - Issue #292
    workflow.add_conditional_edges(
        "N3_verify_red",
        route_after_red,
        {
            "N4_implement_code": "N4_implement_code",
            "N2_scaffold_tests": "N2_scaffold_tests",
            "end": END,
        },
    )

    # N4 -> N4b (with error check) - Issue #147
    workflow.add_conditional_edges(
        "N4_implement_code",
        route_after_implement,
        {
            "N4b_completeness_gate": "N4b_completeness_gate",
            "end": END,
        },
    )

    # N4b -> N5 or N4 (re-implement) or END (max iterations) - Issue #147
    workflow.add_conditional_edges(
        "N4b_completeness_gate",
        route_after_completeness_gate,
        {
            "N5_verify_green": "N5_verify_green",
            "N4_implement_code": "N4_implement_code",
            "end": END,
        },
    )

    # N5 -> N6 or N7 (skip E2E) or N4 (iteration loop) or N2 (exit code routing) - Issue #292
    workflow.add_conditional_edges(
        "N5_verify_green",
        route_after_green,
        {
            "N6_e2e_validation": "N6_e2e_validation",
            "N7_finalize": "N7_finalize",
            "N4_implement_code": "N4_implement_code",
            "N2_scaffold_tests": "N2_scaffold_tests",
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