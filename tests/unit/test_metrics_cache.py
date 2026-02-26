"""Unit tests for assemblyzero.metrics.cache.

Issue #333: Tests for disk-based cache behavior.
Tests: T160, T170, T180, T190, T200
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from assemblyzero.metrics.cache import (
    get_cache_path,
    invalidate_cache,
    load_cached_metrics,
    save_cached_metrics,
)
from assemblyzero.metrics.models import RepoMetrics


def _make_test_metrics(repo: str = "martymcenroe/AssemblyZero") -> RepoMetrics:
    """Create test RepoMetrics."""
    return RepoMetrics(
        repo=repo,
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
    )


class TestGetCachePath:
    """Tests for get_cache_path()."""

    def test_cache_path_format(self) -> None:
        """Cache path ends with .assemblyzero/metrics_cache.json."""
        path = get_cache_path()
        assert path.name == "metrics_cache.json"
        assert path.parent.name == ".assemblyzero"


class TestCacheRoundTrip:
    """Tests for save and load cycle."""

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        """T160: Saved metrics load back identically within TTL."""
        cache_path = tmp_path / "cache.json"
        metrics = _make_test_metrics()
        save_cached_metrics(
            "martymcenroe/AssemblyZero", metrics, ttl_minutes=60, cache_path=cache_path
        )
        loaded = load_cached_metrics("martymcenroe/AssemblyZero", cache_path=cache_path)
        assert loaded is not None
        assert loaded["repo"] == "martymcenroe/AssemblyZero"
        assert loaded["issues_created"] == 42
        assert loaded["issues_closed"] == 35
        assert loaded["issues_open"] == 12
        assert loaded["workflows_used"] == {"requirements": 8, "tdd": 15}
        assert loaded["llds_generated"] == 20
        assert loaded["gemini_reviews"] == 18
        assert loaded["gemini_approvals"] == 15
        assert loaded["gemini_blocks"] == 3

    def test_multiple_repos_independent(self, tmp_path: Path) -> None:
        """Multiple repos in cache are independent."""
        cache_path = tmp_path / "cache.json"
        metrics_a = _make_test_metrics("test/a")
        metrics_b = _make_test_metrics("test/b")
        save_cached_metrics("test/a", metrics_a, ttl_minutes=60, cache_path=cache_path)
        save_cached_metrics("test/b", metrics_b, ttl_minutes=60, cache_path=cache_path)
        loaded_a = load_cached_metrics("test/a", cache_path=cache_path)
        loaded_b = load_cached_metrics("test/b", cache_path=cache_path)
        assert loaded_a is not None
        assert loaded_b is not None
        assert loaded_a["repo"] == "test/a"
        assert loaded_b["repo"] == "test/b"


class TestCacheExpiry:
    """Tests for cache TTL."""

    def test_expired_entry_returns_none(self, tmp_path: Path) -> None:
        """T170: Expired entry returns None."""
        cache_path = tmp_path / "cache.json"
        metrics = _make_test_metrics()
        save_cached_metrics(
            "martymcenroe/AssemblyZero", metrics, ttl_minutes=0, cache_path=cache_path
        )
        time.sleep(0.1)  # Ensure expiry
        loaded = load_cached_metrics("martymcenroe/AssemblyZero", cache_path=cache_path)
        assert loaded is None


class TestCacheMiss:
    """Tests for cache miss scenarios."""

    def test_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        """Cache file that doesn't exist returns None."""
        cache_path = tmp_path / "nonexistent_cache.json"
        loaded = load_cached_metrics("martymcenroe/AssemblyZero", cache_path=cache_path)
        assert loaded is None

    def test_repo_not_in_cache_returns_none(self, tmp_path: Path) -> None:
        """Repo not present in cache returns None."""
        cache_path = tmp_path / "cache.json"
        save_cached_metrics("test/a", _make_test_metrics("test/a"), ttl_minutes=60, cache_path=cache_path)
        loaded = load_cached_metrics("test/missing", cache_path=cache_path)
        assert loaded is None


