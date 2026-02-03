"""Finalize node for requirements workflow.

Updates GitHub issue with final draft, commits artifacts to git, and closes workflow.
For LLD workflows, saves LLD file with embedded review evidence.
"""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from agentos.workflows.requirements.audit import (
    embed_review_evidence,
    next_file_number,
    save_audit_file,
)
from ..git_operations import commit_and_push, GitOperationError

# Constants
GH_TIMEOUT_SECONDS = 30


def _finalize_issue(state: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize issue by updating with final draft.

    Args:
        state: Workflow state containing issue_number, current_draft, etc.

    Returns:
        Updated state with finalization status
    """
    issue_number = state.get("issue_number")
    target_repo = state.get("target_repo", ".")
    audit_dir = Path(state.get("audit_dir", "."))
    current_draft = state.get("current_draft", "")

    if not current_draft:
        error_msg = "No draft to finalize"
        state["error_message"] = error_msg
        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            save_audit_file(audit_dir, file_num, "error", error_msg)
        return state

    try:
        # Update issue comment with final draft using UTF-8 encoding
        result = subprocess.run(
            ["gh", "issue", "comment", str(issue_number), "--body", current_draft],
            capture_output=True,
            text=True,
            encoding="utf-8",  # Fix for Unicode handling on Windows
            cwd=target_repo,
            timeout=GH_TIMEOUT_SECONDS,
            check=False,
        )

        if result.returncode != 0:
            error_msg = f"Failed to post comment to issue #{issue_number}: {result.stderr}"
            state["error_message"] = error_msg
            if audit_dir.exists():
                file_num = next_file_number(audit_dir)
                save_audit_file(audit_dir, file_num, "error", error_msg)
            return state

        state["error_message"] = ""
        state["finalized"] = True

        # Save finalization status to audit
        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            audit_content = f"# Finalized Issue #{issue_number}\n\n"
            audit_content += f"**Comment URL:** {result.stdout.strip()}\n"
            save_audit_file(audit_dir, file_num, "finalize", audit_content)

    except subprocess.TimeoutExpired:
        error_msg = f"Timeout posting comment to issue #{issue_number}"
        state["error_message"] = error_msg
        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            save_audit_file(audit_dir, file_num, "error", error_msg)
    except Exception as e:
        error_msg = f"Unexpected error finalizing issue: {e}"
        state["error_message"] = error_msg
        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            save_audit_file(audit_dir, file_num, "error", error_msg)

    return state


def _commit_and_push_files(state: Dict[str, Any]) -> Dict[str, Any]:
    """Commit and push created files to git.

    Args:
        state: Current workflow state with created_files list

    Returns:
        Updated state with commit_sha if successful
    """
    created_files = state.get("created_files", [])
    if not created_files:
        return state

    workflow_type = state.get("workflow_type", "lld")
    target_repo = state.get("target_repo", ".")
    issue_number = state.get("issue_number")
    slug = state.get("slug")

    try:
        commit_sha = commit_and_push(
            created_files=created_files,
            workflow_type=workflow_type,
            target_repo=target_repo,
            issue_number=issue_number,
            slug=slug,
        )

        if commit_sha:
            state["commit_sha"] = commit_sha

    except GitOperationError as e:
        # Log error but don't fail the workflow - files are already saved
        state["commit_error"] = str(e)

    return state


def _save_lld_file(state: Dict[str, Any]) -> Dict[str, Any]:
    """Save LLD file with embedded review evidence.

    For workflow_type="lld", saves the draft to docs/lld/active/ with
    the actual Gemini verdict embedded.

    Args:
        state: Workflow state with current_draft, lld_status, etc.

    Returns:
        Updated state with created_files populated
    """
    workflow_type = state.get("workflow_type", "lld")
    if workflow_type != "lld":
        return state

    target_repo = Path(state.get("target_repo", "."))
    issue_number = state.get("issue_number")
    current_draft = state.get("current_draft", "")
    lld_status = state.get("lld_status", "BLOCKED")
    verdict_count = state.get("verdict_count", 0)
    audit_dir = Path(state.get("audit_dir", ""))

    if not current_draft:
        return state

    # Embed review evidence with ACTUAL verdict (not hardcoded APPROVED!)
    review_date = datetime.now().strftime("%Y-%m-%d")
    lld_content = embed_review_evidence(
        current_draft,
        verdict=lld_status,  # Use actual verdict from Gemini review
        review_date=review_date,
        review_count=verdict_count,
    )

    # Save to docs/lld/active/LLD-{issue_number}.md
    lld_dir = target_repo / "docs" / "lld" / "active"
    lld_dir.mkdir(parents=True, exist_ok=True)
    lld_path = lld_dir / f"LLD-{issue_number:03d}.md"
    lld_path.write_text(lld_content, encoding="utf-8")

    print(f"    Saved LLD to: {lld_path}")
    print(f"    Final Status: {lld_status}")

    # Add to created_files for commit
    created_files = list(state.get("created_files", []))
    created_files.append(str(lld_path))
    state["created_files"] = created_files
    state["final_lld_path"] = str(lld_path)

    # Save to audit trail
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "final", lld_content)

    return state


def finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    """Public interface for finalize node.

    Finalizes the issue (if applicable), saves LLD file (if LLD workflow),
    and commits artifacts to git.

    Args:
        state: Workflow state

    Returns:
        Updated state with finalization status
    """
    workflow_type = state.get("workflow_type", "lld")

    if workflow_type == "lld":
        # For LLD workflow: save LLD file with embedded review evidence
        state = _save_lld_file(state)
    else:
        # For issue workflow: post comment to GitHub issue
        state = _finalize_issue(state)

    # Then, commit and push artifacts to git
    state = _commit_and_push_files(state)

    return state
