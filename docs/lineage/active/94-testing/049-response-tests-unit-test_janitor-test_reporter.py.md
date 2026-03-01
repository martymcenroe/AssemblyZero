

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

    def test_create_report_filename_format(self, tmp_path):
        """create_report uses janitor-report-YYYY-MM-DD-HHMMSS.md naming."""
        reporter = LocalFileReporter(str(tmp_path))
        result = reporter.create_report("Janitor Report", "# Test", "info")

        filename = Path(result).name
        assert filename.startswith("janitor-report-")
        assert filename.endswith(".md")
        # Verify date portion is present (YYYY-MM-DD)
        date_part = filename[len("janitor-report-"):len("janitor-report-") + 10]
        assert len(date_part) == 10
        assert date_part[4] == "-"
        assert date_part[7] == "-"

    def test_create_report_content_encoding(self, tmp_path):
        """create_report writes UTF-8 encoded content."""
        reporter = LocalFileReporter(str(tmp_path))
        body = "# Report\n\n- ✅ Fixed link\n- ⚠️ Warning\n- ❌ Error"
        result = reporter.create_report("Janitor Report", body, "warning")

        content = Path(result).read_text(encoding="utf-8")
        assert "✅" in content
        assert "⚠️" in content
        assert "❌" in content

    def test_update_report_preserves_path(self, tmp_path):
        """update_report returns the same path that was passed in."""
        reporter = LocalFileReporter(str(tmp_path))
        path = reporter.create_report("Janitor Report", "# Original", "info")

        returned_path = reporter.update_report(path, "# New Content", "warning")
        assert returned_path == path

    def test_find_existing_report_returns_first_match(self, tmp_path):
        """find_existing_report returns the first sorted match for today."""
        reporter = LocalFileReporter(str(tmp_path))
        # Create two reports for today
        path1 = reporter.create_report("Janitor Report", "# First", "info")
        # The second report will have a later timestamp
        path2 = reporter.create_report("Janitor Report", "# Second", "info")

        found = reporter.find_existing_report()
        assert found is not None
        # Should return first sorted (earliest timestamp)
        assert found == path1

    def test_reporter_dir_already_exists(self, tmp_path):
        """LocalFileReporter handles pre-existing janitor-reports/ dir."""
        (tmp_path / "janitor-reports").mkdir()
        reporter = LocalFileReporter(str(tmp_path))
        assert (tmp_path / "janitor-reports").is_dir()
        # Should not raise


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

    def test_find_existing_report_gh_failure(self):
        """find_existing_report returns None when gh command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=1, stdout=""),  # gh issue list fails
            ]
            reporter = GitHubReporter("/repo")
            result = reporter.find_existing_report()

        assert result is None

    def test_find_existing_report_invalid_json(self):
        """find_existing_report returns None on malformed JSON."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0, stdout="not valid json"),
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

    def test_create_report_failure(self):
        """create_report raises RuntimeError on gh failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=1, stdout="", stderr="permission denied"),
            ]
            reporter = GitHubReporter("/repo")
            with pytest.raises(RuntimeError, match="Failed to create GitHub issue"):
                reporter.create_report("Janitor Report", "# Body", "warning")

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

    def test_update_report_failure(self):
        """update_report raises RuntimeError on gh failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=1, stdout="", stderr="not found"),
            ]
            reporter = GitHubReporter("/repo")
            with pytest.raises(RuntimeError, match="Failed to update GitHub issue"):
                reporter.update_report(
                    "https://github.com/user/repo/issues/42", "# Updated", "warning"
                )

    def test_update_report_extracts_issue_number(self):
        """update_report correctly extracts issue number from URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0),  # edit
            ]
            reporter = GitHubReporter("/repo")
            reporter.update_report(
                "https://github.com/martymcenroe/AssemblyZero/issues/99",
                "# Updated",
                "critical",
            )

        edit_call = mock_run.call_args_list[1]
        assert "99" in edit_call.args[0]

    def test_create_report_uses_maintenance_label(self):
        """create_report passes --label maintenance to gh issue create."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(
                    returncode=0,
                    stdout="https://github.com/user/repo/issues/43\n",
                ),
            ]
            reporter = GitHubReporter("/repo")
            reporter.create_report("Janitor Report", "# Body", "warning")

        create_call = mock_run.call_args_list[1]
        cmd_args = create_call.args[0]
        assert "--label" in cmd_args
        label_idx = cmd_args.index("--label")
        assert cmd_args[label_idx + 1] == "maintenance"


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

    def test_build_report_body_no_probe_errors(self):
        """build_report_body omits Probe Errors section when no errors."""
        body = build_report_body(
            [],
            [],
            [ProbeResult(probe="links", status="ok")],
        )
        assert "## Probe Errors" not in body

    def test_build_report_body_multiple_unfixable_categories(self):
        """build_report_body groups unfixable findings by category."""
        unfixable = [
            Finding(probe="todo", category="stale_todo", message="TODO 1", severity="info", fixable=False, file_path="a.py", line_number=1),
            Finding(probe="todo", category="stale_todo", message="TODO 2", severity="info", fixable=False, file_path="b.py", line_number=2),
            Finding(probe="harvest", category="cross_project_drift", message="Drift 1", severity="warning", fixable=False),
        ]
        body = build_report_body(unfixable, [], [])

        assert "### stale_todo" in body
        assert "### cross_project_drift" in body
        assert "TODO 1" in body
        assert "TODO 2" in body
        assert "Drift 1" in body

    def test_build_report_body_fix_action_not_applied(self):
        """build_report_body shows different icon for unapplied fixes."""
        fix_actions = [
            FixAction(
                category="broken_link",
                description="Would fix link in README.md",
                files_modified=["README.md"],
                commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
                applied=False,
            )
        ]
        body = build_report_body([], fix_actions, [])
        assert "🔲" in body
        assert "Would fix link in README.md" in body

    def test_build_report_body_applied_fix_checkmark(self):
        """build_report_body shows checkmark for applied fixes."""
        fix_actions = [
            FixAction(
                category="broken_link",
                description="Fixed link in README.md",
                files_modified=["README.md"],
                commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
                applied=True,
            )
        ]
        body = build_report_body([], fix_actions, [])
        assert "✅" in body

    def test_build_report_body_finding_location_with_line(self):
        """build_report_body includes file:line location for findings."""
        unfixable = [
            Finding(
                probe="todo",
                category="stale_todo",
                message="Stale TODO",
                severity="info",
                fixable=False,
                file_path="tools/helper.py",
                line_number=42,
            )
        ]
        body = build_report_body(unfixable, [], [])
        assert "tools/helper.py:42" in body

    def test_build_report_body_finding_location_without_line(self):
        """build_report_body includes file path without line when line_number is None."""
        unfixable = [
            Finding(
                probe="harvest",
                category="cross_project_drift",
                message="Drift detected",
                severity="warning",
                fixable=False,
                file_path="pyproject.toml",
                line_number=None,
            )
        ]
        body = build_report_body(unfixable, [], [])
        assert "pyproject.toml)" in body

    def test_build_report_body_all_zero_severity(self):
        """build_report_body shows zero counts when no findings."""
        body = build_report_body([], [], [])
        assert "| Critical | 0 |" in body
        assert "| Warning | 0 |" in body
        assert "| Info | 0 |" in body

    def test_build_report_body_multiple_probe_errors(self):
        """build_report_body lists all probe errors."""
        probe_results = [
            ProbeResult(probe="links", status="error", error_message="Permission denied"),
            ProbeResult(probe="harvest", status="error", error_message="Script not found"),
            ProbeResult(probe="todo", status="ok"),
        ]
        body = build_report_body([], [], probe_results)
        assert "## Probe Errors" in body
        assert "links" in body
        assert "Permission denied" in body
        assert "harvest" in body
        assert "Script not found" in body


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
