"""Audit trail utilities for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Provides functions for:
- Sequential file numbering (001, 002, 003...)
- Saving audit files (brief, draft, feedback, verdict, filed.json)
- Moving from active/ to done/{issue#}-{slug}/
- Batch git commit of audit trail
"""

from assemblyzero.utils.shell import run_command
import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

# Module logger for GUARD messages
logger = logging.getLogger(__name__)


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
AUDIT_ACTIVE_DIR = Path("docs/lineage/active")
AUDIT_DONE_DIR = Path("docs/lineage/done")

# Ideas directories (staging area for workflow)
IDEAS_ACTIVE_DIR = Path("ideas/active")
IDEAS_DONE_DIR = Path("ideas/done")


def get_repo_root() -> Path:
    """Detect repository root via git rev-parse.

    Returns:
        Path to repository root.

    Raises:
        RuntimeError: If not in a git repository.
    """
    result = run_command(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Not in a git repository: {result.stderr.strip()}")
    return Path(result.stdout.strip())

def get_repo_short_id(repo_root: Path | None = None) -> str:
    """Get a sanitized 7-character Repo ID.

    Priority:
    1. .assemblyzero/config.json (repo_id field)
    2. Git remote name
    3. Directory name

    Returns:
        7-character capitalized alphanumeric ID.
    """
    root = repo_root or get_repo_root()
    
    # 1. Check config
    config_file = root / ".assemblyzero" / "config.json"
    if config_file.exists():
        try:
            import json
            config = json.loads(config_file.read_text(encoding="utf-8"))
            if "repo_id" in config:
                raw_id = config["repo_id"]
                return _sanitize_repo_id(raw_id)
        except Exception:
            pass

    # 2. Check Git Remote
    try:
        result = run_command(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Extract name from git@github.com:owner/RepoName.git or https://.../RepoName.git
            name_match = re.search(r"/([^/]+?)(?:\.git)?$", url)
            if name_match:
                return _sanitize_repo_id(name_match.group(1))
    except Exception:
        pass

    # 3. Fallback to directory name
    return _sanitize_repo_id(root.name)


def _sanitize_repo_id(raw_id: str) -> str:
    """Sanitize Repo ID: Alphanumeric only, 7 chars, First char capitalized."""
    # Mapping for known repos
    mapping = {
        "assemblyzero": "Assemb0",
        "unleashed": "Unleash",
        "clio": "Clio",
    }
    
    clean = re.sub(r"[^a-zA-Z0-9]", "", raw_id).lower()
    if clean in mapping:
        return mapping[clean]
        
    # Generic sanitization
    res = re.sub(r"[^a-zA-Z0-9]", "", raw_id)
    if not res:
        raise ValueError(f"Repo ID '{raw_id}' is empty after sanitization")
    
    # Truncate and capitalize
    res = res[:7]
    return res[0].upper() + res[1:]



def generate_slug(brief_file: str, repo_root: Path | None = None) -> str:
    """Generate unique slug: {REPO}-{NUM} (Lean Pro Strategy).

    Args:
        brief_file: Path to the brief file.
        repo_root: Repository root path.

    Returns:
        Unique slug string (e.g., 'Assemb0-0042').
    """
    root = repo_root or get_repo_root()
    repo_id = get_repo_short_id(root)
    
    # We use a sequential number scoped to this repo
    num = get_next_issue_number(repo_id, root)
    return f"{repo_id}-{num:04d}"


def get_next_issue_number(repo_id: str, repo_root: Path | None = None) -> int:
    """Get next sequential issue number for this repo.

    Args:
        repo_id: The 7-char Repo ID.
        repo_root: Repository root path.

    Returns:
        Next issue number.
    """
    root = repo_root or get_repo_root()
    active_dir = root / AUDIT_ACTIVE_DIR
    done_dir = root / AUDIT_DONE_DIR
    
    max_num = 0
    # Scan both active and done
    for d in [active_dir, done_dir]:
        if not d.exists():
            continue
        for item in d.iterdir():
            if item.is_dir():
                # Pattern: {REPO}-{NUM}
                match = re.match(rf"^{repo_id}-(\d{{4}})$", item.name)
                if match:
                    num = int(match.group(1))
                    max_num = max(max_num, num)
                    
    return max_num + 1


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
            match = re.search(r"-(\d{3})-", f.name)
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
    """Save an audit file with structured naming: {SLUG}-{NNN}-{TYPE}.md.

    Args:
        audit_dir: Path to the audit directory.
        number: File sequence number (1-999).
        suffix: File suffix (e.g., "brief.md", "draft.md").
        content: File content.

    Returns:
        Path to the saved file.
    """
    slug = audit_dir.name
    filename = f"{slug}-{number:03d}-{suffix}"
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

    slug = audit_dir.name
    filename = f"{slug}-{number:03d}-filed.json"
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


def batch_commit(audit_dir: Path, issue_number: int, repo_root: Path | None = None) -> None:
    """Commit all audit files in a single commit.

    Args:
        audit_dir: Path to the audit directory (in done/).
        issue_number: GitHub issue number for commit message.
        repo_root: Repository root path. Auto-detected if None.
    """
    root = repo_root or get_repo_root()

    # Stage all files in audit_dir
    run_command(
        ["git", "-C", str(root), "add", str(audit_dir)],
        check=True,
        timeout=30,
    )

    # Commit
    commit_msg = f"docs(audit): add audit trail for issue #{issue_number}"
    run_command(
        ["git", "-C", str(root), "commit", "-m", commit_msg],
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


# ---------------------------------------------------------------------------
# Ideas folder utilities (staging area for workflow)
# ---------------------------------------------------------------------------


def is_idea_encrypted(idea_file: Path) -> bool:
    """Check if a file is git-crypt encrypted.

    Git-crypt encrypted files start with a specific binary header.

    Args:
        idea_file: Path to the idea file.

    Returns:
        True if file appears to be git-crypt encrypted.
    """
    try:
        with open(idea_file, "rb") as f:
            header = f.read(10)
            # Git-crypt files start with \x00GITCRYPT
            return header.startswith(b"\x00GITCRYPT")
    except (OSError, IOError):
        return False


def list_ideas(repo_root: Path | None = None) -> list[Path]:
    """List markdown files in ideas/active/, sorted alphabetically.

    Skips git-crypt encrypted files and .gitkeep.

    Args:
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        List of Path objects to idea files.
    """
    root = repo_root or get_repo_root()
    ideas_dir = root / IDEAS_ACTIVE_DIR

    if not ideas_dir.exists():
        return []

    ideas = []
    for f in sorted(ideas_dir.iterdir()):
        if f.is_file() and f.suffix == ".md" and f.name != ".gitkeep":
            if not is_idea_encrypted(f):
                ideas.append(f)

    return ideas


def count_encrypted_ideas(repo_root: Path | None = None) -> int:
    """Count git-crypt encrypted files in ideas/active/.

    Args:
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Number of encrypted idea files.
    """
    root = repo_root or get_repo_root()
    ideas_dir = root / IDEAS_ACTIVE_DIR

    if not ideas_dir.exists():
        return 0

    count = 0
    for f in ideas_dir.iterdir():
        if f.is_file() and f.suffix == ".md" and f.name != ".gitkeep":
            if is_idea_encrypted(f):
                count += 1

    return count


def move_idea_to_done(
    idea_file: Path | str,
    issue_number: int,
    repo_root: Path | None = None,
) -> Path:
    """Move idea file from active/ to done/{issue#}-{name}.md.

    Args:
        idea_file: Path to the idea file (can be relative or absolute).
        issue_number: GitHub issue number.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        New path in ideas/done/.

    Raises:
        FileNotFoundError: If idea file doesn't exist.
    """
    root = repo_root or get_repo_root()
    idea_path = Path(idea_file)

    # Make path absolute if relative
    if not idea_path.is_absolute():
        idea_path = root / idea_path

    if not idea_path.exists():
        raise FileNotFoundError(f"Idea file not found: {idea_path}")

    # Create done directory if needed
    done_dir = root / IDEAS_DONE_DIR
    done_dir.mkdir(parents=True, exist_ok=True)

    # New filename: {issue#}-{original-name}.md
    new_name = f"{issue_number}-{idea_path.name}"
    done_path = done_dir / new_name

    # Move the file
    shutil.move(str(idea_path), str(done_path))
    return done_path


def ensure_ideas_directories(repo_root: Path | None = None) -> None:
    """Ensure ideas directory structure exists.

    Creates ideas/active/ and ideas/done/ with .gitkeep files.

    Args:
        repo_root: Repository root path. Auto-detected if None.
    """
    root = repo_root or get_repo_root()

    for subdir in [IDEAS_ACTIVE_DIR, IDEAS_DONE_DIR]:
        dir_path = root / subdir
        dir_path.mkdir(parents=True, exist_ok=True)

        gitkeep = dir_path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()


# ---------------------------------------------------------------------------
# Workflow Audit Logging (Issue #101)
# ---------------------------------------------------------------------------

WORKFLOW_AUDIT_FILE = Path("docs/lineage/workflow-audit.jsonl")


def log_workflow_execution(
    target_repo: Path,
    slug: str,
    workflow_type: str,
    event: str,
    details: dict | None = None,
) -> None:
    """Log workflow execution to central audit file.

    Creates a JSONL (JSON Lines) audit trail of all workflow executions.
    This enables post-hoc analysis of workflow runs, failures, and patterns.

    Args:
        target_repo: Path to the target repository.
        slug: Workflow slug (used instead of issue_number for issue workflow).
        workflow_type: Type of workflow ("lld" or "issue").
        event: Event type ("start", "guard_warning", "guard_error", "complete", "error").
        details: Optional dict with additional event details.
    """
    log_file = target_repo / WORKFLOW_AUDIT_FILE

    # Ensure directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow_type": workflow_type,
        "slug": slug,
        "target_repo": str(target_repo),
        "event": event,
    }

    if details:
        entry["details"] = details

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        # Don't fail the workflow if audit logging fails
        logger.warning(f"Failed to write workflow audit log: {e}")
