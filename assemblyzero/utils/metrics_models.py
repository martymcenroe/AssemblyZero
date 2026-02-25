"""Data models for cross-project metrics aggregation.

Issue #333: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking.
"""

from __future__ import annotations

from typing import Optional, TypedDict


class TrackedRepoConfig(TypedDict):
    """Configuration for a single tracked repository."""

    owner: str
    name: str
    full_name: str
    enabled: bool


class MetricsCollectionConfig(TypedDict):
    """Top-level configuration for the metrics collector."""

    repos: list[TrackedRepoConfig]
    lookback_days: int
    output_dir: str
    cache_ttl_seconds: int
    github_token_env: str


class RepoIssueMetrics(TypedDict):
    """Issue velocity metrics for a single repository."""

    repo: str
    period_start: str
    period_end: str
    issues_opened: int
    issues_closed: int
    issues_open_current: int
    avg_close_time_hours: Optional[float]
    issues_by_label: dict[str, int]


class RepoWorkflowMetrics(TypedDict):
    """Workflow usage metrics for a single repository."""

    repo: str
    lld_count: int
    requirements_workflows: int
    implementation_workflows: int
    tdd_workflows: int
    report_count: int


class RepoGeminiMetrics(TypedDict):
    """Gemini review outcome metrics for a single repository."""

    repo: str
    total_reviews: int
    approvals: int
    blocks: int
    approval_rate: Optional[float]


class PerRepoMetrics(TypedDict):
    """Combined metrics for a single repository."""

    repo: str
    issues: RepoIssueMetrics
    workflows: RepoWorkflowMetrics
    gemini: RepoGeminiMetrics


class AggregateTotals(TypedDict):
    """Aggregate totals across all repos."""

    issues_opened: int
    issues_closed: int
    issues_open_current: int
    avg_close_time_hours: Optional[float]
    lld_count: int
    total_workflows: int
    gemini_reviews: int
    gemini_approval_rate: Optional[float]
    report_count: int


class CrossProjectMetrics(TypedDict):
    """Aggregated metrics across all tracked repositories."""

    generated_at: str
    period_start: str
    period_end: str
    repos_tracked: int
    repos_collected: int
    repos_failed: list[str]
    totals: AggregateTotals
    per_repo: list[PerRepoMetrics]