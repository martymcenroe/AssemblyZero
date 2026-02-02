"""N5: Finalize node for Requirements Workflow.

Issue #101: Unified Requirements Workflow

Handles finalization for both workflow types:
- Issue workflow: File GitHub issue using gh CLI
- LLD workflow: Save LLD to docs/lld/active/ and update tracking
"""

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentos.workflows.requirements.audit import (
    next_file_number,
    save_audit_file,
    save_final_lld,
    update_lld_status,
)
from agentos.workflows.requirements.state import RequirementsWorkflowState


# Timeout for gh CLI commands
GH_CLI_TIMEOUT_SECONDS = 60


def finalize(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N5: Finalize workflow based on type.

    For issue workflow:
    - Parse title and body from draft
    - File GitHub issue using gh CLI
    - Return issue URL

    For LLD workflow:
    - Save LLD to target_repo/docs/lld/active/
    - Update lld-status.json tracking
    - Return final LLD path

    Args:
        state: Current workflow state.

    Returns:
        State updates with output path/URL.
    """
    workflow_type = state.get("workflow_type", "lld")

    if workflow_type == "issue":
        return _finalize_issue(state)
    else:
        return _finalize_lld(state)


def _finalize_issue(state: RequirementsWorkflowState) -> dict[str, Any]:
    """Finalize issue workflow by filing GitHub issue.

    Args:
        state: Current workflow state.

    Returns:
        State updates with issue_url, filed_issue_number.
    """
    target_repo = Path(state.get("target_repo", ""))
    current_draft = state.get("current_draft", "")
    audit_dir = Path(state.get("audit_dir", ""))

    # Parse title and body from draft
    title, body = _parse_issue_content(current_draft)

    if not title:
        return {"error_message": "Could not parse issue title from draft"}

    # File issue using gh CLI
    try:
        result = subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body],
            capture_output=True,
            text=True,
            timeout=GH_CLI_TIMEOUT_SECONDS,
            cwd=str(target_repo),
        )

        if result.returncode != 0:
            return {"error_message": f"Failed to create issue: {result.stderr.strip()}"}

        issue_url = result.stdout.strip()

        # Extract issue number from URL
        # Format: https://github.com/owner/repo/issues/123
        issue_number = 0
        if "/issues/" in issue_url:
            try:
                issue_number = int(issue_url.split("/issues/")[-1])
            except ValueError:
                pass

    except subprocess.TimeoutExpired:
        return {"error_message": "Timeout creating GitHub issue"}
    except FileNotFoundError:
        return {"error_message": "gh CLI not found. Install GitHub CLI."}

    # Save final state to audit
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        final_content = f"# Issue Filed\n\nURL: {issue_url}\n\n---\n\n{current_draft}"
        save_audit_file(audit_dir, file_num, "final.md", final_content)

    return {
        "issue_url": issue_url,
        "filed_issue_number": issue_number,
        "error_message": "",
    }


def _finalize_lld(state: RequirementsWorkflowState) -> dict[str, Any]:
    """Finalize LLD workflow by saving LLD and updating tracking.

    Args:
        state: Current workflow state.

    Returns:
        State updates with final_lld_path.
    """
    target_repo = Path(state.get("target_repo", ""))
    issue_number = state.get("issue_number", 0)
    current_draft = state.get("current_draft", "")
    lld_status = state.get("lld_status", "APPROVED")
    verdict_count = state.get("verdict_count", 0)
    current_verdict = state.get("current_verdict", "")
    audit_dir = Path(state.get("audit_dir", ""))

    if not issue_number:
        return {"error_message": "No issue number for LLD finalization"}

    # Update Final Status in LLD content to match actual verdict
    # The drafter writes "PENDING" during drafting, but we know the final status now
    final_draft = current_draft
    if lld_status == "APPROVED":
        # Replace any PENDING status with APPROVED
        final_draft = re.sub(
            r"\*\*Final Status:\*\*\s*PENDING[^\n]*",
            "**Final Status:** APPROVED",
            final_draft,
        )

    # Save LLD to target_repo/docs/lld/active/
    lld_path = save_final_lld(
        issue_number=issue_number,
        lld_content=final_draft,
        target_repo=target_repo,
    )

    # Update lld-status.json tracking
    review_info = {
        "has_gemini_review": verdict_count > 0,
        "final_verdict": lld_status,
        "last_review_date": datetime.now(timezone.utc).isoformat(),
        "review_count": verdict_count,
    }
    update_lld_status(
        issue_number=issue_number,
        lld_path=str(lld_path),
        review_info=review_info,
        target_repo=target_repo,
    )

    # Save final state to audit
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        final_content = (
            f"# LLD Finalized\n\n"
            f"Path: {lld_path}\n"
            f"Status: {lld_status}\n"
            f"Reviews: {verdict_count}\n\n"
            f"---\n\n{final_draft}"
        )
        save_audit_file(audit_dir, file_num, "final.md", final_content)

    return {
        "final_lld_path": str(lld_path),
        "error_message": "",
    }


def _parse_issue_content(draft: str) -> tuple[str, str]:
    """Parse issue title and body from markdown draft.

    Expects draft in format:
    # Title Here

    Body content...

    Args:
        draft: Markdown draft content.

    Returns:
        Tuple of (title, body).
    """
    lines = draft.strip().split("\n")

    title = ""
    body_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            body_start = i + 1
            break

    # Skip blank lines after title
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1

    body = "\n".join(lines[body_start:]).strip()

    return title, body
