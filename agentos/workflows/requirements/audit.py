"""Unified audit trail utilities for Requirements Workflow.

Issue #101: Unified Requirements Workflow

Provides functions for:
- Unified audit directory creation (issue and LLD workflows)
- Sequential file numbering (001, 002, 003...)
- Saving audit files (brief/issue, draft, feedback, verdict)
- Path resolution (agentos_root vs target_repo)
- Finalization (issue filing or LLD saving)
- LLD status tracking

CRITICAL PATH RULES:
- Templates and prompts are loaded from agentos_root
- Outputs (LLDs, audit trails, status files) are written to target_repo
- Never use "" (empty string) for paths - it causes auto-detection bugs
- All functions receive explicit paths - no fallback auto-detection
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, TypedDict


# Base directories relative to repo root
AUDIT_ACTIVE_DIR = Path("docs/lineage/active")
AUDIT_DONE_DIR = Path("docs/lineage/done")
LLD_ACTIVE_DIR = Path("docs/lld/active")
LLD_DONE_DIR = Path("docs/lld/done")
LLD_STATUS_FILE = Path("docs/lld/lld-status.json")
IDEAS_ACTIVE_DIR = Path("ideas/active")
IDEAS_DONE_DIR = Path("ideas/done")


# =============================================================================
# Path Resolution
# =============================================================================


def resolve_roots(
    agentos_root: str,
    target_repo: str,
) -> tuple[Path, Path]:
    """Resolve and validate agentos_root and target_repo paths.

    Args:
        agentos_root: Path to AgentOS installation.
        target_repo: Path to target repository.

    Returns:
        Tuple of (agentos_root, target_repo) as resolved Path objects.

    Raises:
        ValueError: If either path is empty.
    """
    if not agentos_root or not agentos_root.strip():
        raise ValueError("agentos_root must be set and non-empty")
    if not target_repo or not target_repo.strip():
        raise ValueError("target_repo must be set and non-empty")

    return Path(agentos_root).resolve(), Path(target_repo).resolve()


def get_audit_dir_path(
    workflow_type: Literal["issue", "lld"],
    target_repo: Path,
    slug: str = "",
    issue_number: int = 0,
) -> Path:
    """Get the audit directory path for a workflow.

    Args:
        workflow_type: Either "issue" or "lld".
        target_repo: Path to target repository.
        slug: Workflow slug (for issue workflow).
        issue_number: GitHub issue number (for LLD workflow).

    Returns:
        Path to audit directory.
    """
    if workflow_type == "issue":
        return target_repo / AUDIT_ACTIVE_DIR / slug
    else:
        return target_repo / AUDIT_ACTIVE_DIR / f"{issue_number}-lld"


# =============================================================================
# Audit Directory Creation
# =============================================================================


def create_audit_dir(
    workflow_type: Literal["issue", "lld"],
    target_repo: Path,
    slug: str = "",
    issue_number: int = 0,
) -> Path:
    """Create audit directory for a workflow.

    Args:
        workflow_type: Either "issue" or "lld".
        target_repo: Path to target repository.
        slug: Workflow slug (for issue workflow).
        issue_number: GitHub issue number (for LLD workflow).

    Returns:
        Path to created directory.
    """
    audit_dir = get_audit_dir_path(
        workflow_type=workflow_type,
        target_repo=target_repo,
        slug=slug,
        issue_number=issue_number,
    )

    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir


# =============================================================================
# File Numbering and Saving
# =============================================================================


def next_file_number(audit_dir: Path) -> int:
    """Get next sequential file number.

    Scans audit_dir for NNN-*.* files and returns max + 1.

    Args:
        audit_dir: Path to the audit directory.

    Returns:
        Next file number (starts at 1 if directory is empty).
    """
    if not audit_dir.exists():
        return 1

    max_num = 0
    for f in audit_dir.iterdir():
        if f.is_file():
            match = re.match(r"^(\d{3})-", f.name)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)

    return max_num + 1


def save_audit_file(
    audit_dir: Path,
    number: int,
    suffix: str,
    content: str,
) -> Path:
    """Save an audit file with sequential numbering.

    Args:
        audit_dir: Path to the audit directory.
        number: File number (1-999).
        suffix: File suffix (e.g., "brief.md", "draft.md", "verdict.md").
        content: File content.

    Returns:
        Path to the saved file.
    """
    filename = f"{number:03d}-{suffix}"
    file_path = audit_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


# =============================================================================
# Template Loading (from AgentOS root)
# =============================================================================


def load_template(
    template_path: Path,
    agentos_root: Path,
) -> str:
    """Load a template file from AgentOS root.

    Templates are part of AgentOS, not the target repo. This function
    enforces loading from agentos_root to prevent path confusion.

    Args:
        template_path: Relative path to template (e.g., "docs/templates/0102...").
        agentos_root: Path to AgentOS installation.

    Returns:
        Template content.

    Raises:
        FileNotFoundError: If template doesn't exist.
    """
    full_path = agentos_root / template_path

    if not full_path.exists():
        raise FileNotFoundError(
            f"Template not found: {full_path}\n"
            f"Expected template at: {template_path}"
        )

    return full_path.read_text(encoding="utf-8")


def load_review_prompt(
    prompt_path: Path,
    agentos_root: Path,
) -> str:
    """Load a review prompt from AgentOS root.

    Review prompts are part of AgentOS, not the target repo.

    Args:
        prompt_path: Relative path to prompt (e.g., "docs/skills/0702c...").
        agentos_root: Path to AgentOS installation.

    Returns:
        Prompt content.

    Raises:
        FileNotFoundError: If prompt doesn't exist.
    """
    full_path = agentos_root / prompt_path

    if not full_path.exists():
        raise FileNotFoundError(
            f"Review prompt not found: {full_path}\n"
            f"Expected prompt at: {prompt_path}"
        )

    return full_path.read_text(encoding="utf-8")


# =============================================================================
# Context Assembly
# =============================================================================


def validate_context_path(context_path: str, target_repo: Path) -> Path | None:
    """Validate and resolve a context file path.

    Security check: Reject paths outside target_repo.

    Args:
        context_path: User-provided path (may be relative or absolute).
        target_repo: Target repository root.

    Returns:
        Resolved absolute Path if valid, None if invalid.
    """
    path = Path(context_path)

    # Resolve to absolute path
    if not path.is_absolute():
        path = (target_repo / path).resolve()
    else:
        path = path.resolve()

    # Security check: must be under target_repo
    try:
        path.relative_to(target_repo)
    except ValueError:
        return None  # Path is outside target_repo

    # Existence check
    if not path.exists():
        return None

    return path


def assemble_context(
    context_files: list[str],
    target_repo: Path,
) -> str:
    """Assemble context content from multiple files.

    Args:
        context_files: List of paths to context files.
        target_repo: Target repository root.

    Returns:
        Assembled context as a single string with file headers.
    """
    if not context_files:
        return ""

    context_parts = []

    for ctx_path in context_files:
        path = validate_context_path(ctx_path, target_repo)
        if path is None:
            continue

        try:
            if path.is_file():
                content = path.read_text(encoding="utf-8", errors="replace")
                rel_path = path.relative_to(target_repo)
                context_parts.append(
                    f"## Reference: {rel_path}\n\n```\n{content}\n```"
                )
            elif path.is_dir():
                # Read all text files in directory
                for f in sorted(path.iterdir()):
                    if f.is_file() and f.suffix in (".md", ".py", ".json", ".yaml", ".txt"):
                        content = f.read_text(encoding="utf-8", errors="replace")
                        rel_path = f.relative_to(target_repo)
                        context_parts.append(
                            f"## Reference: {rel_path}\n\n```\n{content}\n```"
                        )
        except (OSError, UnicodeDecodeError):
            continue

    return "\n\n".join(context_parts)


# =============================================================================
# LLD Status Tracking
# =============================================================================


class LLDStatusEntry(TypedDict):
    """Schema for a single LLD status entry."""

    lld_path: str
    status: str  # "draft", "approved", "blocked"
    has_gemini_review: bool
    final_verdict: str | None
    last_review_date: str | None
    review_count: int


class LLDStatusCache(TypedDict):
    """Schema for lld-status.json cache file."""

    version: str
    last_updated: str
    issues: dict[str, LLDStatusEntry]


def load_lld_tracking(target_repo: Path) -> LLDStatusCache:
    """Load lld-status.json cache file.

    Args:
        target_repo: Target repository root.

    Returns:
        LLDStatusCache dict. Returns empty cache if file doesn't exist.
    """
    status_file = target_repo / LLD_STATUS_FILE

    if not status_file.exists():
        return {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "issues": {},
        }

    try:
        content = status_file.read_text(encoding="utf-8")
        data = json.loads(content)
        return data
    except (json.JSONDecodeError, OSError):
        return {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "issues": {},
        }


def save_lld_tracking(tracking: LLDStatusCache, target_repo: Path) -> None:
    """Save lld-status.json cache file.

    Args:
        tracking: LLDStatusCache dict to save.
        target_repo: Target repository root.
    """
    status_file = target_repo / LLD_STATUS_FILE

    # Ensure directory exists
    status_file.parent.mkdir(parents=True, exist_ok=True)

    # Update timestamp
    tracking["last_updated"] = datetime.now(timezone.utc).isoformat()

    # Write file
    status_file.write_text(
        json.dumps(tracking, indent=2) + "\n",
        encoding="utf-8",
    )


def update_lld_status(
    issue_number: int,
    lld_path: str,
    review_info: dict,
    target_repo: Path,
) -> None:
    """Update tracking for a single issue.

    Args:
        issue_number: GitHub issue number.
        lld_path: Path to LLD file (relative or absolute).
        review_info: Dict with has_gemini_review, final_verdict, etc.
        target_repo: Target repository root.
    """
    # Make path relative to repo root for storage
    lld_path_obj = Path(lld_path)
    if lld_path_obj.is_absolute():
        try:
            lld_path = str(lld_path_obj.relative_to(target_repo))
        except ValueError:
            pass  # Keep as-is if not under target_repo

    # Load existing cache
    tracking = load_lld_tracking(target_repo)

    # Determine status
    if review_info.get("has_gemini_review"):
        if review_info.get("final_verdict") == "APPROVED":
            status = "approved"
        else:
            status = "blocked"
    else:
        status = "draft"

    # Update entry
    tracking["issues"][str(issue_number)] = {
        "lld_path": lld_path,
        "status": status,
        "has_gemini_review": review_info.get("has_gemini_review", False),
        "final_verdict": review_info.get("final_verdict"),
        "last_review_date": review_info.get("last_review_date"),
        "review_count": review_info.get("review_count", 0),
    }

    # Save
    save_lld_tracking(tracking, target_repo)


# =============================================================================
# LLD Finalization
# =============================================================================


def save_final_lld(
    issue_number: int,
    lld_content: str,
    target_repo: Path,
) -> Path:
    """Save approved LLD to target_repo/docs/lld/active/.

    CRITICAL: This writes to target_repo, NOT agentos_root.

    Args:
        issue_number: GitHub issue number.
        lld_content: Final LLD content.
        target_repo: Target repository root.

    Returns:
        Path to saved LLD file.
    """
    lld_dir = target_repo / LLD_ACTIVE_DIR
    lld_dir.mkdir(parents=True, exist_ok=True)

    lld_path = lld_dir / f"LLD-{issue_number:03d}.md"
    lld_path.write_text(lld_content, encoding="utf-8")
    return lld_path


# =============================================================================
# Slug Generation (Issue workflow)
# =============================================================================


def generate_slug(brief_file: str) -> str:
    """Generate slug from brief filename.

    Args:
        brief_file: Path to the brief file.

    Returns:
        Slug string (filename without extension, lowercase, hyphens for spaces).

    Examples:
        "governance-notes.md" -> "governance-notes"
        "My Feature Ideas.md" -> "my-feature-ideas"
    """
    filename = Path(brief_file).stem
    # Lowercase, replace spaces and underscores with hyphens
    slug = filename.lower().replace(" ", "-").replace("_", "-")
    # Remove any non-alphanumeric except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")
