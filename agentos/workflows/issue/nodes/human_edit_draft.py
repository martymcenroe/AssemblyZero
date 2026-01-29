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


def open_vscode_and_wait(file_path: str) -> tuple[bool, str]:
    """Open VS Code with --wait flag and block until closed.

    Args:
        file_path: Path to file to open.

    Returns:
        Tuple of (success, error_message). error_message is empty string on success.
    """
    import os
    import datetime

    # Test mode: skip VS Code launch
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] TEST MODE: Skipping VS Code launch for {file_path}")
        return True, ""

    try:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Launching VS Code: code --wait {file_path}")

        # For markdown files, also open preview side-by-side
        cmd = ["code", "--wait", file_path]
        if file_path.endswith(".md"):
            cmd.extend(["--command", "markdown.showPreviewToSide"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,  # Required on Windows to execute .CMD files
            timeout=86400,  # 24 hours - this is a human review gate
        )
        end_timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{end_timestamp}] VS Code closed (returncode: {result.returncode})")
        if result.returncode != 0:
            error = f"VS Code exited with code {result.returncode}"
            if result.stderr:
                error += f"\nStderr: {result.stderr}"
            if result.stdout:
                error += f"\nStdout: {result.stdout}"
            return False, error
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "VS Code did not close within 24 hours (timeout)"
    except FileNotFoundError:
        return False, "'code' command not found. Is VS Code installed and in PATH?"
    except Exception as e:
        return False, f"Unexpected error launching VS Code: {type(e).__name__}: {e}"


def prompt_user_decision_draft() -> tuple[HumanDecision, str]:
    """Prompt user for decision after reviewing draft.

    Returns:
        Tuple of (decision, feedback).
        Feedback is only populated if decision is REVISE.
    """
    import os

    print("\n" + "=" * 60)
    print("Draft review complete.")
    print("=" * 60)
    print("\n[G]emini - send to Gemini for review")
    print("[R]evise - send back to Claude with feedback")
    print("[S]ave and exit - pause workflow for later")
    print()

    # Test mode: auto-respond
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        choice = "G"
        print(f"Your choice [G/R/S]: {choice} (TEST MODE - auto-send)")
        return (HumanDecision.SEND, "")

    while True:
        choice = input("Your choice [G/R/S]: ").strip().upper()
        if choice == "G":
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
        elif choice == "S":
            return (HumanDecision.MANUAL, "")
        else:
            print("Invalid choice. Please enter G, R, or S.")


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
    success, error = open_vscode_and_wait(draft_path)
    if not success:
        print(f"\nERROR: Failed to open VS Code")
        print(f"  {error}")
        print("\nYou can manually open the file:")
        print(f"  code {draft_path}")
        print("\nPress Enter when you've reviewed the draft...")
        input()

    # Read potentially edited draft
    draft_content = Path(draft_path).read_text(encoding="utf-8")

    # Prompt user
    decision, feedback = prompt_user_decision_draft()

    if decision == HumanDecision.MANUAL:
        # Raise KeyboardInterrupt to pause workflow WITHOUT completing this node.
        # This ensures the checkpoint is saved BEFORE this node, so resume
        # will re-run this node and show the prompt again.
        print("\n>>> Pausing workflow for manual handling...")
        raise KeyboardInterrupt("User chose manual handling")

    if decision == HumanDecision.REVISE:
        # Save feedback to audit trail
        file_counter = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_counter, "feedback.txt", feedback)

        print("\n>>> Sending feedback to Claude for revision (N2)...")
        return {
            "current_draft": draft_content,
            "iteration_count": iteration_count,
            "file_counter": file_counter,
            "user_feedback": feedback,
            "next_node": "N2_draft",
            "error_message": "",
        }

    # SEND - proceed to Gemini
    print("\n>>> Proceeding to Gemini review (N4)...")
    return {
        "current_draft": draft_content,
        "iteration_count": iteration_count,
        "next_node": "N4_review",
        "error_message": "",
    }
