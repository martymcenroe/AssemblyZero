#!/usr/bin/env python
"""Backfill audit directories for existing GitHub issues.

Issue #72: Backfill Audit Directory Structure

This tool fetches existing GitHub issues and generates standardized audit
directories with issue content, comments, and metadata files.

Usage:
    # Dry run to preview
    python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS --dry-run

    # Process single repo
    python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS --verbose

    # Skip existing directories
    python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS --skip-existing

    # Force update managed files only
    python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS --force

    # Limit number of issues (for testing)
    python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS --limit 5
"""

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.workflows.requirements.audit import generate_slug


# =============================================================================
# Constants
# =============================================================================

AUDIT_ACTIVE_DIR = Path("docs/audit/active")
AUDIT_DONE_DIR = Path("docs/audit/done")

# Managed file prefixes (can be overwritten with --force)
MANAGED_FILES = ("001-", "002-", "003-")

# Default rate limit delay (seconds between API calls)
DEFAULT_DELAY = 0.5

# Exponential backoff settings
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0
BACKOFF_MULTIPLIER = 2.0


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Issue:
    """Represents a GitHub issue."""

    number: int
    title: str
    body: str
    state: str  # "open" or "closed"
    created_at: str
    updated_at: str
    closed_at: str | None
    author: str
    labels: list[str]
    assignees: list[str]
    url: str
    comments_url: str


@dataclass
class Comment:
    """Represents a GitHub issue comment."""

    id: int
    author: str
    body: str
    created_at: str
    url: str


@dataclass
class BackfillResult:
    """Result of backfilling a single issue."""

    issue_number: int
    slug: str
    status: str  # "created", "updated", "skipped", "error"
    message: str


# =============================================================================
# GitHub API Functions
# =============================================================================


