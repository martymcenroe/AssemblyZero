"""N2/N4: Human gate nodes for Requirements Workflow.

Issue #101: Unified Requirements Workflow

Provides human checkpoints:
- human_gate_draft: After draft generation (S/R/M choices)
- human_gate_verdict: After Gemini review (A/R/W/M choices)

When gates are disabled or auto_mode is enabled, gates are skipped.
"""

from pathlib import Path
from typing import Any

from agentos.workflows.requirements.state import RequirementsWorkflowState, HumanDecision


def human_gate_draft(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N2: Human checkpoint after draft generation.

    Routes to:
    - N3_review: Send draft to reviewer (auto_mode or gate disabled)
    - N1_generate_draft: Revise with feedback (if verdict shows BLOCKED)
    - END: Manual handling

    Args:
        state: Current workflow state.

    Returns:
        State updates with next_node, iteration_count.
    """
    gates_draft = state.get("config_gates_draft", True)
    auto_mode = state.get("config_auto_mode", False)
    current_verdict = state.get("current_verdict", "")
    iteration_count = state.get("iteration_count", 0) + 1

    # If gate is disabled, skip to review
    if not gates_draft:
        return {
            "next_node": "N3_review",
            "iteration_count": iteration_count,
            "error_message": "",
        }

    # Auto mode: auto-route based on verdict content
    if auto_mode:
        # If there's a blocking verdict, auto-revise
        if current_verdict and "BLOCKED" in current_verdict.upper():
            return {
                "next_node": "N1_generate_draft",
                "iteration_count": iteration_count,
                "error_message": "",
            }

        # Otherwise proceed to review
        return {
            "next_node": "N3_review",
            "iteration_count": iteration_count,
            "error_message": "",
        }

    # Interactive mode would go here
    # For now, default to sending to review
    return {
        "next_node": "N3_review",
        "iteration_count": iteration_count,
        "error_message": "",
    }


def human_gate_verdict(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N4: Human checkpoint after Gemini review.

    Routes to:
    - N5_finalize: Approve verdict and finalize
    - N1_generate_draft: Revise with feedback
    - END: Manual handling

    Args:
        state: Current workflow state.

    Returns:
        State updates with next_node, iteration_count.
    """
    gates_verdict = state.get("config_gates_verdict", True)
    auto_mode = state.get("config_auto_mode", False)
    lld_status = state.get("lld_status", "PENDING")
    current_verdict = state.get("current_verdict", "")
    iteration_count = state.get("iteration_count", 0) + 1

    # If gate is disabled, auto-route based on verdict
    if not gates_verdict:
        if lld_status == "APPROVED" or "APPROVED" in current_verdict.upper():
            return {
                "next_node": "N5_finalize",
                "iteration_count": iteration_count,
                "error_message": "",
            }
        else:
            # Auto-revise if blocked
            return {
                "next_node": "N1_generate_draft",
                "iteration_count": iteration_count,
                "error_message": "",
            }

    # Auto mode: route based on lld_status
    if auto_mode:
        if lld_status == "APPROVED" or "APPROVED" in current_verdict.upper():
            return {
                "next_node": "N5_finalize",
                "iteration_count": iteration_count,
                "error_message": "",
            }
        else:
            # Auto-revise if blocked
            return {
                "next_node": "N1_generate_draft",
                "iteration_count": iteration_count,
                "error_message": "",
            }

    # Interactive mode: default to finalize if approved
    if lld_status == "APPROVED":
        return {
            "next_node": "N5_finalize",
            "iteration_count": iteration_count,
            "error_message": "",
        }

    # Default to revise for blocked verdicts
    return {
        "next_node": "N1_generate_draft",
        "iteration_count": iteration_count,
        "error_message": "",
    }
