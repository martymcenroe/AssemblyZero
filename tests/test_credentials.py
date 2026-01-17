#!/usr/bin/env python3
"""
Tests for agentos_credentials.py - Secure credential management.

Issue: #25
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add tools directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from agentos_credentials import (
    Credential,
    CredentialManager,
    EnvBackend,
    KeychainBackend,
    LegacyFileBackend,
)


class TestCredential:
    """Tests for Credential dataclass."""

    def test_credential_creation(self):
        cred = Credential(name="test", key="secret-key")
        assert cred.name == "test"
        assert cred.key == "secret-key"
        assert cred.credential_type == "api_key"
        assert cred.enabled is True

    def test_credential_with_all_fields(self):
        cred = Credential(
            name="custom",
            key="my-key",
            credential_type="oauth",
            enabled=False
        )
        assert cred.name == "custom"
        assert cred.key == "my-key"
        assert cred.credential_type == "oauth"
        assert cred.enabled is False


class TestEnvBackend:
    """Tests for environment variable backend."""

    def test_get_credentials_when_set(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-test-key"}):
            backend = EnvBackend()
            creds = backend.get_credentials()
            assert len(creds) == 1
            assert creds[0].name == "env"
            assert creds[0].key == "env-test-key"

    def test_get_credentials_when_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            # Ensure GEMINI_API_KEY is not set
            os.environ.pop("GEMINI_API_KEY", None)
            backend = EnvBackend()
            creds = backend.get_credentials()
            assert len(creds) == 0

    def test_is_available_when_set(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}):
            backend = EnvBackend()
            assert backend.is_available() is True

    def test_is_available_when_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GEMINI_API_KEY", None)
            backend = EnvBackend()
            assert backend.is_available() is False

    def test_store_credential_returns_false(self):
        backend = EnvBackend()
        result = backend.store_credential(Credential(name="test", key="key"))
        assert result is False

    def test_delete_credential_returns_false(self):
        backend = EnvBackend()
        result = backend.delete_credential("test")
        assert result is False


class TestLegacyFileBackend:
    """Tests for legacy plaintext file backend."""

    def test_get_credentials_from_valid_file(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps({
            "credentials": [
                {"name": "key1", "key": "secret1", "type": "api_key", "enabled": True},
                {"name": "key2", "key": "secret2", "type": "api_key", "enabled": True},
            ]
        }))

        backend = LegacyFileBackend(path=creds_file)
        creds = backend.get_credentials()

        assert len(creds) == 2
        assert creds[0].name == "key1"
        assert creds[0].key == "secret1"
        assert creds[1].name == "key2"

    def test_get_credentials_skips_disabled(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps({
            "credentials": [
                {"name": "enabled", "key": "secret1", "enabled": True},
                {"name": "disabled", "key": "secret2", "enabled": False},
            ]
        }))

        backend = LegacyFileBackend(path=creds_file)
        creds = backend.get_credentials()

        assert len(creds) == 1
        assert creds[0].name == "enabled"

    def test_get_credentials_file_not_exists(self):
        backend = LegacyFileBackend(path=Path("/nonexistent/path.json"))
        creds = backend.get_credentials()
        assert len(creds) == 0

    def test_is_available_when_file_exists(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps({"credentials": []}))

        backend = LegacyFileBackend(path=creds_file)
        assert backend.is_available() is True

    def test_is_available_when_file_not_exists(self):
        backend = LegacyFileBackend(path=Path("/nonexistent/path.json"))
        assert backend.is_available() is False

    def test_store_credential_returns_false(self):
        backend = LegacyFileBackend()
        result = backend.store_credential(Credential(name="test", key="key"))
        assert result is False

    def test_delete_credential_returns_false(self):
        backend = LegacyFileBackend()
        result = backend.delete_credential("test")
        assert result is False


class TestKeychainBackend:
    """Tests for OS keychain backend."""

    def test_is_available_handles_no_keyring_error(self):
        """Test graceful handling when no keyring backend available."""
        import keyring.errors

        with patch('keyring.get_password', side_effect=keyring.errors.NoKeyringError()):
            backend = KeychainBackend()
            assert backend.is_available() is False

    def test_get_credentials_handles_no_keyring_error(self):
        """Test graceful fallback when keyring unavailable."""
        import keyring.errors

        with patch('keyring.get_password', side_effect=keyring.errors.NoKeyringError()):
            backend = KeychainBackend()
            creds = backend.get_credentials()
            assert len(creds) == 0

    def test_store_credential_handles_no_keyring_error(self):
        """Test graceful failure when keyring unavailable."""
        import keyring.errors

        with patch('keyring.set_password', side_effect=keyring.errors.NoKeyringError()):
            backend = KeychainBackend()
            result = backend.store_credential(Credential(name="test", key="key"))
            assert result is False


class TestCredentialManager:
    """Tests for the unified credential manager."""

    def test_env_var_takes_priority(self):
        """Environment variable should be checked first."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-key"}):
            manager = CredentialManager()
            creds = manager.get_credentials()
            assert len(creds) == 1
            assert creds[0].name == "env"
            assert creds[0].key == "env-key"

    def test_falls_back_to_legacy_file(self, tmp_path):
        """Should fall back to legacy file when env not set and keychain empty."""
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps({
            "credentials": [
                {"name": "legacy-key", "key": "legacy-secret", "enabled": True}
            ]
        }))

        # Remove GEMINI_API_KEY but preserve HOME vars
        env_without_gemini = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env_without_gemini, clear=True):
            manager = CredentialManager()
            # Replace legacy backend path
            manager.backends[2] = LegacyFileBackend(path=creds_file)

            # Mock keychain as returning empty
            with patch.object(manager.backends[1], 'get_credentials', return_value=[]):
                creds = manager.get_credentials()
                assert len(creds) == 1
                assert creds[0].name == "legacy-key"

    def test_returns_empty_when_no_credentials(self):
        """Should return empty list when no credentials available."""
        # Remove GEMINI_API_KEY but preserve HOME vars
        env_without_gemini = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env_without_gemini, clear=True):
            manager = CredentialManager()
            # Mock all backends as returning empty
            manager.backends[0] = MagicMock(get_credentials=MagicMock(return_value=[]))
            manager.backends[1] = MagicMock(get_credentials=MagicMock(return_value=[]))
            manager.backends[2] = MagicMock(get_credentials=MagicMock(return_value=[]))

            creds = manager.get_credentials()
            assert len(creds) == 0


class TestMigration:
    """Tests for credential migration functionality."""

    def test_migrate_to_keychain_raises_when_unavailable(self):
        """Migration should fail gracefully when keychain unavailable."""
        import keyring.errors

        manager = CredentialManager()

        with patch.object(manager.backends[1], 'is_available', return_value=False):
            with pytest.raises(RuntimeError, match="Keychain not available"):
                manager.migrate_to_keychain()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
