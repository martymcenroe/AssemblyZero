"""N2/N4: Human gate nodes for Requirements Workflow.

Issue #101: Unified Requirements Workflow
Issue #160: Fix human gates to actually gate

Provides human checkpoints:
- human_gate_draft: After draft generation (S/R/M choices)
- human_gate_verdict: After Gemini review (A/R/W/M choices)

When gates are disabled or auto_mode is enabled, gates are skipped.
When gates are enabled and not in auto_mode, prompts user for input.

#3585 (ADR 0236): when N4 decides on its own it decides on ``lld_status``
alone. APPROVED finalizes, BLOCKED revises, and anything else halts; the word
APPROVED somewhere in the verdict text (as in "NOT APPROVED") used to
finalize. Its own revise loop stops at ``max_iterations`` reviews; it used to
run until GraphRecursionError. A human at the prompt still decides himself.
"""

import logging
import sys
from typing import Any

from assemblyzero.workflows.requirements.state import RequirementsWorkflowState, HumanDecision

logger = logging.getLogger(__name__)


def _loud(message: str) -> str:
    """One ERROR line on stderr and in the log (ADR 0236 property 1)."""
    logger.error("[N4] %s", message)
    print(f"ERROR [N4] {message}", file=sys.stderr, flush=True)
    return message


def _decide_verdict(
    state: RequirementsWorkflowState, lld_status: str, iteration_count: int, label: str
) -> dict[str, Any]:
    """N4's own decision, for a disabled gate or auto mode (#3585).

    Decides on ``lld_status`` alone, the status the review node set. A status
    it does not know, and a revise loop that has spent its reviews, set
    ``error_message``, which ``route_from_human_gate_verdict`` sends to HALT.
    """
    if lld_status == "APPROVED":
        print(f"    {label} APPROVED -> finalizing")
        return {"next_node": "N5_finalize", "iteration_count": iteration_count,
                "error_message": ""}
    if lld_status != "BLOCKED":
        return {"next_node": "HALT", "iteration_count": iteration_count,
                "error_message": _loud(
                    f"the verdict gate cannot decide on review status "
                    f"{lld_status!r}: only APPROVED finalizes and only BLOCKED "
                    f"revises"
                )}
    verdict_count = state.get("verdict_count", 0)
    max_iterations = state.get("max_iterations", 3)
    if verdict_count >= max_iterations:
        return {"next_node": "HALT", "iteration_count": iteration_count,
                "error_message": _loud(
                    f"the draft is still BLOCKED after {verdict_count} review(s), "
                    f"the cap of {max_iterations}, so the verdict gate stops "
                    f"revising"
                )}
    print(f"    {label} BLOCKED -> revising")
    return {"next_node": "N1_generate_draft", "iteration_count": iteration_count,
            "error_message": ""}


def _prompt_draft_gate() -> str:
    """Prompt user for draft gate decision.

    Returns:
        User's choice (S/R/M), uppercase.
    """
    valid_choices = {"S", "R", "M"}

    while True:
        print()
        print("    Draft Gate Options:")
        print("      [S] Send to Gemini review")
        print("      [R] Revise draft (return to drafter)")
        print("      [M] Manual handling (exit workflow)")
        print()
        choice = input("    Enter choice (S/R/M): ").strip().upper()

        if choice in valid_choices:
            return choice

        print(f"    Invalid choice '{choice}'. Please enter S, R, or M.")


def _prompt_verdict_gate(lld_status: str) -> str:
    """Prompt user for verdict gate decision.

    Args:
        lld_status: Current LLD status (APPROVED/BLOCKED).

    Returns:
        User's choice (A/R/W/M), uppercase.
    """
    valid_choices = {"A", "R", "W", "M"}

    while True:
        print()
        print(f"    Verdict Gate Options (current status: {lld_status}):")
        print("      [A] Approve and finalize")
        print("      [R] Revise draft (return to drafter)")
        print("      [W] Write feedback (add comments, then revise)")
        print("      [M] Manual handling (exit workflow)")
        print()
        choice = input("    Enter choice (A/R/W/M): ").strip().upper()

        if choice in valid_choices:
            return choice

        print(f"    Invalid choice '{choice}'. Please enter A, R, W, or M.")


