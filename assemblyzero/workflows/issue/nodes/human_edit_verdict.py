"""N5: Human Edit Verdict node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Opens VS Code with draft + verdict, waits for user to close, prompts A/R/M.
This is the second human gate - Gemini output can be sanitized before
it reaches Claude (on revision) or before filing.
"""

import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.issue.audit import next_file_number, save_audit_file
from assemblyzero.workflows.issue.state import HumanDecision, IssueWorkflowState


def is_verdict_clean(verdict_content: str) -> bool:
    """Check if Gemini verdict approves the issue.

    The verdict uses markdown checkboxes to indicate the decision:
    - [x] **APPROVED** - Issue is ready to file
    - [x] **REVISE** - Issue needs changes

    Args:
        verdict_content: The verdict text to check.

    Returns:
        True if verdict is clean (auto-file), False if needs revision.
    """
    # Check for explicit approval (checked APPROVED box)
    if "[x] **APPROVED**" not in verdict_content:
        return False

    # Check for NO revision request (checked REVISE box)
    if "[x] **REVISE**" in verdict_content:
        return False

    return True


def open_vscode_non_blocking(file1: str, file2: str) -> tuple[bool, str]:
    """Open VS Code with two files (no --wait, non-blocking).

    Args:
        file1: First file path (left pane - draft).
        file2: Second file path (right pane - verdict).

    Returns:
        Tuple of (success, error_message). error_message is empty string on success.
    """
    import os
    import datetime

    # Test mode: skip VS Code launch
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] TEST MODE: Skipping VS Code launch for {file1} and {file2}")
        return True, ""

    try:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Launching VS Code (non-blocking): code {file1} {file2}")

        # For markdown files, also open preview side-by-side
        cmd = ["code", file1, file2]
        if file1.endswith(".md") or file2.endswith(".md"):
            cmd.extend(["--command", "markdown.showPreviewToSide"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,  # Required on Windows to execute .CMD files
            timeout=10,  # Short timeout - just launching, not waiting
        )
        if result.returncode != 0:
            error = f"VS Code exited with code {result.returncode}"
            if result.stderr:
                error += f"\nStderr: {result.stderr}"
            if result.stdout:
                error += f"\nStdout: {result.stdout}"
            return False, error
        return True, ""
    except subprocess.TimeoutExpired:
        # This shouldn't happen for non-blocking launch
        return False, "VS Code launch timed out"
    except FileNotFoundError:
        return False, "'code' command not found. Is VS Code installed and in PATH?"
    except Exception as e:
        return False, f"Unexpected error launching VS Code: {type(e).__name__}: {e}"


def open_vscode_split_and_wait(file1: str, file2: str) -> tuple[bool, str]:
    """Open VS Code with two files in split view, wait until closed.

    Args:
        file1: First file path (left pane - draft).
        file2: Second file path (right pane - verdict).

    Returns:
        Tuple of (success, error_message). error_message is empty string on success.
    """
    import os
    import datetime

    # Test mode: skip VS Code launch
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] TEST MODE: Skipping VS Code launch for {file1} and {file2}")
        return True, ""

    try:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        # Open first file, then second with --wait
        # VS Code will show them in tabs; user can split manually
        print(f"[{timestamp}] Launching VS Code: code --wait {file1} {file2}")

        # For markdown files, also open preview side-by-side
        cmd = ["code", "--wait", file1, file2]
        if file1.endswith(".md") or file2.endswith(".md"):
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


def prompt_user_decision_verdict() -> tuple[HumanDecision, str]:
    """Prompt user for decision after reviewing verdict.

    Returns:
        Tuple of (decision, feedback).
        Feedback is only populated if decision is WRITE_FEEDBACK.
    """
    import os

    print("\n" + "=" * 60)
    print("Verdict review complete.")
    print("=" * 60)
    print("\n[A]pprove and file the issue")
    print("[R]evise - re-read verdict from disk, send to Claude")
    print("[W]rite feedback - re-read verdict + add comments, send to Claude")
    print("[M]anual - exit for manual handling")
    print()

    # Test mode: auto-respond
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        # Check if we should force a revision (for testing revision flow)
        if os.environ.get("AGENTOS_TEST_REVISION") == "1":
            # Only revise once, then approve
            os.environ["AGENTOS_TEST_REVISION"] = "0"
            choice = "R"
            print(f"Your choice [A/R/W/M]: {choice} (TEST MODE - forcing revision to test Gemini feedback flow)")
            return (HumanDecision.REVISE, "")
        else:
            choice = "A"
            print(f"Your choice [A/R/W/M]: {choice} (TEST MODE - auto-approve)")
            return (HumanDecision.APPROVE, "")

    while True:
        choice = input("Your choice [A/R/W/M]: ").strip().upper()
        if choice == "A":
            return (HumanDecision.APPROVE, "")
        elif choice == "R":
            # Re-read verdict from disk (user may have edited), no additional comments
            return (HumanDecision.REVISE, "")
        elif choice == "W":
            # Re-read verdict + prompt for additional feedback
            print("\nEnter additional feedback for Claude (end with empty line):")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            feedback = "\n".join(lines)
            return (HumanDecision.WRITE_FEEDBACK, feedback)
        elif choice == "M":
            return (HumanDecision.MANUAL, "")
        else:
            print("Invalid choice. Please enter A, R, W, or M.")


def human_edit_verdict(state: IssueWorkflowState) -> dict[str, Any]:
    """N5: Automated verdict routing with VSCode preview.

    Auto-routing logic:
    1. Parse verdict: if PASSED + no suggestions → auto-file (N6)
    2. If verdict has feedback → auto-revise (N2)
    3. Only prompt human if Claude explicitly asks for orchestrator clarification

    Steps:
    1. Read verdict
    2. Check if clean (PASSED + no suggestions)
    3. Open VS Code non-blocking for inspection
    4. Auto-route: clean → N6_file, not clean → N2_draft

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

    import os

    # Display iteration info
    print(f"\n>>> Iteration {iteration_count} | Draft #{draft_count} | Verdict #{verdict_count}")

    # Read files
    draft_content = Path(draft_path).read_text(encoding="utf-8")
    verdict_content = Path(verdict_path).read_text(encoding="utf-8")

    # Check if verdict is perfectly clean
    clean = is_verdict_clean(verdict_content)

    # Auto mode: skip VS Code preview (will open done/ folder at end of workflow)
    if os.environ.get("AGENTOS_AUTO_MODE") != "1":
        # Interactive mode: open VS Code non-blocking for inspection
        print(f">>> Opening verdict in VS Code (non-blocking):")
        print(f"    {draft_path}")
        print(f"    {verdict_path}")
        open_vscode_non_blocking(draft_path, verdict_path)

    if clean:
        # Perfectly clean - auto-file
        print(f"\n{'=' * 60}")
        print("VERDICT PASSED with no suggestions")
        print(f"{'=' * 60}")
        print(">>> Auto-filing issue to GitHub (N6)...")
        return {
            "current_draft": draft_content,
            "current_verdict": verdict_content,
            "next_node": "N6_file",
            "error_message": "",
        }
    else:
        # Has feedback - auto-revise
        print(f"\n{'=' * 60}")
        print("WARNING: Verdict has feedback (suggestions/architecture)")
        print(f"{'=' * 60}")
        print(">>> Auto-sending to Claude for revision (N2)...")
        return {
            "current_draft": draft_content,
            "current_verdict": verdict_content,
            "file_counter": file_counter,
            "user_feedback": "",
            "next_node": "N2_draft",
            "error_message": "",
        }
