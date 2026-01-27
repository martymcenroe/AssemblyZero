"""N3: Human Edit Draft node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Opens VS Code with draft, waits for user to close, then prompts S/R/M.
This is the first human gate - no LLM output reaches Gemini without review.
"""

import subprocess
from pathlib import Path
from typing import Any

from agentos.workflows.issue.audit import next_file_number, save_audit_file
from agentos.workflows.issue.state import HumanDecision, IssueWorkflowState


def open_vscode_and_wait(file_path: str) -> bool:
    """Open VS Code with --wait flag and block until closed.

    Args:
        file_path: Path to file to open.

    Returns:
        True if VS Code exited successfully, False otherwise.
    """
    try:
        result = subprocess.run(
            ["code", "--wait", file_path],
            timeout=3600,  # 1 hour max
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def prompt_user_decision_draft() -> tuple[HumanDecision, str]:
    """Prompt user for decision after reviewing draft.

    Returns:
        Tuple of (decision, feedback).
        Feedback is only populated if decision is REVISE.
    """
    print("\n" + "=" * 60)
    print("Draft review complete.")
    print("=" * 60)
    print("\n[S]end to Gemini for review")
    print("[R]evise - send back to Claude with feedback")
    print("[M]anual - exit for manual handling")
    print()

    while True:
        choice = input("Your choice [S/R/M]: ").strip().upper()
        if choice == "S":
            return (HumanDecision.SEND, "")
        elif choice == "R":
            print("\nEnter feedback for Claude (end with empty line):")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            feedback = "\n".join(lines)
            return (HumanDecision.REVISE, feedback)
        elif choice == "M":
            return (HumanDecision.MANUAL, "")
        else:
            print("Invalid choice. Please enter S, R, or M.")


def human_edit_draft(state: IssueWorkflowState) -> dict[str, Any]:
    """N3: Human gate after Claude draft.

    Steps:
    1. Increment iteration_count
    2. Open VS Code with draft file (--wait flag)
    3. Wait for user to close editor
    4. Read (potentially edited) draft
    5. Display iteration info
    6. Prompt: [S]end to Gemini / [R]evise / [M]anual
    7. If R: save feedback, route to N2
    8. If S: route to N4
    9. If M: exit

    Args:
        state: Current workflow state.

    Returns:
        dict with: current_draft, next_node, user_feedback (if revising),
                   iteration_count, file_counter
    """
    audit_dir = Path(state.get("audit_dir", ""))
    draft_path = state.get("current_draft_path", "")
    iteration_count = state.get("iteration_count", 0)
    draft_count = state.get("draft_count", 0)
    file_counter = state.get("file_counter", 0)

    if not draft_path or not Path(draft_path).exists():
        return {"error_message": "No draft file to review"}

    # Increment iteration count
    iteration_count += 1

    # Display iteration info
    print(f"\n>>> Iteration {iteration_count} | Draft #{draft_count}")
    print(f">>> Opening: {draft_path}")

    # Open VS Code and wait
    success = open_vscode_and_wait(draft_path)
    if not success:
        print("Warning: VS Code may not have closed cleanly.")

    # Read potentially edited draft
    draft_content = Path(draft_path).read_text(encoding="utf-8")

    # Prompt user
    decision, feedback = prompt_user_decision_draft()

    if decision == HumanDecision.MANUAL:
        return {
            "current_draft": draft_content,
            "iteration_count": iteration_count,
            "next_node": "MANUAL_EXIT",
            "error_message": "User chose manual handling",
        }

    if decision == HumanDecision.REVISE:
        # Save feedback to audit trail
        file_counter = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_counter, "feedback.txt", feedback)

        return {
            "current_draft": draft_content,
            "iteration_count": iteration_count,
            "file_counter": file_counter,
            "user_feedback": feedback,
            "next_node": "N2_draft",
            "error_message": "",
        }

    # SEND - proceed to Gemini
    return {
        "current_draft": draft_content,
        "iteration_count": iteration_count,
        "next_node": "N4_review",
        "error_message": "",
    }
