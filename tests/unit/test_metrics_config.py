"""Unit tests for assemblyzero.metrics.config.

Issue #333: Tests for config loading and validation.
Tests: T010, T020, T030, T040, T050, T250
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.metrics.config import (
    ConfigError,
    get_default_config_path,
    load_config,
    validate_config,
    validate_repo_name,
)

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "metrics"


class TestLoadConfig:
    """Tests for load_config()."""

    def test_load_valid_config(self) -> None:
        """T010: Valid config file returns TrackedReposConfig with 3 repos."""
        config = load_config(_FIXTURES_DIR / "tracked_repos_valid.json")
        assert len(config["repos"]) == 3
        assert config["repos"][0] == "martymcenroe/AssemblyZero"
        assert config["cache_ttl_minutes"] == 60
        assert config["github_token_env"] == "GITHUB_TOKEN"

    def test_load_missing_file_raises(self) -> None:
        """T020: Missing file raises ConfigError with path in message."""
        missing = _FIXTURES_DIR / "nonexistent.json"
        with pytest.raises(ConfigError, match="Config file not found"):
            load_config(missing)

    def test_load_malformed_json_raises(self) -> None:
        """T030: Malformed JSON raises ConfigError."""
        with pytest.raises(ConfigError, match="Failed to parse"):
            load_config(_FIXTURES_DIR / "tracked_repos_malformed.json")

    def test_load_empty_repos_raises(self) -> None:
        """T040: Empty repos list raises ConfigError."""
        with pytest.raises(ConfigError, match="repos list cannot be empty"):
            load_config(_FIXTURES_DIR / "tracked_repos_empty.json")

    def test_load_uses_default_path_when_none(self) -> None:
        """load_config with None falls back to get_default_config_path()."""
        # Since default path probably doesn't exist, expect ConfigError
        with pytest.raises(ConfigError):
            load_config(None)

    def test_load_non_object_json_raises(self, tmp_path: Path) -> None:
        """Config that is a JSON array (not object) raises ConfigError."""
        arr_file = tmp_path / "array.json"
        arr_file.write_text('["not", "an", "object"]', encoding="utf-8")
        with pytest.raises(ConfigError, match="Config must be a JSON object"):
            load_config(arr_file)


class TestGetDefaultConfigPath:
    """Tests for get_default_config_path()."""

    def test_default_path_resolution(self) -> None:
        """T050: Default path ends with .assemblyzero/tracked_repos.json."""
        path = get_default_config_path()
        assert path.name == "tracked_repos.json"
        assert path.parent.name == ".assemblyzero"


class TestValidateConfig:
    """Tests for validate_config()."""

    def test_missing_repos_key(self) -> None:
        """Missing 'repos' key raises ConfigError."""
        with pytest.raises(ConfigError, match="Missing required key: repos"):
            validate_config({"cache_ttl_minutes": 60})

    def test_repos_not_a_list(self) -> None:
        """Non-list 'repos' raises ConfigError."""
        with pytest.raises(ConfigError, match="repos must be a list"):
            validate_config({"repos": "not-a-list"})

    def test_empty_repos_list(self) -> None:
        """Empty repos list raises ConfigError."""
        with pytest.raises(ConfigError, match="repos list cannot be empty"):
            validate_config({"repos": []})

    def test_invalid_repo_name_rejected(self) -> None:
        """Invalid repo name raises ConfigError."""
        with pytest.raises(ConfigError, match="Invalid repo name"):
            validate_config({"repos": ["'; DROP TABLE--"]})

    def test_defaults_applied(self) -> None:
        """Defaults applied for optional fields when not specified."""
        config = validate_config({"repos": ["martymcenroe/AssemblyZero"]})
        assert config["cache_ttl_minutes"] == 60
        assert config["github_token_env"] == "GITHUB_TOKEN"

    def test_custom_values_preserved(self) -> None:
        """Custom values are preserved when provided."""
        config = validate_config({
            "repos": ["martymcenroe/AssemblyZero"],
            "cache_ttl_minutes": 120,
            "github_token_env": "MY_GITHUB_TOKEN",
        })
        assert config["cache_ttl_minutes"] == 120
        assert config["github_token_env"] == "MY_GITHUB_TOKEN"

    def test_negative_ttl_raises(self) -> None:
        """Negative cache_ttl_minutes raises ConfigError."""
        with pytest.raises(ConfigError, match="cache_ttl_minutes must be non-negative"):
            validate_config({"repos": ["a/b"], "cache_ttl_minutes": -1})

    def test_zero_ttl_accepted(self) -> None:
        """Zero cache_ttl_minutes is accepted (no caching)."""
        config = validate_config({"repos": ["a/b"], "cache_ttl_minutes": 0})
        assert config["cache_ttl_minutes"] == 0

    def test_empty_github_token_env_raises(self) -> None:
        """Empty github_token_env string raises ConfigError."""
        with pytest.raises(ConfigError, match="github_token_env must be a non-empty string"):
            validate_config({"repos": ["a/b"], "github_token_env": ""})

    def test_multiple_valid_repos(self) -> None:
        """Multiple valid repos are accepted."""
        config = validate_config({
            "repos": [
                "martymcenroe/AssemblyZero",
                "martymcenroe/ProjectAlpha",
                "org.name/repo-v2",
            ],
        })
        assert len(config["repos"]) == 3


class TestValidateRepoName:
    """Tests for validate_repo_name()."""

    def test_valid_names(self) -> None:
        """T250: Valid repo names are accepted."""
        assert validate_repo_name("martymcenroe/AssemblyZero") is True
        assert validate_repo_name("org.name/repo-v2") is True
        assert validate_repo_name("valid_org/valid_repo") is True

    def test_injection_strings_rejected(self) -> None:
        """T250: Injection strings are rejected."""
        assert validate_repo_name("'; DROP TABLE--") is False

    def test_empty_string_rejected(self) -> None:
        """T250: Empty string is rejected."""
        assert validate_repo_name("") is False

    def test_no_slash_rejected(self) -> None:
        """T250: String without slash is rejected."""
        assert validate_repo_name("no-slash") is False

    def test_multiple_slashes_rejected(self) -> None:
        """T250: Multiple slashes are rejected."""
        assert validate_repo_name("a/b/c") is False

    def test_space_in_name_rejected(self) -> None:
        """T250: Space in name is rejected."""
        assert validate_repo_name("a/ b") is False
