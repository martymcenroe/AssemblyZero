"""Output formatters for cross-project metrics.

Issue #333: JSON snapshot and markdown table formatters.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import orjson

from assemblyzero.metrics.models import AggregatedMetrics


def format_json_snapshot(metrics: AggregatedMetrics) -> str:
    """Serialize aggregated metrics to pretty-printed JSON string."""
    raw = orjson.dumps(dict(metrics), option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
    return raw.decode("utf-8")


def format_markdown_table(metrics: AggregatedMetrics) -> str:
    """Format aggregated metrics as a markdown report with tables."""
    lines: list[str] = []
    lines.append("# Cross-Project Metrics Report")
    lines.append("")

    period_start = metrics["period_start"][:10]
    period_end = metrics["period_end"][:10]
    lines.append(
        f"**Period:** {period_start} to {period_end}"
    )
    lines.append(
        f"**Repos Tracked:** {metrics['repos_tracked']} | "
        f"**Repos Reachable:** {metrics['repos_reachable']}"
    )
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Issues Created | {metrics['total_issues_created']} |")
    lines.append(f"| Total Issues Closed | {metrics['total_issues_closed']} |")
    lines.append(f"| Total Issues Open | {metrics['total_issues_open']} |")
    lines.append(f"| Total LLDs Generated | {metrics['total_llds_generated']} |")
    lines.append(f"| Total Gemini Reviews | {metrics['total_gemini_reviews']} |")
    approval_pct = f"{metrics['gemini_approval_rate'] * 100:.1f}%"
    lines.append(f"| Gemini Approval Rate | {approval_pct} |")
    lines.append("")

    # Workflows table
    if metrics["workflows_by_type"]:
        lines.append("## Workflows by Type")
        lines.append("")
        lines.append("| Workflow | Count |")
        lines.append("|----------|-------|")
        for wf_type, count in sorted(metrics["workflows_by_type"].items()):
            lines.append(f"| {wf_type} | {count} |")
        lines.append("")

    # Per-repo table
    if metrics["per_repo"]:
        lines.append("## Per-Repository Breakdown")
        lines.append("")
        lines.append(
            "| Repo | Created | Closed | Open | LLDs | Reviews | Approval Rate |"
        )
        lines.append(
            "|------|---------|--------|------|------|---------|---------------|"
        )
        for rm in metrics["per_repo"]:
            if rm["gemini_reviews"] > 0:
                rate = f"{rm['gemini_approvals'] / rm['gemini_reviews'] * 100:.1f}%"
            else:
                rate = "N/A"
            lines.append(
                f"| {rm['repo']} | {rm['issues_created']} | {rm['issues_closed']} | "
                f"{rm['issues_open']} | {rm['llds_generated']} | "
                f"{rm['gemini_reviews']} | {rate} |"
            )
        lines.append("")

    return "\n".join(lines)


def write_snapshot(metrics: AggregatedMetrics, output_dir: Path) -> Path:
    """Write JSON snapshot to output_dir/cross-project-{date}.json.

    Returns the path of the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    filename = f"cross-project-{date_str}.json"
    output_path = output_dir / filename
    json_content = format_json_snapshot(metrics)
    output_path.write_text(json_content, encoding="utf-8")
    return output_path