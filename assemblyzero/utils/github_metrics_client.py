"""GitHub API client wrapper for cross-project metrics collection.

Issue #333: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking.

Provides caching, retry-with-backoff, and rate-limit awareness for
fetching issues, repo contents, and review verdicts via PyGithub.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from github import Github, GithubException, UnknownObjectException
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class GitHubMetricsClient:
    """GitHub API client for metrics collection with caching and rate-limit awareness."""

    def __init__(self, token: str | None = None, cache_ttl: int = 300) -> None:
        """Initialize client with optional token and cache TTL.

        Args:
            token: GitHub personal access token. If None, reads from
                   GITHUB_TOKEN or GH_TOKEN environment variables.
            cache_ttl: Cache time-to-live in seconds.
        """
        self._token = self._resolve_token(token)
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}

        if self._token:
            self._github = Github(login_or_token=self._token)
            logger.debug("GitHub client initialized in authenticated mode")
        else:
            self._github = Github()
            logger.debug(
                "GitHub client initialized in unauthenticated mode "
                "(60 requests/hour limit)"
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=30))
    def fetch_issues(
        self,
        repo_full_name: str,
        since: str,
        state: str = "all",
    ) -> list[dict]:
        """Fetch issues from a repository within a date range.

        Args:
            repo_full_name: 'owner/name' format
            since: ISO 8601 date string for lookback start
            state: 'open', 'closed', or 'all'

        Returns:
            List of issue dicts with: number, title, state, created_at,
            closed_at, labels, is_pull_request.

        Raises:
            github.GithubException: On API errors after retries exhausted.
        """
        cache_key = self._get_cache_key(
            repo_full_name, "issues", {"since": since, "state": state}
        )
        if self._is_cache_valid(cache_key):
            logger.debug("Cache hit for issues: %s", cache_key)
            return self._cache[cache_key][1]

        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)

        repo = self._github.get_repo(repo_full_name)
        issues_paged = repo.get_issues(state=state, since=since_dt, sort="created")

        raw_items: list[dict] = []
        for issue in issues_paged:
            raw_items.append(
                {
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "created_at": (
                        issue.created_at.isoformat() if issue.created_at else None
                    ),
                    "closed_at": (
                        issue.closed_at.isoformat() if issue.closed_at else None
                    ),
                    "labels": [label.name for label in issue.labels],
                    "pull_request": issue.pull_request,
                }
            )

        filtered = self._filter_issues_only(raw_items)

        self._cache[cache_key] = (time.time(), filtered)
        return filtered

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=30))
    def fetch_repo_contents(
        self,
        repo_full_name: str,
        path: str,
    ) -> list[dict]:
        """Fetch directory contents from a repository.

        Args:
            repo_full_name: 'owner/name' format
            path: Repository-relative path (e.g., 'docs/lld/active')

        Returns:
            List of content dicts with: name, type, path, size.
            Returns empty list if path doesn't exist (404).
        """
        cache_key = self._get_cache_key(
            repo_full_name, "contents", {"path": path}
        )
        if self._is_cache_valid(cache_key):
            logger.debug("Cache hit for contents: %s", cache_key)
            return self._cache[cache_key][1]

        try:
            repo = self._github.get_repo(repo_full_name)
            contents = repo.get_contents(path)
        except UnknownObjectException:
            logger.debug("Path not found (404): %s/%s", repo_full_name, path)
            result: list[dict] = []
            self._cache[cache_key] = (time.time(), result)
            return result

        # get_contents returns a single ContentFile or a list
        if not isinstance(contents, list):
            contents = [contents]

        result = [
            {
                "name": item.name,
                "type": item.type,
                "path": item.path,
                "size": item.size,
            }
            for item in contents
        ]

        self._cache[cache_key] = (time.time(), result)
        return result

    def get_rate_limit_remaining(self) -> dict:
        """Get current GitHub API rate limit status.

        Returns:
            Dict with 'remaining', 'limit', 'reset_at' keys.
        """
        try:
            rate_limit = self._github.get_rate_limit()
            core = rate_limit.core
            return {
                "remaining": core.remaining,
                "limit": core.limit,
                "reset_at": core.reset.isoformat() if core.reset else "unknown",
            }
        except GithubException:
            logger.warning("Failed to fetch rate limit status")
            return {"remaining": 0, "limit": 0, "reset_at": "unknown"}

    def _get_cache_key(
        self, repo_full_name: str, endpoint: str, params: dict
    ) -> str:
        """Generate a deterministic cache key for a given request.

        Args:
            repo_full_name: 'owner/name' format
            endpoint: API endpoint identifier (e.g., 'issues', 'contents')
            params: Request parameters dict

        Returns:
            String cache key.
        """
        sorted_params = "&".join(
            f"{k}={v}" for k, v in sorted(params.items())
        )
        return f"{repo_full_name}:{endpoint}:{sorted_params}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check whether a cached entry exists and has not expired.

        Args:
            cache_key: Key returned by _get_cache_key.

        Returns:
            True if cache hit is valid (exists and within TTL), False otherwise.
        """
        if cache_key not in self._cache:
            return False

        stored_time, _ = self._cache[cache_key]
        return (time.time() - stored_time) < self._cache_ttl

    def _filter_issues_only(self, items: list[dict]) -> list[dict]:
        """Filter out pull requests from issue list.

        GitHub API returns PRs in the issues endpoint. This filters them out
        by checking for the 'pull_request' key having a truthy value.
        """
        return [
            item
            for item in items
            if not item.get("pull_request")
        ]

    def _resolve_token(self, token: str | None) -> str | None:
        """Resolve GitHub token from argument or environment variables.

        Checks in order:
        1. Explicit token argument
        2. GITHUB_TOKEN environment variable
        3. GH_TOKEN environment variable

        Args:
            token: Explicitly provided token, or None.

        Returns:
            Resolved token string, or None if no token found.
        """
        if token is not None:
            return token

        github_token = os.environ.get("GITHUB_TOKEN")
        if github_token:
            return github_token

        gh_token = os.environ.get("GH_TOKEN")
        if gh_token:
            return gh_token

        return None