class TestCacheCorruption:
    """Tests for corrupt cache handling."""

    def test_corrupt_file_returns_none(self, tmp_path: Path) -> None:
        """T180: Corrupt JSON file returns None."""
        cache_path = tmp_path / "cache.json"
        cache_path.write_text("{this is not valid json!!!", encoding="utf-8")
        loaded = load_cached_metrics("martymcenroe/AssemblyZero", cache_path=cache_path)
        assert loaded is None

    def test_non_dict_json_returns_none(self, tmp_path: Path) -> None:
        """Non-dict JSON (e.g. array) in cache file returns None."""
        cache_path = tmp_path / "cache.json"
        cache_path.write_text('["not", "a", "dict"]', encoding="utf-8")
        loaded = load_cached_metrics("martymcenroe/AssemblyZero", cache_path=cache_path)
        assert loaded is None

    def test_invalid_expires_at_returns_none(self, tmp_path: Path) -> None:
        """Invalid expires_at value returns None."""
        import orjson

        cache_path = tmp_path / "cache.json"
        data = {
            "martymcenroe/AssemblyZero": {
                "repo": "martymcenroe/AssemblyZero",
                "metrics": dict(_make_test_metrics()),
                "cached_at": "2026-02-25T14:30:00+00:00",
                "expires_at": "not-a-date",
            }
        }
        cache_path.write_bytes(orjson.dumps(data))
        loaded = load_cached_metrics("martymcenroe/AssemblyZero", cache_path=cache_path)
        assert loaded is None


class TestCacheInvalidation:
    """Tests for cache invalidation."""

    def test_invalidate_single_repo(self, tmp_path: Path) -> None:
        """T190: Invalidate removes only specified repo; others remain."""
        cache_path = tmp_path / "cache.json"
        for name in ["test/a", "test/b", "test/c"]:
            save_cached_metrics(
                name, _make_test_metrics(name), ttl_minutes=60, cache_path=cache_path
            )
        invalidate_cache("test/b", cache_path=cache_path)
        assert load_cached_metrics("test/a", cache_path=cache_path) is not None
        assert load_cached_metrics("test/b", cache_path=cache_path) is None
        assert load_cached_metrics("test/c", cache_path=cache_path) is not None

    def test_invalidate_all(self, tmp_path: Path) -> None:
        """T200: Invalidate all removes all entries."""
        cache_path = tmp_path / "cache.json"
        for name in ["test/a", "test/b", "test/c"]:
            save_cached_metrics(
                name, _make_test_metrics(name), ttl_minutes=60, cache_path=cache_path
            )
        invalidate_cache(repo=None, cache_path=cache_path)
        assert load_cached_metrics("test/a", cache_path=cache_path) is None
        assert load_cached_metrics("test/b", cache_path=cache_path) is None
        assert load_cached_metrics("test/c", cache_path=cache_path) is None

    def test_invalidate_nonexistent_repo_no_error(self, tmp_path: Path) -> None:
        """Invalidating a repo not in cache does not raise."""
        cache_path = tmp_path / "cache.json"
        save_cached_metrics("test/a", _make_test_metrics("test/a"), ttl_minutes=60, cache_path=cache_path)
        invalidate_cache("test/missing", cache_path=cache_path)
        assert load_cached_metrics("test/a", cache_path=cache_path) is not None

    def test_invalidate_all_nonexistent_file_no_error(self, tmp_path: Path) -> None:
        """Invalidating all when cache file doesn't exist does not raise."""
        cache_path = tmp_path / "nonexistent_cache.json"
        invalidate_cache(repo=None, cache_path=cache_path)  # Should not raise

    def test_cache_directory_created(self, tmp_path: Path) -> None:
        """Cache directory is created if it doesn't exist."""
        cache_path = tmp_path / "subdir" / "deep" / "cache.json"
        save_cached_metrics(
            "test/a", _make_test_metrics("test/a"), ttl_minutes=60, cache_path=cache_path
        )
        assert cache_path.exists()
