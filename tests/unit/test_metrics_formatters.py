"""Unit tests for assemblyzero.metrics.formatters.

Issue #333: Tests for JSON and markdown output formatting.
Tests: T210, T220, T230
"""

from __future__ import annotations

import json
from pathlib import Path

from assemblyzero.metrics.formatters import (
    format_json_snapshot,
    format_markdown_table,
    write_snapshot,
)
from assemblyzero.metrics.models import AggregatedMetrics, RepoMetrics


def _make_aggregated() -> AggregatedMetrics:
    """Create test AggregatedMetrics."""
    return AggregatedMetrics(
        repos_tracked=2,
        repos_reachable=2,
        period_start="2026-01-26T00:00:00+00:00",
        period_end="2026-02-25T00:00:00+00:00",
        total_issues_created=67,
        total_issues_closed=55,
        total_issues_open=20,
        total_llds_generated=32,
        total_gemini_reviews=28,
        gemini_approval_rate=0.857,
        workflows_by_type={"requirements": 12, "tdd": 23},
        per_repo=[
            RepoMetrics(
                repo="martymcenroe/AssemblyZero",
                period_start="2026-01-26T00:00:00+00:00",
                period_end="2026-02-25T00:00:00+00:00",
                issues_created=42,
                issues_closed=35,
                issues_open=12,
                workflows_used={"requirements": 8, "tdd": 15},
                llds_generated=20,
                gemini_reviews=18,
                gemini_approvals=15,
                gemini_blocks=3,
                collection_timestamp="2026-02-25T14:30:00+00:00",
            ),
            RepoMetrics(
                repo="martymcenroe/ProjectAlpha",
                period_start="2026-01-26T00:00:00+00:00",
                period_end="2026-02-25T00:00:00+00:00",
                issues_created=25,
                issues_closed=20,
                issues_open=8,
                workflows_used={"requirements": 4, "tdd": 8},
                llds_generated=12,
                gemini_reviews=10,
                gemini_approvals=8,
                gemini_blocks=2,
                collection_timestamp="2026-02-25T14:30:15+00:00",
            ),
        ],
        generated_at="2026-02-25T14:31:00+00:00",
    )


def _make_empty_aggregated() -> AggregatedMetrics:
    """Create empty AggregatedMetrics with no repos."""
    return AggregatedMetrics(
        repos_tracked=0,
        repos_reachable=0,
        period_start="2026-01-26T00:00:00+00:00",
        period_end="2026-02-25T00:00:00+00:00",
        total_issues_created=0,
        total_issues_closed=0,
        total_issues_open=0,
        total_llds_generated=0,
        total_gemini_reviews=0,
        gemini_approval_rate=0.0,
        workflows_by_type={},
        per_repo=[],
        generated_at="2026-02-25T14:31:00+00:00",
    )


class TestFormatJsonSnapshot:
    """Tests for format_json_snapshot()."""

    def test_produces_valid_json(self) -> None:
        """T210: Produces valid JSON with expected keys."""
        metrics = _make_aggregated()
        result = format_json_snapshot(metrics)
        parsed = json.loads(result)
        assert "repos_tracked" in parsed
        assert "total_issues_created" in parsed
        assert "gemini_approval_rate" in parsed
        assert "per_repo" in parsed
        assert parsed["repos_tracked"] == 2
        assert parsed["total_issues_created"] == 67

    def test_json_is_pretty_printed(self) -> None:
        """JSON output is indented (not a single line)."""
        metrics = _make_aggregated()
        result = format_json_snapshot(metrics)
        assert "\n" in result

    def test_empty_metrics_valid_json(self) -> None:
        """Empty aggregated metrics produce valid JSON."""
        metrics = _make_empty_aggregated()
        result = format_json_snapshot(metrics)
        parsed = json.loads(result)
        assert parsed["repos_tracked"] == 0
        assert parsed["per_repo"] == []

    def test_all_aggregated_keys_present(self) -> None:
        """All AggregatedMetrics keys are present in JSON output."""
        metrics = _make_aggregated()
        result = format_json_snapshot(metrics)
        parsed = json.loads(result)
        expected_keys = {
            "repos_tracked", "repos_reachable", "period_start", "period_end",
            "total_issues_created", "total_issues_closed", "total_issues_open",
            "total_llds_generated", "total_gemini_reviews", "gemini_approval_rate",
            "workflows_by_type", "per_repo", "generated_at",
        }
        assert expected_keys.issubset(set(parsed.keys()))


