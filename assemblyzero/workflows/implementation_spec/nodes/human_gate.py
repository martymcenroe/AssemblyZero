"""N4: Human Gate node for Implementation Spec Workflow.

Issue #304: Implementation Readiness Review Workflow (LLD → Implementation Spec)

Optional human review checkpoint after mechanical validation (N3) passes.
When enabled (human_gate_enabled=True), presents the spec draft to the user
and prompts for a decision:
- [S] Send to Gemini review (proceed to N5)
- [R] Revise spec (return to N2 with optional feedback)
- [M] Manual handling (exit workflow)

When disabled (default), the graph routing in route_after_validation() skips
this node entirely and proceeds directly to N5.

This node populates:
- next_node: Routing decision ("N5_review_spec", "N2_generate_spec", or "END")
- review_feedback: User feedback if revision requested
- error_message: "" on success, error text on failure
"""

import sys
from typing import Any

from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState


# =============================================================================
# Constants
# =============================================================================

# Preview truncation for spec draft display
MAX_PREVIEW_LINES = 80


# =============================================================================
# Internal Helpers
# =============================================================================


def _prompt_human_gate() -> str:
    """Prompt user for human gate decision.

    Presents three options and loops until a valid choice is entered.

    Returns:
        User's choice (S/R/M), uppercase.
    """
    valid_choices = {"S", "R", "M"}

    while True:
        print()
        print("    Human Gate Options:")
        print("      [S] Send to Gemini review")
        print("      [R] Revise spec (return to drafter)")
        print("      [M] Manual handling (exit workflow)")
        print()
        choice = input("    Enter choice (S/R/M): ").strip().upper()

        if choice in valid_choices:
            return choice

        print(f"    Invalid choice '{choice}'. Please enter S, R, or M.")


def _display_spec_preview(spec_draft: str) -> None:
    """Display a truncated preview of the spec draft for human review.

    Shows the first MAX_PREVIEW_LINES of the spec draft so the reviewer
    can make an informed decision without scrolling through the entire
    document.

    Args:
        spec_draft: Full Implementation Spec markdown content.
    """
    lines = spec_draft.splitlines()
    total_lines = len(lines)

    print()
    print("    " + "=" * 60)
    print("    IMPLEMENTATION SPEC DRAFT PREVIEW")
    print("    " + "=" * 60)

    preview_lines = lines[:MAX_PREVIEW_LINES]
    for line in preview_lines:
        print(f"    | {line}")

    if total_lines > MAX_PREVIEW_LINES:
        print(f"    | ... ({total_lines - MAX_PREVIEW_LINES} more lines)")

    print("    " + "=" * 60)
    print(f"    Total: {total_lines} lines")
    print()


# =============================================================================
# Main Node
# =============================================================================


def human_gate(state: ImplementationSpecState) -> dict[str, Any]:
    """N4: Optional human review checkpoint.

    Issue #304: Implementation Readiness Review Workflow

    Presents the generated Implementation Spec draft to a human reviewer
    for approval before sending to Gemini review (N5). This gate is only
    reached when human_gate_enabled=True and N3 validation passed.

    Three modes of operation:
    1. Gate disabled (human_gate_enabled=False): This node is never reached;
       graph routing skips directly to N5. If it is invoked anyway, the graph
       is misrouted and the node halts (#3585); it used to route to N5.
    2. Interactive mode: Displays spec preview and prompts for S/R/M decision.
       If R is chosen, optionally collects feedback for the drafter.

    Steps:
    1. Check if gate should be active (safety fallback if disabled)
    2. Display spec draft preview
    3. Prompt user for decision
    4. Return routing decision via next_node

    Args:
        state: Current workflow state. Requires:
            - spec_draft: Generated Implementation Spec markdown (from N2)
            - human_gate_enabled: Whether this gate should be active
            - review_iteration: Current iteration count

    Returns:
        Dict with state field updates:
        - next_node: "N5_review_spec", "N2_generate_spec", or "END"
        - review_feedback: User feedback text (if revision requested)
        - error_message: "" on success
    """
    print("\n[N4] Human gate (spec review)...")

    human_gate_enabled = state.get("human_gate_enabled", False)
    spec_draft = state.get("spec_draft", "")
    review_iteration = state.get("review_iteration", 0)
    issue_number = state.get("issue_number", 0)

    # --------------------------------------------------------------------------
    # GUARD: the gate is disabled but the node was invoked anyway. #3585:
    # route_after_validation sends here only when human_gate_enabled is True,
    # so this is a misrouted graph, and it halts. It used to proceed to N5 as
    # a "safety fallback", which hid the misrouting.
    # --------------------------------------------------------------------------
    if not human_gate_enabled:
        message = (
            f"[N4] human_gate for issue #{issue_number}: reached with "
            f"human_gate_enabled False; route_after_validation sends here only "
            f"when it is True, so the graph is misrouted"
        )
        print(f"ERROR {message}", file=sys.stderr, flush=True)
        return {
            "next_node": "",
            "error_message": message,
        }

    # --------------------------------------------------------------------------
    # GUARD: Must have a spec draft to review
    # --------------------------------------------------------------------------
    if not spec_draft:
        print("    [GUARD] No spec draft available for review")
        return {
            "next_node": "END",
            "error_message": "Human gate reached with no spec draft to review.",
        }

    # --------------------------------------------------------------------------
    # Display context and preview
    # --------------------------------------------------------------------------
    print(f"    Issue: #{issue_number}")
    print(f"    Iteration: {review_iteration}")
    print(f"    Spec length: {len(spec_draft)} chars, {len(spec_draft.splitlines())} lines")

    _display_spec_preview(spec_draft)

    # --------------------------------------------------------------------------
    # Interactive: prompt user for decision
    # --------------------------------------------------------------------------
    choice = _prompt_human_gate()

    if choice == "S":
        print("    User chose: Send to Gemini review")
        return {
            "next_node": "N5_review_spec",
            "error_message": "",
        }
    elif choice == "R":
        print("    User chose: Revise spec")
        print()
        feedback = input("    Enter feedback for drafter (or press Enter to skip): ").strip()

        if feedback:
            print(
                f"    Feedback recorded: {feedback[:80]}..."
                if len(feedback) > 80
                else f"    Feedback recorded: {feedback}"
            )
        else:
            feedback = "Human reviewer requested revision (no specific feedback provided)."
            print("    No specific feedback — generic revision request recorded.")

        return {
            "next_node": "N2_generate_spec",
            "review_feedback": feedback,
            "error_message": "",
        }
    else:  # "M" - Manual
        print("    User chose: Manual handling (exiting workflow)")
        return {
            "next_node": "END",
            "error_message": "",
        }