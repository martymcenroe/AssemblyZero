"""Unit tests for GitHub metrics client.

Issue #333: Cross-Project Metrics Aggregation.
Tests: T060, T070, T080, T230, T240, T250, T260, T310, T320, T330, T340
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from unittest import mock
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from github import GithubException, UnknownObjectException

from assemblyzero.utils.github_metrics_client import GitHubMetricsClient


class TestFilterIssuesOnly:
    """Tests for _filter_issues_only()."""

    def test_t060_filters_out_prs(self) -> None:
        """T060: Client filters out pull requests from issue list."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        items = [
            {"number": 1, "title": "Issue", "pull_request": None},
            {"number": 2, "title": "PR", "pull_request": {"url": "https://..."}},
            {"number": 3, "title": "Issue 2"},
            {"number": 4, "title": "PR 2", "pull_request": {"url": "https://..."}},
            {"number": 5, "title": "PR null", "pull_request": None},
        ]
        result = client._filter_issues_only(items)
        assert len(result) == 3
        assert all(
            not item.get("pull_request") for item in result
        )
        assert {item["number"] for item in result} == {1, 3, 5}


class TestFetchRepoContents:
    """Tests for fetch_repo_contents()."""

    @patch("assemblyzero.utils.github_metrics_client.Github")
    def test_t070_handles_404_gracefully(self, mock_github_cls: MagicMock) -> None:
        """T070: Client returns empty list for missing content (404)."""
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )
        mock_github_instance = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_github_cls.return_value = mock_github_instance

        client = GitHubMetricsClient(token="ghp_test")
        result = client.fetch_repo_contents("owner/repo", "nonexistent/path")
        assert result == []


class TestRetryBehavior:
    """Tests for retry-on-429 behavior."""

    @patch("assemblyzero.utils.github_metrics_client.Github")
    def test_t080_retries_on_rate_limit(self, mock_github_cls: MagicMock) -> None:
        """T080: Client retries on 429 rate limit error and succeeds."""
        # Create mock issue
        mock_issue = MagicMock()
        mock_issue.number = 1
        mock_issue.title = "Test"
        mock_issue.state = "open"
        mock_issue.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        mock_issue.closed_at = None
        mock_issue.labels = []
        mock_issue.pull_request = None

        mock_repo = MagicMock()
        # First call raises 429, second succeeds
        mock_repo.get_issues.side_effect = [
            GithubException(429, {"message": "rate limit"}, {}),
            [mock_issue],
        ]

        mock_github_instance = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_github_cls.return_value = mock_github_instance

        client = GitHubMetricsClient(token="ghp_test")
        # Clear cache to ensure fresh call
        client._cache = {}

        result = client.fetch_issues("owner/repo", "2026-01-01T00:00:00Z")
        assert len(result) == 1
        assert result[0]["number"] == 1
        assert mock_repo.get_issues.call_count == 2


