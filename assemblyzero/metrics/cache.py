"""Disk-based cache layer for cross-project metrics.

Issue #333: Cache API responses to minimize GitHub API calls.
"""

from __future__ import annotations

import logging
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import orjson

from assemblyzero.metrics.models import CacheEntry, RepoMetrics

logger = logging.getLogger(__name__)


def get_cache_path() -> Path:
    """Return ~/.assemblyzero/metrics_cache.json."""
    return Path.home() / ".assemblyzero" / "metrics_cache.json"


def _load_cache_file(cache_path: Path) -> dict[str, Any]:
    """Load and parse the cache file. Returns empty dict on any error."""
    if not cache_path.exists():
        return {}
    try:
        raw = cache_path.read_bytes()
        data = orjson.loads(raw)
        if not isinstance(data, dict):
            logger.warning("Cache file is not a JSON object, treating as empty")
            return {}
        return data
    except (orjson.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read cache file %s: %s", cache_path, exc)
        return {}


def _write_cache_file(cache_path: Path, data: dict[str, Any]) -> None:
    """Write cache data to disk with owner-only permissions."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    raw = orjson.dumps(data, option=orjson.OPT_INDENT_2)
    cache_path.write_bytes(raw)
    try:
        os.chmod(cache_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except OSError as exc:
        logger.warning("Could not set file permissions on %s: %s", cache_path, exc)


def load_cached_metrics(
    repo: str,
    cache_path: Path | None = None,
) -> RepoMetrics | None:
    """Load cached metrics for a repo if cache entry exists and is not expired.

    Returns None if no cache, expired, or cache file corrupt.
    """
    path = cache_path or get_cache_path()
    cache_data = _load_cache_file(path)

    entry = cache_data.get(repo)
    if entry is None:
        logger.debug("Cache miss for %s: no entry", repo)
        return None

    expires_at_str = entry.get("expires_at", "")
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
    except (ValueError, TypeError):
        logger.warning("Invalid expires_at for %s, treating as expired", repo)
        return None

    now = datetime.now(tz=timezone.utc)
    if now >= expires_at:
        logger.debug("Cache miss for %s: expired at %s", repo, expires_at_str)
        return None

    logger.debug("Cache hit for %s", repo)
    return entry.get("metrics")


def save_cached_metrics(
    repo: str,
    metrics: RepoMetrics,
    ttl_minutes: int,
    cache_path: Path | None = None,
) -> None:
    """Save metrics to disk cache with TTL."""
    path = cache_path or get_cache_path()
    cache_data = _load_cache_file(path)

    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)

    entry: CacheEntry = {
        "repo": repo,
        "metrics": metrics,
        "cached_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    cache_data[repo] = entry
    _write_cache_file(path, cache_data)
    logger.debug("Cached metrics for %s (expires %s)", repo, expires_at.isoformat())


def invalidate_cache(
    repo: str | None = None,
    cache_path: Path | None = None,
) -> None:
    """Invalidate cache for a specific repo, or all repos if repo is None."""
    path = cache_path or get_cache_path()

    if repo is None:
        # Invalidate all
        if path.exists():
            _write_cache_file(path, {})
            logger.debug("Invalidated all cache entries")
        return

    cache_data = _load_cache_file(path)
    if repo in cache_data:
        del cache_data[repo]
        _write_cache_file(path, cache_data)
        logger.debug("Invalidated cache for %s", repo)