"""Configuration loading and validation for cross-project metrics.

Issue #333: Load tracked repos config from ~/.assemblyzero/tracked_repos.json.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import orjson

from assemblyzero.metrics.models import TrackedReposConfig

REPO_NAME_PATTERN: re.Pattern[str] = re.compile(
    r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$"
)

_DEFAULT_CACHE_TTL_MINUTES: int = 60
_DEFAULT_GITHUB_TOKEN_ENV: str = "GITHUB_TOKEN"


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""


def get_default_config_path() -> Path:
    """Return ~/.assemblyzero/tracked_repos.json."""
    return Path.home() / ".assemblyzero" / "tracked_repos.json"


def validate_repo_name(name: str) -> bool:
    """Check if a repo name matches the allowed owner/name pattern."""
    return bool(REPO_NAME_PATTERN.match(name))


def validate_config(config: dict[str, Any]) -> TrackedReposConfig:
    """Validate raw dict against TrackedReposConfig schema.

    Raises ConfigError on validation failure.
    Applies defaults for optional fields.
    """
    if "repos" not in config:
        msg = "Missing required key: repos"
        raise ConfigError(msg)

    repos = config["repos"]
    if not isinstance(repos, list):
        msg = "repos must be a list"
        raise ConfigError(msg)

    if len(repos) == 0:
        msg = "repos list cannot be empty"
        raise ConfigError(msg)

    for repo_name in repos:
        if not isinstance(repo_name, str) or not validate_repo_name(repo_name):
            msg = f"Invalid repo name: {repo_name}"
            raise ConfigError(msg)

    cache_ttl = config.get("cache_ttl_minutes", _DEFAULT_CACHE_TTL_MINUTES)
    if not isinstance(cache_ttl, int) or cache_ttl < 0:
        msg = "cache_ttl_minutes must be non-negative"
        raise ConfigError(msg)

    token_env = config.get("github_token_env", _DEFAULT_GITHUB_TOKEN_ENV)
    if not isinstance(token_env, str) or not token_env:
        msg = "github_token_env must be a non-empty string"
        raise ConfigError(msg)

    return TrackedReposConfig(
        repos=repos,
        cache_ttl_minutes=cache_ttl,
        github_token_env=token_env,
    )


def load_config(config_path: Path | None = None) -> TrackedReposConfig:
    """Load and validate tracked repos config from disk.

    Default path: ~/.assemblyzero/tracked_repos.json
    Raises ConfigError if file missing, malformed, or repos list empty.
    """
    path = config_path or get_default_config_path()

    if not path.exists():
        msg = f"Config file not found: {path}"
        raise ConfigError(msg)

    raw_bytes = path.read_bytes()
    try:
        raw_config = orjson.loads(raw_bytes)
    except orjson.JSONDecodeError as exc:
        msg = f"Failed to parse config: {exc}"
        raise ConfigError(msg) from exc

    if not isinstance(raw_config, dict):
        msg = "Config must be a JSON object"
        raise ConfigError(msg)

    return validate_config(raw_config)