"""N5: Human Edit Verdict node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Opens VS Code with draft + verdict, waits for user to close, prompts A/R/M.
This is the second human gate - Gemini output can be sanitized before
it reaches Claude (on revision) or before filing.
"""

import subprocess
from pathlib import Path
from typing import Any

from agentos.workflows.issue.audit import next_file_number, save_audit_file
from agentos.workflows.issue.state import HumanDecision, IssueWorkflowState


def open_vscode_split_and_wait(file1: str, file2: str) -> bool:
    """Open VS Code with two files in split view, wait until closed.

    Args:
        file1: First file path (left pane - draft).
        file2: Second file path (right pane - verdict).

    Returns:
        True if VS Code exited successfully, False otherwise.
    """
    try:
        # Open first file, then second with --wait
        # VS Code will show them in tabs; user can split manually
        result = subprocess.run(
            ["code", "--wait", file1, file2],
            timeout=3600,  # 1 hour max
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def prompt_user_decision_verdict() -> tuple[HumanDecision, str]:
    """Prompt user for decision after reviewing verdict.

    Returns:
        Tuple of (decision, feedback).
        Feedback is only populated if decision is REVISE.
    """
    print("\n" + "=" * 60)
    print("Verdict review complete.")
    print("=" * 60)
    print("\n[A]pprove and file the issue")
    print("[R]evise - send back to Claude with feedback")
    print("[M]anual - exit for manual handling")
    print()

    while True:
        choice = input("Your choice [A/R/M]: ").strip().upper()
        if choice == "A":
            return (HumanDecision.APPROVE, "")
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
            print("Invalid choice. Please enter A, R, or M.")


def human_edit_verdict(state: IssueWorkflowState) -> dict[str, Any]:
    """N5: Human gate after Gemini verdict.

    Steps:
    1. Open VS Code with draft + verdict (split view)
    2. Wait for user to close editor
    3. Read (potentially sanitized) verdict
    4. Display iteration info
    5. Prompt: [A]pprove / [R]evise / [M]anual
    6. If R: save feedback, route to N2
    7. If A: route to N6
    8. If M: exit

    Args:
        state: Current workflow state.

    Returns:
        dict with: current_draft, current_verdict, next_node,
                   user_feedback (if revising), file_counter
    """
    audit_dir = Path(state.get("audit_dir", ""))
    draft_path = state.get("current_draft_path", "")
    verdict_path = state.get("current_verdict_path", "")
    iteration_count = state.get("iteration_count", 0)
    draft_count = state.get("draft_count", 0)
    verdict_count = state.get("verdict_count", 0)
    file_counter = state.get("file_counter", 0)

    if not draft_path or not Path(draft_path).exists():
        return {"error_message": "No draft file to review"}

    if not verdict_path or not Path(verdict_path).exists():
        return {"error_message": "No verdict file to review"}

    # Display iteration info
    print(f"\n>>> Iteration {iteration_count} | Draft #{draft_count} | Verdict #{verdict_count}")
    print(f">>> Opening: {draft_path}")
    print(f">>>          {verdict_path}")

    # Open VS Code with both files and wait
    success = open_vscode_split_and_wait(draft_path, verdict_path)
    if not success:
        print("Warning: VS Code may not have closed cleanly.")

    # Read potentially edited files
    draft_content = Path(draft_path).read_text(encoding="utf-8")
    verdict_content = Path(verdict_path).read_text(encoding="utf-8")

    # Prompt user
    decision, feedback = prompt_user_decision_verdict()

    if decision == HumanDecision.MANUAL:
        return {
            "current_draft": draft_content,
            "current_verdict": verdict_content,
            "next_node": "MANUAL_EXIT",
            "error_message": "User chose manual handling",
        }

    if decision == HumanDecision.REVISE:
        # Save feedback to audit trail
        file_counter = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_counter, "feedback.txt", feedback)

        return {
            "current_draft": draft_content,
            "current_verdict": verdict_content,
            "file_counter": file_counter,
            "user_feedback": feedback,
            "next_node": "N2_draft",
            "error_message": "",
        }

    # APPROVE - proceed to file issue
    return {
        "current_draft": draft_content,
        "current_verdict": verdict_content,
        "next_node": "N6_file",
        "error_message": "",
    }
