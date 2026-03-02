"""Unit tests for assemblyzero.metrics.collector.

Issue #333: Tests for per-repo collection logic.
Tests: T060, T070, T080, T090, T100, T110, T260, T270, T300, T310
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.metrics.collector import (
    CollectionError,
    collect_repo_metrics,
    count_gemini_verdicts,
    count_issues_in_period,
    count_lineage_artifacts,
    detect_workflows_used,
)
from github import UnknownObjectException


def _mock_issue(
    number: int,
    state: str,
    created_at: datetime,
    closed_at: datetime | None = None,
    labels: list[str] | None = None,
    is_pr: bool = False,
) -> MagicMock:
    """Create a mock PyGithub Issue."""
    issue = MagicMock()
    issue.number = number
    issue.state = state
    issue.created_at = created_at
    issue.closed_at = closed_at
    issue.pull_request = MagicMock() if is_pr else None
    mock_labels = []
    for label_name in (labels or []):
        lbl = MagicMock()
        lbl.name = label_name
        mock_labels.append(lbl)
    issue.labels = mock_labels
    return issue


def _mock_content_file(
    name: str,
    file_type: str = "dir",
    content: str | None = None,
    path: str | None = None,
) -> MagicMock:
    """Create a mock PyGithub ContentFile."""
    cf = MagicMock()
    cf.name = name
    cf.type = file_type
    cf.path = path or f"docs/{name}"
    if content is not None:
        cf.content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    else:
        cf.content = None
    return cf


class TestCountIssuesInPeriod:
    """Tests for count_issues_in_period()."""

    def test_counts_issues_correctly(self) -> None:
        """T060: Returns correct (created, closed, open) tuple."""
        repo = MagicMock()
        period_start = datetime(2026, 2, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 2, 25, tzinfo=timezone.utc)

        all_issues = [
            _mock_issue(1, "closed", datetime(2026, 2, 5, tzinfo=timezone.utc), datetime(2026, 2, 10, tzinfo=timezone.utc)),
            _mock_issue(2, "closed", datetime(2026, 2, 8, tzinfo=timezone.utc), datetime(2026, 2, 15, tzinfo=timezone.utc)),
            _mock_issue(3, "open", datetime(2026, 2, 12, tzinfo=timezone.utc)),
            _mock_issue(4, "open", datetime(2026, 2, 20, tzinfo=timezone.utc)),
        ]
        open_issues = [
            _mock_issue(3, "open", datetime(2026, 2, 12, tzinfo=timezone.utc)),
            _mock_issue(4, "open", datetime(2026, 2, 20, tzinfo=timezone.utc)),
        ]
        repo.get_issues.side_effect = lambda state, since=None: all_issues if state == "all" else open_issues

        created, closed, open_now = count_issues_in_period(repo, period_start, period_end)
        assert created == 4
        assert closed == 2
        assert open_now == 2

    def test_skips_pull_requests(self) -> None:
        """PRs are excluded from issue counts."""
        repo = MagicMock()
        period_start = datetime(2026, 2, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 2, 25, tzinfo=timezone.utc)

        all_issues = [
            _mock_issue(1, "closed", datetime(2026, 2, 5, tzinfo=timezone.utc), datetime(2026, 2, 10, tzinfo=timezone.utc)),
            _mock_issue(2, "closed", datetime(2026, 2, 8, tzinfo=timezone.utc), datetime(2026, 2, 12, tzinfo=timezone.utc), is_pr=True),
        ]
        open_issues = [
            _mock_issue(3, "open", datetime(2026, 2, 15, tzinfo=timezone.utc), is_pr=True),
        ]
        repo.get_issues.side_effect = lambda state, since=None: all_issues if state == "all" else open_issues

        created, closed, open_now = count_issues_in_period(repo, period_start, period_end)
        assert created == 1  # Only issue #1, not PR #2
        assert closed == 1   # Only issue #1, not PR #2
        assert open_now == 0  # PR #3 is filtered out

    def test_no_issues_returns_zeros(self) -> None:
        """No issues in period returns (0, 0, 0)."""
        repo = MagicMock()
        period_start = datetime(2026, 2, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 2, 25, tzinfo=timezone.utc)

        repo.get_issues.return_value = []

        created, closed, open_now = count_issues_in_period(repo, period_start, period_end)
        assert created == 0
        assert closed == 0
        assert open_now == 0

    def test_configurable_period_7_days(self) -> None:
        """T300: Respects 7-day period for date range filtering."""
        repo = MagicMock()
        period_start = datetime(2026, 2, 18, tzinfo=timezone.utc)
        period_end = datetime(2026, 2, 25, tzinfo=timezone.utc)

        all_issues = [
            _mock_issue(1, "open", datetime(2026, 2, 20, tzinfo=timezone.utc)),
            _mock_issue(2, "closed", datetime(2026, 2, 1, tzinfo=timezone.utc), datetime(2026, 2, 19, tzinfo=timezone.utc)),
        ]
        open_issues = [_mock_issue(1, "open", datetime(2026, 2, 20, tzinfo=timezone.utc))]
        repo.get_issues.side_effect = lambda state, since=None: all_issues if state == "all" else open_issues

        created, closed, open_now = count_issues_in_period(repo, period_start, period_end)
        assert created == 1  # Only issue #1 created in window
        assert closed == 1   # Issue #2 closed in window
        assert open_now == 1


class TestDetectWorkflowsUsed:
    """Tests for detect_workflows_used()."""

    def test_detects_from_labels(self) -> None:
        """T070: Returns dict with correct workflow type counts from labels."""
        repo = MagicMock()
        issues = [
            _mock_issue(1, "closed", datetime(2026, 2, 1, tzinfo=timezone.utc), labels=["workflow:requirements"]),
            _mock_issue(2, "open", datetime(2026, 2, 5, tzinfo=timezone.utc), labels=["workflow:requirements", "workflow:tdd"]),
            _mock_issue(3, "closed", datetime(2026, 2, 10, tzinfo=timezone.utc), labels=["workflow:tdd"]),
            _mock_issue(4, "open", datetime(2026, 2, 15, tzinfo=timezone.utc), labels=["bug"]),
        ]
        repo.get_issues.return_value = issues

        result = detect_workflows_used(repo)
        assert result == {"requirements": 2, "tdd": 2}

    def test_heuristic_fallback_from_filenames(self) -> None:
        """T310: Detects workflows from LLD filenames when no workflow labels."""
        repo = MagicMock()
        # No workflow labels on issues
        issues = [
            _mock_issue(1, "open", datetime(2026, 2, 1, tzinfo=timezone.utc), labels=["bug"]),
        ]
        repo.get_issues.return_value = issues

        # LLD filenames contain workflow keywords
        active_contents = [
            _mock_content_file("333-requirements-analysis", "dir"),
            _mock_content_file("334-tdd-workflow", "dir"),
        ]
        done_contents = [
            _mock_content_file("300-requirements-setup", "dir"),
        ]
        repo.get_contents.side_effect = lambda path: (
            active_contents if "active" in path else done_contents
        )

        result = detect_workflows_used(repo)
        assert "requirements" in result
        assert result["requirements"] >= 2
        assert "tdd" in result

    def test_empty_repo_returns_empty_dict(self) -> None:
        """Empty repo with no issues and no LLD dirs returns empty dict."""
        repo = MagicMock()
        repo.get_issues.return_value = []
        repo.get_contents.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )

        result = detect_workflows_used(repo)
        assert result == {}


class TestCountLineageArtifacts:
    """Tests for count_lineage_artifacts()."""

    def test_counts_lld_folders(self) -> None:
        """T080: Returns correct LLD count from active + done dirs."""
        repo = MagicMock()
        active_contents = [
            _mock_content_file("333-metrics", "dir"),
            _mock_content_file("334-auth", "dir"),
        ]
        done_contents = [
            _mock_content_file("300-setup", "dir"),
            _mock_content_file("301-ci", "dir"),
            _mock_content_file("302-deploy", "dir"),
        ]
        repo.get_contents.side_effect = lambda path: (
            active_contents if "active" in path else done_contents
        )

        count = count_lineage_artifacts(repo)
        assert count == 5

    def test_missing_directory_returns_zero(self) -> None:
        """T110: Returns 0 if docs/lld/ directories don't exist."""
        repo = MagicMock()
        repo.full_name = "test/repo"
        repo.get_contents.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )

        count = count_lineage_artifacts(repo)
        assert count == 0

    def test_single_item_not_list(self) -> None:
        """Returns 1 when get_contents returns a single ContentFile (not list)."""
        repo = MagicMock()
        single_item = _mock_content_file("333-only", "dir")
        # First call returns single item, second raises 404
        repo.get_contents.side_effect = [
            single_item,
            UnknownObjectException(404, {"message": "Not Found"}, {}),
        ]

        count = count_lineage_artifacts(repo)
        assert count == 1


