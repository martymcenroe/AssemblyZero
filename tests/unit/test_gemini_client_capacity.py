"""Unit tests for gemini_client.py capacity error handling.

Issue #483: 503 errors silently dropped in retry loop.
Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Tests verify that:
- 503 capacity exhausted errors appear in the error list after retries exhaust
- All-capacity-exhausted returns CAPACITY_EXHAUSTED error type
- Capacity errors are not silently dropped
"""

from unittest.mock import patch
from pathlib import Path
import json

import pytest

from assemblyzero.core.gemini_client import (
    GeminiClient,
    GeminiErrorType,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def creds_dir(tmp_path: Path) -> Path:
    """Temporary directory with credentials and state files.

    #1605: api_key credentials are no longer loaded — governance is
    subscription/OAuth-only.  Fixture updated to use type: oauth.
    """
    creds_file = tmp_path / "gemini-credentials.json"
    state_file = tmp_path / "gemini-rotation-state.json"

    creds_file.write_text(json.dumps({
        "credentials": [
            {"name": "api-key-1", "type": "oauth", "enabled": True},
        ]
    }), encoding="utf-8")

    state_file.write_text(json.dumps({
        "exhausted": {},
        "last_success": None,
    }), encoding="utf-8")

    return tmp_path


@pytest.fixture
def multi_creds_dir(tmp_path: Path) -> Path:
    """Temporary directory with multiple credentials (all will 503).

    #1605: api_key credentials are no longer loaded — governance is
    subscription/OAuth-only.  Fixture updated to use type: oauth.
    """
    creds_file = tmp_path / "gemini-credentials.json"
    state_file = tmp_path / "gemini-rotation-state.json"

    creds_file.write_text(json.dumps({
        "credentials": [
            {"name": "api-key-1", "type": "oauth", "enabled": True},
            {"name": "api-key-2", "type": "oauth", "enabled": True},
        ]
    }), encoding="utf-8")

    state_file.write_text(json.dumps({
        "exhausted": {},
        "last_success": None,
    }), encoding="utf-8")

    return tmp_path


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Bug #483 — Silent 503 drop
# ═══════════════════════════════════════════════════════════════════════════════


class TestCapacity503Fix:
    """Tests for issue #483: 503 errors must not be silently dropped."""

    def test_503_appears_in_errors(self, creds_dir: Path) -> None:
        """After retries exhaust on 503, the error appears in the result.

        #1605: patch _invoke_via_cli (OAuth transport) to return a 503/capacity
        error on every attempt.  The rotation loop must surface the error
        rather than silently dropping it.
        """
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=creds_dir / "gemini-credentials.json",
            state_file=creds_dir / "gemini-rotation-state.json",
        )

        with patch.object(client, "_invoke_via_cli",
                          return_value=(False, "", "503 The model is overloaded. MODEL_CAPACITY_EXHAUSTED")), \
             patch("assemblyzero.core.gemini_client.time.sleep"):  # Skip actual delays

            result = client.invoke(
                system_instruction="test",
                content="test",
            )

        assert result.success is False
        assert result.error_message is not None
        # The error message must mention capacity exhaustion — NOT be empty
        assert "Capacity exhausted" in result.error_message or "capacity" in result.error_message.lower()

    def test_all_capacity_returns_capacity_type(self, multi_creds_dir: Path) -> None:
        """When all credentials fail with 503, error_type is CAPACITY_EXHAUSTED.

        #1605: patch _invoke_via_cli for both OAuth credentials.
        """
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=multi_creds_dir / "gemini-credentials.json",
            state_file=multi_creds_dir / "gemini-rotation-state.json",
        )

        with patch.object(client, "_invoke_via_cli",
                          return_value=(False, "", "503 The model is overloaded. MODEL_CAPACITY_EXHAUSTED")), \
             patch("assemblyzero.core.gemini_client.time.sleep"):

            result = client.invoke(
                system_instruction="test",
                content="test",
            )

        assert result.success is False
        assert result.error_type == GeminiErrorType.CAPACITY_EXHAUSTED

    def test_capacity_error_not_silently_dropped(self, creds_dir: Path) -> None:
        """Regression: capacity errors must produce a non-empty error_message.

        Before the fix, the while loop `continue` on capacity errors
        never appended to the errors list, so after retries exhausted
        the error was silently dropped.

        #1605: patch _invoke_via_cli (OAuth transport) with a 529 capacity error.
        """
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=creds_dir / "gemini-credentials.json",
            state_file=creds_dir / "gemini-rotation-state.json",
        )

        with patch.object(client, "_invoke_via_cli",
                          return_value=(False, "", "529 RESOURCE_EXHAUSTED")), \
             patch("assemblyzero.core.gemini_client.time.sleep"):

            result = client.invoke(
                system_instruction="test",
                content="test",
            )

        # The critical assertion: error_message must NOT be empty
        assert result.error_message is not None
        assert len(result.error_message) > 0
        # And it must reference the credential that failed
        assert "api-key-1" in result.error_message
