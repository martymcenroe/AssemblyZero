"""Unified audit trail utilities for Requirements Workflow.

Issue #101: Unified Requirements Workflow

Provides functions for:
- Unified audit directory creation (issue and LLD workflows)
- Sequential file numbering (001, 002, 003...)
- Saving audit files (brief/issue, draft, feedback, verdict)
- Path resolution (assemblyzero_root vs target_repo)
- Finalization (issue filing or LLD saving)
- LLD status tracking

CRITICAL PATH RULES:
- Templates and prompts are loaded from assemblyzero_root
- Outputs (LLDs, audit trails, status files) are written to target_repo
- Never use "" (empty string) for paths - it causes auto-detection bugs
- All functions receive explicit paths - no fallback auto-detection
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, TypedDict

from assemblyzero.core.config import REVIEWER_MODEL


# Base directories relative to repo root
AUDIT_ACTIVE_DIR = Path("docs/lineage/active")
AUDIT_DONE_DIR = Path("docs/lineage/done")
LLD_ACTIVE_DIR = Path("docs/lld/active")
LLD_DONE_DIR = Path("docs/lld/done")
LLD_STATUS_FILE = Path("docs/lld/lld-status.json")
IDEAS_ACTIVE_DIR = Path("ideas/active")
IDEAS_DONE_DIR = Path("ideas/done")

# Directories to exclude from repo structure listings
EXCLUDED_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    ".tox",
    "dist",
    "build",
    "*.egg-info",
    ".assemblyzero",
    ".claude",
    ".idea",
    ".vscode",
}


# =============================================================================
# Repository Structure
# =============================================================================


def get_repo_structure(
    repo_path: str | Path,
    max_depth: int = 3,
    focus_dirs: list[str] | None = None,
) -> str:
    """Generate a tree view of repository directory structure.

    Used to provide context to the drafter when validation fails,
    so it can see what directories actually exist.

    Args:
        repo_path: Path to the repository root.
        max_depth: Maximum depth to traverse (default 3).
        focus_dirs: If provided, only show these top-level directories
                   (e.g., ["src", "tests"]). If None, shows all.

    Returns:
        Tree-formatted string showing directory structure.

    Example output:
        src/
          __init__.py
          main.py
          elementizer/
            __init__.py
          output/
            __init__.py
        tests/
          __init__.py
          fixtures/
          unit/
    """
    repo = Path(repo_path)
    if not repo.exists():
        return f"(Repository not found: {repo_path})"

    lines: list[str] = []

    def should_exclude(name: str) -> bool:
        """Check if directory/file should be excluded."""
        if name.startswith("."):
            return name in EXCLUDED_DIRS or name.startswith(".")
        return name in EXCLUDED_DIRS or name.endswith(".egg-info")

    def add_tree(path: Path, prefix: str = "", depth: int = 0) -> None:
        """Recursively add directory tree."""
        if depth > max_depth:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        # Separate dirs and files
        dirs = [e for e in entries if e.is_dir() and not should_exclude(e.name)]
        files = [e for e in entries if e.is_file() and not should_exclude(e.name)]

        # Show directories first
        for d in dirs:
            lines.append(f"{prefix}{d.name}/")
            add_tree(d, prefix + "  ", depth + 1)

        # Show key files (only at depth 0-1 to avoid noise)
        if depth <= 1:
            # Show Python files and important config files
            important_files = [
                f for f in files
                if f.suffix in (".py", ".toml", ".yaml", ".yml", ".json", ".md")
                and f.name not in ("poetry.lock", "package-lock.json")
            ]
            # Limit to avoid overwhelming output
            for f in important_files[:10]:
                lines.append(f"{prefix}{f.name}")
            if len(important_files) > 10:
                lines.append(f"{prefix}... and {len(important_files) - 10} more files")

    # Get top-level entries
    try:
        top_entries = sorted(repo.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return "(Permission denied reading repository)"

    top_dirs = [e for e in top_entries if e.is_dir() and not should_exclude(e.name)]

    # Filter to focus dirs if specified
    if focus_dirs:
        top_dirs = [d for d in top_dirs if d.name in focus_dirs]

    # If no focus dirs specified, prioritize src/tests but include others
    if not focus_dirs:
        priority = {"src", "tests", "lib", "app", "pkg"}
        priority_dirs = [d for d in top_dirs if d.name in priority]
        other_dirs = [d for d in top_dirs if d.name not in priority]

        # Show priority dirs first, then up to 3 others
        top_dirs = priority_dirs + other_dirs[:3]

    for d in top_dirs:
        lines.append(f"{d.name}/")
        add_tree(d, "  ", 1)

    if not lines:
        return "(No relevant directories found)"

    return "\n".join(lines)


# =============================================================================
# Path Resolution
# =============================================================================


def resolve_roots(
    assemblyzero_root: str,
    target_repo: str,
) -> tuple[Path, Path]:
    """Resolve and validate assemblyzero_root and target_repo paths.

    Args:
        assemblyzero_root: Path to AssemblyZero installation.
        target_repo: Path to target repository.

    Returns:
        Tuple of (assemblyzero_root, target_repo) as resolved Path objects.

    Raises:
        ValueError: If either path is empty.
    """
    if not assemblyzero_root or not assemblyzero_root.strip():
        raise ValueError("assemblyzero_root must be set and non-empty")
    if not target_repo or not target_repo.strip():
        raise ValueError("target_repo must be set and non-empty")

    return Path(assemblyzero_root).resolve(), Path(target_repo).resolve()


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
    target_repo: Path,
    workflow_type: Literal["issue", "lld"],
    slug: str = "",
    issue_number: int | None = None,
) -> Path:
    """Create audit directory for a workflow.

    Args:
        target_repo: Path to target repository.
        workflow_type: Either "issue" or "lld".
        slug: Workflow slug (for issue workflow).
        issue_number: GitHub issue number (for LLD workflow).

    Returns:
        Path to created directory.
    """
    audit_dir = get_audit_dir_path(
        workflow_type=workflow_type,
        target_repo=target_repo,
        slug=slug,
        issue_number=issue_number or 0,
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
        suffix: File suffix (e.g., "draft.md", "verdict.md", "issue.md").
        content: File content.

    Returns:
        Path to the saved file.
    """
    filename = f"{number:03d}-{suffix}"
    file_path = audit_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


