"""Unit tests for CLI exit codes.

Issue #333: Tests for tools/collect-cross-project-metrics.py main() function.
Tests: T280, T290
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.metrics.collector import CollectionError
from assemblyzero.metrics.models import RepoMetrics

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_cli_module():
    """Dynamically import the hyphenated CLI module."""
    spec = importlib.util.spec_from_file_location(
        "collect_cross_project_metrics",
        _PROJECT_ROOT / "tools" / "collect-cross-project-metrics.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_test_metrics(repo: str) -> RepoMetrics:
    """Create test RepoMetrics."""
    return RepoMetrics(
        repo=repo,
        period_start="2026-01-26T00:00:00+00:00",
        period_end="2026-02-25T00:00:00+00:00",
        issues_created=10,
        issues_closed=8,
        issues_open=2,
        workflows_used={"requirements": 3},
        llds_generated=5,
        gemini_reviews=4,
        gemini_approvals=3,
        gemini_blocks=1,
        collection_timestamp="2026-02-25T14:30:00+00:00",
    )


class TestCLIExitCodes:
    """Tests for CLI exit codes (T280, T290)."""

    @patch("assemblyzero.metrics.cache.load_cached_metrics", return_value=None)
    @patch("assemblyzero.metrics.collector.collect_repo_metrics")
    @patch("assemblyzero.metrics.config.load_config")
    def test_partial_failure_exit_code_1(
        self,
        mock_load_config: MagicMock,
        mock_collect: MagicMock,
        mock_cache: MagicMock,
        tmp_path: Path,
    ) -> None:
        """T280: Partial failure returns exit code 1."""
        mod = _load_cli_module()

        mock_load_config.return_value = {
            "repos": ["test/a", "test/b", "test/c"],
            "cache_ttl_minutes": 60,
            "github_token_env": "GITHUB_TOKEN",
        }
        mock_collect.side_effect = [
            _make_test_metrics("test/a"),
            _make_test_metrics("test/b"),
            CollectionError("unreachable"),
        ]

        with patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}):
            exit_code = mod.main([
                "--no-cache",
                "--output-dir", str(tmp_path),
                "--format", "json",
            ])
        assert exit_code == 1

    @patch("assemblyzero.metrics.cache.load_cached_metrics", return_value=None)
    @patch("assemblyzero.metrics.collector.collect_repo_metrics")
    @patch("assemblyzero.metrics.config.load_config")
    def test_complete_failure_exit_code_2(
        self,
        mock_load_config: MagicMock,
        mock_collect: MagicMock,
        mock_cache: MagicMock,
        tmp_path: Path,
    ) -> None:
        """T290: Complete failure returns exit code 2."""
        mod = _load_cli_module()

        mock_load_config.return_value = {
            "repos": ["test/a", "test/b", "test/c"],
            "cache_ttl_minutes": 60,
            "github_token_env": "GITHUB_TOKEN",
        }
        mock_collect.side_effect = CollectionError("all unreachable")

        with patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}):
            exit_code = mod.main([
                "--no-cache",
                "--output-dir", str(tmp_path),
                "--format", "json",
            ])
        assert exit_code == 2

    @patch("assemblyzero.metrics.config.load_config")
    def test_config_error_exit_code_2(
        self,
        mock_load_config: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Config error returns exit code 2."""
        from assemblyzero.metrics.config import ConfigError

        mod = _load_cli_module()
        mock_load_config.side_effect = ConfigError("Config file not found")

        exit_code = mod.main([
            "--output-dir", str(tmp_path),
            "--format", "json",
        ])
        assert exit_code == 2

    @patch("assemblyzero.metrics.cache.load_cached_metrics", return_value=None)
    @patch("assemblyzero.metrics.collector.collect_repo_metrics")
    @patch("assemblyzero.metrics.config.load_config")
    def test_all_success_exit_code_0(
        self,
        mock_load_config: MagicMock,
        mock_collect: MagicMock,
        mock_cache: MagicMock,
        tmp_path: Path,
    ) -> None:
        """All repos collected successfully returns exit code 0."""
        mod = _load_cli_module()

        mock_load_config.return_value = {
            "repos": ["test/a", "test/b"],
            "cache_ttl_minutes": 60,
            "github_token_env": "GITHUB_TOKEN",
        }
        mock_collect.side_effect = [
            _make_test_metrics("test/a"),
            _make_test_metrics("test/b"),
        ]

        with patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}):
            exit_code = mod.main([
                "--no-cache",
                "--output-dir", str(tmp_path),
                "--format", "json",
            ])
        assert exit_code == 0


class TestCLIArgParsing:
    """Tests for CLI argument parsing."""

    def test_parse_args_defaults(self) -> None:
        """Default argument values are correct."""
        mod = _load_cli_module()
        args = mod._parse_args([])
        assert args.config is None
        assert args.period_days == 30
        assert args.output_format == "both"
        assert args.no_cache is False
        assert args.verbose is False

    def test_parse_args_custom(self, tmp_path: Path) -> None:
        """Custom arguments are parsed correctly."""
        mod = _load_cli_module()
        args = mod._parse_args([
            "--config", str(tmp_path / "config.json"),
            "--period-days", "7",
            "--format", "markdown",
            "--no-cache",
            "--verbose",
        ])
        assert args.config == tmp_path / "config.json"
        assert args.period_days == 7
        assert args.output_format == "markdown"
        assert args.no_cache is True
        assert args.verbose is True
