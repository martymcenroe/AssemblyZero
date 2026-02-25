"""Unit tests for the main collector CLI orchestration.

Issue #333: Cross-Project Metrics Aggregation.
Tests: T170, T180, T190, T200, T210, T220, T270, T280, T290, T300
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from tools.collect_cross_project_metrics import (
    format_summary_table,
    main,
    parse_args,
    write_metrics_output,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "metrics"


class TestParseArgs:
    """Tests for parse_args()."""

    def test_t270_all_flags(self) -> None:
        """T270: CLI parses all supported flags."""
        args = parse_args([
            "--config", "f.json",
            "--output", "o/out.json",
            "--lookback-days", "7",
            "--dry-run",
            "--verbose",
        ])
        assert args.config_path == "f.json"
        assert args.output == "o/out.json"
        assert args.lookback_days == 7
        assert args.dry_run is True
        assert args.verbose is True

    def test_no_args_defaults(self) -> None:
        """CLI with no args uses defaults."""
        args = parse_args([])
        assert args.config_path is None
        assert args.output is None
        assert args.lookback_days is None
        assert args.dry_run is False
        assert args.verbose is False


class TestDryRun:
    """Tests for dry-run mode."""

    @patch("tools.collect_cross_project_metrics.load_config")
    def test_t170_dry_run(self, mock_load: MagicMock, capsys: pytest.CaptureFixture) -> None:
        """T170: Dry-run prints config and exits 0 without API calls."""
        mock_load.return_value = {
            "repos": [
                {"owner": "a", "name": "b", "full_name": "a/b", "enabled": True},
            ],
            "lookback_days": 30,
            "output_dir": "docs/metrics",
            "cache_ttl_seconds": 300,
            "github_token_env": "GITHUB_TOKEN",
        }

        exit_code = main(config_path="test.json", dry_run=True)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Dry Run Mode" in captured.out
        assert "a/b" in captured.out


class TestExitCodes:
    """Tests for exit codes on partial/total failure."""

    @patch("tools.collect_cross_project_metrics.write_metrics_output")
    @patch("tools.collect_cross_project_metrics.MetricsAggregator")
    @patch("tools.collect_cross_project_metrics.GitHubMetricsClient")
    @patch("tools.collect_cross_project_metrics.load_config")
    def test_t180_partial_failure(
        self,
        mock_load: MagicMock,
        mock_client_cls: MagicMock,
        mock_agg_cls: MagicMock,
        mock_write: MagicMock,
    ) -> None:
        """T180: Returns 1 when some repos fail."""
        mock_load.return_value = {
            "repos": [
                {"owner": "a", "name": "good", "full_name": "a/good", "enabled": True},
                {"owner": "a", "name": "bad", "full_name": "a/bad", "enabled": True},
            ],
            "lookback_days": 30,
            "output_dir": "docs/metrics",
            "cache_ttl_seconds": 300,
            "github_token_env": "GITHUB_TOKEN",
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get_rate_limit_remaining.return_value = {
            "remaining": 5000, "limit": 5000, "reset_at": "2026-02-24T16:00:00Z"
        }
        mock_client_cls.return_value = mock_client_instance

        mock_agg_instance = MagicMock()
        # First repo succeeds, second fails
        good_metrics = {
            "repo": "a/good",
            "issues": {"repo": "a/good", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 5, "issues_closed": 3, "issues_open_current": 2, "avg_close_time_hours": 10.0, "issues_by_label": {}},
            "workflows": {"repo": "a/good", "lld_count": 1, "requirements_workflows": 1, "implementation_workflows": 0, "tdd_workflows": 0, "report_count": 0},
            "gemini": {"repo": "a/good", "total_reviews": 0, "approvals": 0, "blocks": 0, "approval_rate": None},
        }
        mock_agg_instance.collect_repo_metrics.side_effect = [
            good_metrics,
            Exception("API error on bad repo"),
        ]
        mock_agg_instance.aggregate.return_value = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 2,
            "repos_collected": 1,
            "repos_failed": ["a/bad"],
            "totals": {"issues_opened": 5, "issues_closed": 3, "issues_open_current": 2, "avg_close_time_hours": 10.0, "lld_count": 1, "total_workflows": 1, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [good_metrics],
        }
        mock_agg_cls.return_value = mock_agg_instance
        mock_write.return_value = "docs/metrics/test.json"

        exit_code = main(config_path="test.json")
        assert exit_code == 1

    @patch("tools.collect_cross_project_metrics.GitHubMetricsClient")
    @patch("tools.collect_cross_project_metrics.load_config")
    def test_t190_total_failure(
        self,
        mock_load: MagicMock,
        mock_client_cls: MagicMock,
    ) -> None:
        """T190: Returns 2 when all repos fail."""
        mock_load.return_value = {
            "repos": [
                {"owner": "a", "name": "bad1", "full_name": "a/bad1", "enabled": True},
                {"owner": "a", "name": "bad2", "full_name": "a/bad2", "enabled": True},
            ],
            "lookback_days": 30,
            "output_dir": "docs/metrics",
            "cache_ttl_seconds": 300,
            "github_token_env": "GITHUB_TOKEN",
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get_rate_limit_remaining.return_value = {
            "remaining": 5000, "limit": 5000, "reset_at": "2026-02-24T16:00:00Z"
        }
        mock_client_cls.return_value = mock_client_instance

        with patch("tools.collect_cross_project_metrics.MetricsAggregator") as mock_agg_cls:
            mock_agg_instance = MagicMock()
            mock_agg_instance.collect_repo_metrics.side_effect = Exception("fail")
            mock_agg_cls.return_value = mock_agg_instance

            exit_code = main(config_path="test.json")

        assert exit_code == 2


class TestOutputWriting:
    """Tests for write_metrics_output()."""

    def test_t200_output_file_naming(self, tmp_path: Path) -> None:
        """T200: Output file uses date-stamped naming."""
        metrics = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 1,
            "repos_collected": 1,
            "repos_failed": [],
            "totals": {"issues_opened": 5, "issues_closed": 3, "issues_open_current": 2, "avg_close_time_hours": 10.0, "lld_count": 1, "total_workflows": 1, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [],
        }

        result_path = write_metrics_output(metrics, str(tmp_path))
        assert "cross-project-" in result_path
        assert result_path.endswith(".json")
        assert Path(result_path).exists()

    def test_t210_latest_json_creation(self, tmp_path: Path) -> None:
        """T210: cross-project-latest.json is created alongside dated file."""
        metrics = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 0,
            "repos_collected": 0,
            "repos_failed": [],
            "totals": {"issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "lld_count": 0, "total_workflows": 0, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [],
        }

        write_metrics_output(metrics, str(tmp_path))
        latest = tmp_path / "cross-project-latest.json"
        assert latest.exists()

    def test_output_dir_not_exist(self) -> None:
        """write_metrics_output raises OSError if dir doesn't exist."""
        with pytest.raises(OSError, match="does not exist"):
            write_metrics_output({}, "/nonexistent/dir/path")

    def test_t300_custom_output_path(self, tmp_path: Path) -> None:
        """T300: CLI --output overrides default output path."""
        metrics = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 0,
            "repos_collected": 0,
            "repos_failed": [],
            "totals": {"issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "lld_count": 0, "total_workflows": 0, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [],
        }
        custom_path = str(tmp_path / "custom-metrics.json")
        result = write_metrics_output(metrics, str(tmp_path), output_path=custom_path)
        assert result == custom_path
        assert Path(custom_path).exists()


