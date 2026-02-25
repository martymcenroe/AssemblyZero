"""Integration tests for GitHub metrics collection against real API.

Issue #333: Cross-Project Metrics Aggregation.

These tests hit the real GitHub API and require a valid GITHUB_TOKEN.
Run with: poetry run pytest tests/integration/ -v -m integration
"""

from __future__ import annotations

import os

import pytest

from assemblyzero.utils.github_metrics_client import GitHubMetricsClient


pytestmark = pytest.mark.integration


@pytest.fixture()
def github_client() -> GitHubMetricsClient:
    """Create an authenticated GitHub client for integration tests."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN or GH_TOKEN not set")
    return GitHubMetricsClient(token=token, cache_ttl=60)


class TestGitHubIntegration:
    """Integration tests against real GitHub API."""

    def test_rate_limit_check(self, github_client: GitHubMetricsClient) -> None:
        """Verify rate limit endpoint returns valid data."""
        result = github_client.get_rate_limit_remaining()
        assert "remaining" in result
        assert "limit" in result
        assert isinstance(result["remaining"], int)
        assert result["remaining"] >= 0

    def test_fetch_public_repo_issues(
        self, github_client: GitHubMetricsClient
    ) -> None:
        """Fetch issues from a known public repo."""
        issues = github_client.fetch_issues(
            "octocat/Hello-World", since="2020-01-01T00:00:00Z", state="all"
        )
        assert isinstance(issues, list)
        # Hello-World repo has issues
        if issues:
            assert "number" in issues[0]
            assert "title" in issues[0]
            assert "state" in issues[0]

    def test_fetch_public_repo_contents(
        self, github_client: GitHubMetricsClient
    ) -> None:
        """Fetch contents from a known public repo."""
        contents = github_client.fetch_repo_contents("octocat/Hello-World", ".")
        assert isinstance(contents, list)
        assert len(contents) > 0
        assert "name" in contents[0]

    def test_fetch_nonexistent_path_returns_empty(
        self, github_client: GitHubMetricsClient
    ) -> None:
        """Fetching a nonexistent path returns empty list."""
        contents = github_client.fetch_repo_contents(
            "octocat/Hello-World", "nonexistent/path/here"
        )
        assert contents == []