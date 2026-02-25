```python
"""Unit tests for metrics configuration loading and validation.

Issue #333: Cross-Project Metrics Aggregation.
Tests: T010, T020, T030, T040, T050
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from assemblyzero.utils.metrics_config import (
    load_config,
    parse_repo_string,
    validate_config,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "metrics"


class TestLoadConfig:
    """Tests for load_config()."""

    def test_t010_load_from_explicit_path(self) -> None:
        """T010: Config loading from explicit path returns valid config."""
        config_path = str(FIXTURES_DIR / "tracked_repos.json")
        config = load_config(config_path)

        assert "repos" in config
        assert len(config["repos"]) == 3
        assert config["lookback_days"] == 30
        assert config["output_dir"] == "docs/metrics"

    def test_t020_load_from_env_var(self, tmp_path: Path) -> None:
        """T020: Config loading fallback to ASSEMBLYZERO_METRICS_CONFIG env var."""
        config_data = {
            "repos": ["martymcenroe/AssemblyZero"],
            "lookback_days": 14,
        }
        config_file = tmp_path / "env_config.json"
        config_file.write_text(json.dumps(config_data))

        with mock.patch.dict(
            os.environ, {"ASSEMBLYZERO_METRICS_CONFIG": str(config_file)}
        ):
            config = load_config()

        assert len(config["repos"]) == 1
        assert config["lookback_days"] == 14

    def test_load_file_not_found(self) -> None:
        """Config loading raises FileNotFoundError when no config found."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(FileNotFoundError, match="No config file found"):
                load_config("/nonexistent/path/config.json")

    def test_load_malformed_json(self, tmp_path: Path) -> None:
        """Config loading raises ValueError on malformed JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")

        with pytest.raises(ValueError, match="Config file is malformed"):
            load_config(str(bad_file))


class TestValidateConfig:
    """Tests for validate_config()."""

    def test_t030_rejects_empty_repos(self) -> None:
        """T030: Config validation rejects empty repos list."""
        with pytest.raises(ValueError, match="non-empty list"):
            validate_config({"repos": []})

    def test_t040_rejects_invalid_repo_format(self) -> None:
        """T040: Config validation rejects malformed repo string."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            validate_config({"repos": ["invalid"]})

    def test_rejects_missing_repos_key(self) -> None:
        """Config validation rejects missing repos key."""
        with pytest.raises(ValueError, match="'repos' key is required"):
            validate_config({})

    def test_rejects_negative_lookback_days(self) -> None:
        """Config validation rejects negative lookback_days."""
        with pytest.raises(ValueError, match="positive integer"):
            validate_config({"repos": ["a/b"], "lookback_days": -1})

    def test_accepts_string_repos(self) -> None:
        """Config validation accepts string-format repos and converts them."""
        config = validate_config({"repos": ["owner/repo"]})
        assert config["repos"][0]["owner"] == "owner"
        assert config["repos"][0]["name"] == "repo"
        assert config["repos"][0]["full_name"] == "owner/repo"
        assert config["repos"][0]["enabled"] is True

    def test_accepts_dict_repos_with_full_name(self) -> None:
        """Config validation accepts dict-format repos with full_name."""
        config = validate_config(
            {"repos": [{"full_name": "owner/repo", "enabled": False}]}
        )
        assert config["repos"][0]["enabled"] is False
        assert config["repos"][0]["owner"] == "owner"

    def test_accepts_dict_repos_with_owner_name(self) -> None:
        """Config validation accepts dict-format repos with owner+name."""
        config = validate_config(
            {"repos": [{"owner": "org", "name": "project"}]}
        )
        assert config["repos"][0]["full_name"] == "org/project"

    def test_applies_defaults(self) -> None:
        """Config validation applies defaults for optional fields."""
        config = validate_config({"repos": ["a/b"]})
        assert config["lookback_days"] == 30
        assert config["output_dir"] == "docs/metrics"
        assert config["cache_ttl_seconds"] == 300
        assert config["github_token_env"] == "GITHUB_TOKEN"


class TestParseRepoString:
    """Tests for parse_repo_string()."""

    def test_t050_parse_valid_input(self) -> None:
        """T050: parse_repo_string parses valid 'owner/name' format."""
        result = parse_repo_string("martymcenroe/AssemblyZero")
        assert result["owner"] == "martymcenroe"
        assert result["name"] == "AssemblyZero"
        assert result["full_name"] == "martymcenroe/AssemblyZero"
        assert result["enabled"] is True

    def test_parse_with_special_chars(self) -> None:
        """parse_repo_string handles dots, hyphens, underscores."""
        result = parse_repo_string("my-org/my_repo.v2")
        assert result["owner"] == "my-org"
        assert result["name"] == "my_repo.v2"

    def test_parse_rejects_no_slash(self) -> None:
        """parse_repo_string rejects string without slash."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            parse_repo_string("noslash")

    def test_parse_rejects_empty(self) -> None:
        """parse_repo_string rejects empty string."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            parse_repo_string("")

    def test_parse_rejects_multiple_slashes(self) -> None:
        """parse_repo_string rejects strings with multiple slashes."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            parse_repo_string("a/b/c")
```
