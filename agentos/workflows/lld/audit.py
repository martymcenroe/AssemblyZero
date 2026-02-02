"""Audit trail utilities for LLD Governance workflow.

Issue #86: LLD Creation & Governance Review Workflow
Issue #95: --select and LLD Status Tracking
LLD: docs/LLDs/active/LLD-086-lld-governance-workflow.md

Provides functions for:
- Sequential file numbering (001, 002, 003...)
- Saving audit files (issue, draft, verdict, approved.json)
- LLD output to docs/lld/active/
- LLD status tracking and Gemini review detection
"""

import json
import logging
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from agentos.core.config import REVIEWER_MODEL

# Module logger for GUARD messages
logger = logging.getLogger(__name__)


class ApprovedMetadata(TypedDict):
    """Schema for approved.json metadata file."""

    issue_number: int
    issue_title: str
    approved_at: str  # ISO8601
    final_lld_path: str
    total_iterations: int
    draft_count: int
    verdict_count: int


# Base directories relative to repo root
AUDIT_ACTIVE_DIR = Path("docs/lineage/active")
LLD_ACTIVE_DIR = Path("docs/lld/active")
LLD_DONE_DIR = Path("docs/lld/done")
LLD_STATUS_FILE = Path("docs/lld/lld-status.json")


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


