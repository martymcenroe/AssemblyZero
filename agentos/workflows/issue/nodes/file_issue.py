"""N6: File Issue node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Executes gh issue create - ONLY this node can file issues.
The agent never has access to gh; only Python can execute it.
"""

import re
import subprocess
from pathlib import Path
from typing import Any

from agentos.workflows.issue.audit import (
    batch_commit,
    get_repo_root,
    move_to_done,
    next_file_number,
    save_filed_metadata,
)
from agentos.workflows.issue.state import ErrorRecovery, IssueWorkflowState


def get_repo_name() -> str:
    """Get repository name in owner/repo format.

    Returns:
        Repository name like "martymcenroe/AgentOS".

    Raises:
        RuntimeError: If not in a git repository or no remote.
    """
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        capture_output=True,
        text=True,
        timeout=10,
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
    print("\n" + "=" * 60)
    print("GitHub rejected the issue creation.")
    print("=" * 60)
    print("\n[R]etry - attempt gh issue create again")
    print("[E]dit - reopen VS Code and return to review")
    print("[A]bort - exit with error (files stay in active/)")
    print()

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

    # Get repo name
    try:
        repo = get_repo_name()
    except RuntimeError as e:
        return {"error_message": str(e)}

    # Parse labels and title from draft
    labels = parse_labels_from_draft(current_draft)
    title = parse_title_from_draft(current_draft)

    print(f"\n>>> Filing issue: {title}")
    print(f">>> Labels: {', '.join(labels) if labels else 'none'}")
    print(f">>> Repo: {repo}")

    # Ensure labels exist
    if labels:
        failed_labels = ensure_labels_exist(labels, repo)
        if failed_labels:
            print(f"Warning: Failed to create labels: {failed_labels}")

    # Attempt to create issue (with retry loop)
    max_retries = 3
    for attempt in range(max_retries):
        success, issue_number, issue_url, error_msg = create_issue(
            title, draft_path, labels, repo
        )

        if success:
            print(f"\n>>> Issue created: {issue_url}")

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

            # Move to done/
            done_dir = move_to_done(audit_dir, issue_number, slug)
            print(f">>> Audit trail moved to: {done_dir}")

            # Batch commit
            try:
                batch_commit(done_dir, issue_number)
                print(f">>> Committed audit trail for #{issue_number}")
            except subprocess.CalledProcessError as e:
                print(f"Warning: Failed to commit audit trail: {e}")

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