def human_gate_draft(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N2: Human checkpoint after draft generation.

    Routes to:
    - N3_review: Send draft to reviewer (user chooses S, or auto_mode/disabled)
    - N1_generate_draft: Revise with feedback (user chooses R)
    - END: Manual handling (user chooses M)

    Args:
        state: Current workflow state.

    Returns:
        State updates with next_node, iteration_count.
    """
    gates_draft = state.get("config_gates_draft", True)
    auto_mode = state.get("config_auto_mode", False)
    current_verdict = state.get("current_verdict", "")
    iteration_count = state.get("iteration_count", 0) + 1

    print("\n[N2] Human gate (draft)...")

    # If gate is disabled, skip to review
    if not gates_draft:
        print("    Gate disabled -> proceeding to review")
        return {
            "next_node": "N3_review",
            "iteration_count": iteration_count,
            "error_message": "",
        }

    # Auto mode: auto-route based on verdict content
    if auto_mode:
        # If there's a blocking verdict, auto-revise
        if current_verdict and "BLOCKED" in current_verdict.upper():
            print("    [AUTO] BLOCKED verdict -> revising draft")
            return {
                "next_node": "N1_generate_draft",
                "iteration_count": iteration_count,
                "error_message": "",
            }

        # Otherwise proceed to review
        print("    [AUTO] Proceeding to review")
        return {
            "next_node": "N3_review",
            "iteration_count": iteration_count,
            "error_message": "",
        }

    # Interactive mode: prompt user for decision
    choice = _prompt_draft_gate()

    if choice == HumanDecision.SEND.value:  # "S"
        print("    User chose: Send to review")
        return {
            "next_node": "N3_review",
            "iteration_count": iteration_count,
            "error_message": "",
        }
    elif choice == HumanDecision.REVISE.value:  # "R"
        print("    User chose: Revise draft")
        return {
            "next_node": "N1_generate_draft",
            "iteration_count": iteration_count,
            "error_message": "",
        }
    else:  # "M" - Manual
        print("    User chose: Manual handling")
        return {
            "next_node": "END",
            "iteration_count": iteration_count,
            "error_message": "",
        }


def human_gate_verdict(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N4: Human checkpoint after Gemini review.

    Routes to:
    - N5_finalize: Approve verdict and finalize (user chooses A, or auto_mode/disabled with APPROVED)
    - N1_generate_draft: Revise with feedback (user chooses R/W, or auto_mode/disabled with BLOCKED)
    - END: Manual handling (user chooses M)

    Args:
        state: Current workflow state.

    Returns:
        State updates with next_node, iteration_count, user_feedback (if W chosen).
    """
    gates_verdict = state.get("config_gates_verdict", True)
    auto_mode = state.get("config_auto_mode", False)
    lld_status = state.get("lld_status", "PENDING")
    iteration_count = state.get("iteration_count", 0) + 1

    print(f"\n[N4] Human gate (verdict: {lld_status})...")

    # If gate is disabled, or in auto mode, the gate decides (#3585).
    if not gates_verdict:
        return _decide_verdict(state, lld_status, iteration_count, "Gate disabled,")
    if auto_mode:
        return _decide_verdict(state, lld_status, iteration_count, "[AUTO]")

    # Interactive mode: prompt user for decision
    choice = _prompt_verdict_gate(lld_status)

    if choice == HumanDecision.APPROVE.value:  # "A"
        print("    User chose: Approve and finalize")
        return {
            "next_node": "N5_finalize",
            "iteration_count": iteration_count,
            "error_message": "",
        }
    elif choice == HumanDecision.REVISE.value:  # "R"
        print("    User chose: Revise draft")
        return {
            "next_node": "N1_generate_draft",
            "iteration_count": iteration_count,
            "error_message": "",
        }
    elif choice == HumanDecision.WRITE_FEEDBACK.value:  # "W"
        print("    User chose: Write feedback")
        print()
        feedback = input("    Enter feedback for drafter: ").strip()
        print(f"    Feedback recorded: {feedback[:50]}..." if len(feedback) > 50 else f"    Feedback recorded: {feedback}")
        return {
            "next_node": "N1_generate_draft",
            "iteration_count": iteration_count,
            "user_feedback": feedback,
            "error_message": "",
        }
    else:  # "M" - Manual
        print("    User chose: Manual handling")
        return {
            "next_node": "END",
            "iteration_count": iteration_count,
            "error_message": "",
        }
