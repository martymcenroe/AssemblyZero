"""N6: File Issue node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Executes gh issue create - ONLY this node can file issues.
The agent never has access to gh; only Python can execute it.
"""

import datetime
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from agentos.core.config import REVIEWER_MODEL
from agentos.workflows.issue.audit import (
    batch_commit,
    get_repo_root,
    log_workflow_execution,
    move_idea_to_done,
    move_to_done,
    next_file_number,
    save_filed_metadata,
)
from agentos.workflows.issue.state import ErrorRecovery, IssueWorkflowState


def add_approval_footer(content: str, verdict_count: int) -> str:
    """Add Gemini approval footer to issue content.

    Args:
        content: The issue draft content.
        verdict_count: Number of review cycles.

    Returns:
        Content with approval footer appended.
    """
    review_date = datetime.datetime.now().strftime("%Y-%m-%d")
    footer = f"""

---

<sub>**Gemini Review:** APPROVED | **Model:** `{REVIEWER_MODEL}` | **Date:** {review_date} | **Reviews:** {verdict_count}</sub>
"""
    return content + footer


def open_vscode_folder(folder_path: str) -> tuple[bool, str]:
    """Open a folder in VS Code for review.

    Args:
        folder_path: Path to folder to open.

    Returns:
        Tuple of (success, error_message). error_message is empty string on success.
    """
    # Test mode: skip VS Code launch
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] TEST MODE: Skipping VS Code launch for folder {folder_path}")
        return True, ""

    try:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Launching VS Code: code {folder_path}")

        result = subprocess.run(
            ["code", folder_path],
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
        return False, "VS Code launch timed out"
    except FileNotFoundError:
        return False, "'code' command not found. Is VS Code installed and in PATH?"
    except Exception as e:
        return False, f"Unexpected error launching VS Code: {type(e).__name__}: {e}"


def get_repo_name(repo_root: str | None = None) -> str:
    """Get repository name in owner/repo format.

    Args:
        repo_root: Repository root path to run gh from. If None, uses cwd.

    Returns:
        Repository name like "martymcenroe/AgentOS".

    Raises:
        RuntimeError: If not in a git repository or no remote.
    """
    cmd = ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=repo_root,  # Run from target repo directory
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get repo name: {result.stderr}")
    return result.stdout.strip()


def parse_labels_from_draft(draft_content: str) -> list[str]:
    """Extract labels from **Labels:** line in draft.

    Args:
        draft_content: The draft markdown content.

    Returns:
        List of label names.

    Example:
        "**Labels:** `enhancement`, `langgraph`, `governance`"
        -> ["enhancement", "langgraph", "governance"]
    """
    # Look for **Labels:** line
    match = re.search(r"\*\*Labels:\*\*\s*(.+)$", draft_content, re.MULTILINE)
    if not match:
        return []

    labels_line = match.group(1)
    # Extract labels from backticks or comma-separated
    labels = re.findall(r"`([^`]+)`", labels_line)
    if not labels:
        # Try comma-separated without backticks
        labels = [l.strip() for l in labels_line.split(",") if l.strip()]

    return labels


def parse_title_from_draft(draft_content: str) -> str:
    """Extract title from first H1 heading in draft.

    Args:
        draft_content: The draft markdown content.

    Returns:
        Issue title, or "Untitled Issue" if not found.
    """
    match = re.search(r"^#\s+(.+)$", draft_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Untitled Issue"


def check_label_exists(label: str, repo: str) -> bool:
    """Check if a label exists in the repository.

    Args:
        label: Label name to check.
        repo: Repository in owner/repo format.

    Returns:
        True if label exists, False otherwise.
    """
    result = subprocess.run(
        ["gh", "label", "list", "--repo", repo, "--json", "name", "-q", f'.[].name'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return False

    existing_labels = result.stdout.strip().split("\n")
    return label in existing_labels


def create_label(label: str, repo: str) -> bool:
    """Create a label in the repository.

    Args:
        label: Label name to create.
        repo: Repository in owner/repo format.

    Returns:
        True if created successfully, False otherwise.
    """
    result = subprocess.run(
        ["gh", "label", "create", label, "--repo", repo],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0


def ensure_labels_exist(labels: list[str], repo: str) -> list[str]:
    """Ensure all labels exist, creating any that are missing.

    Args:
        labels: List of label names.
        repo: Repository in owner/repo format.

    Returns:
        List of labels that failed to create.
    """
    failed = []
    for label in labels:
        if not check_label_exists(label, repo):
            print(f"Creating label: {label}")
            if not create_label(label, repo):
                failed.append(label)
    return failed


def create_issue(
    title: str,
    body_file: str,
    labels: list[str],
    repo: str,
) -> tuple[bool, int, str, str]:
    """Create a GitHub issue using gh CLI.

    Args:
        title: Issue title.
        body_file: Path to file containing issue body.
        labels: List of labels to apply.
        repo: Repository in owner/repo format.

    Returns:
        Tuple of (success, issue_number, issue_url, error_message).
    """
    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body-file", body_file,
    ]

    # Add labels
    for label in labels:
        cmd.extend(["--label", label])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        return (False, 0, "", result.stderr)

    # Parse issue URL from output
    # Output is typically: https://github.com/owner/repo/issues/123
    url = result.stdout.strip()
    match = re.search(r"/issues/(\d+)", url)
    if match:
        issue_number = int(match.group(1))
    else:
        issue_number = 0

    return (True, issue_number, url, "")


def prompt_error_recovery() -> ErrorRecovery:
    """Prompt user for recovery action after GitHub error.

    Returns:
        User's choice.
    """
    import os

    print("\n" + "=" * 60)
    print("GitHub rejected the issue creation.")
    print("=" * 60)
    print("\n[R]etry - attempt gh issue create again")
    print("[E]dit - reopen VS Code and return to review")
    print("[A]bort - exit with error (files stay in active/)")
    print()

    # Test mode: abort on error
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        choice = "A"
        print(f"Your choice [R/E/A]: {choice} (TEST MODE - abort)")
        return ErrorRecovery.ABORT

    while True:
        choice = input("Your choice [R/E/A]: ").strip().upper()
        if choice == "R":
            return ErrorRecovery.RETRY
        elif choice == "E":
            return ErrorRecovery.EDIT
        elif choice == "A":
            return ErrorRecovery.ABORT
        else:
            print("Invalid choice. Please enter R, E, or A.")


def file_issue(state: IssueWorkflowState) -> dict[str, Any]:
    """N6: File the issue using gh CLI.

    Steps:
    1. Parse labels from draft
    2. For each label: check/create via gh
    3. Execute gh issue create
    4. If error: prompt R/E/A
    5. On success: save filed.json, move to done/, batch commit

    Args:
        state: Current workflow state.

    Returns:
        dict with: issue_number, issue_url, next_node (if error recovery)
    """
    audit_dir = Path(state.get("audit_dir", ""))
    draft_path = state.get("current_draft_path", "")
    current_draft = state.get("current_draft", "")
    slug = state.get("slug", "")
    brief_file = state.get("brief_file", "")
    iteration_count = state.get("iteration_count", 0)
    draft_count = state.get("draft_count", 0)
    verdict_count = state.get("verdict_count", 0)
    file_counter = state.get("file_counter", 0)

    if not draft_path or not Path(draft_path).exists():
        return {"error_message": "No draft file to file"}

    # Get repo name (use repo_root for cross-repo workflows)
    repo_root = state.get("repo_root", "")
    try:
        repo = get_repo_name(repo_root if repo_root else None)
        # --------------------------------------------------------------------------
        # GUARD: Cross-repo verification - log which repo we're operating on (Issue #101)
        # --------------------------------------------------------------------------
        print(f"    [GUARD] Operating on repo: {repo}")
        # --------------------------------------------------------------------------
    except RuntimeError as e:
        return {"error_message": str(e)}

    # Parse labels and title from draft
    labels = parse_labels_from_draft(current_draft)
    title = parse_title_from_draft(current_draft)

    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] Filing issue to GitHub...")
    print(f">>> Title: {title}")
    print(f">>> Labels: {', '.join(labels) if labels else 'none'}")
    print(f">>> Repo: {repo}")

    # Ensure labels exist
    if labels:
        failed_labels = ensure_labels_exist(labels, repo)
        if failed_labels:
            print(f"Warning: Failed to create labels: {failed_labels}")

    # Add Gemini approval footer to draft before filing
    draft_with_footer = add_approval_footer(current_draft, verdict_count)

    # Update the draft file with footer (so audit trail has final version)
    Path(draft_path).write_text(draft_with_footer, encoding='utf-8')

    # Attempt to create issue (with retry loop)
    max_retries = 3
    for attempt in range(max_retries):
        success, issue_number, issue_url, error_msg = create_issue(
            title, draft_path, labels, repo
        )

        if success:
            print(f"\n>>> Issue created: {issue_url}")

            # --------------------------------------------------------------------------
            # GUARD: Output verification - verify issue was filed correctly (Issue #101)
            # --------------------------------------------------------------------------
            if issue_number == 0:
                print("    [GUARD] WARNING: Issue created but number not parsed from URL")

            if not issue_url or not issue_url.startswith("https://"):
                print(f"    [GUARD] WARNING: Issue URL looks invalid: {issue_url}")
            # --------------------------------------------------------------------------

            # Save filed.json
            file_counter = next_file_number(audit_dir)
            save_filed_metadata(
                audit_dir,
                file_counter,
                issue_number,
                issue_url,
                title,
                brief_file,
                iteration_count,
                draft_count,
                verdict_count,
            )

            # Move to done/ (use repo_root for cross-repo workflows)
            repo_root_path = Path(repo_root) if repo_root else None
            done_dir = move_to_done(audit_dir, issue_number, slug, repo_root_path)
            print(f">>> Audit trail moved to: {done_dir}")

            # Move source idea to done/ if workflow was started from --select
            source_idea = state.get("source_idea", "")
            if source_idea:
                try:
                    idea_done_path = move_idea_to_done(source_idea, issue_number, repo_root_path)
                    print(f">>> Idea moved to: {idea_done_path}")
                except FileNotFoundError:
                    print(f"Warning: Source idea not found: {source_idea}")
                except Exception as e:
                    print(f"Warning: Failed to move idea: {e}")

            # Batch commit (use repo_root for cross-repo workflows)
            try:
                batch_commit(done_dir, issue_number, repo_root_path)
                print(f">>> Committed audit trail for #{issue_number}")
            except subprocess.CalledProcessError as e:
                print(f"Warning: Failed to commit audit trail: {e}")

            # Auto mode: open done/ folder for review (since we skipped VS Code during workflow)
            if os.environ.get("AGENTOS_AUTO_MODE") == "1":
                print(f"\n>>> Opening audit trail for review...")
                success, error = open_vscode_folder(str(done_dir))
                if not success:
                    print(f"Warning: Failed to open VS Code: {error}")

            # Log workflow completion to audit trail
            repo_root_path = Path(repo_root) if repo_root else get_repo_root()
            log_workflow_execution(
                target_repo=repo_root_path,
                slug=slug,
                workflow_type="issue",
                event="complete",
                details={
                    "issue_number": issue_number,
                    "issue_url": issue_url,
                    "verdict_count": verdict_count,
                    "draft_count": draft_count,
                },
            )

            return {
                "issue_number": issue_number,
                "issue_url": issue_url,
                "error_message": "",
            }

        # Error occurred
        print(f"\n>>> Error: {error_msg}")

        if attempt < max_retries - 1:
            recovery = prompt_error_recovery()

            if recovery == ErrorRecovery.RETRY:
                print(">>> Retrying...")
                continue
            elif recovery == ErrorRecovery.EDIT:
                return {
                    "next_node": "N5_human_edit_verdict",
                    "error_message": "",
                }
            else:  # ABORT
                return {
                    "error_message": f"ABORTED: {error_msg}",
                }

    # All retries exhausted
    return {
        "error_message": f"Failed after {max_retries} attempts: {error_msg}",
    }
