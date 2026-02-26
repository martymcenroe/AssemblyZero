"""Data models for cross-project metrics.

Issue #333: Typed data structures for repo metrics, aggregated metrics, and config.
"""

from __future__ import annotations

from typing import Any, TypedDict


class TrackedReposConfig(TypedDict):
    """Configuration for tracked repositories."""

    repos: list[str]
    cache_ttl_minutes: int
    github_token_env: str


class RepoMetrics(TypedDict):
    """Metrics collected for a single repository."""

    repo: str
    period_start: str
    period_end: str
    issues_created: int
    issues_closed: int
    issues_open: int
    workflows_used: dict[str, int]
    llds_generated: int
    gemini_reviews: int
    gemini_approvals: int
    gemini_blocks: int
    collection_timestamp: str


class AggregatedMetrics(TypedDict):
    """Cross-project aggregated metrics."""

    repos_tracked: int
    repos_reachable: int
    period_start: str
    period_end: str
    total_issues_created: int
    total_issues_closed: int
    total_issues_open: int
    total_llds_generated: int
    total_gemini_reviews: int
    gemini_approval_rate: float
    workflows_by_type: dict[str, int]
    per_repo: list[RepoMetrics]
    generated_at: str


class CacheEntry(TypedDict):
    """A cached metrics entry with expiry."""

    repo: str
    metrics: RepoMetrics
    cached_at: str
    expires_at: str


_NON_NEGATIVE_INT_FIELDS: list[str] = [
    "issues_created",
    "issues_closed",
    "issues_open",
    "llds_generated",
    "gemini_reviews",
    "gemini_approvals",
    "gemini_blocks",
]


def validate_repo_metrics(metrics: dict[str, Any]) -> None:
    """Validate a metrics dict. Raises ValueError on invalid data.

    Checks that all integer fields are non-negative and repo is non-empty.
    """
    repo = metrics.get("repo", "")
    if not repo:
        msg = "repo cannot be empty"
        raise ValueError(msg)

    for field in _NON_NEGATIVE_INT_FIELDS:
        value = metrics.get(field)
        if value is not None and value < 0:
            msg = f"{field} must be non-negative, got {value}"
            raise ValueError(msg)


def create_repo_metrics(
    *,
    repo: str,
    period_start: str,
    period_end: str,
    issues_created: int,
    issues_closed: int,
    issues_open: int,
    workflows_used: dict[str, int],
    llds_generated: int,
    gemini_reviews: int,
    gemini_approvals: int,
    gemini_blocks: int,
    collection_timestamp: str,
) -> RepoMetrics:
    """Create and validate a RepoMetrics dict.

    Raises ValueError if any field is invalid.
    """
    result: RepoMetrics = {
        "repo": repo,
        "period_start": period_start,
        "period_end": period_end,
        "issues_created": issues_created,
        "issues_closed": issues_closed,
        "issues_open": issues_open,
        "workflows_used": workflows_used,
        "llds_generated": llds_generated,
        "gemini_reviews": gemini_reviews,
        "gemini_approvals": gemini_approvals,
        "gemini_blocks": gemini_blocks,
        "collection_timestamp": collection_timestamp,
    }
    validate_repo_metrics(result)
    return result