class TestCountGeminiVerdicts:
    """Tests for count_gemini_verdicts()."""

    def test_counts_verdicts_correctly(self) -> None:
        """T090: Returns correct (total, approvals, blocks) tuple."""
        repo = MagicMock()
        repo.full_name = "test/repo"

        report_dirs = [
            _mock_content_file("333", "dir", path="docs/reports/333"),
            _mock_content_file("334", "dir", path="docs/reports/334"),
        ]
        dir_333_files = [
            _mock_content_file(
                "gemini-review-333.md", "file",
                content="Verdict: APPROVE\nDetails...",
                path="docs/reports/333/gemini-review-333.md",
            ),
            _mock_content_file(
                "gemini-review-333-2.md", "file",
                content="Status: APPROVE\nOK",
                path="docs/reports/333/gemini-review-333-2.md",
            ),
        ]
        dir_334_files = [
            _mock_content_file(
                "gemini-review-334.md", "file",
                content="Verdict: BLOCK\nIssue found",
                path="docs/reports/334/gemini-review-334.md",
            ),
            _mock_content_file(
                "gemini-review-334-2.md", "file",
                content="Verdict: APPROVE\nGood",
                path="docs/reports/334/gemini-review-334-2.md",
            ),
        ]

        def get_contents_side_effect(path: str) -> list[MagicMock]:
            if path == "docs/reports":
                return report_dirs
            if "333" in path:
                return dir_333_files
            if "334" in path:
                return dir_334_files
            return []

        repo.get_contents.side_effect = get_contents_side_effect

        total, approvals, blocks = count_gemini_verdicts(repo)
        assert total == 4
        assert approvals == 3
        assert blocks == 1

    def test_no_reports_dir_returns_zeros(self) -> None:
        """docs/reports/ missing returns (0, 0, 0)."""
        repo = MagicMock()
        repo.full_name = "test/repo"
        repo.get_contents.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )

        total, approvals, blocks = count_gemini_verdicts(repo)
        assert total == 0
        assert approvals == 0
        assert blocks == 0

    def test_non_gemini_files_skipped(self) -> None:
        """Files not matching gemini-*.md pattern are skipped."""
        repo = MagicMock()
        repo.full_name = "test/repo"

        report_dirs = [
            _mock_content_file("333", "dir", path="docs/reports/333"),
        ]
        dir_files = [
            _mock_content_file(
                "implementation-report.md", "file",
                content="Not a gemini file",
                path="docs/reports/333/implementation-report.md",
            ),
            _mock_content_file(
                "gemini-review-333.md", "file",
                content="Verdict: APPROVE\nOK",
                path="docs/reports/333/gemini-review-333.md",
            ),
        ]

        def get_contents_side_effect(path: str) -> list[MagicMock]:
            if path == "docs/reports":
                return report_dirs
            return dir_files

        repo.get_contents.side_effect = get_contents_side_effect

        total, approvals, blocks = count_gemini_verdicts(repo)
        assert total == 1  # Only the gemini file
        assert approvals == 1
        assert blocks == 0