def create_lld_audit_dir(issue_number: int, repo_root: Path | None = None) -> Path:
    """Create audit directory for this LLD workflow.

    Args:
        issue_number: GitHub issue number.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Path to created directory (docs/audit/active/{issue_number}-lld/).
    """
    root = repo_root or get_repo_root()
    audit_dir = root / AUDIT_ACTIVE_DIR / f"{issue_number}-lld"

    audit_dir.mkdir(parents=True, exist_ok=True)
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
        suffix: File suffix (e.g., "issue.md", "draft.md", "verdict.md").
        content: File content.

    Returns:
        Path to the saved file.
    """
    filename = f"{number:03d}-{suffix}"
    file_path = audit_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


def save_approved_metadata(
    audit_dir: Path,
    number: int,
    issue_number: int,
    issue_title: str,
    final_lld_path: str,
    total_iterations: int,
    draft_count: int,
    verdict_count: int,
) -> Path:
    """Save approved.json metadata file.

    Args:
        audit_dir: Path to the audit directory.
        number: File number.
        issue_number: GitHub issue number.
        issue_title: Issue title.
        final_lld_path: Path to final LLD in docs/LLDs/active/.
        total_iterations: Total loop iterations.
        draft_count: Number of drafts generated.
        verdict_count: Number of verdicts received.

    Returns:
        Path to the saved approved.json file.
    """
    metadata: ApprovedMetadata = {
        "issue_number": issue_number,
        "issue_title": issue_title,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "final_lld_path": final_lld_path,
        "total_iterations": total_iterations,
        "draft_count": draft_count,
        "verdict_count": verdict_count,
    }

    filename = f"{number:03d}-approved.json"
    file_path = audit_dir / filename
    file_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return file_path


def save_final_lld(
    issue_number: int,
    lld_content: str,
    repo_root: Path | None = None,
) -> Path:
    """Save approved LLD to docs/LLDs/active/.

    Args:
        issue_number: GitHub issue number.
        lld_content: Final LLD content.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Path to saved LLD file.
    """
    root = repo_root or get_repo_root()
    lld_dir = root / LLD_ACTIVE_DIR
    lld_dir.mkdir(parents=True, exist_ok=True)

    lld_path = lld_dir / f"LLD-{issue_number:03d}.md"
    lld_path.write_text(lld_content, encoding="utf-8")
    return lld_path


def validate_context_path(context_path: str, repo_root: Path | None = None) -> Path:
    """Validate and resolve a context file path.

    Security check per LLD Section 7: Reject paths outside project root.

    Args:
        context_path: User-provided path (may be relative or absolute).
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Resolved absolute Path if valid.

    Raises:
        ValueError: If path is outside project root or doesn't exist.
    """
    root = repo_root or get_repo_root()
    path = Path(context_path)

    # Resolve to absolute path
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()

    # Security check: must be under repo root
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError(
            f"Context path outside project root: {context_path}\n"
            f"All paths must be within: {root}"
        )

    # Existence check
    if not path.exists():
        raise ValueError(f"Context path does not exist: {context_path}")

    return path


def assemble_context(context_files: list[str], repo_root: Path | None = None) -> str:
    """Assemble context content from multiple files.

    Args:
        context_files: List of paths to context files.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Assembled context as a single string with file headers.
    """
    if not context_files:
        return ""

    root = repo_root or get_repo_root()
    context_parts = []

    for ctx_path in context_files:
        try:
            path = validate_context_path(ctx_path, root)

            if path.is_file():
                content = path.read_text(encoding="utf-8", errors="replace")
                context_parts.append(
                    f"## Reference: {path.name}\n\n```\n{content}\n```"
                )
            elif path.is_dir():
                # Read all text files in directory
                for f in sorted(path.iterdir()):
                    if f.is_file() and f.suffix in (".md", ".py", ".json", ".yaml", ".txt"):
                        content = f.read_text(encoding="utf-8", errors="replace")
                        context_parts.append(
                            f"## Reference: {f.name}\n\n```\n{content}\n```"
                        )
        except ValueError as e:
            print(f"[WARN] Skipping context: {e}")
            continue

    return "\n\n".join(context_parts)


# ---------------------------------------------------------------------------
# LLD Status Tracking (Issue #95)
# ---------------------------------------------------------------------------


class LLDStatusEntry(TypedDict):
    """Schema for a single LLD status entry in lld-status.json."""

    lld_path: str
    status: str  # "draft", "approved", "blocked"
    has_gemini_review: bool
    final_verdict: str | None  # "APPROVED", "BLOCKED", None
    last_review_date: str | None  # ISO8601 date or None
    review_count: int


class LLDStatusCache(TypedDict):
    """Schema for lld-status.json cache file."""

    version: str
    last_updated: str  # ISO8601
    issues: dict[str, LLDStatusEntry]


def detect_gemini_review(lld_content: str) -> dict:
    """Detect Gemini review evidence in LLD content.

    Detection patterns (in priority order):
    1. **Final Status:** APPROVED line
    2. Review Summary table with Gemini entries
    3. ### Gemini Review #N headings
    4. Status field in Context section

    Args:
        lld_content: LLD markdown content.

    Returns:
        dict with:
            has_review: bool
            final_verdict: str | None ("APPROVED", "BLOCKED", etc.)
            review_count: int
            last_review_date: str | None
    """
    result = {
        "has_review": False,
        "final_verdict": None,
        "review_count": 0,
        "last_review_date": None,
    }

    if not lld_content:
        return result

    # Pattern 1: **Final Status:** APPROVED/BLOCKED
    final_status_match = re.search(
        r"\*\*Final Status:\*\*\s*(APPROVED|BLOCKED|PENDING)",
        lld_content,
        re.IGNORECASE,
    )
    if final_status_match:
        result["final_verdict"] = final_status_match.group(1).upper()
        if result["final_verdict"] in ("APPROVED", "BLOCKED"):
            result["has_review"] = True

    # Pattern 2: Review Summary table
    # | Review | Date | Verdict |
    # | Gemini #1 | 2026-01-29 | APPROVED |
    table_matches = re.findall(
        r"\|\s*Gemini\s*#?\d+\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\w+)\s*\|",
        lld_content,
    )
    if table_matches:
        result["has_review"] = True
        result["review_count"] = len(table_matches)
        # Get the latest date
        dates = [m[0] for m in table_matches]
        if dates:
            result["last_review_date"] = max(dates)
        # Get verdict from last review
        if table_matches:
            result["final_verdict"] = table_matches[-1][1].upper()

    # Pattern 3: ### Gemini Review #N (APPROVED/BLOCKED)
    review_headings = re.findall(
        r"###\s*Gemini Review\s*#?(\d+)\s*\((\w+)\)",
        lld_content,
        re.IGNORECASE,
    )
    if review_headings:
        result["has_review"] = True
        result["review_count"] = max(result["review_count"], len(review_headings))
        # Get verdict from last review heading
        if review_headings:
            result["final_verdict"] = result["final_verdict"] or review_headings[-1][1].upper()

    # Pattern 4: Status field with Gemini approval
    # * **Status:** Approved (Gemini Review, 2026-01-29)
    status_match = re.search(
        r"\*\s*\*\*Status:\*\*\s*(Approved|Blocked).*?(\d{4}-\d{2}-\d{2})",
        lld_content,
        re.IGNORECASE,
    )
    if status_match:
        result["has_review"] = True
        if not result["final_verdict"]:
            result["final_verdict"] = status_match.group(1).upper()
        if not result["last_review_date"]:
            result["last_review_date"] = status_match.group(2)

    return result


def get_lld_path_for_issue(issue_number: int, repo_root: Path | None = None) -> Path | None:
    """Find LLD file for an issue number.

    Searches docs/lld/active/ and docs/lld/done/ for:
    - LLD-{N}-*.md (padded, e.g., LLD-086-desc.md)
    - LLD-{N}.md (simple, e.g., LLD-42.md)
    - {N}-*.md (legacy format)

    Prefers done/ over active/ (done/ is authoritative).

    Args:
        issue_number: GitHub issue number.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Path to LLD file if found, None otherwise.
    """
    root = repo_root or get_repo_root()

    # Build search patterns
    patterns = [
        f"LLD-{issue_number:03d}-*.md",  # LLD-086-desc.md
        f"LLD-{issue_number:03d}.md",     # LLD-086.md
        f"LLD-{issue_number}-*.md",       # LLD-86-desc.md (unpadded)
        f"LLD-{issue_number}.md",         # LLD-86.md
        f"{issue_number}-*.md",           # 86-desc.md
    ]

    # Search done/ first (authoritative)
    for directory in [LLD_DONE_DIR, LLD_ACTIVE_DIR]:
        dir_path = root / directory
        if not dir_path.exists():
            continue

        for pattern in patterns:
            matches = list(dir_path.glob(pattern))
            if matches:
                # If multiple matches, use most recent by mtime
                if len(matches) > 1:
                    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return matches[0]

    return None


def load_lld_tracking(repo_root: Path | None = None) -> LLDStatusCache:
    """Load lld-status.json cache file.

    Args:
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        LLDStatusCache dict. Returns empty cache if file doesn't exist.
    """
    root = repo_root or get_repo_root()
    status_file = root / LLD_STATUS_FILE

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
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] Failed to load lld-status.json: {e}")
        return {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "issues": {},
        }


def save_lld_tracking(tracking: LLDStatusCache, repo_root: Path | None = None) -> None:
    """Save lld-status.json cache file.

    Args:
        tracking: LLDStatusCache dict to save.
        repo_root: Repository root path. Auto-detected if None.
    """
    root = repo_root or get_repo_root()
    status_file = root / LLD_STATUS_FILE

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
    repo_root: Path | None = None,
) -> None:
    """Update tracking for a single issue.

    Args:
        issue_number: GitHub issue number.
        lld_path: Path to LLD file (relative or absolute).
        review_info: Dict with has_gemini_review, final_verdict, etc.
        repo_root: Repository root path. Auto-detected if None.
    """
    root = repo_root or get_repo_root()

    # Make path relative to repo root for storage
    lld_path_obj = Path(lld_path)
    if lld_path_obj.is_absolute():
        try:
            lld_path = str(lld_path_obj.relative_to(root))
        except ValueError:
            pass  # Keep as-is if not under repo root

    # Load existing cache
    tracking = load_lld_tracking(root)

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
    save_lld_tracking(tracking, root)


def scan_all_llds(repo_root: Path | None = None) -> dict[int, LLDStatusEntry]:
    """Scan all LLD files and return status for each.

    Scans docs/lld/active/*.md and docs/lld/done/*.md.

    Args:
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Dict mapping issue_number -> LLDStatusEntry.
    """
    root = repo_root or get_repo_root()
    results: dict[int, LLDStatusEntry] = {}

    # Issue number extraction patterns
    issue_patterns = [
        re.compile(r"^LLD-(\d+)-"),   # LLD-086-desc.md
        re.compile(r"^LLD-(\d+)\."),  # LLD-086.md
        re.compile(r"^(\d+)-"),       # 86-desc.md
    ]

    for directory in [LLD_DONE_DIR, LLD_ACTIVE_DIR]:
        dir_path = root / directory
        if not dir_path.exists():
            continue

        for lld_file in dir_path.glob("*.md"):
            if lld_file.name.startswith("."):
                continue

            # Extract issue number from filename
            issue_number = None
            for pattern in issue_patterns:
                match = pattern.match(lld_file.name)
                if match:
                    issue_number = int(match.group(1))
                    break

            if issue_number is None:
                print(f"[WARN] Could not extract issue number from: {lld_file.name}")
                continue

            # Skip if already found in done/ (done/ is authoritative)
            if issue_number in results:
                continue

            # Read and analyze content
            try:
                content = lld_file.read_text(encoding="utf-8")
                review_info = detect_gemini_review(content)

                # Determine status
                if review_info["has_review"]:
                    if review_info["final_verdict"] == "APPROVED":
                        status = "approved"
                    else:
                        status = "blocked"
                else:
                    status = "draft"

                results[issue_number] = {
                    "lld_path": str(lld_file.relative_to(root)),
                    "status": status,
                    "has_gemini_review": review_info["has_review"],
                    "final_verdict": review_info["final_verdict"],
                    "last_review_date": review_info["last_review_date"],
                    "review_count": review_info["review_count"],
                }

            except OSError as e:
                print(f"[WARN] Failed to read {lld_file}: {e}")
                continue

    return results


def rebuild_lld_cache(repo_root: Path | None = None) -> int:
    """Rebuild lld-status.json from all LLD files.

    Args:
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Number of LLDs processed.
    """
    root = repo_root or get_repo_root()

    print("Scanning LLD files...")
    results = scan_all_llds(root)

    tracking: LLDStatusCache = {
        "version": "1.0",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "issues": {str(k): v for k, v in results.items()},
    }

    save_lld_tracking(tracking, root)

    # Print summary
    approved = sum(1 for e in results.values() if e["status"] == "approved")
    draft = sum(1 for e in results.values() if e["status"] == "draft")
    blocked = sum(1 for e in results.values() if e["status"] == "blocked")

    print(f"\nLLD Status Cache Rebuilt:")
    print(f"  Total LLDs: {len(results)}")
    print(f"  Approved: {approved}")
    print(f"  Draft: {draft}")
    print(f"  Blocked: {blocked}")
    print(f"\nSaved to: {root / LLD_STATUS_FILE}")

    return len(results)


def check_lld_status(issue_number: int, repo_root: Path | None = None) -> LLDStatusEntry | None:
    """Check LLD status for an issue.

    First checks cache, then falls back to file scan.

    Args:
        issue_number: GitHub issue number.
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        LLDStatusEntry if LLD exists, None otherwise.
    """
    root = repo_root or get_repo_root()

    # Check cache first
    tracking = load_lld_tracking(root)
    cached = tracking["issues"].get(str(issue_number))
    if cached:
        return cached

    # Fall back to file scan
    lld_path = get_lld_path_for_issue(issue_number, root)
    if not lld_path:
        return None

    # Read and analyze
    try:
        content = lld_path.read_text(encoding="utf-8")
        review_info = detect_gemini_review(content)

        # Determine status
        if review_info["has_review"]:
            if review_info["final_verdict"] == "APPROVED":
                status = "approved"
            else:
                status = "blocked"
        else:
            status = "draft"

        entry: LLDStatusEntry = {
            "lld_path": str(lld_path.relative_to(root)),
            "status": status,
            "has_gemini_review": review_info["has_review"],
            "final_verdict": review_info["final_verdict"],
            "last_review_date": review_info["last_review_date"],
            "review_count": review_info["review_count"],
        }

        # Update cache for next time
        update_lld_status(issue_number, str(lld_path), review_info, root)

        return entry

    except OSError:
        return None


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


# ---------------------------------------------------------------------------
# Workflow Audit Logging (Issue #101)
# ---------------------------------------------------------------------------

WORKFLOW_AUDIT_FILE = Path("docs/lineage/workflow-audit.jsonl")


def log_workflow_execution(
    target_repo: Path,
    issue_number: int,
    workflow_type: str,
    event: str,
    details: dict | None = None,
) -> None:
    """Log workflow execution to central audit file.

    Creates a JSONL (JSON Lines) audit trail of all workflow executions.
    This enables post-hoc analysis of workflow runs, failures, and patterns.

    Args:
        target_repo: Path to the target repository.
        issue_number: GitHub issue number being processed.
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
        "issue_number": issue_number,
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


def get_workflow_audit_summary(
    target_repo: Path,
    issue_number: int | None = None,
) -> list[dict]:
    """Read workflow audit entries, optionally filtered by issue.

    Args:
        target_repo: Path to the target repository.
        issue_number: Optional filter by issue number.

    Returns:
        List of audit entries (most recent last).
    """
    log_file = target_repo / WORKFLOW_AUDIT_FILE

    if not log_file.exists():
        return []

    entries = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        if issue_number is None or entry.get("issue_number") == issue_number:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return []

    return entries
