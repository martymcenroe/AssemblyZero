"""Parameterized StateGraph for Requirements Workflow.

Issue #101: Unified Requirements Workflow

Creates a LangGraph StateGraph that connects:
- N0: load_input (brief or issue loading)
- N1: generate_draft (pluggable drafter)
- N2: human_gate_draft (human checkpoint)
- N3: review (pluggable reviewer)
- N4: human_gate_verdict (human checkpoint)
- N5: finalize (issue filing or LLD saving)

Graph structure:
    START -> N0 -> N1 -> N2 -> N3 -> N4 -> N5 -> END
                    ^          |         |
                    |          v         |
                    +-----<----+---------+

Routing is controlled by:
- error_message: Non-empty routes to END
- config_gates_*: Whether human gates are enabled
- next_node: Set by human gate nodes for routing decisions
- lld_status: Used for auto-routing when gates disabled
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agentos.workflows.requirements.nodes import (
    finalize,
    generate_draft,
    human_gate_draft,
    human_gate_verdict,
    load_input,
    review,
)
from agentos.workflows.requirements.state import RequirementsWorkflowState


# =============================================================================
# Node Name Constants
# =============================================================================

N0_LOAD_INPUT = "N0_load_input"
N1_GENERATE_DRAFT = "N1_generate_draft"
N2_HUMAN_GATE_DRAFT = "N2_human_gate_draft"
N3_REVIEW = "N3_review"
N4_HUMAN_GATE_VERDICT = "N4_human_gate_verdict"
N5_FINALIZE = "N5_finalize"


# =============================================================================
# Routing Functions
# =============================================================================


def route_after_load_input(
    state: RequirementsWorkflowState,
) -> Literal["N1_generate_draft", "END"]:
    """Route after load_input node.

    Routes to:
    - N1_generate_draft: Success
    - END: Error loading input

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "END"
    return "N1_generate_draft"


def route_after_generate_draft(
    state: RequirementsWorkflowState,
) -> Literal["N2_human_gate_draft", "N3_review", "END"]:
    """Route after generate_draft node.

    Routes to:
    - N2_human_gate_draft: Gate enabled
    - N3_review: Gate disabled
    - END: Error generating draft

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "END"

    if state.get("config_gates_draft", True):
        return "N2_human_gate_draft"
    else:
        return "N3_review"


def route_from_human_gate_draft(
    state: RequirementsWorkflowState,
) -> Literal["N3_review", "N1_generate_draft", "END"]:
    """Route from human_gate_draft node.

    Routes based on next_node set by the gate:
    - N3_review: Send to review
    - N1_generate_draft: Revise draft
    - END: Manual handling

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    next_node = state.get("next_node", "")

    if next_node == "N3_review":
        return "N3_review"
    elif next_node == "N1_generate_draft":
        return "N1_generate_draft"
    else:
        return "END"


def route_after_review(
    state: RequirementsWorkflowState,
) -> Literal["N4_human_gate_verdict", "N5_finalize", "N1_generate_draft", "END"]:
    """Route after review node.

    Routes to:
    - N4_human_gate_verdict: Gate enabled
    - N5_finalize: Gate disabled and approved
    - N1_generate_draft: Gate disabled and blocked (if iterations remain)
    - END: Error in review or max iterations reached

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "END"

    if state.get("config_gates_verdict", True):
        return "N4_human_gate_verdict"
    else:
        # Auto-route based on verdict
        lld_status = state.get("lld_status", "PENDING")
        if lld_status == "APPROVED":
            return "N5_finalize"
        else:
            # Check max iterations before looping back
            iteration_count = state.get("iteration_count", 0)
            max_iterations = state.get("max_iterations", 20)
            if iteration_count >= max_iterations:
                # Max iterations reached - finalize with current status
                return "N5_finalize"
            return "N1_generate_draft"


def route_from_human_gate_verdict(
    state: RequirementsWorkflowState,
) -> Literal["N5_finalize", "N1_generate_draft", "END"]:
    """Route from human_gate_verdict node.

    Routes based on next_node set by the gate:
    - N5_finalize: Approve and finalize
    - N1_generate_draft: Revise draft
    - END: Manual handling

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    next_node = state.get("next_node", "")

    if next_node == "N5_finalize":
        return "N5_finalize"
    elif next_node == "N1_generate_draft":
        return "N1_generate_draft"
    else:
        return "END"


def route_after_finalize(
    state: RequirementsWorkflowState,
) -> Literal["END"]:
    """Route after finalize node.

    Always routes to END (workflow complete).

    Args:
        state: Current workflow state.

    Returns:
        END.
    """
    return "END"


# =============================================================================
# Graph Creation
# =============================================================================


def create_requirements_graph() -> StateGraph:
    """Create the requirements workflow graph.

    Graph structure:
        START -> N0 -> N1 -> N2 -> N3 -> N4 -> N5 -> END
                        ^          |         |
                        |          v         |
                        +-----<----+---------+

    Returns:
        Uncompiled StateGraph.
    """
    # Create graph with state schema
    graph = StateGraph(RequirementsWorkflowState)

    # Add nodes
    graph.add_node(N0_LOAD_INPUT, load_input)
    graph.add_node(N1_GENERATE_DRAFT, generate_draft)
    graph.add_node(N2_HUMAN_GATE_DRAFT, human_gate_draft)
    graph.add_node(N3_REVIEW, review)
    graph.add_node(N4_HUMAN_GATE_VERDICT, human_gate_verdict)
    graph.add_node(N5_FINALIZE, finalize)

    # Add edges
    # START -> N0
    graph.add_edge(START, N0_LOAD_INPUT)

    # N0 -> N1 or END (on error)
    graph.add_conditional_edges(
        N0_LOAD_INPUT,
        route_after_load_input,
        {
            "N1_generate_draft": N1_GENERATE_DRAFT,
            "END": END,
        },
    )

    # N1 -> N2 or N3 or END (based on gates and error)
    graph.add_conditional_edges(
        N1_GENERATE_DRAFT,
        route_after_generate_draft,
        {
            "N2_human_gate_draft": N2_HUMAN_GATE_DRAFT,
            "N3_review": N3_REVIEW,
            "END": END,
        },
    )

    # N2 -> N3 or N1 or END (based on human decision)
    graph.add_conditional_edges(
        N2_HUMAN_GATE_DRAFT,
        route_from_human_gate_draft,
        {
            "N3_review": N3_REVIEW,
            "N1_generate_draft": N1_GENERATE_DRAFT,
            "END": END,
        },
    )

    # N3 -> N4 or N5 or N1 or END (based on gates and verdict)
    graph.add_conditional_edges(
        N3_REVIEW,
        route_after_review,
        {
            "N4_human_gate_verdict": N4_HUMAN_GATE_VERDICT,
            "N5_finalize": N5_FINALIZE,
            "N1_generate_draft": N1_GENERATE_DRAFT,
            "END": END,
        },
    )

    # N4 -> N5 or N1 or END (based on human decision)
    graph.add_conditional_edges(
        N4_HUMAN_GATE_VERDICT,
        route_from_human_gate_verdict,
        {
            "N5_finalize": N5_FINALIZE,
            "N1_generate_draft": N1_GENERATE_DRAFT,
            "END": END,
        },
    )

    # N5 -> END
    graph.add_edge(N5_FINALIZE, END)

    return graph
