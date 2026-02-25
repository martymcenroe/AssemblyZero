```python
"""Aggregation engine for cross-project metrics.

Issue #333: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking.

Combines per-repo data collected via GitHubMetricsClient into unified
cross-project metrics with aggregate totals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from assemblyzero.utils.github_metrics_client import GitHubMetricsClient
from assemblyzero.utils.metrics_models import (
    AggregateTotals,
    CrossProjectMetrics,
    MetricsCollectionConfig,
    PerRepoMetrics,
    RepoGeminiMetrics,
    RepoIssueMetrics,
    RepoWorkflowMetrics,
    TrackedRepoConfig,
)

logger = logging.getLogger(__name__)

# Labels that indicate specific workflow types
_REQUIREMENTS_LABELS = {"requirements", "lld"}
_IMPLEMENTATION_LABELS = {"implementation"}
_TDD_LABELS = {"tdd", "testing"}


class MetricsAggregator:
    """Aggregates per-repo metrics into cross-project totals."""

    def __init__(
        self, client: GitHubMetricsClient, config: MetricsCollectionConfig
    ) -> None:
        """Initialize aggregator with API client and config.

        Args:
            client: Configured GitHubMetricsClient instance.
            config: Validated MetricsCollectionConfig.
        """
        self._client = client
        self._config = config

    def collect_repo_metrics(self, repo: TrackedRepoConfig) -> PerRepoMetrics:
        """Collect all metrics for a single repository.

        Orchestrates calls to collect issue, workflow, and Gemini metrics.
        If any sub-collection fails, that section returns zero/empty values
        rather than failing the entire repo collection.

        Args:
            repo: Repository configuration.

        Returns:
            PerRepoMetrics with all collected data.
        """
        repo_full_name = repo["full_name"]
        now = datetime.now(tz=timezone.utc)
        period_end = now.strftime("%Y-%m-%d")
        period_start = (
            now - timedelta(days=self._config["lookback_days"])
        ).strftime("%Y-%m-%d")

        # Collect issue metrics with fault isolation
        try:
            issues = self.collect_issue_metrics(repo_full_name, period_start, period_end)
        except Exception:
            logger.warning(
                "Failed to collect issue metrics for %s", repo_full_name, exc_info=True
            )
            issues = _empty_issue_metrics(repo_full_name, period_start, period_end)

        # Collect workflow metrics with fault isolation
        try:
            workflows = self.collect_workflow_metrics(repo_full_name)
        except Exception:
            logger.warning(
                "Failed to collect workflow metrics for %s",
                repo_full_name,
                exc_info=True,
            )
            workflows = _empty_workflow_metrics(repo_full_name)

        # Collect Gemini metrics with fault isolation
        try:
            gemini = self.collect_gemini_metrics(repo_full_name)
        except Exception:
            logger.warning(
                "Failed to collect Gemini metrics for %s",
                repo_full_name,
                exc_info=True,
            )
            gemini = _empty_gemini_metrics(repo_full_name)

        return PerRepoMetrics(
            repo=repo_full_name,
            issues=issues,
            workflows=workflows,
            gemini=gemini,
        )

    def collect_issue_metrics(
        self, repo_full_name: str, since: str, until: str
    ) -> RepoIssueMetrics:
        """Collect issue velocity metrics for a repository.

        Args:
            repo_full_name: 'owner/name' format
            since: Period start (ISO 8601 date, e.g. '2026-01-25')
            until: Period end (ISO 8601 date, e.g. '2026-02-24')

        Returns:
            RepoIssueMetrics with counts, averages, and label breakdowns.
        """
        since_iso = f"{since}T00:00:00Z"
        issues = self._client.fetch_issues(repo_full_name, since=since_iso, state="all")

        issues_opened = 0
        issues_closed = 0
        issues_open_current = 0
        close_times_hours: list[float] = []
        label_counts: dict[str, int] = {}

        for issue in issues:
            created_at = issue.get("created_at")
            closed_at = issue.get("closed_at")
            state = issue.get("state", "")
            labels = issue.get("labels", [])

            # Count opened (all issues in the period)
            issues_opened += 1

            # Count currently open
            if state == "open":
                issues_open_current += 1

            # Count closed and compute close time
            if state == "closed" and closed_at:
                issues_closed += 1
                if created_at:
                    try:
                        created_dt = datetime.fromisoformat(
                            created_at.replace("Z", "+00:00")
                        )
                        closed_dt = datetime.fromisoformat(
                            closed_at.replace("Z", "+00:00")
                        )
                        delta_hours = (
                            closed_dt - created_dt
                        ).total_seconds() / 3600.0
                        close_times_hours.append(delta_hours)
                    except (ValueError, TypeError):
                        pass

            # Count labels
            for label in labels:
                label_lower = label.lower() if isinstance(label, str) else str(label)
                label_counts[label_lower] = label_counts.get(label_lower, 0) + 1

        avg_close_time: Optional[float] = None
        if close_times_hours:
            avg_close_time = round(
                sum(close_times_hours) / len(close_times_hours), 2
            )

        return RepoIssueMetrics(
            repo=repo_full_name,
            period_start=since,
            period_end=until,
            issues_opened=issues_opened,
            issues_closed=issues_closed,
            issues_open_current=issues_open_current,
            avg_close_time_hours=avg_close_time,
            issues_by_label=label_counts,
        )

    def collect_workflow_metrics(self, repo_full_name: str) -> RepoWorkflowMetrics:
        """Collect workflow usage metrics by inspecting repo contents.

        Checks for:
        - docs/lld/active/ or docs/lld/ (LLD files)
        - docs/reports/ (report directories)
        - Workflow labels on issues (requirements, implementation, tdd)

        Args:
            repo_full_name: 'owner/name' format

        Returns:
            RepoWorkflowMetrics with counts per workflow type.
        """
        # Count LLD files
        lld_contents = self._client.fetch_repo_contents(
            repo_full_name, "docs/lld/active"
        )
        if not lld_contents:
            lld_contents = self._client.fetch_repo_contents(
                repo_full_name, "docs/lld"
            )
        lld_count = sum(
            1
            for item in lld_contents
            if item.get("type") == "file" and item.get("name", "").endswith(".md")
        )

        # Count report directories
        report_contents = self._client.fetch_repo_contents(
            repo_full_name, "docs/reports"
        )
        report_count = sum(
            1 for item in report_contents if item.get("type") == "dir"
        )

        # Count workflow labels from cached issues
        requirements_count = 0
        implementation_count = 0
        tdd_count = 0

        # Fetch issues to count workflow labels (will use cache if available)
        now = datetime.now(tz=timezone.utc)
        since = (
            now - timedelta(days=self._config["lookback_days"])
        ).strftime("%Y-%m-%dT00:00:00Z")

        try:
            issues = self._client.fetch_issues(repo_full_name, since=since, state="all")
            for issue in issues:
                labels = {
                    lbl.lower() if isinstance(lbl, str) else str(lbl)
                    for lbl in issue.get("labels", [])
                }
                if labels & _REQUIREMENTS_LABELS:
                    requirements_count += 1
                if labels & _IMPLEMENTATION_LABELS:
                    implementation_count += 1
                if labels & _TDD_LABELS:
                    tdd_count += 1
        except Exception:
            logger.debug(
                "Could not fetch issues for workflow label counting: %s",
                repo_full_name,
            )

        return RepoWorkflowMetrics(
            repo=repo_full_name,
            lld_count=lld_count,
            requirements_workflows=requirements_count,
            implementation_workflows=implementation_count,
            tdd_workflows=tdd_count,
            report_count=report_count,
        )

    def collect_gemini_metrics(self, repo_full_name: str) -> RepoGeminiMetrics:
        """Collect Gemini review outcome metrics.

        Inspects verdict files in the repository for APPROVE/BLOCK counts.
        Looks in standard locations:
        - docs/reports/ subdirectories for gemini-verdict* files
        - .gemini-reviews/ (if present)

        Args:
            repo_full_name: 'owner/name' format

        Returns:
            RepoGeminiMetrics with review counts and approval rate.
        """
        approvals = 0
        blocks = 0

        # Check docs/reports/ for verdict files
        report_dirs = self._client.fetch_repo_contents(
            repo_full_name, "docs/reports"
        )
        for report_dir in report_dirs:
            if report_dir.get("type") != "dir":
                continue
            dir_path = report_dir.get("path", "")
            dir_contents = self._client.fetch_repo_contents(
                repo_full_name, dir_path
            )
            for item in dir_contents:
                name = item.get("name", "").lower()
                if "gemini-verdict" in name or "gemini_verdict" in name:
                    # Parse verdict from file name conventions
                    if "approve" in name or "approved" in name:
                        approvals += 1
                    elif "block" in name or "blocked" in name:
                        blocks += 1
                    else:
                        # Count as a review but verdict unknown from name alone
                        # For v1, default to approval if verdict file exists
                        approvals += 1

        # Check .gemini-reviews/ directory
        gemini_dir_contents = self._client.fetch_repo_contents(
            repo_full_name, ".gemini-reviews"
        )
        for item in gemini_dir_contents:
            name = item.get("name", "").lower()
            if "approve" in name or "approved" in name:
                approvals += 1
            elif "block" in name or "blocked" in name:
                blocks += 1

        total_reviews = approvals + blocks
        approval_rate: Optional[float] = None
        if total_reviews > 0:
            approval_rate = round(approvals / total_reviews, 3)

        return RepoGeminiMetrics(
            repo=repo_full_name,
            total_reviews=total_reviews,
            approvals=approvals,
            blocks=blocks,
            approval_rate=approval_rate,
        )

    def aggregate(
        self,
        per_repo_results: list[PerRepoMetrics],
        repos_failed: list[str] | None = None,
    ) -> CrossProjectMetrics:
        """Aggregate per-repo metrics into cross-project totals.

        Args:
            per_repo_results: List of successfully collected repo metrics.
            repos_failed: List of repo full_names that failed collection.

        Returns:
            CrossProjectMetrics with totals and per-repo breakdown.
        """
        if repos_failed is None:
            repos_failed = []

        now = datetime.now(tz=timezone.utc)
        period_end = now.strftime("%Y-%m-%d")
        period_start = (
            now - timedelta(days=self._config["lookback_days"])
        ).strftime("%Y-%m-%d")

        total_opened = sum(r["issues"]["issues_opened"] for r in per_repo_results)
        total_closed = sum(r["issues"]["issues_closed"] for r in per_repo_results)
        total_open = sum(
            r["issues"]["issues_open_current"] for r in per_repo_results
        )
        total_lld = sum(r["workflows"]["lld_count"] for r in per_repo_results)
        total_workflows = sum(
            r["workflows"]["requirements_workflows"]
            + r["workflows"]["implementation_workflows"]
            + r["workflows"]["tdd_workflows"]
            for r in per_repo_results
        )
        total_gemini = sum(r["gemini"]["total_reviews"] for r in per_repo_results)
        total_approvals = sum(r["gemini"]["approvals"] for r in per_repo_results)
        total_reports = sum(r["workflows"]["report_count"] for r in per_repo_results)

        avg_close_time = self._calculate_aggregate_close_time(per_repo_results)

        gemini_approval_rate: Optional[float] = None
        if total_gemini > 0:
            gemini_approval_rate = round(total_approvals / total_gemini, 3)

        totals = AggregateTotals(
            issues_opened=total_opened,
            issues_closed=total_closed,
            issues_open_current=total_open,
            avg_close_time_hours=avg_close_time,
            lld_count=total_lld,
            total_workflows=total_workflows,
            gemini_reviews=total_gemini,
            gemini_approval_rate=gemini_approval_rate,
            report_count=total_reports,
        )

        repos_tracked = len(per_repo_results) + len(repos_failed)

        return CrossProjectMetrics(
            generated_at=now.isoformat(),
            period_start=period_start,
            period_end=period_end,
            repos_tracked=repos_tracked,
            repos_collected=len(per_repo_results),
            repos_failed=repos_failed,
            totals=totals,
            per_repo=per_repo_results,
        )

    def _calculate_aggregate_close_time(
        self, per_repo: list[PerRepoMetrics]
    ) -> float | None:
        """Calculate weighted average close time across repos.

        Weights by number of closed issues per repo.
        Returns None if no closed issues across all repos.
        """
        total_weighted_hours = 0.0
        total_closed_count = 0

        for repo_metrics in per_repo:
            avg_hours = repo_metrics["issues"]["avg_close_time_hours"]
            closed_count = repo_metrics["issues"]["issues_closed"]
            if avg_hours is not None and closed_count > 0:
                total_weighted_hours += avg_hours * closed_count
                total_closed_count += closed_count

        if total_closed_count == 0:
            return None

        return round(total_weighted_hours / total_closed_count, 2)


def _empty_issue_metrics(
    repo: str, period_start: str, period_end: str
) -> RepoIssueMetrics:
    """Return zeroed-out issue metrics for fault isolation."""
    return RepoIssueMetrics(
        repo=repo,
        period_start=period_start,
        period_end=period_end,
        issues_opened=0,
        issues_closed=0,
        issues_open_current=0,
        avg_close_time_hours=None,
        issues_by_label={},
    )


def _empty_workflow_metrics(repo: str) -> RepoWorkflowMetrics:
    """Return zeroed-out workflow metrics for fault isolation."""
    return RepoWorkflowMetrics(
        repo=repo,
        lld_count=0,
        requirements_workflows=0,
        implementation_workflows=0,
        tdd_workflows=0,
        report_count=0,
    )


def _empty_gemini_metrics(repo: str) -> RepoGeminiMetrics:
    """Return zeroed-out Gemini metrics for fault isolation."""
    return RepoGeminiMetrics(
        repo=repo,
        total_reviews=0,
        approvals=0,
        blocks=0,
        approval_rate=None,
    )
```