# =============================================================================
# Template Loading (from AssemblyZero root)
# =============================================================================


def load_template(
    template_path: Path,
    assemblyzero_root: Path,
) -> str:
    """Load a template file from AssemblyZero root.

    Templates are part of AssemblyZero, not the target repo. This function
    enforces loading from assemblyzero_root to prevent path confusion.

    Args:
        template_path: Relative path to template (e.g., "docs/templates/0102...").
        assemblyzero_root: Path to AssemblyZero installation.

    Returns:
        Template content.

    Raises:
        FileNotFoundError: If template doesn't exist.
    """
    full_path = assemblyzero_root / template_path

    if not full_path.exists():
        raise FileNotFoundError(
            f"Template not found: {full_path}\n"
            f"Expected template at: {template_path}"
        )

    return full_path.read_text(encoding="utf-8")


def load_review_prompt(
    prompt_path: Path,
    assemblyzero_root: Path,
) -> str:
    """Load a review prompt from AssemblyZero root.

    Review prompts are part of AssemblyZero, not the target repo.

    Args:
        prompt_path: Relative path to prompt (e.g., "docs/skills/0702c...").
        assemblyzero_root: Path to AssemblyZero installation.

    Returns:
        Prompt content.

    Raises:
        FileNotFoundError: If prompt doesn't exist.
    """
    full_path = assemblyzero_root / prompt_path

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


def _reset_lld_status_entry(issue_number: int, target_repo: Path) -> None:
    """Reset lld-status.json entry when regenerating an LLD.

    Issue #279: When an LLD is regenerated, the old approval status is stale
    and must be invalidated. The new LLD must go through fresh Gemini review.

    Args:
        issue_number: GitHub issue number.
        target_repo: Target repository root.
    """
    tracking = load_lld_tracking(target_repo)
    issue_key = str(issue_number)

    if issue_key in tracking["issues"]:
        # Reset to draft status, clear approval
        tracking["issues"][issue_key] = {
            "lld_path": f"docs\\lld\\active\\LLD-{issue_number:03d}.md",
            "status": "draft",
            "has_gemini_review": False,
            "final_verdict": None,
            "last_review_date": None,
            "review_count": 0,
        }
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

    CRITICAL: This writes to target_repo, NOT assemblyzero_root.

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