def run_gh_command(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a gh CLI command safely.

    Args:
        args: Command arguments (without 'gh' prefix).
        timeout: Command timeout in seconds.

    Returns:
        CompletedProcess result.

    Raises:
        subprocess.TimeoutExpired: If command times out.
        subprocess.CalledProcessError: If command fails.
    """
    cmd = ["gh"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        shell=False,  # SECURITY: Never use shell=True
    )


def check_gh_auth() -> bool:
    """Check if gh CLI is authenticated.

    Returns:
        True if authenticated, False otherwise.
    """
    try:
        result = run_gh_command(["auth", "status"])
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def fetch_issues(
    repo: str,
    state: str = "all",
    limit: int | None = None,
) -> list[Issue]:
    """Fetch issues from a GitHub repository.

    Args:
        repo: Repository in owner/name format.
        state: Issue state filter ("open", "closed", "all").
        limit: Maximum number of issues to fetch.

    Returns:
        List of Issue objects.

    Raises:
        RuntimeError: If API call fails.
    """
    args = [
        "issue", "list",
        "--repo", repo,
        "--state", state,
        "--json", "number,title,body,state,createdAt,updatedAt,closedAt,author,labels,assignees,url,comments",
    ]

    if limit:
        args.extend(["--limit", str(limit)])
    else:
        args.extend(["--limit", "1000"])  # Fetch up to 1000

    result = run_gh_command(args, timeout=60)

    if result.returncode != 0:
        raise RuntimeError(f"Failed to fetch issues: {result.stderr}")

    data = json.loads(result.stdout)
    issues = []

    for item in data:
        issues.append(Issue(
            number=item["number"],
            title=item["title"],
            body=item.get("body") or "",
            state=item["state"],
            created_at=item["createdAt"],
            updated_at=item["updatedAt"],
            closed_at=item.get("closedAt"),
            author=item["author"]["login"] if item.get("author") else "unknown",
            labels=[label["name"] for label in item.get("labels", [])],
            assignees=[a["login"] for a in item.get("assignees", [])],
            url=item["url"],
            comments_url=item["url"] + "/comments",
        ))

    return issues


def fetch_comments(repo: str, issue_number: int) -> list[Comment]:
    """Fetch comments for a specific issue.

    Args:
        repo: Repository in owner/name format.
        issue_number: Issue number.

    Returns:
        List of Comment objects.
    """
    args = [
        "api",
        f"repos/{repo}/issues/{issue_number}/comments",
        "--jq", ".",
    ]

    result = run_gh_command(args, timeout=30)

    if result.returncode != 0:
        return []  # Fail open - return empty list

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    comments = []
    for item in data:
        comments.append(Comment(
            id=item["id"],
            author=item["user"]["login"] if item.get("user") else "unknown",
            body=item.get("body") or "",
            created_at=item["created_at"],
            url=item["html_url"],
        ))

    return comments


def fetch_with_backoff(
    fetch_func,
    *args,
    max_retries: int = MAX_RETRIES,
    **kwargs,
) -> Any:
    """Fetch with exponential backoff for rate limits.

    Args:
        fetch_func: Function to call.
        *args: Positional arguments for fetch_func.
        max_retries: Maximum retry attempts.
        **kwargs: Keyword arguments for fetch_func.

    Returns:
        Result of fetch_func.

    Raises:
        RuntimeError: If all retries exhausted.
    """
    backoff = INITIAL_BACKOFF

    for attempt in range(max_retries + 1):
        try:
            return fetch_func(*args, **kwargs)
        except RuntimeError as e:
            if "rate limit" in str(e).lower() or "429" in str(e):
                if attempt < max_retries:
                    print(f"  Rate limited, waiting {backoff:.1f}s...")
                    time.sleep(backoff)
                    backoff *= BACKOFF_MULTIPLIER
                    continue
            raise

    raise RuntimeError("Max retries exhausted")


# =============================================================================
# Slug Generation
# =============================================================================


def generate_issue_slug(title: str) -> str:
    """Generate a slug from issue title.

    Args:
        title: Issue title.

    Returns:
        URL-safe slug.
    """
    # Use the same logic as generate_slug from requirements/audit.py
    # but adapted for titles instead of filenames
    slug = title.lower()
    # Replace spaces and underscores with hyphens
    slug = slug.replace(" ", "-").replace("_", "-")
    # Remove any non-alphanumeric except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Truncate to reasonable length
    slug = slug[:50]
    return slug.strip("-")


# =============================================================================
# File Generation
# =============================================================================


def generate_issue_markdown(issue: Issue) -> str:
    """Generate 001-issue.md content.

    Args:
        issue: Issue object.

    Returns:
        Markdown content.
    """
    lines = [
        f"# #{issue.number}: {issue.title}",
        "",
        f"**URL:** {issue.url}",
        f"**Author:** @{issue.author}",
        f"**State:** {issue.state}",
        f"**Created:** {issue.created_at}",
        f"**Updated:** {issue.updated_at}",
    ]

    if issue.closed_at:
        lines.append(f"**Closed:** {issue.closed_at}")

    if issue.labels:
        lines.append(f"**Labels:** {', '.join(issue.labels)}")

    if issue.assignees:
        lines.append(f"**Assignees:** {', '.join('@' + a for a in issue.assignees)}")

    lines.extend([
        "",
        "---",
        "",
        issue.body or "*No description provided.*",
    ])

    return "\n".join(lines)


def generate_comments_markdown(issue: Issue, comments: list[Comment]) -> str:
    """Generate 002-comments.md content.

    Args:
        issue: Issue object.
        comments: List of Comment objects.

    Returns:
        Markdown content.
    """
    lines = [
        f"# Comments for #{issue.number}: {issue.title}",
        "",
        f"**Total Comments:** {len(comments)}",
        "",
    ]

    if not comments:
        lines.append("*No comments on this issue.*")
    else:
        for i, comment in enumerate(comments, 1):
            lines.extend([
                "---",
                "",
                f"## Comment {i}",
                "",
                f"**Author:** @{comment.author}",
                f"**Date:** {comment.created_at}",
                f"**URL:** {comment.url}",
                "",
                comment.body or "*Empty comment.*",
                "",
            ])

    return "\n".join(lines)


def generate_metadata_json(issue: Issue, comments: list[Comment]) -> str:
    """Generate 003-metadata.json content.

    Args:
        issue: Issue object.
        comments: List of Comment objects.

    Returns:
        JSON content.
    """
    metadata = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generator": "backfill_issue_audit.py",
        "issue": {
            "number": issue.number,
            "title": issue.title,
            "state": issue.state,
            "author": issue.author,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "closed_at": issue.closed_at,
            "labels": issue.labels,
            "assignees": issue.assignees,
            "url": issue.url,
        },
        "comments": {
            "count": len(comments),
            "authors": list(set(c.author for c in comments)),
        },
    }

    return json.dumps(metadata, indent=2) + "\n"


# =============================================================================
# Directory Operations
# =============================================================================


def get_audit_dir(issue: Issue, repo_root: Path) -> Path:
    """Get the audit directory path for an issue.

    Args:
        issue: Issue object.
        repo_root: Repository root path.

    Returns:
        Path to audit directory.
    """
    slug = generate_issue_slug(issue.title)
    dir_name = f"{issue.number}-{slug}"

    if issue.state == "open":
        return repo_root / AUDIT_ACTIVE_DIR / dir_name
    else:
        return repo_root / AUDIT_DONE_DIR / dir_name


def is_managed_file(filename: str) -> bool:
    """Check if a file is a managed file (can be overwritten with --force).

    Args:
        filename: File name.

    Returns:
        True if managed file.
    """
    return filename.startswith(MANAGED_FILES)


def write_audit_files(
    audit_dir: Path,
    issue: Issue,
    comments: list[Comment],
    force: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Write audit files to directory.

    Args:
        audit_dir: Audit directory path.
        issue: Issue object.
        comments: List of Comment objects.
        force: If True, overwrite managed files.
        dry_run: If True, don't actually write.

    Returns:
        List of files written/would be written.
    """
    files_written = []

    # File definitions
    files = [
        ("001-issue.md", generate_issue_markdown(issue)),
        ("002-comments.md", generate_comments_markdown(issue, comments)),
        ("003-metadata.json", generate_metadata_json(issue, comments)),
    ]

    for filename, content in files:
        file_path = audit_dir / filename

        # Check if we should write
        if file_path.exists() and not force:
            continue

        if dry_run:
            files_written.append(filename)
        else:
            file_path.write_text(content, encoding="utf-8")
            files_written.append(filename)

    return files_written


# =============================================================================
# Backfill Logic
# =============================================================================


def backfill_issue(
    issue: Issue,
    repo: str,
    repo_root: Path,
    skip_existing: bool = False,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    delay: float = DEFAULT_DELAY,
) -> BackfillResult:
    """Backfill audit directory for a single issue.

    Args:
        issue: Issue object.
        repo: Repository in owner/name format.
        repo_root: Repository root path.
        skip_existing: Skip if directory exists.
        force: Overwrite managed files.
        dry_run: Don't actually write.
        verbose: Print verbose output.
        delay: Delay between API calls.

    Returns:
        BackfillResult object.
    """
    slug = generate_issue_slug(issue.title)
    audit_dir = get_audit_dir(issue, repo_root)

    # Check existing
    if audit_dir.exists():
        if skip_existing:
            return BackfillResult(
                issue_number=issue.number,
                slug=slug,
                status="skipped",
                message="Directory exists (--skip-existing)",
            )
        elif not force:
            return BackfillResult(
                issue_number=issue.number,
                slug=slug,
                status="skipped",
                message="Directory exists (use --force to update)",
            )

    # Fetch comments
    if verbose:
        print(f"  Fetching comments for #{issue.number}...")

    try:
        comments = fetch_with_backoff(fetch_comments, repo, issue.number)
    except RuntimeError as e:
        return BackfillResult(
            issue_number=issue.number,
            slug=slug,
            status="error",
            message=f"Failed to fetch comments: {e}",
        )

    # Rate limit delay
    if delay > 0:
        time.sleep(delay)

    # Create directory
    if not dry_run:
        audit_dir.mkdir(parents=True, exist_ok=True)

    # Write files
    try:
        files_written = write_audit_files(
            audit_dir, issue, comments, force=force, dry_run=dry_run
        )
    except OSError as e:
        return BackfillResult(
            issue_number=issue.number,
            slug=slug,
            status="error",
            message=f"Failed to write files: {e}",
        )

    if not files_written:
        return BackfillResult(
            issue_number=issue.number,
            slug=slug,
            status="skipped",
            message="No files needed updating",
        )

    status = "created" if not audit_dir.exists() or dry_run else "updated"
    return BackfillResult(
        issue_number=issue.number,
        slug=slug,
        status=status,
        message=f"Files: {', '.join(files_written)}",
    )


def backfill_repo(
    repo: str,
    repo_root: Path,
    skip_existing: bool = False,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    quiet: bool = False,
    delay: float = DEFAULT_DELAY,
    limit: int | None = None,
) -> list[BackfillResult]:
    """Backfill audit directories for all issues in a repository.

    Args:
        repo: Repository in owner/name format.
        repo_root: Repository root path.
        skip_existing: Skip if directory exists.
        force: Overwrite managed files.
        dry_run: Don't actually write.
        verbose: Print verbose output.
        quiet: Suppress non-error output.
        delay: Delay between API calls.
        limit: Maximum number of issues to process.

    Returns:
        List of BackfillResult objects.
    """
    results = []

    # Fetch issues
    if not quiet:
        print(f"Fetching issues from {repo}...")

    try:
        issues = fetch_with_backoff(fetch_issues, repo, state="all", limit=limit)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return results

    if not quiet:
        print(f"Found {len(issues)} issues")
        if dry_run:
            print("DRY RUN: No files will be written")
        print()

    # Process each issue
    for i, issue in enumerate(issues, 1):
        if not quiet:
            state_indicator = "[OPEN]" if issue.state == "open" else "[CLOSED]"
            print(f"[{i}/{len(issues)}] {state_indicator} #{issue.number}: {issue.title[:50]}...")

        result = backfill_issue(
            issue=issue,
            repo=repo,
            repo_root=repo_root,
            skip_existing=skip_existing,
            force=force,
            dry_run=dry_run,
            verbose=verbose,
            delay=delay,
        )

        results.append(result)

        if verbose or result.status == "error":
            status_icons = {
                "created": "+",
                "updated": "~",
                "skipped": "-",
                "error": "!",
            }
            icon = status_icons.get(result.status, "?")
            print(f"  [{icon}] {result.status}: {result.message}")

    return results


# =============================================================================
# CLI
# =============================================================================


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Arguments to parse (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Backfill audit directories for existing GitHub issues.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to preview
  python tools/backfill_issue_audit.py --repo owner/name --dry-run

  # Process with verbose output
  python tools/backfill_issue_audit.py --repo owner/name --verbose

  # Skip existing directories
  python tools/backfill_issue_audit.py --repo owner/name --skip-existing

  # Force update managed files
  python tools/backfill_issue_audit.py --repo owner/name --force
        """,
    )

    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub repository in owner/name format",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip issues that already have audit directories",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite managed files (001-, 002-, 003-*)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose output",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress non-error output",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay between API calls in seconds (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of issues to process",
    )
    parser.add_argument(
        "--root",
        type=str,
        help="Repository root path (default: current directory)",
    )

    return parser.parse_args(args)


def print_summary(results: list[BackfillResult], quiet: bool = False) -> None:
    """Print summary of backfill results.

    Args:
        results: List of BackfillResult objects.
        quiet: Suppress output.
    """
    if quiet:
        return

    created = sum(1 for r in results if r.status == "created")
    updated = sum(1 for r in results if r.status == "updated")
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = sum(1 for r in results if r.status == "error")

    print()
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"  Created: {created}")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {errors}")
    print(f"  Total:   {len(results)}")
    print("=" * 50)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    args = parse_args()

    # Validate repo format
    if "/" not in args.repo:
        print(f"ERROR: Invalid repo format: {args.repo}", file=sys.stderr)
        print("Expected format: owner/name", file=sys.stderr)
        return 1

    # Check gh auth
    if not check_gh_auth():
        print("ERROR: gh CLI not authenticated", file=sys.stderr)
        print("Run: gh auth login", file=sys.stderr)
        return 1

    # Resolve repo root
    if args.root:
        repo_root = Path(args.root).resolve()
    else:
        repo_root = Path.cwd().resolve()

    # Run backfill
    results = backfill_repo(
        repo=args.repo,
        repo_root=repo_root,
        skip_existing=args.skip_existing,
        force=args.force,
        dry_run=args.dry_run,
        verbose=args.verbose,
        quiet=args.quiet,
        delay=args.delay,
        limit=args.limit,
    )

    # Print summary
    print_summary(results, quiet=args.quiet)

    # Return error if any failures
    errors = sum(1 for r in results if r.status == "error")
    if errors > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