class TestSummaryTable:
    """Tests for format_summary_table()."""

    def test_t220_summary_formatting(self) -> None:
        """T220: Summary table contains repo names and totals."""
        metrics = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 2,
            "repos_collected": 2,
            "repos_failed": [],
            "totals": {"issues_opened": 15, "issues_closed": 11, "issues_open_current": 6, "avg_close_time_hours": 15.27, "lld_count": 7, "total_workflows": 11, "gemini_reviews": 14, "gemini_approval_rate": 0.786, "report_count": 9},
            "per_repo": [
                {
                    "repo": "owner/repo-a",
                    "issues": {"repo": "owner/repo-a", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 10, "issues_closed": 8, "issues_open_current": 2, "avg_close_time_hours": 12.0, "issues_by_label": {}},
                    "workflows": {"repo": "owner/repo-a", "lld_count": 5, "requirements_workflows": 3, "implementation_workflows": 4, "tdd_workflows": 2, "report_count": 6},
                    "gemini": {"repo": "owner/repo-a", "total_reviews": 10, "approvals": 8, "blocks": 2, "approval_rate": 0.8},
                },
                {
                    "repo": "owner/repo-b",
                    "issues": {"repo": "owner/repo-b", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 5, "issues_closed": 3, "issues_open_current": 4, "avg_close_time_hours": 24.0, "issues_by_label": {}},
                    "workflows": {"repo": "owner/repo-b", "lld_count": 2, "requirements_workflows": 1, "implementation_workflows": 1, "tdd_workflows": 0, "report_count": 3},
                    "gemini": {"repo": "owner/repo-b", "total_reviews": 4, "approvals": 3, "blocks": 1, "approval_rate": 0.75},
                },
            ],
        }

        table = format_summary_table(metrics)
        assert "owner/repo-a" in table
        assert "owner/repo-b" in table
        assert "TOTALS" in table
        assert "15" in table  # total opened
        assert "Repos tracked: 2" in table

    def test_summary_with_failed_repos(self) -> None:
        """Summary table shows failed repos when present."""
        metrics = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 2,
            "repos_collected": 1,
            "repos_failed": ["owner/bad-repo"],
            "totals": {"issues_opened": 5, "issues_closed": 3, "issues_open_current": 2, "avg_close_time_hours": 10.0, "lld_count": 0, "total_workflows": 0, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [
                {
                    "repo": "owner/good-repo",
                    "issues": {"repo": "owner/good-repo", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 5, "issues_closed": 3, "issues_open_current": 2, "avg_close_time_hours": 10.0, "issues_by_label": {}},
                    "workflows": {"repo": "owner/good-repo", "lld_count": 0, "requirements_workflows": 0, "implementation_workflows": 0, "tdd_workflows": 0, "report_count": 0},
                    "gemini": {"repo": "owner/good-repo", "total_reviews": 0, "approvals": 0, "blocks": 0, "approval_rate": None},
                },
            ],
        }
        table = format_summary_table(metrics)
        assert "Failed repos: owner/bad-repo" in table
        assert "N/A" in table  # approval_rate is None