# =============================================================================
# Lineage Versioning (Standard 0012)
# =============================================================================


class ExistingLLDInfo(TypedDict):
    """Information about existing LLD and lineage for an issue.

    Note: lineage_path is always returned (even if directory doesn't exist yet)
    so that validation can create it to save error files. Use lineage_exists
    to check if the directory already exists.
    """

    lld_exists: bool
    lineage_exists: bool
    lld_path: Path | None
    lineage_path: Path  # Always returned - Issue #341


def check_existing_lld(issue_number: int, target_repo: Path) -> ExistingLLDInfo:
    """Check if LLD and/or lineage already exist for an issue.

    Per Standard 0012, before regenerating an LLD we must check for:
    - Existing LLD file: docs/lld/active/LLD-{issue}.md
    - Existing lineage directory: docs/lineage/active/{issue}-lld/

    Args:
        issue_number: GitHub issue number.
        target_repo: Target repository root.

    Returns:
        ExistingLLDInfo dict with existence flags and paths.
    """
    lld_path = target_repo / LLD_ACTIVE_DIR / f"LLD-{issue_number:03d}.md"
    lineage_path = target_repo / AUDIT_ACTIVE_DIR / f"{issue_number}-lld"

    return {
        "lld_exists": lld_path.exists(),
        "lineage_exists": lineage_path.exists(),
        "lld_path": lld_path if lld_path.exists() else None,
        # Issue #341: Always return lineage_path so validation can create
        # the directory and save error files for new LLDs
        "lineage_path": lineage_path,
    }


def shift_lineage_versions(issue_number: int, target_repo: Path) -> list[str]:
    """Shift existing lineage directories to preserve history.

    Per Standard 0012, when regenerating an LLD:
    1. Delete existing LLD file
    2. Shift lineage: {issue}-lld-n1 -> {issue}-lld-n2 (if n1 exists)
    3. Rename current: {issue}-lld -> {issue}-lld-n1

    Args:
        issue_number: GitHub issue number.
        target_repo: Target repository root.

    Returns:
        List of operations performed (for logging).
    """
    operations: list[str] = []
    active_dir = target_repo / AUDIT_ACTIVE_DIR

    # Paths
    lld_path = target_repo / LLD_ACTIVE_DIR / f"LLD-{issue_number:03d}.md"
    lineage_current = active_dir / f"{issue_number}-lld"
    lineage_n1 = active_dir / f"{issue_number}-lld-n1"
    lineage_n2 = active_dir / f"{issue_number}-lld-n2"

    # Step 1: Delete existing LLD file
    if lld_path.exists():
        lld_path.unlink()
        operations.append(f"Deleted: {lld_path.relative_to(target_repo)}")

    # Step 1.5: Reset lld-status.json entry (Issue #279: prevent stale approval)
    # When regenerating, the old approval is invalid - must go through fresh review
    _reset_lld_status_entry(issue_number, target_repo)
    operations.append(f"Reset status for issue #{issue_number} in lld-status.json")

    # Step 2: Shift n1 -> n2 (if n1 exists)
    if lineage_n1.exists():
        if lineage_n2.exists():
            # n2 already exists - remove it first (oldest version discarded)
            import shutil
            shutil.rmtree(lineage_n2)
            operations.append(f"Removed: {lineage_n2.relative_to(target_repo)} (oldest)")
        lineage_n1.rename(lineage_n2)
        operations.append(
            f"Shifted: {lineage_n1.relative_to(target_repo)} -> "
            f"{lineage_n2.relative_to(target_repo)}"
        )

    # Step 3: Shift current -> n1 (if current exists)
    if lineage_current.exists():
        lineage_current.rename(lineage_n1)
        operations.append(
            f"Shifted: {lineage_current.relative_to(target_repo)} -> "
            f"{lineage_n1.relative_to(target_repo)}"
        )

    return operations


# =============================================================================
# Review Evidence Embedding
# =============================================================================


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