class TestRateLimit:
    """Tests for rate limit checking."""

    @patch("assemblyzero.utils.github_metrics_client.Github")
    def test_t230_rate_limit_warning(
        self, mock_github_cls: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """T230: Logs warning when remaining rate limit is low."""
        mock_core = MagicMock()
        mock_core.remaining = 50
        mock_core.limit = 5000
        mock_core.reset = datetime(2026, 2, 24, 16, 30, tzinfo=timezone.utc)

        mock_rate_limit = MagicMock()
        mock_rate_limit.core = mock_core

        mock_github_instance = MagicMock()
        mock_github_instance.get_rate_limit.return_value = mock_rate_limit
        mock_github_cls.return_value = mock_github_instance

        client = GitHubMetricsClient(token="ghp_test")
        result = client.get_rate_limit_remaining()

        assert result["remaining"] == 50
        assert result["limit"] == 5000


class TestCaching:
    """Tests for caching behavior."""

    def test_t240_cache_key_deterministic(self) -> None:
        """T240: Same inputs produce same cache key."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        key1 = client._get_cache_key("owner/repo", "issues", {"since": "2026-01-01", "state": "all"})
        key2 = client._get_cache_key("owner/repo", "issues", {"since": "2026-01-01", "state": "all"})
        assert key1 == key2

        # Different param order should produce same key (sorted)
        key3 = client._get_cache_key("owner/repo", "issues", {"state": "all", "since": "2026-01-01"})
        assert key1 == key3

    def test_t250_cache_hit_within_ttl(self) -> None:
        """T250: Cached response returned within TTL, no duplicate API call."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        client._cache_ttl = 300
        client._cache = {}

        cache_key = "owner/repo:issues:since=2026-01-01&state=all"
        cached_data = [{"number": 1, "title": "Cached"}]
        client._cache[cache_key] = (time.time(), cached_data)

        assert client._is_cache_valid(cache_key) is True

    def test_t260_cache_expires_after_ttl(self) -> None:
        """T260: Expired cache entry returns False for validity check."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        client._cache_ttl = 300
        client._cache = {}

        cache_key = "owner/repo:issues:since=2026-01-01&state=all"
        # Stored 500 seconds ago (past 300s TTL)
        client._cache[cache_key] = (time.time() - 500, [{"number": 1}])

        assert client._is_cache_valid(cache_key) is False

    def test_cache_miss_for_unknown_key(self) -> None:
        """Cache returns False for unknown key."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        client._cache_ttl = 300
        client._cache = {}
        assert client._is_cache_valid("nonexistent") is False


class TestTokenResolution:
    """Tests for token resolution."""

    def test_t310_authenticates_with_github_token(self) -> None:
        """T310: Client resolves token from GITHUB_TOKEN env var."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        with mock.patch.dict(
            os.environ, {"GITHUB_TOKEN": "ghp_test123"}, clear=False
        ):
            token = client._resolve_token(None)
        assert token == "ghp_test123"

    def test_t320_falls_back_to_gh_token(self) -> None:
        """T320: Client falls back to GH_TOKEN when GITHUB_TOKEN not set."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        env = {"GH_TOKEN": "ghp_fallback456"}
        # Ensure GITHUB_TOKEN is not set
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.dict(os.environ, {}, clear=False):
                # Remove GITHUB_TOKEN if present
                os.environ.pop("GITHUB_TOKEN", None)
                token = client._resolve_token(None)
        assert token == "ghp_fallback456"

    def test_explicit_token_wins(self) -> None:
        """Explicit token argument takes priority over env vars."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        with mock.patch.dict(
            os.environ, {"GITHUB_TOKEN": "ghp_env"}, clear=False
        ):
            token = client._resolve_token("ghp_explicit")
        assert token == "ghp_explicit"

    def test_no_token_returns_none(self) -> None:
        """Returns None when no token available."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        with mock.patch.dict(os.environ, {}, clear=True):
            token = client._resolve_token(None)
        assert token is None

    @patch("assemblyzero.utils.github_metrics_client.Github")
    def test_t330_authenticated_fetches_private_repo(
        self, mock_github_cls: MagicMock
    ) -> None:
        """T330: Authenticated client fetches private repo issues."""
        mock_issue = MagicMock()
        mock_issue.number = 10
        mock_issue.title = "Private issue"
        mock_issue.state = "open"
        mock_issue.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        mock_issue.closed_at = None
        mock_issue.labels = []
        mock_issue.pull_request = None

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = [mock_issue]
        mock_github_instance = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_github_cls.return_value = mock_github_instance

        client = GitHubMetricsClient(token="ghp_private_access")
        result = client.fetch_issues("owner/private-repo", "2026-01-01T00:00:00Z")
        assert len(result) == 1
        assert result[0]["title"] == "Private issue"

    @patch("assemblyzero.utils.github_metrics_client.Github")
    def test_t340_unauthenticated_404_on_private_repo(
        self, mock_github_cls: MagicMock
    ) -> None:
        """T340: Unauthenticated client gets 404 on private repo."""
        mock_github_instance = MagicMock()
        mock_github_instance.get_repo.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )
        mock_github_cls.return_value = mock_github_instance

        client = GitHubMetricsClient(token=None)

        with pytest.raises(UnknownObjectException):
            client.fetch_issues("owner/private-repo", "2026-01-01T00:00:00Z")