class TestFormatMarkdownTable:
    """Tests for format_markdown_table()."""

    def test_contains_table_headers(self) -> None:
        """T220: Markdown output contains expected headings and table headers."""
        metrics = _make_aggregated()
        result = format_markdown_table(metrics)
        assert "# Cross-Project Metrics Report" in result
        assert "| Metric | Value |" in result
        assert "| Repo |" in result
        assert "martymcenroe/AssemblyZero" in result
        assert "martymcenroe/ProjectAlpha" in result
        assert "85.7%" in result  # Approval rate

    def test_summary_section_present(self) -> None:
        """T220: Summary section contains all key metrics."""
        metrics = _make_aggregated()
        result = format_markdown_table(metrics)
        assert "Total Issues Created | 67" in result
        assert "Total Issues Closed | 55" in result
        assert "Total Issues Open | 20" in result
        assert "Total LLDs Generated | 32" in result
        assert "Total Gemini Reviews | 28" in result

    def test_period_in_header(self) -> None:
        """Period dates appear in the header."""
        metrics = _make_aggregated()
        result = format_markdown_table(metrics)
        assert "2026-01-26" in result
        assert "2026-02-25" in result

    def test_workflows_table_present(self) -> None:
        """Workflows by Type section appears with correct data."""
        metrics = _make_aggregated()
        result = format_markdown_table(metrics)
        assert "## Workflows by Type" in result
        assert "| Workflow | Count |" in result
        assert "requirements" in result
        assert "tdd" in result

    def test_per_repo_approval_rates(self) -> None:
        """Per-repo breakdown shows correct approval rates."""
        metrics = _make_aggregated()
        result = format_markdown_table(metrics)
        # AssemblyZero: 15/18 = 83.3%
        assert "83.3%" in result
        # ProjectAlpha: 8/10 = 80.0%
        assert "80.0%" in result

    def test_empty_metrics_no_crash(self) -> None:
        """Empty aggregated metrics produce valid markdown without crashing."""
        metrics = _make_empty_aggregated()
        result = format_markdown_table(metrics)
        assert "# Cross-Project Metrics Report" in result
        assert "| Metric | Value |" in result

    def test_repo_with_zero_reviews_shows_na(self) -> None:
        """Repo with 0 gemini_reviews shows N/A for approval rate."""
        metrics = AggregatedMetrics(
            repos_tracked=1,
            repos_reachable=1,
            period_start="2026-01-26T00:00:00+00:00",
            period_end="2026-02-25T00:00:00+00:00",
            total_issues_created=10,
            total_issues_closed=5,
            total_issues_open=5,
            total_llds_generated=0,
            total_gemini_reviews=0,
            gemini_approval_rate=0.0,
            workflows_by_type={},
            per_repo=[
                RepoMetrics(
                    repo="test/zero-reviews",
                    period_start="2026-01-26T00:00:00+00:00",
                    period_end="2026-02-25T00:00:00+00:00",
                    issues_created=10,
                    issues_closed=5,
                    issues_open=5,
                    workflows_used={},
                    llds_generated=0,
                    gemini_reviews=0,
                    gemini_approvals=0,
                    gemini_blocks=0,
                    collection_timestamp="2026-02-25T14:30:00+00:00",
                ),
            ],
            generated_at="2026-02-25T14:31:00+00:00",
        )
        result = format_markdown_table(metrics)
        assert "N/A" in result


class TestWriteSnapshot:
    """Tests for write_snapshot()."""

    def test_writes_file_with_correct_name(self, tmp_path: Path) -> None:
        """T230: Creates file at cross-project-{date}.json with valid JSON."""
        metrics = _make_aggregated()
        result_path = write_snapshot(metrics, tmp_path)
        assert result_path.exists()
        assert result_path.name.startswith("cross-project-")
        assert result_path.name.endswith(".json")
        content = json.loads(result_path.read_text(encoding="utf-8"))
        assert content["repos_tracked"] == 2

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        """Creates output directory if it doesn't exist."""
        metrics = _make_aggregated()
        output_dir = tmp_path / "nested" / "dir"
        result_path = write_snapshot(metrics, output_dir)
        assert result_path.exists()
        assert output_dir.exists()

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Overwrites file if it already exists (same date)."""
        metrics = _make_aggregated()
        path1 = write_snapshot(metrics, tmp_path)
        # Write again -- should succeed and overwrite
        path2 = write_snapshot(metrics, tmp_path)
        assert path1 == path2
        assert path2.exists()
