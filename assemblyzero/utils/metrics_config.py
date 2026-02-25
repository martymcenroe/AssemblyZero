"""Configuration loader for cross-project metrics collection.

Issue #333: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from assemblyzero.utils.metrics_models import (
    MetricsCollectionConfig,
    TrackedRepoConfig,
)

_REPO_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")

_DEFAULT_CONFIG: dict = {
    "lookback_days": 30,
    "output_dir": "docs/metrics",
    "cache_ttl_seconds": 300,
    "github_token_env": "GITHUB_TOKEN",
}

_CONFIG_SEARCH_LOCATIONS = [
    lambda: os.environ.get("ASSEMBLYZERO_METRICS_CONFIG"),
    lambda: str(Path.home() / ".assemblyzero" / "tracked_repos.json"),
    lambda: "tracked_repos.json",
]


def load_config(config_path: str | None = None) -> MetricsCollectionConfig:
    """Load and validate tracked repos configuration.

    Searches in order:
    1. Explicit config_path argument
    2. ASSEMBLYZERO_METRICS_CONFIG environment variable
    3. ~/.assemblyzero/tracked_repos.json
    4. ./tracked_repos.json (project root)

    Raises:
        FileNotFoundError: If no config file found at any location.
        ValueError: If config file is malformed or fails validation.
    """
    resolved_path = _resolve_config_path(config_path)
    if resolved_path is None:
        searched = _get_searched_paths(config_path)
        raise FileNotFoundError(
            f"No config file found. Searched: {', '.join(searched)}"
        )

    try:
        raw_text = Path(resolved_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise FileNotFoundError(
            f"Cannot read config file at '{resolved_path}': {exc}"
        ) from exc

    try:
        raw_config = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Config file is malformed: {exc}") from exc

    if not isinstance(raw_config, dict):
        raise ValueError("Config file must contain a JSON object at the top level")

    return validate_config(raw_config)


def validate_config(config: dict) -> MetricsCollectionConfig:
    """Validate raw config dict against expected schema.

    Checks:
    - 'repos' key exists and is a non-empty list
    - Each repo entry has owner/name or full_name (or is a string)
    - lookback_days is positive integer
    - output_dir is a string

    Raises:
        ValueError: On validation failure with descriptive message.
    """
    if "repos" not in config:
        raise ValueError("'repos' key is required")

    repos_raw = config["repos"]
    if not isinstance(repos_raw, list) or len(repos_raw) == 0:
        raise ValueError("'repos' must be a non-empty list")

    parsed_repos: list[TrackedRepoConfig] = []
    for entry in repos_raw:
        if isinstance(entry, str):
            parsed_repos.append(parse_repo_string(entry))
        elif isinstance(entry, dict):
            # Validate dict-format repo entry
            if "full_name" in entry:
                full_name = entry["full_name"]
                if not _REPO_PATTERN.match(full_name):
                    raise ValueError(
                        f"Invalid repo format: '{full_name}'. Expected 'owner/name'."
                    )
                owner, name = full_name.split("/", 1)
                parsed_repos.append(
                    TrackedRepoConfig(
                        owner=entry.get("owner", owner),
                        name=entry.get("name", name),
                        full_name=full_name,
                        enabled=entry.get("enabled", True),
                    )
                )
            elif "owner" in entry and "name" in entry:
                full_name = f"{entry['owner']}/{entry['name']}"
                parsed_repos.append(
                    TrackedRepoConfig(
                        owner=entry["owner"],
                        name=entry["name"],
                        full_name=full_name,
                        enabled=entry.get("enabled", True),
                    )
                )
            else:
                raise ValueError(
                    f"Repo entry must have 'full_name' or both 'owner' and 'name': {entry}"
                )
        else:
            raise ValueError(
                f"Invalid repo entry type: {type(entry).__name__}. Expected string or dict."
            )

    # Validate lookback_days
    lookback_days = config.get("lookback_days", _DEFAULT_CONFIG["lookback_days"])
    if not isinstance(lookback_days, int) or lookback_days < 1:
        raise ValueError("'lookback_days' must be a positive integer")

    output_dir = config.get("output_dir", _DEFAULT_CONFIG["output_dir"])
    cache_ttl_seconds = config.get(
        "cache_ttl_seconds", _DEFAULT_CONFIG["cache_ttl_seconds"]
    )
    github_token_env = config.get(
        "github_token_env", _DEFAULT_CONFIG["github_token_env"]
    )

    return MetricsCollectionConfig(
        repos=parsed_repos,
        lookback_days=lookback_days,
        output_dir=output_dir,
        cache_ttl_seconds=cache_ttl_seconds,
        github_token_env=github_token_env,
    )


def parse_repo_string(repo_str: str) -> TrackedRepoConfig:
    """Parse 'owner/name' string into TrackedRepoConfig.

    Args:
        repo_str: Repository identifier like 'martymcenroe/AssemblyZero'

    Returns:
        TrackedRepoConfig with owner, name, full_name, enabled=True

    Raises:
        ValueError: If string doesn't match 'owner/name' format.
    """
    if not _REPO_PATTERN.match(repo_str):
        raise ValueError(
            f"Invalid repo format: '{repo_str}'. Expected 'owner/name'."
        )

    owner, name = repo_str.split("/", 1)
    return TrackedRepoConfig(
        owner=owner,
        name=name,
        full_name=repo_str,
        enabled=True,
    )


def _resolve_config_path(config_path: str | None) -> str | None:
    """Resolve the actual config file path from search locations.

    Returns the first path that exists, or None.
    """
    if config_path is not None:
        if Path(config_path).is_file():
            return config_path
        return None

    for location_fn in _CONFIG_SEARCH_LOCATIONS:
        candidate = location_fn()
        if candidate and Path(candidate).is_file():
            return candidate

    return None


def _get_searched_paths(config_path: str | None) -> list[str]:
    """Return the list of paths that were searched for config."""
    paths: list[str] = []
    if config_path is not None:
        paths.append(config_path)
    else:
        for location_fn in _CONFIG_SEARCH_LOCATIONS:
            candidate = location_fn()
            if candidate:
                paths.append(candidate)
    return paths