

```python
"""Cross-project metrics aggregation.

Issue #333: Combine per-repo metrics into unified summary.
"""

from __future__ import annotations

from datetime import datetime, timezone

from assemblyzero.metrics.models import AggregatedMetrics, RepoMetrics


def compute_approval_rate(approvals: int, total: int) -> float:
    """Safely compute approval rate, returning 0.0 if total is 0.

    Result is rounded to 3 decimal places.
    """
    if total == 0:
        return 0.0
    return round(approvals / total, 3)


def aggregate_metrics(
    repo_metrics: list[RepoMetrics],
    period_start: str,
    period_end: str,
) -> AggregatedMetrics:
    """Combine per-repo metrics into a unified cross-project summary."""
    total_created = 0
    total_closed = 0
    total_open = 0
    total_llds = 0
    total_reviews = 0
    total_approvals = 0
    workflows_combined: dict[str, int] = {}

    for rm in repo_metrics:
        total_created += rm["issues_created"]
        total_closed += rm["issues_closed"]
        total_open += rm["issues_open"]
        total_llds += rm["llds_generated"]
        total_reviews += rm["gemini_reviews"]
        total_approvals += rm["gemini_approvals"]
        for wf_type, count in rm["workflows_used"].items():
            workflows_combined[wf_type] = workflows_combined.get(wf_type, 0) + count

    return AggregatedMetrics(
        repos_tracked=len(repo_metrics),
        repos_reachable=len(repo_metrics),
        period_start=period_start,
        period_end=period_end,
        total_issues_created=total_created,
        total_issues_closed=total_closed,
        total_issues_open=total_open,
        total_llds_generated=total_llds,
        total_gemini_reviews=total_reviews,
        gemini_approval_rate=compute_approval_rate(total_approvals, total_reviews),
        workflows_by_type=workflows_combined,
        per_repo=list(repo_metrics),
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
    )
```
