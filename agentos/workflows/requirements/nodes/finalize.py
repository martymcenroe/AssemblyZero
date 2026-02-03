"""Finalize node for requirements workflow.

Updates GitHub issue with final draft, commits artifacts to git, and closes workflow.
For LLD workflows, saves LLD file with embedded review evidence.
"""

import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from agentos.workflows.requirements.audit import (
    embed_review_evidence,
    next_file_number,
    save_audit_file,
    update_lld_status,
)
from ..git_operations import commit_and_push, GitOperationError

# Constants
GH_TIMEOUT_SECONDS = 30


def _parse_issue_content(draft: str) -> tuple:
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


def _finalize_issue(state: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize issue workflow by filing GitHub issue.

    Args:
        state: Workflow state containing current_draft, target_repo, etc.

    Returns:
        Updated state with issue_url, filed_issue_number.
    """
    target_repo = Path(state.get("target_repo", "."))
    current_draft = state.get("current_draft", "")
    audit_dir = Path(state.get("audit_dir", "."))

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
            encoding="utf-8",  # Fix for Unicode handling on Windows
            timeout=GH_TIMEOUT_SECONDS,
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


def validate_lld_final(content: str) -> list[str]:
    """Final structural checks before LLD finalization.

    Issue #235: Mechanical validation gate to catch structural issues
    before saving the final LLD.

    Issue #245: Only checks the 'Open Questions' section for unchecked items,
    ignoring Definition of Done and other sections.

    Args:
        content: LLD content to validate.

    Returns:
        List of error messages. Empty list if validation passes.
    """
    errors = []

    if not content:
        return errors

    # Check for unresolved open questions ONLY in the Open Questions section
    # Pattern: from "### Open Questions" or "## Open Questions"
    # until the next "##" header or end of document
    pattern = r"(?:^##?#?\s*Open Questions\s*\n)(.*?)(?=^##|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if match:
        open_questions_section = match.group(1)
        if re.search(r"^- \[ \]", open_questions_section, re.MULTILINE):
            errors.append("Unresolved open questions remain")

    # Check for unresolved TODO in table cells
    if re.search(r"\|\s*TODO\s*\|", content):
        errors.append("Unresolved TODO in table cell")

    return errors


def _save_lld_file(state: Dict[str, Any]) -> Dict[str, Any]:
    """Save LLD file with embedded review evidence.

    For workflow_type="lld", saves the draft to docs/lld/active/ with
    the actual Gemini verdict embedded. Also updates lld-status.json tracking.

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

    # Validate issue_number
    if not issue_number:
        state["error_message"] = "No issue number for LLD finalization"
        return state

    if not current_draft:
        return state

    # Gate 2: Validate LLD structure before finalization (Issue #235)
    validation_errors = validate_lld_final(current_draft)
    if validation_errors:
        error_msg = "BLOCKED: " + "; ".join(validation_errors)
        print(f"    VALIDATION: {error_msg}")
        state["error_message"] = error_msg
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

    # Output verification guard
    if not lld_path.exists():
        state["error_message"] = f"LLD file not created at {lld_path}"
        return state

    print(f"    Saved LLD to: {lld_path}")
    print(f"    Final Status: {lld_status}")

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
    print(f"    Updated lld-status.json tracking")

    # Add to created_files for commit
    created_files = list(state.get("created_files", []))
    created_files.append(str(lld_path))

    # Add ALL lineage files to created_files (Issue #241)
    if audit_dir.exists():
        for lineage_file in audit_dir.glob("*"):
            if lineage_file.is_file():
                created_files.append(str(lineage_file))

    state["created_files"] = created_files
    state["final_lld_path"] = str(lld_path)

    # Save to audit trail
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "final.md", lld_content)

    return state


def _cleanup_source_idea(state: Dict[str, Any]) -> None:
    """Move source idea to ideas/done/ after successful issue creation.

    Issue #219: Ideas file not moved to done/ after issue creation.

    Args:
        state: Workflow state with source_idea, filed_issue_number, error_message.
    """
    source_idea = state.get("source_idea", "")
    if not source_idea:
        return

    source_path = Path(source_idea)
    if not source_path.exists():
        return

    # Only cleanup on success (no error and issue was filed)
    if state.get("error_message"):
        return

    # Get issue number from filed_issue_number
    issue_number = state.get("filed_issue_number", 0)
    if not issue_number:
        return

    # Ensure ideas/done/ exists
    done_dir = source_path.parent.parent / "done"
    done_dir.mkdir(exist_ok=True)

    # Move with issue number prefix
    new_name = f"{issue_number}-{source_path.name}"
    dest_path = done_dir / new_name

    shutil.move(str(source_path), str(dest_path))
    print(f"  Moved idea to: {dest_path}")


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
        # _finalize_issue returns only updates, merge them into state
        updates = _finalize_issue(state)
        state.update(updates)

    # Then, commit and push artifacts to git
    state = _commit_and_push_files(state)

    # Cleanup source idea after successful issue creation
    if workflow_type == "issue" and not state.get("error_message"):
        _cleanup_source_idea(state)

    return state
