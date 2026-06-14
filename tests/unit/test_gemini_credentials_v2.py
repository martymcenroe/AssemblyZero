"""Tests for gemini-test-credentials-v2.py OAuth testing (Issue #150).

TDD: These tests define the expected behavior for OAuth credential testing.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add tools directory to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))


class TestOAuthCredentialTesting:
    """Tests for OAuth credential testing functionality."""

    def test_oauth_valid_credentials_returns_success(self, tmp_path):
        """Valid OAuth credentials should return success."""
        # Import here to allow path setup
        from importlib import import_module
        spec = import_module("gemini-test-credentials-v2")
        test_oauth = spec.test_oauth

        # Mock OAuth credential data
        oauth_cred = {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret",
            "refresh_token": "test-refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
        }

        # Mock the genai Client to return success
        with patch.object(spec, "genai") as mock_genai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Hello world!"
            mock_client.models.generate_content.return_value = mock_response
            mock_genai.Client.return_value = mock_client

            success, message = test_oauth("test-oauth", oauth_cred)

        assert success is True
        assert "OK" in message

    def test_oauth_missing_refresh_token_returns_failure(self, tmp_path):
        """OAuth credentials without refresh_token should fail."""
        from importlib import import_module
        spec = import_module("gemini-test-credentials-v2")
        test_oauth = spec.test_oauth

        # OAuth cred missing refresh_token
        oauth_cred = {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret",
            # Missing refresh_token
        }

        success, message = test_oauth("test-oauth", oauth_cred)

        assert success is False
        assert "refresh_token" in message.lower() or "missing" in message.lower()

    def test_oauth_missing_client_id_returns_failure(self, tmp_path):
        """OAuth credentials without client_id should fail."""
        from importlib import import_module
        spec = import_module("gemini-test-credentials-v2")
        test_oauth = spec.test_oauth

        # OAuth cred missing client_id
        oauth_cred = {
            "client_secret": "test-client-secret",
            "refresh_token": "test-refresh-token",
        }

        success, message = test_oauth("test-oauth", oauth_cred)

        assert success is False
        assert "client_id" in message.lower() or "missing" in message.lower()

    def test_oauth_invalid_credentials_returns_auth_error(self, tmp_path):
        """Invalid OAuth credentials should return auth error."""
        from importlib import import_module
        spec = import_module("gemini-test-credentials-v2")
        test_oauth = spec.test_oauth

        oauth_cred = {
            "client_id": "invalid-client-id",
            "client_secret": "invalid-secret",
            "refresh_token": "invalid-token",
        }

        # Mock to raise auth error
        with patch.object(spec, "genai") as mock_genai:
            from google.genai import errors
            mock_genai.Client.side_effect = Exception("invalid_grant: Token has been revoked")

            success, message = test_oauth("test-oauth", oauth_cred)

        assert success is False
        assert "invalid" in message.lower() or "error" in message.lower()

    def test_oauth_empty_credentials_returns_failure(self, tmp_path):
        """Empty OAuth credentials dict should fail."""
        from importlib import import_module
        spec = import_module("gemini-test-credentials-v2")
        test_oauth = spec.test_oauth

        oauth_cred = {}

        success, message = test_oauth("test-oauth", oauth_cred)

        assert success is False

    def test_oauth_api_timeout_returns_timeout_error(self, tmp_path):
        """OAuth API timeout should return timeout error."""
        from importlib import import_module
        spec = import_module("gemini-test-credentials-v2")
        test_oauth = spec.test_oauth

        oauth_cred = {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret",
            "refresh_token": "test-refresh-token",
        }

        # Mock to raise timeout
        with patch.object(spec, "genai") as mock_genai:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception("Request timed out")
            mock_genai.Client.return_value = mock_client

            success, message = test_oauth("test-oauth", oauth_cred)

        assert success is False
        assert "timeout" in message.lower() or "error" in message.lower()

    def test_oauth_quota_exceeded_returns_rate_limit_error(self, tmp_path):
        """OAuth quota exceeded should return rate limit error."""
        from importlib import import_module
        spec = import_module("gemini-test-credentials-v2")
        test_oauth = spec.test_oauth

        oauth_cred = {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret",
            "refresh_token": "test-refresh-token",
        }

        # Mock to raise quota error
        with patch.object(spec, "genai") as mock_genai:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception("429 QUOTA_EXHAUSTED")
            mock_genai.Client.return_value = mock_client

            success, message = test_oauth("test-oauth", oauth_cred)

        assert success is False
        assert "rate" in message.lower() or "quota" in message.lower() or "429" in message
