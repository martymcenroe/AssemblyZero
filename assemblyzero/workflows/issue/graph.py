"""StateGraph definition for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Defines the compiled graph with:
- N0-N6 nodes
- Conditional edges for routing after human gates
- Interrupt points at human nodes
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.issue.nodes import (
    draft,
    file_issue,
    human_edit_draft,
    human_edit_verdict,
    load_brief,
    review,
    sandbox,
)
from assemblyzero.workflows.issue.state import IssueWorkflowState


def route_after_draft_edit(
    state: IssueWorkflowState,
) -> Literal["N4_review", "N2_draft", "end"]:
    """Conditional routing after N3 (human edit draft).

    Routes based on state["next_node"]:
    - "N4_review" -> Proceed to Gemini review
    - "N2_draft" -> Loop back for revision
    - "MANUAL_EXIT" -> End workflow

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    next_node = state.get("next_node", "")
    error = state.get("error_message", "")

    if error and "MANUAL" in error:
        return "end"

    if next_node == "N4_review":
        return "N4_review"
    elif next_node == "N2_draft":
        return "N2_draft"
    else:
        return "end"


def route_after_verdict_edit(
    state: IssueWorkflowState,
) -> Literal["N6_file", "N2_draft", "end"]:
    """Conditional routing after N5 (human edit verdict).

    Routes based on state["next_node"]:
    - "N6_file" -> Proceed to file issue
    - "N2_draft" -> Loop back for revision
    - "MANUAL_EXIT" -> End workflow

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    next_node = state.get("next_node", "")
    error = state.get("error_message", "")

    if error and "MANUAL" in error:
        return "end"

    if next_node == "N6_file":
        return "N6_file"
    elif next_node == "N2_draft":
        return "N2_draft"
    elif next_node == "N5_human_edit_verdict":
        # Error recovery: return to N5
        return "end"  # Will be handled by CLI
    else:
        return "end"


def route_after_file(
    state: IssueWorkflowState,
) -> Literal["N5_human_edit_verdict", "end"]:
    """Conditional routing after N6 (file issue).

    Routes based on error recovery:
    - If next_node is N5, return for editing
    - Otherwise end

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    next_node = state.get("next_node", "")

    if next_node == "N5_human_edit_verdict":
        return "N5_human_edit_verdict"
    else:
        return "end"


def check_error(state: IssueWorkflowState) -> Literal["continue", "end"]:
    """Check if workflow should continue or end due to error.

    Args:
        state: Current workflow state.

    Returns:
        "continue" or "end".
    """
    error = state.get("error_message", "")
    if error and not error.startswith("SLUG_COLLISION:"):
        return "end"
    return "continue"


def build_issue_workflow() -> StateGraph:
    """Build the issue creation workflow StateGraph.

    Returns:
        Compiled StateGraph ready for execution.

    Graph structure:
        N0_load_brief -> N1_sandbox -> N2_draft -> N3_human_edit_draft
                                          ^              |
                                          |              v
                                          +---- N4_review -> N5_human_edit_verdict
                                          |                        |
                                          +------------------------+
                                                                   |
                                                                   v
                                                             N6_file -> END
    """
    # Create graph with state type
    workflow = StateGraph(IssueWorkflowState)

    # Add nodes
    workflow.add_node("N0_load_brief", load_brief)
    workflow.add_node("N1_sandbox", sandbox)
    workflow.add_node("N2_draft", draft)
    workflow.add_node("N3_human_edit_draft", human_edit_draft)
    workflow.add_node("N4_review", review)
    workflow.add_node("N5_human_edit_verdict", human_edit_verdict)
    workflow.add_node("N6_file", file_issue)

    # Set entry point
    workflow.set_entry_point("N0_load_brief")

    # Add edges: N0 -> N1 (with error check)
    workflow.add_conditional_edges(
        "N0_load_brief",
        check_error,
        {
            "continue": "N1_sandbox",
            "end": END,
        },
    )

    # N1 -> N2 (with error check)
    workflow.add_conditional_edges(
        "N1_sandbox",
        check_error,
        {
            "continue": "N2_draft",
            "end": END,
        },
    )

    # N2 -> N3 (with error check)
    workflow.add_conditional_edges(
        "N2_draft",
        check_error,
        {
            "continue": "N3_human_edit_draft",
            "end": END,
        },
    )

    # N3 -> N4 or N2 (conditional based on user choice)
    workflow.add_conditional_edges(
        "N3_human_edit_draft",
        route_after_draft_edit,
        {
            "N4_review": "N4_review",
            "N2_draft": "N2_draft",
            "end": END,
        },
    )

    # N4 -> N5 (with error check)
    workflow.add_conditional_edges(
        "N4_review",
        check_error,
        {
            "continue": "N5_human_edit_verdict",
            "end": END,
        },
    )

    # N5 -> N6 or N2 (conditional based on user choice)
    workflow.add_conditional_edges(
        "N5_human_edit_verdict",
        route_after_verdict_edit,
        {
            "N6_file": "N6_file",
            "N2_draft": "N2_draft",
            "end": END,
        },
    )

    # N6 -> END or N5 (error recovery)
    workflow.add_conditional_edges(
        "N6_file",
        route_after_file,
        {
            "N5_human_edit_verdict": "N5_human_edit_verdict",
            "end": END,
        },
    )

    return workflow


def compile_issue_workflow():
    """Compile the issue workflow with checkpointer.

    Returns:
        Compiled graph with SQLite checkpointer.
    """
    from langgraph.checkpoint.sqlite import SqliteSaver

    workflow = build_issue_workflow()

    # Use SQLite for persistence
    # Checkpoints are keyed by thread_id (brief filename slug)
    memory = SqliteSaver.from_conn_string(":memory:")

    return workflow.compile(checkpointer=memory)
