"""StateGraph definition for LLD Governance workflow.

Issue #86: LLD Creation & Governance Review Workflow
LLD: docs/LLDs/active/LLD-086-lld-governance-workflow.md

Defines the compiled graph with:
- N0-N4 nodes
- Conditional edges for routing after human edit and review
- Checkpoint support via SqliteSaver
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from agentos.workflows.lld.nodes import (
    design,
    fetch_issue,
    finalize,
    human_edit,
    review,
)
from agentos.workflows.lld.state import LLDWorkflowState


def route_after_fetch(
    state: LLDWorkflowState,
) -> Literal["N1_design", "end"]:
    """Route after N0 (fetch_issue).

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    if error:
        return "end"
    return "N1_design"


def route_after_design(
    state: LLDWorkflowState,
) -> Literal["N2_human_edit", "end"]:
    """Route after N1 (design).

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    design_status = state.get("design_status", "")

    if error or design_status == "FAILED":
        return "end"
    return "N2_human_edit"


def route_after_human_edit(
    state: LLDWorkflowState,
) -> Literal["N3_review", "N1_design", "end"]:
    """Route after N2 (human_edit).

    Routes based on state["next_node"]:
    - "N3_review" -> Proceed to Gemini review
    - "N1_design" -> Loop back for revision
    - "END" -> End workflow

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    next_node = state.get("next_node", "")
    error = state.get("error_message", "")

    if error and "MANUAL" in error:
        return "end"

    if next_node == "N3_review":
        return "N3_review"
    elif next_node == "N1_design":
        return "N1_design"
    else:
        return "end"


def route_after_review(
    state: LLDWorkflowState,
) -> Literal["N4_finalize", "N2_human_edit", "end"]:
    """Route after N3 (review).

    Routes based on state["next_node"] set by review node:
    - "N4_finalize" -> Approved, proceed to finalize
    - "N2_human_edit" -> Rejected, loop back for revision
    - "END" -> Max iterations reached

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    next_node = state.get("next_node", "")
    error = state.get("error_message", "")

    if error:
        return "end"

    if next_node == "N4_finalize":
        return "N4_finalize"
    elif next_node == "N2_human_edit":
        return "N2_human_edit"
    else:
        return "end"


def build_lld_workflow() -> StateGraph:
    """Build the LLD governance workflow StateGraph.

    Returns:
        StateGraph ready for compilation.

    Graph structure:
        N0_fetch_issue -> N1_design -> N2_human_edit -> N3_review
                              ^              |              |
                              |              |              v
                              +--------------+         N4_finalize -> END
                              |                             |
                              +-----------------------------+
                                    (revision loop)
    """
    # Create graph with state type
    workflow = StateGraph(LLDWorkflowState)

    # Add nodes
    workflow.add_node("N0_fetch_issue", fetch_issue)
    workflow.add_node("N1_design", design)
    workflow.add_node("N2_human_edit", human_edit)
    workflow.add_node("N3_review", review)
    workflow.add_node("N4_finalize", finalize)

    # Set entry point
    workflow.set_entry_point("N0_fetch_issue")

    # Add edges: N0 -> N1 (with error check)
    workflow.add_conditional_edges(
        "N0_fetch_issue",
        route_after_fetch,
        {
            "N1_design": "N1_design",
            "end": END,
        },
    )

    # N1 -> N2 (with error check)
    workflow.add_conditional_edges(
        "N1_design",
        route_after_design,
        {
            "N2_human_edit": "N2_human_edit",
            "end": END,
        },
    )

    # N2 -> N3 or N1 (conditional based on user choice)
    workflow.add_conditional_edges(
        "N2_human_edit",
        route_after_human_edit,
        {
            "N3_review": "N3_review",
            "N1_design": "N1_design",
            "end": END,
        },
    )

    # N3 -> N4 or N2 (conditional based on verdict)
    workflow.add_conditional_edges(
        "N3_review",
        route_after_review,
        {
            "N4_finalize": "N4_finalize",
            "N2_human_edit": "N2_human_edit",
            "end": END,
        },
    )

    # N4 -> END
    workflow.add_edge("N4_finalize", END)

    return workflow
