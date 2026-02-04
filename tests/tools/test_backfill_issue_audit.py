"""Unit tests for backfill_issue_audit.py tool.

Issue #72: Backfill Audit Directory Structure
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import from tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from backfill_issue_audit import (
    AUDIT_ACTIVE_DIR,
    AUDIT_DONE_DIR,
    MANAGED_FILES,
    BackfillResult,
    Comment,
    Issue,
    generate_comments_markdown,
    generate_issue_markdown,
    generate_issue_slug,
    generate_metadata_json,
    get_audit_dir,
    is_managed_file,
    parse_args,
    write_audit_files,
)


# =============================================================================
# Fixtures
# =============================================================================

FIXTURES_DIR = Path(__file__).parent.parent.parent / "tools" / "fixtures"


@pytest.fixture
def sample_issues():
    """Load sample issues from fixture."""
    with open(FIXTURES_DIR / "sample_issues.json") as f:
        return json.load(f)


@pytest.fixture
def sample_comments():
    """Load sample comments from fixture."""
    with open(FIXTURES_DIR / "sample_comments.json") as f:
        return json.load(f)


@pytest.fixture
def open_issue():
    """Create an open Issue object."""
    return Issue(
        number=42,
        title="Add user authentication",
        body="Implement OAuth2 authentication flow.",
        state="open",
        created_at="2024-01-15T10:30:00Z",
        updated_at="2024-01-20T14:45:00Z",
        closed_at=None,
        author="developer1",
        labels=["enhancement", "security"],
        assignees=["developer1"],
        url="https://github.com/example/repo/issues/42",
        comments_url="https://github.com/example/repo/issues/42/comments",
    )


@pytest.fixture
def closed_issue():
    """Create a closed Issue object."""
    return Issue(
        number=17,
        title="Fix database connection leak",
        body="Database connections are not being properly closed.",
        state="closed",
        created_at="2024-01-10T08:00:00Z",
        updated_at="2024-01-12T16:30:00Z",
        closed_at="2024-01-12T16:30:00Z",
        author="bugfinder",
        labels=["bug", "database"],
        assignees=["developer2", "developer3"],
        url="https://github.com/example/repo/issues/17",
        comments_url="https://github.com/example/repo/issues/17/comments",
    )


@pytest.fixture
def sample_comment_list():
    """Create sample Comment objects."""
    return [
        Comment(
            id=1001,
            author="reviewer1",
            body="Looks good! Can you add tests?",
            created_at="2024-01-16T11:00:00Z",
            url="https://github.com/example/repo/issues/42#issuecomment-1001",
        ),
        Comment(
            id=1002,
            author="developer1",
            body="Good point, I'll add tests.",
            created_at="2024-01-16T14:30:00Z",
            url="https://github.com/example/repo/issues/42#issuecomment-1002",
        ),
    ]


# =============================================================================
# Slug Generation Tests
# =============================================================================


class TestGenerateIssueSlug:
    """Tests for generate_issue_slug function."""

    def test_basic_title(self):
        """Should convert title to lowercase slug."""
        assert generate_issue_slug("Add User Authentication") == "add-user-authentication"

    def test_removes_special_characters(self):
        """Should remove special characters."""
        assert generate_issue_slug("Fix: Bug #123") == "fix-bug-123"

    def test_collapses_multiple_hyphens(self):
        """Should collapse multiple hyphens."""
        assert generate_issue_slug("Fix -- Multiple --- Hyphens") == "fix-multiple-hyphens"

    def test_truncates_long_titles(self):
        """Should truncate to 50 characters."""
        long_title = "A" * 100
        result = generate_issue_slug(long_title)
        assert len(result) <= 50

    def test_handles_underscores(self):
        """Should convert underscores to hyphens."""
        assert generate_issue_slug("add_new_feature") == "add-new-feature"

    def test_strips_leading_trailing_hyphens(self):
        """Should strip leading/trailing hyphens."""
        assert generate_issue_slug("---Fix Bug---") == "fix-bug"


# =============================================================================
# File Generation Tests
# =============================================================================


class TestGenerateIssueMarkdown:
    """Tests for generate_issue_markdown function."""

    def test_includes_title(self, open_issue):
        """Should include issue title."""
        result = generate_issue_markdown(open_issue)
        assert f"# #{open_issue.number}: {open_issue.title}" in result

    def test_includes_url(self, open_issue):
        """Should include issue URL."""
        result = generate_issue_markdown(open_issue)
        assert f"**URL:** {open_issue.url}" in result

    def test_includes_author(self, open_issue):
        """Should include author."""
        result = generate_issue_markdown(open_issue)
        assert f"**Author:** @{open_issue.author}" in result

    def test_includes_body(self, open_issue):
        """Should include issue body."""
        result = generate_issue_markdown(open_issue)
        assert open_issue.body in result

    def test_includes_closed_date_when_closed(self, closed_issue):
        """Should include closed date for closed issues."""
        result = generate_issue_markdown(closed_issue)
        assert f"**Closed:** {closed_issue.closed_at}" in result

    def test_handles_empty_body(self, open_issue):
        """Should handle empty body."""
        open_issue.body = ""
        result = generate_issue_markdown(open_issue)
        assert "*No description provided.*" in result


class TestGenerateCommentsMarkdown:
    """Tests for generate_comments_markdown function."""

    def test_includes_comment_count(self, open_issue, sample_comment_list):
        """Should include total comment count."""
        result = generate_comments_markdown(open_issue, sample_comment_list)
        assert "**Total Comments:** 2" in result

    def test_includes_each_comment(self, open_issue, sample_comment_list):
        """Should include each comment."""
        result = generate_comments_markdown(open_issue, sample_comment_list)
        for comment in sample_comment_list:
            assert f"@{comment.author}" in result
            assert comment.body in result

    def test_handles_no_comments(self, open_issue):
        """Should handle issues with no comments."""
        result = generate_comments_markdown(open_issue, [])
        assert "**Total Comments:** 0" in result
        assert "*No comments on this issue.*" in result


class TestGenerateMetadataJson:
    """Tests for generate_metadata_json function."""

    def test_valid_json(self, open_issue, sample_comment_list):
        """Should generate valid JSON."""
        result = generate_metadata_json(open_issue, sample_comment_list)
        data = json.loads(result)
        assert "schema_version" in data
        assert "issue" in data

    def test_includes_issue_data(self, open_issue, sample_comment_list):
        """Should include issue data."""
        result = generate_metadata_json(open_issue, sample_comment_list)
        data = json.loads(result)
        assert data["issue"]["number"] == open_issue.number
        assert data["issue"]["title"] == open_issue.title

    def test_includes_comment_count(self, open_issue, sample_comment_list):
        """Should include comment count."""
        result = generate_metadata_json(open_issue, sample_comment_list)
        data = json.loads(result)
        assert data["comments"]["count"] == len(sample_comment_list)


# =============================================================================
# Directory Operation Tests
# =============================================================================


class TestGetAuditDir:
    """Tests for get_audit_dir function."""

    def test_open_issue_goes_to_active(self, open_issue, tmp_path):
        """Open issues should go to active directory."""
        result = get_audit_dir(open_issue, tmp_path)
        assert AUDIT_ACTIVE_DIR.name in str(result)

    def test_closed_issue_goes_to_done(self, closed_issue, tmp_path):
        """Closed issues should go to done directory."""
        result = get_audit_dir(closed_issue, tmp_path)
        assert AUDIT_DONE_DIR.name in str(result)

    def test_dir_name_includes_number_and_slug(self, open_issue, tmp_path):
        """Directory name should include issue number and slug."""
        result = get_audit_dir(open_issue, tmp_path)
        assert str(open_issue.number) in result.name
        assert "add-user-authentication" in result.name


class TestIsManagedFile:
    """Tests for is_managed_file function."""

    def test_managed_files(self):
        """Should recognize managed files."""
        assert is_managed_file("001-issue.md") is True
        assert is_managed_file("002-comments.md") is True
        assert is_managed_file("003-metadata.json") is True

    def test_non_managed_files(self):
        """Should not recognize non-managed files."""
        assert is_managed_file("004-custom.md") is False
        assert is_managed_file("notes.md") is False
        assert is_managed_file("README.md") is False


class TestWriteAuditFiles:
    """Tests for write_audit_files function."""

    def test_creates_all_files(self, open_issue, sample_comment_list, tmp_path):
        """Should create all three files."""
        audit_dir = tmp_path / "42-test"
        audit_dir.mkdir()

        files = write_audit_files(audit_dir, open_issue, sample_comment_list)

        assert "001-issue.md" in files
        assert "002-comments.md" in files
        assert "003-metadata.json" in files
        assert (audit_dir / "001-issue.md").exists()
        assert (audit_dir / "002-comments.md").exists()
        assert (audit_dir / "003-metadata.json").exists()

    def test_dry_run_does_not_write(self, open_issue, sample_comment_list, tmp_path):
        """Dry run should not write files."""
        audit_dir = tmp_path / "42-test"
        audit_dir.mkdir()

        files = write_audit_files(audit_dir, open_issue, sample_comment_list, dry_run=True)

        assert len(files) == 3
        assert not (audit_dir / "001-issue.md").exists()

    def test_skips_existing_without_force(self, open_issue, sample_comment_list, tmp_path):
        """Should skip existing files without force flag."""
        audit_dir = tmp_path / "42-test"
        audit_dir.mkdir()
        (audit_dir / "001-issue.md").write_text("existing")

        files = write_audit_files(audit_dir, open_issue, sample_comment_list, force=False)

        assert "001-issue.md" not in files
        assert (audit_dir / "001-issue.md").read_text() == "existing"

    def test_overwrites_with_force(self, open_issue, sample_comment_list, tmp_path):
        """Should overwrite existing files with force flag."""
        audit_dir = tmp_path / "42-test"
        audit_dir.mkdir()
        (audit_dir / "001-issue.md").write_text("existing")

        files = write_audit_files(audit_dir, open_issue, sample_comment_list, force=True)

        assert "001-issue.md" in files
        assert (audit_dir / "001-issue.md").read_text() != "existing"


# =============================================================================
# CLI Tests
# =============================================================================


class TestParseArgs:
    """Tests for parse_args function."""

    def test_requires_repo(self):
        """Should require --repo argument."""
        with pytest.raises(SystemExit):
            parse_args([])

    def test_parses_repo(self):
        """Should parse --repo argument."""
        args = parse_args(["--repo", "owner/name"])
        assert args.repo == "owner/name"

    def test_dry_run_flag(self):
        """Should parse --dry-run flag."""
        args = parse_args(["--repo", "owner/name", "--dry-run"])
        assert args.dry_run is True

    def test_skip_existing_flag(self):
        """Should parse --skip-existing flag."""
        args = parse_args(["--repo", "owner/name", "--skip-existing"])
        assert args.skip_existing is True

    def test_force_flag(self):
        """Should parse --force flag."""
        args = parse_args(["--repo", "owner/name", "--force"])
        assert args.force is True

    def test_verbose_flag(self):
        """Should parse --verbose flag."""
        args = parse_args(["--repo", "owner/name", "--verbose"])
        assert args.verbose is True

    def test_quiet_flag(self):
        """Should parse --quiet flag."""
        args = parse_args(["--repo", "owner/name", "--quiet"])
        assert args.quiet is True

    def test_delay_option(self):
        """Should parse --delay option."""
        args = parse_args(["--repo", "owner/name", "--delay", "1.5"])
        assert args.delay == 1.5

    def test_limit_option(self):
        """Should parse --limit option."""
        args = parse_args(["--repo", "owner/name", "--limit", "10"])
        assert args.limit == 10


# =============================================================================
# Data Class Tests
# =============================================================================


class TestBackfillResult:
    """Tests for BackfillResult dataclass."""

    def test_create_result(self):
        """Should create result with all fields."""
        result = BackfillResult(
            issue_number=42,
            slug="add-auth",
            status="created",
            message="Files: 001-issue.md, 002-comments.md",
        )
        assert result.issue_number == 42
        assert result.slug == "add-auth"
        assert result.status == "created"


class TestIssue:
    """Tests for Issue dataclass."""

    def test_create_issue(self, open_issue):
        """Should create issue with all fields."""
        assert open_issue.number == 42
        assert open_issue.state == "open"
        assert "enhancement" in open_issue.labels


class TestComment:
    """Tests for Comment dataclass."""

    def test_create_comment(self, sample_comment_list):
        """Should create comment with all fields."""
        comment = sample_comment_list[0]
        assert comment.id == 1001
        assert comment.author == "reviewer1"


# =============================================================================
# Integration Tests (with mocked subprocess)
# =============================================================================


class TestFetchIssues:
    """Tests for fetch_issues function with mocked subprocess."""

    def test_fetch_issues_success(self, sample_issues):
        """Should parse issues from gh CLI output."""
        from backfill_issue_audit import fetch_issues

        with patch("backfill_issue_audit.run_gh_command") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_issues),
            )

            issues = fetch_issues("owner/repo")

            assert len(issues) == 3
            assert issues[0].number == 42
            assert issues[1].state == "closed"

    def test_fetch_issues_failure(self):
        """Should raise RuntimeError on failure."""
        from backfill_issue_audit import fetch_issues

        with patch("backfill_issue_audit.run_gh_command") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="API error",
            )

            with pytest.raises(RuntimeError, match="Failed to fetch issues"):
                fetch_issues("owner/repo")


class TestFetchComments:
    """Tests for fetch_comments function with mocked subprocess."""

    def test_fetch_comments_success(self, sample_comments):
        """Should parse comments from gh CLI output."""
        from backfill_issue_audit import fetch_comments

        with patch("backfill_issue_audit.run_gh_command") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(sample_comments["42"]),
            )

            comments = fetch_comments("owner/repo", 42)

            assert len(comments) == 2
            assert comments[0].author == "reviewer1"

    def test_fetch_comments_failure_returns_empty(self):
        """Should return empty list on failure (fail open)."""
        from backfill_issue_audit import fetch_comments

        with patch("backfill_issue_audit.run_gh_command") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="API error",
            )

            comments = fetch_comments("owner/repo", 42)

            assert comments == []


class TestCheckGhAuth:
    """Tests for check_gh_auth function."""

    def test_auth_success(self):
        """Should return True when authenticated."""
        from backfill_issue_audit import check_gh_auth

        with patch("backfill_issue_audit.run_gh_command") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            assert check_gh_auth() is True

    def test_auth_failure(self):
        """Should return False when not authenticated."""
        from backfill_issue_audit import check_gh_auth

        with patch("backfill_issue_audit.run_gh_command") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            assert check_gh_auth() is False
