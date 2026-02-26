

```python
"""Per-repo metrics collection via GitHub API.

Issue #333: Fetch issue data, lineage counts, and verdict files per repository.
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timedelta, timezone

from github import Github, GithubException, UnknownObjectException
from github.ContentFile import ContentFile
from github.Repository import Repository

from assemblyzero.metrics.models import RepoMetrics, create_repo_metrics

logger = logging.getLogger(__name__)

_WORKFLOW_LABEL_PREFIX: str = "workflow:"
_APPROVE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Verdict|Status):\s*APPROVE", re.IGNORECASE
)
_BLOCK_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Verdict|Status):\s*BLOCK", re.IGNORECASE
)


class CollectionError(Exception):
    """Raised when metrics collection fails for a repository."""


def collect_repo_metrics(
    repo_full_name: str,
    github_token: str,
    period_days: int = 30,
) -> RepoMetrics:
    """Collect all metrics for a single repository.

    Fetches issues, scans for lineage folders and verdict files.
    Uses PyGithub for API access.
    Raises CollectionError if repo is unreachable.
    """
    try:
        if github_token:
            gh = Github(github_token)
        else:
            logger.warning("No GitHub token provided. Only public repos accessible.")
            gh = Github()

        repo = gh.get_repo(repo_full_name)
    except UnknownObjectException as exc:
        msg = f"Failed to access repo '{repo_full_name}': {exc.data.get('message', str(exc))}"
        raise CollectionError(msg) from exc
    except GithubException as exc:
        msg = f"GitHub API error for '{repo_full_name}': {exc.data.get('message', str(exc)) if hasattr(exc, 'data') and exc.data else str(exc)}"
        raise CollectionError(msg) from exc

    now = datetime.now(tz=timezone.utc)
    period_end = now
    period_start = now - timedelta(days=period_days)

    created, closed, open_now = count_issues_in_period(repo, period_start, period_end)
    workflows = detect_workflows_used(repo)
    llds = count_lineage_artifacts(repo)
    total_reviews, approvals, blocks = count_gemini_verdicts(repo)

    return create_repo_metrics(
        repo=repo_full_name,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        issues_created=created,
        issues_closed=closed,
        issues_open=open_now,
        workflows_used=workflows,
        llds_generated=llds,
        gemini_reviews=total_reviews,
        gemini_approvals=approvals,
        gemini_blocks=blocks,
        collection_timestamp=now.isoformat(),
    )


def count_issues_in_period(
    repo: Repository,
    period_start: datetime,
    period_end: datetime,
) -> tuple[int, int, int]:
    """Count issues created, closed, and currently open.

    Returns (created_in_period, closed_in_period, currently_open).
    Uses 'since' parameter to minimize API pages fetched.
    """
    created = 0
    closed = 0

    # Get issues created since period_start (all states)
    all_issues = repo.get_issues(state="all", since=period_start)
    for issue in all_issues:
        if issue.pull_request is not None:
            continue  # Skip PRs
        if issue.created_at and period_start <= issue.created_at <= period_end:
            created += 1
        if (
            issue.closed_at
            and period_start <= issue.closed_at <= period_end
        ):
            closed += 1

    # Count currently open issues
    open_issues = repo.get_issues(state="open")
    open_now = sum(1 for i in open_issues if i.pull_request is None)

    return (created, closed, open_now)


def detect_workflows_used(repo: Repository) -> dict[str, int]:
    """Detect workflow types by scanning issue labels and LLD filenames.

    Scans labels: 'workflow:requirements', 'workflow:tdd', etc.
    Falls back to heuristic: LLD filenames.
    """
    workflow_counts: dict[str, int] = {}

    # Primary: scan issue labels
    issues = repo.get_issues(state="all")
    for issue in issues:
        if issue.pull_request is not None:
            continue
        for label in issue.labels:
            label_name = label.name if hasattr(label, "name") else str(label)
            if label_name.startswith(_WORKFLOW_LABEL_PREFIX):
                workflow_type = label_name[len(_WORKFLOW_LABEL_PREFIX):]
                workflow_counts[workflow_type] = workflow_counts.get(workflow_type, 0) + 1

    # Fallback: heuristic from LLD filenames if no labels found
    if not workflow_counts:
        workflow_counts = _detect_workflows_from_lld_filenames(repo)

    return workflow_counts


def _detect_workflows_from_lld_filenames(repo: Repository) -> dict[str, int]:
    """Heuristic fallback: detect workflows from LLD filenames."""
    workflow_counts: dict[str, int] = {}
    keyword_map = {
        "requirements": "requirements",
        "tdd": "tdd",
        "implementation": "implementation",
        "design": "requirements",
    }

    for dir_path in ("docs/lld/active", "docs/lld/done"):
        try:
            contents = repo.get_contents(dir_path)
            if not isinstance(contents, list):
                contents = [contents]
            for item in contents:
                name_lower = item.name.lower()
                for keyword, workflow_type in keyword_map.items():
                    if keyword in name_lower:
                        workflow_counts[workflow_type] = (
                            workflow_counts.get(workflow_type, 0) + 1
                        )
                        break  # One workflow type per file
        except (UnknownObjectException, GithubException):
            continue

    return workflow_counts


def count_lineage_artifacts(repo: Repository) -> int:
    """Count LLD folders in docs/lld/active/ and docs/lld/done/ directories.

    Returns 0 if directories don't exist.
    """
    count = 0
    for dir_path in ("docs/lld/active", "docs/lld/done"):
        try:
            contents = repo.get_contents(dir_path)
            if isinstance(contents, list):
                count += len(contents)
            else:
                count += 1
        except (UnknownObjectException, GithubException):
            logger.debug("Directory %s not found in %s", dir_path, repo.full_name)
            continue
    return count


def _get_file_content(content_file: ContentFile) -> str:
    """Decode file content from a GitHub ContentFile."""
    if content_file.content is not None:
        return base64.b64decode(content_file.content).decode("utf-8", errors="replace")
    return ""


def count_gemini_verdicts(repo: Repository) -> tuple[int, int, int]:
    """Count Gemini verdict files and their outcomes.

    Scans docs/reports/*/gemini-*.md files.
    Returns (total_reviews, approvals, blocks).
    """
    total = 0
    approvals = 0
    blocks = 0

    try:
        reports_contents = repo.get_contents("docs/reports")
        if not isinstance(reports_contents, list):
            reports_contents = [reports_contents]
    except (UnknownObjectException, GithubException):
        logger.debug("docs/reports/ not found in %s", repo.full_name)
        return (0, 0, 0)

    for item in reports_contents:
        if item.type != "dir":
            continue
        try:
            dir_contents = repo.get_contents(item.path)
            if not isinstance(dir_contents, list):
                dir_contents = [dir_contents]
            for file_item in dir_contents:
                if not file_item.name.startswith("gemini-") or not file_item.name.endswith(".md"):
                    continue
                total += 1
                try:
                    content = _get_file_content(file_item)
                    if _APPROVE_PATTERN.search(content):
                        approvals += 1
                    elif _BLOCK_PATTERN.search(content):
                        blocks += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Could not read verdict file %s: %s", file_item.path, exc
                    )
        except (UnknownObjectException, GithubException):
            continue

    return (total, approvals, blocks)
```
