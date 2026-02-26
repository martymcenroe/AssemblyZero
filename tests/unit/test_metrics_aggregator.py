"""Unit tests for assemblyzero.metrics.aggregator.

Issue #333: Tests for cross-repo aggregation.
Tests: T120, T130, T140, T150
"""

from __future__ import annotations

from assemblyzero.metrics.aggregator import aggregate_metrics, compute_approval_rate
from assemblyzero.metrics.models import RepoMetrics


def _make_metrics(
    repo: str,
    created: int = 0,
    closed: int = 0,
    open_: int = 0,
    llds: int = 0,
    reviews: int = 0,
    approvals: int = 0,
    blocks: int = 0,
    workflows: dict[str, int] | None = None,
) -> RepoMetrics:
    """Create test RepoMetrics with specified values."""
    return RepoMetrics(
        repo=repo,
        period_start="2026-01-26T00:00:00+00:00",
        period_end="2026-02-25T00:00:00+00:00",
        issues_created=created,
        issues_closed=closed,
        issues_open=open_,
        workflows_used=workflows or {},
        llds_generated=llds,
        gemini_reviews=reviews,
        gemini_approvals=approvals,
        gemini_blocks=blocks,
        collection_timestamp="2026-02-25T14:30:00+00:00",
    )


class TestAggregateMetrics:
    """Tests for aggregate_metrics()."""

    def test_multi_repo_summation(self) -> None:
        """T120: Sums totals correctly across 3 repos."""
        repos = [
            _make_metrics(
                "a/x", created=42, closed=35, open_=12,
                llds=20, reviews=18, approvals=15, blocks=3,
                workflows={"req": 8, "tdd": 15},
            ),
            _make_metrics(
                "a/y", created=25, closed=20, open_=8,
                llds=12, reviews=10, approvals=8, blocks=2,
                workflows={"req": 4, "tdd": 8, "impl": 5},
            ),
            _make_metrics(
                "a/z", created=20, closed=17, open_=5,
                llds=8, reviews=7, approvals=7, blocks=0,
                workflows={"req": 3, "tdd": 5, "impl": 5},
            ),
        ]
        result = aggregate_metrics(
            repos, "2026-01-26T00:00:00+00:00", "2026-02-25T00:00:00+00:00"
        )
        assert result["total_issues_created"] == 87
        assert result["total_issues_closed"] == 72
        assert result["total_issues_open"] == 25
        assert result["total_llds_generated"] == 40
        assert result["total_gemini_reviews"] == 35
        assert result["gemini_approval_rate"] == 0.857
        assert result["workflows_by_type"]["req"] == 15
        assert result["workflows_by_type"]["tdd"] == 28
        assert result["workflows_by_type"]["impl"] == 10
        assert result["repos_tracked"] == 3
        assert result["repos_reachable"] == 3
        assert len(result["per_repo"]) == 3

    def test_empty_input_zeroed(self) -> None:
        """T130: Empty input produces zeroed output."""
        result = aggregate_metrics(
            [], "2026-01-26T00:00:00+00:00", "2026-02-25T00:00:00+00:00"
        )
        assert result["repos_tracked"] == 0
        assert result["repos_reachable"] == 0
        assert result["total_issues_created"] == 0
        assert result["total_issues_closed"] == 0
        assert result["total_issues_open"] == 0
        assert result["total_llds_generated"] == 0
        assert result["total_gemini_reviews"] == 0
        assert result["gemini_approval_rate"] == 0.0
        assert result["workflows_by_type"] == {}
        assert result["per_repo"] == []

    def test_single_repo_identity(self) -> None:
        """T140: Single repo aggregated equals that repo's values."""
        single = _make_metrics(
            "a/x", created=42, closed=35, open_=12,
            llds=20, reviews=18, approvals=15, blocks=3,
        )
        result = aggregate_metrics(
            [single], "2026-01-26T00:00:00+00:00", "2026-02-25T00:00:00+00:00"
        )
        assert result["total_issues_created"] == 42
        assert result["total_issues_closed"] == 35
        assert result["total_issues_open"] == 12
        assert result["total_llds_generated"] == 20
        assert result["total_gemini_reviews"] == 18
        assert result["repos_tracked"] == 1
        assert result["repos_reachable"] == 1

    def test_period_timestamps_preserved(self) -> None:
        """Period start/end are preserved in output."""
        result = aggregate_metrics(
            [], "2026-01-01T00:00:00+00:00", "2026-02-01T00:00:00+00:00"
        )
        assert result["period_start"] == "2026-01-01T00:00:00+00:00"
        assert result["period_end"] == "2026-02-01T00:00:00+00:00"

    def test_generated_at_populated(self) -> None:
        """generated_at field is a non-empty ISO timestamp."""
        result = aggregate_metrics(
            [], "2026-01-26T00:00:00+00:00", "2026-02-25T00:00:00+00:00"
        )
        assert result["generated_at"]
        assert "T" in result["generated_at"]

    def test_workflow_merging(self) -> None:
        """Workflows from different repos merge by type correctly."""
        repos = [
            _make_metrics("a/x", workflows={"requirements": 3}),
            _make_metrics("a/y", workflows={"requirements": 2, "tdd": 5}),
        ]
        result = aggregate_metrics(
            repos, "2026-01-26T00:00:00+00:00", "2026-02-25T00:00:00+00:00"
        )
        assert result["workflows_by_type"]["requirements"] == 5
        assert result["workflows_by_type"]["tdd"] == 5


class TestComputeApprovalRate:
    """Tests for compute_approval_rate()."""

    def test_zero_reviews_returns_zero(self) -> None:
        """T150: Returns 0.0 when total is 0."""
        assert compute_approval_rate(0, 0) == 0.0

    def test_normal_rate(self) -> None:
        """T150: Normal computation rounds to 3 decimal places."""
        assert compute_approval_rate(30, 35) == 0.857

    def test_perfect_rate(self) -> None:
        """T150: All approvals returns 1.0."""
        assert compute_approval_rate(10, 10) == 1.0

    def test_zero_approvals(self) -> None:
        """T150: Zero approvals with some reviews returns 0.0."""
        assert compute_approval_rate(0, 5) == 0.0

    def test_two_thirds(self) -> None:
        """Computation of 2/3 rounds correctly."""
        assert compute_approval_rate(2, 3) == 0.667
