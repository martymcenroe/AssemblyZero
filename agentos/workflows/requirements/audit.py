"""Audit utilities for requirements workflow.

Provides functions for creating audit directories and saving audit files.
"""

import re
from pathlib import Path
from typing import Any

from agentos.core.config import REVIEWER_MODEL


def create_audit_dir(
    target_repo: Path,
    workflow_type: str,
    slug: str = "",
    issue_number: int | None = None,
) -> Path:
    """Create audit directory for workflow execution.

    Creates lineage directory at docs/lineage/active/{dir_name}/
    - Issue workflow: dir_name = slug (e.g., "my-feature")
    - LLD workflow: dir_name = "{issue_number}-lld" (e.g., "42-lld")

    Args:
        target_repo: Repository root path
        workflow_type: Type of workflow ("issue" or "lld")
        slug: Slug name for issue workflow
        issue_number: Issue number for LLD workflow

    Returns:
        Path to audit directory
    """
    # Build directory name based on workflow type
    if workflow_type == "issue":
        dir_name = slug if slug else "issue"
    else:  # lld
        dir_name = f"{issue_number}-lld" if issue_number else "lld"

    audit_dir = target_repo / "docs" / "lineage" / "active" / dir_name
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir


def next_file_number(audit_dir: Path) -> int:
    """Get next sequential file number for audit files.
    
    Args:
        audit_dir: Audit directory path
        
    Returns:
        Next available file number
    """
    if not audit_dir.exists():
        return 1
    
    existing_files = list(audit_dir.glob("*.md"))
    if not existing_files:
        return 1
    
    # Extract numbers from filenames (format: NNN-type.md)
    numbers = []
    for f in existing_files:
        try:
            num = int(f.stem.split("-")[0])
            numbers.append(num)
        except (ValueError, IndexError):
            continue
    
    return max(numbers, default=0) + 1


def save_audit_file(
    audit_dir: Path,
    file_num: int,
    file_type: str,
    content: str,
) -> Path:
    """Save audit file with sequential numbering.

    Args:
        audit_dir: Audit directory path
        file_num: File number
        file_type: Type of file (e.g., 'issue', 'error', 'finalize')
        content: File content

    Returns:
        Path to saved file
    """
    filename = f"{file_num:03d}-{file_type}.md"
    file_path = audit_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


def load_template(template_path: Path, agentos_root: Path) -> str:
    """Load template file from agentos_root.

    Args:
        template_path: Relative path to template file
        agentos_root: Root directory of AgentOS

    Returns:
        Template content as string

    Raises:
        FileNotFoundError: If template file doesn't exist
    """
    full_path = agentos_root / template_path
    if not full_path.exists():
        raise FileNotFoundError(f"Template not found: {full_path}")

    return full_path.read_text(encoding="utf-8")


def load_review_prompt(prompt_path: Path, agentos_root: Path) -> str:
    """Load review prompt file from agentos_root.

    Args:
        prompt_path: Relative path to review prompt file
        agentos_root: Root directory of AgentOS

    Returns:
        Review prompt content as string

    Raises:
        FileNotFoundError: If review prompt file doesn't exist
    """
    full_path = agentos_root / prompt_path
    if not full_path.exists():
        raise FileNotFoundError(f"Review prompt not found: {full_path}")

    return full_path.read_text(encoding="utf-8")


def embed_review_evidence(
    lld_content: str,
    verdict: str,
    review_date: str,
    review_count: int,
) -> str:
    """Embed review evidence in LLD content.

    Adds/updates:
    1. Status field: "* **Status:** Approved (Gemini Review, {date})"
    2. Review Summary table entry
    3. Final Status marker at end of document

    Args:
        lld_content: Original LLD content.
        verdict: Review verdict ("APPROVED", "BLOCKED").
        review_date: ISO8601 date of review.
        review_count: Review iteration number.

    Returns:
        Updated LLD content with embedded evidence.
    """
    # Update Status field if present
    # Pattern: * **Status:** Draft -> * **Status:** Approved (Gemini Review, date)
    status_pattern = re.compile(
        r"(\*\s*\*\*Status:\*\*)\s*\w+(?:\s*\([^)]*\))?",
        re.IGNORECASE,
    )
    new_status = f"\\1 {verdict.capitalize()} ({REVIEWER_MODEL}, {review_date})"
    lld_content = status_pattern.sub(new_status, lld_content, count=1)

    # Update or create Review Summary table in Appendix
    review_entry = f"| {review_count} | {review_date} | {verdict} | `{REVIEWER_MODEL}` |"

    # Check if Review Summary table exists
    if "### Review Summary" in lld_content:
        # Find the table and add/update entry (supports both old 3-col and new 4-col format)
        table_pattern = re.compile(
            r"(### Review Summary\s*\n\n\| Review \| Date \| Verdict[^\n]*\|\n\|[^\n]+\|)\n",
            re.MULTILINE,
        )
        if table_pattern.search(lld_content):
            # Add new row after header
            lld_content = table_pattern.sub(
                f"\\1\n{review_entry}\n",
                lld_content,
            )
    else:
        # Create Review Summary section before Final Status
        review_section = f"""

### Review Summary

| Review | Date | Verdict | Model |
|--------|------|---------|-------|
{review_entry}
"""
        # Add before Final Status or at end
        if "**Final Status:**" in lld_content:
            lld_content = lld_content.replace(
                "**Final Status:**",
                f"{review_section}\n**Final Status:**",
            )
        else:
            lld_content += review_section

    # Update Final Status
    final_status_pattern = re.compile(
        r"\*\*Final Status:\*\*\s*\w+",
        re.IGNORECASE,
    )
    if final_status_pattern.search(lld_content):
        lld_content = final_status_pattern.sub(
            f"**Final Status:** {verdict}",
            lld_content,
        )
    else:
        lld_content += f"\n\n**Final Status:** {verdict}\n"

    return lld_content