"""Tests for assemblyzero.telemetry.actor — actor detection."""

import os
from unittest.mock import patch

import pytest

from assemblyzero.telemetry.actor import detect_actor, detect_github_user, get_machine_id


class TestDetectActor:
    """Test actor detection logic."""

    def test_human_by_default(self):
        """No Claude env vars → human."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove CLAUDECODE and UNLEASHED_VERSION if present
            os.environ.pop("CLAUDECODE", None)
            os.environ.pop("UNLEASHED_VERSION", None)
            assert detect_actor() == "human"

    def test_claude_via_claudecode(self):
        """CLAUDECODE set (even empty) → claude."""
        with patch.dict(os.environ, {"CLAUDECODE": ""}, clear=False):
            assert detect_actor() == "claude"

    def test_claude_via_claudecode_nonempty(self):
        """CLAUDECODE with value → claude."""
        with patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=False):
            assert detect_actor() == "claude"

    def test_claude_via_unleashed_version(self):
        """UNLEASHED_VERSION set → claude."""
        env = {"UNLEASHED_VERSION": "c-24"}
        with patch.dict(os.environ, env, clear=True):
            assert detect_actor() == "claude"


class TestDetectGithubUser:
    """Test GitHub user detection."""

    def test_returns_string(self):
        """Should always return a string, never None."""
        # Clear cache
        if hasattr(detect_github_user, "_cached"):
            delattr(detect_github_user, "_cached")
        result = detect_github_user()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_caches_result(self):
        """Second call returns cached value without subprocess."""
        if hasattr(detect_github_user, "_cached"):
            delattr(detect_github_user, "_cached")
        first = detect_github_user()
        second = detect_github_user()
        assert first == second

    def test_fallback_on_error(self):
        """Returns 'unknown' when gh CLI fails."""
        if hasattr(detect_github_user, "_cached"):
            delattr(detect_github_user, "_cached")
        with patch("assemblyzero.telemetry.actor.subprocess.run", side_effect=FileNotFoundError):
            result = detect_github_user()
            assert result == "unknown"


class TestGetMachineId:
    """Test machine ID generation."""

    def test_returns_stable_hash(self):
        """Same machine → same ID across calls."""
        if hasattr(get_machine_id, "_cached"):
            delattr(get_machine_id, "_cached")
        first = get_machine_id()
        # Clear cache and call again
        if hasattr(get_machine_id, "_cached"):
            delattr(get_machine_id, "_cached")
        second = get_machine_id()
        assert first == second

    def test_returns_12_char_hex(self):
        """Machine ID is a 12-char hex string."""
        if hasattr(get_machine_id, "_cached"):
            delattr(get_machine_id, "_cached")
        result = get_machine_id()
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)