class TestCollectRepoMetrics:
    """Tests for collect_repo_metrics()."""

    @patch("assemblyzero.metrics.collector.Github")
    def test_unreachable_repo_raises_collection_error(self, mock_github_cls: MagicMock) -> None:
        """T100: Raises CollectionError for unreachable repo."""
        mock_gh = MagicMock()
        mock_github_cls.return_value = mock_gh
        mock_gh.get_repo.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )

        with pytest.raises(CollectionError, match="martymcenroe/NonExistent"):
            collect_repo_metrics("martymcenroe/NonExistent", "ghp_fake_token")

    @patch("assemblyzero.metrics.collector.Github")
    def test_token_passed_to_github(self, mock_github_cls: MagicMock) -> None:
        """T260: Token passed to Github() constructor."""
        mock_gh = MagicMock()
        mock_github_cls.return_value = mock_gh
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_issues.return_value = []
        mock_repo.get_contents.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )
        mock_repo.full_name = "martymcenroe/AssemblyZero"

        collect_repo_metrics("martymcenroe/AssemblyZero", "ghp_real_token", period_days=30)
        mock_github_cls.assert_called_once_with("ghp_real_token", timeout=30)

    @patch("assemblyzero.metrics.collector.Github")
    def test_empty_token_no_auth(self, mock_github_cls: MagicMock) -> None:
        """T270: Empty token calls Github() without token."""
        mock_gh = MagicMock()
        mock_github_cls.return_value = mock_gh
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_issues.return_value = []
        mock_repo.get_contents.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )
        mock_repo.full_name = "martymcenroe/PublicRepo"

        collect_repo_metrics("martymcenroe/PublicRepo", "", period_days=30)
        mock_github_cls.assert_called_once_with(timeout=30)

    @patch("assemblyzero.metrics.collector.Github")
    def test_returns_repo_metrics_dict(self, mock_github_cls: MagicMock) -> None:
        """collect_repo_metrics returns a RepoMetrics dict with all required keys."""
        mock_gh = MagicMock()
        mock_github_cls.return_value = mock_gh
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_issues.return_value = []
        mock_repo.get_contents.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )
        mock_repo.full_name = "test/repo"

        result = collect_repo_metrics("test/repo", "ghp_token", period_days=7)
        assert result["repo"] == "test/repo"
        assert "period_start" in result
        assert "period_end" in result
        assert "issues_created" in result
        assert "collection_timestamp" in result
