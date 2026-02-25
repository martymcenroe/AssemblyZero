"""Unit tests for metrics aggregation logic.

Issue #333: Cross-Project Metrics Aggregation.
Tests: T090, T100, T110, T120, T130, T140, T150, T160
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.utils.metrics_aggregator import MetricsAggregator
from assemblyzero.utils.metrics_models import (
    MetricsCollectionConfig,
    PerRepoMetrics,
    RepoGeminiMetrics,
    RepoIssueMetrics,
    RepoWorkflowMetrics,
    TrackedRepoConfig,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "metrics"


def _make_config(lookback_days: int = 30) -> MetricsCollectionConfig:
    """Create a test config."""
    return MetricsCollectionConfig(
        repos=[],
        lookback_days=lookback_days,
        output_dir="docs/metrics",
        cache_ttl_seconds=300,
        github_token_env="GITHUB_TOKEN",
    )


def _make_mock_client() -> MagicMock:
    """Create a mock GitHubMetricsClient."""
    return MagicMock()


class TestCollectIssueMetrics:
    """Tests for collect_issue_metrics()."""

    def test_t090_happy_path(self) -> None:
        """T090: Issue metrics with mix of open/closed issues."""
        mock_client = _make_mock_client()
        mock_client.fetch_issues.return_value = [
            {
                "number": 1,
                "state": "closed",
                "created_at": "2026-02-10T08:00:00Z",
                "closed_at": "2026-02-10T20:00:00Z",
                "labels": ["bug", "tdd"],
            },
            {
                "number": 2,
                "state": "closed",
                "created_at": "2026-02-11T10:00:00Z",
                "closed_at": "2026-02-12T10:00:00Z",
                "labels": ["feature", "implementation"],
            },
            {
                "number": 3,
                "state": "open",
                "created_at": "2026-02-13T09:00:00Z",
                "closed_at": None,
                "labels": ["feature"],
            },
        ]

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_issue_metrics(
            "owner/repo", "2026-02-01", "2026-02-24"
        )

        assert result["issues_opened"] == 3
        assert result["issues_closed"] == 2
        assert result["issues_open_current"] == 1
        # Issue 1: 12 hours, Issue 2: 24 hours -> avg = 18.0
        assert result["avg_close_time_hours"] == 18.0
        assert result["issues_by_label"]["bug"] == 1
        assert result["issues_by_label"]["feature"] == 2
        assert result["issues_by_label"]["tdd"] == 1
        assert result["issues_by_label"]["implementation"] == 1

    def test_t100_zero_issues(self) -> None:
        """T100: Issue metrics with zero issues returns zeroed values."""
        mock_client = _make_mock_client()
        mock_client.fetch_issues.return_value = []

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_issue_metrics(
            "owner/repo", "2026-02-01", "2026-02-24"
        )

        assert result["issues_opened"] == 0
        assert result["issues_closed"] == 0
        assert result["issues_open_current"] == 0
        assert result["avg_close_time_hours"] is None
        assert result["issues_by_label"] == {}


class TestWorkflowDetection:
    """Tests for collect_workflow_metrics()."""

    def test_t110_from_labels(self) -> None:
        """T110: Workflow detection from issue labels."""
        mock_client = _make_mock_client()
        # No content files
        mock_client.fetch_repo_contents.return_value = []
        # Issues with workflow labels
        mock_client.fetch_issues.return_value = [
            {"number": 1, "labels": ["requirements"], "state": "open"},
            {"number": 2, "labels": ["lld"], "state": "closed"},
            {"number": 3, "labels": ["implementation"], "state": "closed"},
            {"number": 4, "labels": ["tdd"], "state": "open"},
            {"number": 5, "labels": ["implementation", "requirements"], "state": "closed"},
        ]

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_workflow_metrics("owner/repo")

        assert result["requirements_workflows"] == 3  # issues 1, 2, 5
        assert result["implementation_workflows"] == 2  # issues 3, 5
        assert result["tdd_workflows"] == 1  # issue 4

    def test_t120_from_content_listing(self) -> None:
        """T120: Workflow detection from content listing (LLD files)."""
        mock_client = _make_mock_client()

        def mock_contents(repo: str, path: str) -> list[dict]:
            if path == "docs/lld/active":
                return [
                    {"name": "001.md", "type": "file", "path": "docs/lld/active/001.md", "size": 100},
                    {"name": "002.md", "type": "file", "path": "docs/lld/active/002.md", "size": 200},
                    {"name": "003.md", "type": "file", "path": "docs/lld/active/003.md", "size": 150},
                    {"name": "readme.txt", "type": "file", "path": "docs/lld/active/readme.txt", "size": 50},
                    {"name": "004.md", "type": "file", "path": "docs/lld/active/004.md", "size": 300},
                    {"name": "archive", "type": "dir", "path": "docs/lld/active/archive", "size": 0},
                ]
            if path == "docs/reports":
                return [
                    {"name": "333", "type": "dir", "path": "docs/reports/333", "size": 0},
                    {"name": "320", "type": "dir", "path": "docs/reports/320", "size": 0},
                ]
            return []

        mock_client.fetch_repo_contents.side_effect = mock_contents
        mock_client.fetch_issues.return_value = []

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_workflow_metrics("owner/repo")

        assert result["lld_count"] == 4  # 4 .md files (not .txt, not dir)
        assert result["report_count"] == 2  # 2 dirs


class TestGeminiMetrics:
    """Tests for collect_gemini_metrics()."""

    def test_t130_verdict_counting(self) -> None:
        """T130: Gemini metrics correctly count APPROVE and BLOCK."""
        mock_client = _make_mock_client()

        def mock_contents(repo: str, path: str) -> list[dict]:
            if path == "docs/reports":
                return [
                    {"name": "333", "type": "dir", "path": "docs/reports/333", "size": 0},
                    {"name": "320", "type": "dir", "path": "docs/reports/320", "size": 0},
                ]
            if path == "docs/reports/333":
                return [
                    {"name": "gemini-verdict-approved.json", "type": "file", "path": "docs/reports/333/gemini-verdict-approved.json", "size": 50},
                ]
            if path == "docs/reports/320":
                return [
                    {"name": "gemini-verdict-blocked.json", "type": "file", "path": "docs/reports/320/gemini-verdict-blocked.json", "size": 50},
                ]
            if path == ".gemini-reviews":
                return [
                    {"name": "review-approved-1.json", "type": "file", "path": ".gemini-reviews/review-approved-1.json", "size": 30},
                    {"name": "review-approved-2.json", "type": "file", "path": ".gemini-reviews/review-approved-2.json", "size": 30},
                    {"name": "review-blocked-1.json", "type": "file", "path": ".gemini-reviews/review-blocked-1.json", "size": 30},
                ]
            return []

        mock_client.fetch_repo_contents.side_effect = mock_contents

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_gemini_metrics("owner/repo")

        assert result["approvals"] == 3  # 1 from reports/333 + 2 from .gemini-reviews
        assert result["blocks"] == 2  # 1 from reports/320 + 1 from .gemini-reviews
        assert result["total_reviews"] == 5
        assert result["approval_rate"] == 0.6

    def test_t140_no_verdicts(self) -> None:
        """T140: Gemini metrics with no verdicts returns zeros."""
        mock_client = _make_mock_client()
        mock_client.fetch_repo_contents.return_value = []

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_gemini_metrics("owner/repo")

        assert result["total_reviews"] == 0
        assert result["approvals"] == 0
        assert result["blocks"] == 0
        assert result["approval_rate"] is None


class TestAggregation:
    """Tests for aggregate()."""

    def test_t150_cross_repo_aggregation(self) -> None:
        """T150: Aggregation across multiple repos sums correctly."""
        mock_client = _make_mock_client()
        config = _make_config()
        agg = MetricsAggregator(client=mock_client, config=config)

        repo_a = PerRepoMetrics(
            repo="owner/repo-a",
            issues=RepoIssueMetrics(
                repo="owner/repo-a", period_start="2026-01-25", period_end="2026-02-24",
                issues_opened=10, issues_closed=8, issues_open_current=2,
                avg_close_time_hours=12.0, issues_by_label={"bug": 3},
            ),
            workflows=RepoWorkflowMetrics(
                repo="owner/repo-a", lld_count=5,
                requirements_workflows=3, implementation_workflows=4,
                tdd_workflows=2, report_count=6,
            ),
            gemini=RepoGeminiMetrics(
                repo="owner/repo-a", total_reviews=10,
                approvals=8, blocks=2, approval_rate=0.8,
            ),
        )
        repo_b = PerRepoMetrics(
            repo="owner/repo-b",
            issues=RepoIssueMetrics(
                repo="owner/repo-b", period_start="2026-01-25", period_end="2026-02-24",
                issues_opened=5, issues_closed=3, issues_open_current=4,
                avg_close_time_hours=24.0, issues_by_label={"feature": 2},
            ),
            workflows=RepoWorkflowMetrics(
                repo="owner/repo-b", lld_count=2,
                requirements_workflows=1, implementation_workflows=1,
                tdd_workflows=0, report_count=3,
            ),
            gemini=RepoGeminiMetrics(
                repo="owner/repo-b", total_reviews=4,
                approvals=3, blocks=1, approval_rate=0.75,
            ),
        )

        result = agg.aggregate([repo_a, repo_b])

        assert result["totals"]["issues_opened"] == 15
        assert result["totals"]["issues_closed"] == 11
        assert result["totals"]["issues_open_current"] == 6
        assert result["totals"]["lld_count"] == 7
        # total_workflows = (3+4+2) + (1+1+0) = 11
        assert result["totals"]["total_workflows"] == 11
        assert result["totals"]["gemini_reviews"] == 14
        # gemini_approval_rate = (8+3) / (10+4) = 11/14 ≈ 0.786
        assert result["totals"]["gemini_approval_rate"] == 0.786
        assert result["totals"]["report_count"] == 9
        # weighted avg close time = (12*8 + 24*3) / (8+3) = (96+72)/11 ≈ 15.27
        assert result["totals"]["avg_close_time_hours"] == 15.27
        assert result["repos_collected"] == 2
        assert result["repos_failed"] == []
        assert len(result["per_repo"]) == 2

    def test_t160_aggregation_with_failed_repos(self) -> None:
        """T160: Failed repos listed, successful ones aggregated."""
        mock_client = _make_mock_client()
        config = _make_config()
        agg = MetricsAggregator(client=mock_client, config=config)

        repo_a = PerRepoMetrics(
            repo="owner/repo-a",
            issues=RepoIssueMetrics(
                repo="owner/repo-a", period_start="2026-01-25", period_end="2026-02-24",
                issues_opened=5, issues_closed=3, issues_open_current=2,
                avg_close_time_hours=10.0, issues_by_label={},
            ),
            workflows=RepoWorkflowMetrics(
                repo="owner/repo-a", lld_count=1,
                requirements_workflows=1, implementation_workflows=1,
                tdd_workflows=0, report_count=1,
            ),
            gemini=RepoGeminiMetrics(
                repo="owner/repo-a", total_reviews=2,
                approvals=2, blocks=0, approval_rate=1.0,
            ),
        )

        result = agg.aggregate([repo_a], repos_failed=["owner/failed-repo"])

        assert result["repos_tracked"] == 2  # 1 success + 1 failed
        assert result["repos_collected"] == 1
        assert result["repos_failed"] == ["owner/failed-repo"]
        assert result["totals"]["issues_opened"] == 5