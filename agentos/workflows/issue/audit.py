"""Audit trail utilities for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Provides functions for:
- Sequential file numbering (001, 002, 003...)
- Saving audit files (brief, draft, feedback, verdict, filed.json)
- Moving from active/ to done/{issue#}-{slug}/
- Batch git commit of audit trail
"""

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict


class FiledMetadata(TypedDict):
    """Schema for filed.json metadata file."""

    issue_number: int
    issue_url: str
    title: str
    filed_at: str  # ISO8601
    brief_file: str
    total_iterations: int
    draft_count: int
    verdict_count: int


# Base directories relative to repo root
AUDIT_ACTIVE_DIR = Path("docs/audit/active")
AUDIT_DONE_DIR = Path("docs/audit/done")


def get_repo_root() -> Path:
    """Detect repository root via git rev-parse.

    Returns:
        Path to repository root.

    Raises:
        RuntimeError: If not in a git repository.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Not in a git repository: {result.stderr.strip()}")
    return Path(result.stdout.strip())


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


def slug_exists(slug: str, repo_root: Path | None = None) -> bool:
    """Check if slug directory already exists in active/.

    Args:
        slug: The slug to check.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        True if active/{slug}/ exists.
    """
    root = repo_root or get_repo_root()
    return (root / AUDIT_ACTIVE_DIR / slug).exists()


def create_audit_dir(slug: str, repo_root: Path | None = None) -> Path:
    """Create audit directory for this workflow.

    Args:
        slug: Workflow slug.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Path to created directory (docs/audit/active/{slug}/).

    Raises:
        FileExistsError: If directory already exists.
    """
    root = repo_root or get_repo_root()
    audit_dir = root / AUDIT_ACTIVE_DIR / slug

    if audit_dir.exists():
        raise FileExistsError(f"Audit directory already exists: {audit_dir}")

    audit_dir.mkdir(parents=True, exist_ok=False)
    return audit_dir


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
        suffix: File suffix (e.g., "brief.md", "draft.md", "feedback.txt").
        content: File content.

    Returns:
        Path to the saved file.
    """
    filename = f"{number:03d}-{suffix}"
    file_path = audit_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


def save_filed_metadata(
    audit_dir: Path,
    number: int,
    issue_number: int,
    issue_url: str,
    title: str,
    brief_file: str,
    total_iterations: int,
    draft_count: int,
    verdict_count: int,
) -> Path:
    """Save filed.json metadata file.

    Args:
        audit_dir: Path to the audit directory.
        number: File number.
        issue_number: GitHub issue number.
        issue_url: GitHub issue URL.
        title: Issue title.
        brief_file: Original brief filename.
        total_iterations: Total loop iterations.
        draft_count: Number of drafts generated.
        verdict_count: Number of verdicts received.

    Returns:
        Path to the saved filed.json file.
    """
    metadata: FiledMetadata = {
        "issue_number": issue_number,
        "issue_url": issue_url,
        "title": title,
        "filed_at": datetime.now(timezone.utc).isoformat(),
        "brief_file": brief_file,
        "total_iterations": total_iterations,
        "draft_count": draft_count,
        "verdict_count": verdict_count,
    }

    filename = f"{number:03d}-filed.json"
    file_path = audit_dir / filename
    file_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return file_path


def move_to_done(
    audit_dir: Path,
    issue_number: int,
    slug: str,
    repo_root: Path | None = None,
) -> Path:
    """Move audit directory from active/ to done/{issue#}-{slug}/.

    Args:
        audit_dir: Current path in active/.
        issue_number: GitHub issue number.
        slug: Workflow slug.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        New path in done/.
    """
    root = repo_root or get_repo_root()
    done_dir = root / AUDIT_DONE_DIR / f"{issue_number}-{slug}"

    # Ensure done directory exists
    done_dir.parent.mkdir(parents=True, exist_ok=True)

    # Move the directory
    shutil.move(str(audit_dir), str(done_dir))
    return done_dir


def batch_commit(audit_dir: Path, issue_number: int) -> None:
    """Commit all audit files in a single commit.

    Args:
        audit_dir: Path to the audit directory (in done/).
        issue_number: GitHub issue number for commit message.
    """
    repo_root = get_repo_root()

    # Stage all files in audit_dir
    subprocess.run(
        ["git", "-C", str(repo_root), "add", str(audit_dir)],
        check=True,
        timeout=30,
    )

    # Commit
    commit_msg = f"docs(audit): add audit trail for issue #{issue_number}"
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", commit_msg],
        check=True,
        timeout=30,
    )


def ensure_audit_directories(repo_root: Path | None = None) -> None:
    """Ensure audit directory structure exists.

    Creates docs/audit/active/ and docs/audit/done/ with .gitkeep files.

    Args:
        repo_root: Repository root path. Auto-detected if None.
    """
    root = repo_root or get_repo_root()

    for subdir in [AUDIT_ACTIVE_DIR, AUDIT_DONE_DIR]:
        dir_path = root / subdir
        dir_path.mkdir(parents=True, exist_ok=True)

        gitkeep = dir_path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
