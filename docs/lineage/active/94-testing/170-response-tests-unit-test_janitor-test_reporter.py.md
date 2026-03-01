

```python
"""Tests for janitor reporters.

Issue #94: Lu-Tze: The Janitor
Test IDs: T150-T180, T270-T300, T360-T380
"""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.janitor.reporter import (
    GitHubReporter,
    LocalFileReporter,
    build_report_body,
    get_reporter,
)
from assemblyzero.workflows.janitor.state import (
    Finding,
    FixAction,
    ProbeResult,
)


class TestLocalFileReporter:
    """Test LocalFileReporter. T150-T170, T270-T290, T380."""

    def test_create_report(self, tmp_path):
        """T150/T270/T380: create_report writes markdown file to janitor-reports/."""
        reporter = LocalFileReporter(str(tmp_path))
        result = reporter.create_report(
            "Janitor Report", "# Test Report\nContent here", "warning"
        )

        assert result.startswith(str(tmp_path / "janitor-reports"))
        assert result.endswith(".md")
        assert Path(result).exists()
        assert "# Test Report" in Path(result).read_text()

    def test_update_report(self, tmp_path):
        """T160/T280: update_report overwrites existing file."""
        reporter = LocalFileReporter(str(tmp_path))
        path = reporter.create_report("Janitor Report", "# Original", "info")

        updated_path = reporter.update_report(path, "# Updated", "warning")

        assert updated_path == path
        assert Path(path).read_text() == "# Updated"

    def test_find_existing_report_today(self, tmp_path):
        """T170/T290: find_existing_report returns path for today's report."""
        reporter = LocalFileReporter(str(tmp_path))
        created_path = reporter.create_report("Janitor Report", "# Test", "info")

        found = reporter.find_existing_report()

        assert found is not None
        assert found == created_path

    def test_find_existing_report_none(self, tmp_path):
        """find_existing_report returns None when no report exists."""
        reporter = LocalFileReporter(str(tmp_path))
        assert reporter.find_existing_report() is None

    def test_creates_janitor_reports_dir(self, tmp_path):
        """LocalFileReporter creates janitor-reports/ directory on init."""
        reporter = LocalFileReporter(str(tmp_path))
        assert (tmp_path / "janitor-reports").is_dir()


class TestGitHubReporter:
    """Test GitHubReporter. T360, T370."""

    def test_init_with_gh_auth(self):
        """GitHubReporter initializes successfully with gh auth."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            reporter = GitHubReporter("/repo")
        assert reporter.repo_root == "/repo"

    def test_init_with_github_token(self):
        """T360: GitHubReporter falls back to GITHUB_TOKEN."""
        with patch("subprocess.run") as mock_run, patch.dict(
            os.environ, {"GITHUB_TOKEN": "ghp_test123"}
        ):
            mock_run.return_value = MagicMock(returncode=1)
            reporter = GitHubReporter("/repo")
        assert reporter.repo_root == "/repo"

    def test_init_no_auth_raises(self):
        """GitHubReporter raises RuntimeError without auth."""
        with patch("subprocess.run") as mock_run, patch.dict(
            os.environ, {}, clear=True
        ):
            # Remove GITHUB_TOKEN if set
            os.environ.pop("GITHUB_TOKEN", None)
            mock_run.return_value = MagicMock(returncode=1)
            with pytest.raises(RuntimeError, match="gh CLI not authenticated"):
                GitHubReporter("/repo")

    def test_find_existing_report(self):
        """T370: find_existing_report returns existing issue URL."""
        with patch("subprocess.run") as mock_run:
            # First call: gh auth status (success)
            # Second call: gh issue list (returns issue)
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(
                    returncode=0,
                    stdout=json.dumps(
                        [{"url": "https://github.com/user/repo/issues/42"}]
                    ),
                ),
            ]
            reporter = GitHubReporter("/repo")
            result = reporter.find_existing_report()

        assert result == "https://github.com/user/repo/issues/42"

    def test_find_existing_report_none(self):
        """find_existing_report returns None when no matching issue."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0, stdout="[]"),  # no issues
            ]
            reporter = GitHubReporter("/repo")
            result = reporter.find_existing_report()

        assert result is None

    def test_create_report(self):
        """create_report calls gh issue create."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(
                    returncode=0,
                    stdout="https://github.com/user/repo/issues/43\n",
                ),
            ]
            reporter = GitHubReporter("/repo")
            url = reporter.create_report("Janitor Report", "# Body", "warning")

        assert url == "https://github.com/user/repo/issues/43"

    def test_update_report(self):
        """update_report calls gh issue edit."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0),  # edit
            ]
            reporter = GitHubReporter("/repo")
            url = reporter.update_report(
                "https://github.com/user/repo/issues/42", "# Updated", "warning"
            )

        assert url == "https://github.com/user/repo/issues/42"
        # Verify gh issue edit was called with correct issue number
        edit_call = mock_run.call_args_list[1]
        assert "42" in edit_call.args[0]


class TestBuildReportBody:
    """Test report body generation. T180, T300."""

    def test_build_report_body_all_sections(self):
        """T180/T300: build_report_body produces markdown with all sections."""
        unfixable = [
            Finding(
                probe="todo",
                category="stale_todo",
                message="Stale TODO in helper.py:42",
                severity="info",
                fixable=False,
                file_path="tools/helper.py",
                line_number=42,
            )
        ]
        fix_actions = [
            FixAction(
                category="broken_link",
                description="Fixed link in README.md",
                files_modified=["README.md"],
                commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
                applied=True,
            )
        ]
        probe_results = [
            ProbeResult(probe="links", status="findings", findings=[]),
            ProbeResult(probe="harvest", status="error", error_message="Script not found"),
        ]

        body = build_report_body(unfixable, fix_actions, probe_results)

        assert "# Janitor Report" in body
        assert "## Summary" in body
        assert "## Auto-Fixed Issues" in body
        assert "Fixed link in README.md" in body
        assert "## Requires Human Attention" in body
        assert "stale_todo" in body
        assert "## Probe Errors" in body
        assert "harvest" in body
        assert "Script not found" in body

    def test_build_report_body_no_unfixable(self):
        """build_report_body handles empty unfixable findings."""
        body = build_report_body([], [], [])
        assert "No issues require human attention" in body
        assert "No auto-fixes applied" in body

    def test_build_report_body_severity_counts(self):
        """build_report_body counts severities correctly."""
        unfixable = [
            Finding(probe="links", category="c1", message="m1", severity="warning", fixable=False),
            Finding(probe="links", category="c2", message="m2", severity="critical", fixable=False),
            Finding(probe="links", category="c3", message="m3", severity="info", fixable=False),
        ]
        body = build_report_body(unfixable, [], [])
        assert "| Critical | 1 |" in body
        assert "| Warning | 1 |" in body
        assert "| Info | 1 |" in body


class TestGetReporter:
    """Test reporter factory."""

    def test_get_reporter_local(self, tmp_path):
        """get_reporter returns LocalFileReporter for 'local'."""
        reporter = get_reporter("local", str(tmp_path))
        assert isinstance(reporter, LocalFileReporter)

    def test_get_reporter_github(self):
        """get_reporter returns GitHubReporter for 'github'."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            reporter = get_reporter("github", "/repo")
        assert isinstance(reporter, GitHubReporter)
```
