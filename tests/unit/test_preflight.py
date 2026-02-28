"""Unit tests for assemblyzero/core/preflight.py.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Tests cover:
- check_gemini_available: credential-based availability check (no API calls)
- check_gemini_reachable: lightweight API ping
- PreflightResult structure
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.core.preflight import (
    PreflightResult,
    check_gemini_available,
    check_gemini_reachable,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def creds_dir(tmp_path: Path) -> Path:
    """Temporary directory for credentials and state files."""
    return tmp_path


@pytest.fixture
def all_available_creds(creds_dir: Path) -> tuple[Path, Path]:
    """Credentials file with all credentials available (none exhausted)."""
    creds_file = creds_dir / "gemini-credentials.json"
    state_file = creds_dir / "gemini-rotation-state.json"

    creds_file.write_text(json.dumps({
        "credentials": [
            {"name": "api-key-1", "type": "api_key", "key": "key1", "enabled": True},
            {"name": "api-key-2", "type": "api_key", "key": "key2", "enabled": True},
            {"name": "oauth-primary", "type": "oauth", "enabled": True},
        ]
    }), encoding="utf-8")

    state_file.write_text(json.dumps({
        "exhausted": {},
        "last_success": "api-key-1",
    }), encoding="utf-8")

    return creds_file, state_file


@pytest.fixture
def all_exhausted_creds(creds_dir: Path) -> tuple[Path, Path]:
    """Credentials file with all credentials exhausted."""
    creds_file = creds_dir / "gemini-credentials.json"
    state_file = creds_dir / "gemini-rotation-state.json"

    creds_file.write_text(json.dumps({
        "credentials": [
            {"name": "api-key-1", "type": "api_key", "key": "key1", "enabled": True},
            {"name": "api-key-2", "type": "api_key", "key": "key2", "enabled": True},
        ]
    }), encoding="utf-8")

    # All exhausted with future reset times
    state_file.write_text(json.dumps({
        "exhausted": {
            "api-key-1": "2099-12-31T23:59:59+00:00",
            "api-key-2": "2099-12-31T23:59:59+00:00",
        },
    }), encoding="utf-8")

    return creds_file, state_file


@pytest.fixture
def partial_exhausted_creds(creds_dir: Path) -> tuple[Path, Path]:
    """Credentials file with some credentials exhausted."""
    creds_file = creds_dir / "gemini-credentials.json"
    state_file = creds_dir / "gemini-rotation-state.json"

    creds_file.write_text(json.dumps({
        "credentials": [
            {"name": "api-key-1", "type": "api_key", "key": "key1", "enabled": True},
            {"name": "api-key-2", "type": "api_key", "key": "key2", "enabled": True},
            {"name": "api-key-3", "type": "api_key", "key": "key3", "enabled": True},
        ]
    }), encoding="utf-8")

    state_file.write_text(json.dumps({
        "exhausted": {
            "api-key-1": "2099-12-31T23:59:59+00:00",
        },
    }), encoding="utf-8")

    return creds_file, state_file


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: check_gemini_available
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckGeminiAvailable:
    """Tests for check_gemini_available() — zero API calls."""

    def test_all_creds_available(self, all_available_creds: tuple[Path, Path]) -> None:
        """All credentials available → passed=True."""
        creds_file, state_file = all_available_creds
        result = check_gemini_available(
            credentials_file=creds_file, state_file=state_file
        )
        assert isinstance(result, PreflightResult)
        assert result.passed is True
        assert result.available_credentials == 3
        assert result.total_credentials == 3
        assert len(result.exhausted_names) == 0

    def test_all_creds_exhausted(self, all_exhausted_creds: tuple[Path, Path]) -> None:
        """All credentials exhausted → passed=False."""
        creds_file, state_file = all_exhausted_creds
        result = check_gemini_available(
            credentials_file=creds_file, state_file=state_file
        )
        assert result.passed is False
        assert result.available_credentials == 0
        assert result.total_credentials == 2
        assert len(result.exhausted_names) == 2

    def test_partial_exhaustion(self, partial_exhausted_creds: tuple[Path, Path]) -> None:
        """Some credentials exhausted → passed=True (some still available)."""
        creds_file, state_file = partial_exhausted_creds
        result = check_gemini_available(
            credentials_file=creds_file, state_file=state_file
        )
        assert result.passed is True
        assert result.available_credentials == 2
        assert result.total_credentials == 3
        assert "api-key-1" in result.exhausted_names

    def test_missing_credentials_file(self, creds_dir: Path) -> None:
        """Missing credentials file → passed=False with warning."""
        result = check_gemini_available(
            credentials_file=creds_dir / "nonexistent.json",
            state_file=creds_dir / "nonexistent-state.json",
        )
        assert result.passed is False
        assert len(result.warnings) > 0

    def test_missing_state_file_defaults_to_all_available(
        self, creds_dir: Path
    ) -> None:
        """Missing state file → all credentials treated as available."""
        creds_file = creds_dir / "gemini-credentials.json"
        creds_file.write_text(json.dumps({
            "credentials": [
                {"name": "api-key-1", "type": "api_key", "key": "k1", "enabled": True},
            ]
        }), encoding="utf-8")

        result = check_gemini_available(
            credentials_file=creds_file,
            state_file=creds_dir / "nonexistent-state.json",
        )
        assert result.passed is True
        assert result.available_credentials == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: check_gemini_reachable
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckGeminiReachable:
    """Tests for check_gemini_reachable() — lightweight API ping."""

    def test_reachable_ping_success(self, all_available_creds: tuple[Path, Path]) -> None:
        """Successful API ping → model_reachable=True."""
        creds_file, state_file = all_available_creds

        # Mock the Gemini client to return success
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.response = "pong"
        mock_result.error_type = None

        with patch("assemblyzero.core.gemini_client.GeminiClient") as mock_client_cls:
            mock_client_cls.return_value.invoke.return_value = mock_result
            result = check_gemini_reachable(
                model="gemini-3-pro-preview",
                credentials_file=creds_file,
                state_file=state_file,
            )

        assert result.model_reachable is True
        assert result.passed is True

    def test_reachable_ping_503(self, all_available_creds: tuple[Path, Path]) -> None:
        """503 response → model_reachable=False."""
        creds_file, state_file = all_available_creds

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.response = None
        mock_result.error_type = "CAPACITY_EXHAUSTED"
        mock_result.error_message = "503 capacity exhausted"

        with patch("assemblyzero.core.gemini_client.GeminiClient") as mock_client_cls:
            mock_client_cls.return_value.invoke.return_value = mock_result
            result = check_gemini_reachable(
                model="gemini-3-pro-preview",
                credentials_file=creds_file,
                state_file=state_file,
            )

        assert result.model_reachable is False
        assert result.passed is False
        assert len(result.warnings) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: PreflightResult structure
# ═══════════════════════════════════════════════════════════════════════════════


class TestPreflightResult:
    """Tests for PreflightResult dataclass."""

    def test_dataclass_fields(self) -> None:
        """PreflightResult has all expected fields."""
        result = PreflightResult(
            passed=True,
            available_credentials=3,
            total_credentials=3,
            exhausted_names=[],
            model_reachable=True,
            warnings=[],
        )
        assert result.passed is True
        assert result.available_credentials == 3
        assert result.total_credentials == 3
        assert result.exhausted_names == []
        assert result.model_reachable is True
        assert result.warnings == []