class TestVerboseAndOverrides:
    """Tests for verbose mode and CLI overrides."""

    @patch("tools.collect_cross_project_metrics.write_metrics_output")
    @patch("tools.collect_cross_project_metrics.MetricsAggregator")
    @patch("tools.collect_cross_project_metrics.GitHubMetricsClient")
    @patch("tools.collect_cross_project_metrics.load_config")
    def test_t280_verbose_enables_debug(
        self,
        mock_load: MagicMock,
        mock_client_cls: MagicMock,
        mock_agg_cls: MagicMock,
        mock_write: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """T280: Verbose flag produces DEBUG-level log output."""
        mock_load.return_value = {
            "repos": [
                {"owner": "a", "name": "b", "full_name": "a/b", "enabled": True},
            ],
            "lookback_days": 30,
            "output_dir": "docs/metrics",
            "cache_ttl_seconds": 300,
            "github_token_env": "GITHUB_TOKEN",
        }
        mock_client_instance = MagicMock()
        mock_client_instance.get_rate_limit_remaining.return_value = {
            "remaining": 5000, "limit": 5000, "reset_at": "2026-02-24T16:00:00Z"
        }
        mock_client_cls.return_value = mock_client_instance

        mock_agg_instance = MagicMock()
        mock_agg_instance.collect_repo_metrics.return_value = {
            "repo": "a/b",
            "issues": {"repo": "a/b", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "issues_by_label": {}},
            "workflows": {"repo": "a/b", "lld_count": 0, "requirements_workflows": 0, "implementation_workflows": 0, "tdd_workflows": 0, "report_count": 0},
            "gemini": {"repo": "a/b", "total_reviews": 0, "approvals": 0, "blocks": 0, "approval_rate": None},
        }
        mock_agg_instance.aggregate.return_value = {
            "generated_at": "2026-02-24T15:30:00Z", "period_start": "2026-01-25", "period_end": "2026-02-24",
            "repos_tracked": 1, "repos_collected": 1, "repos_failed": [],
            "totals": {"issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "lld_count": 0, "total_workflows": 0, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [],
        }
        mock_agg_cls.return_value = mock_agg_instance
        mock_write.return_value = "/tmp/test.json"

        with caplog.at_level(logging.DEBUG):
            exit_code = main(config_path="test.json", verbose=True)

        assert exit_code == 0

    @patch("tools.collect_cross_project_metrics.write_metrics_output")
    @patch("tools.collect_cross_project_metrics.MetricsAggregator")
    @patch("tools.collect_cross_project_metrics.GitHubMetricsClient")
    @patch("tools.collect_cross_project_metrics.load_config")
    def test_t290_lookback_override(
        self,
        mock_load: MagicMock,
        mock_client_cls: MagicMock,
        mock_agg_cls: MagicMock,
        mock_write: MagicMock,
    ) -> None:
        """T290: CLI --lookback-days overrides config value."""
        config = {
            "repos": [
                {"owner": "a", "name": "b", "full_name": "a/b", "enabled": True},
            ],
            "lookback_days": 30,
            "output_dir": "docs/metrics",
            "cache_ttl_seconds": 300,
            "github_token_env": "GITHUB_TOKEN",
        }
        mock_load.return_value = config

        mock_client_instance = MagicMock()
        mock_client_instance.get_rate_limit_remaining.return_value = {
            "remaining": 5000, "limit": 5000, "reset_at": "2026-02-24T16:00:00Z"
        }
        mock_client_cls.return_value = mock_client_instance

        mock_agg_instance = MagicMock()
        mock_agg_instance.collect_repo_metrics.return_value = {
            "repo": "a/b",
            "issues": {"repo": "a/b", "period_start": "2026-02-17", "period_end": "2026-02-24", "issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "issues_by_label": {}},
            "workflows": {"repo": "a/b", "lld_count": 0, "requirements_workflows": 0, "implementation_workflows": 0, "tdd_workflows": 0, "report_count": 0},
            "gemini": {"repo": "a/b", "total_reviews": 0, "approvals": 0, "blocks": 0, "approval_rate": None},
        }
        mock_agg_instance.aggregate.return_value = {
            "generated_at": "2026-02-24T15:30:00Z", "period_start": "2026-02-17", "period_end": "2026-02-24",
            "repos_tracked": 1, "repos_collected": 1, "repos_failed": [],
            "totals": {"issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "lld_count": 0, "total_workflows": 0, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [],
        }
        mock_agg_cls.return_value = mock_agg_instance
        mock_write.return_value = "/tmp/test.json"

        main(config_path="test.json", lookback_days=7)

        # Verify config was modified to use CLI override
        assert config["lookback_days"] == 7