"""Tests for the Gemini client with rotation logic.

Test Scenarios from LLD:
- 090: 429 triggers rotation
- 100: 529 triggers backoff
- 110: All credentials exhausted
- 120: Model verification
- 130: Forbidden model rejected
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core.gemini_client import (
    Credential,
    GeminiCallResult,
    GeminiClient,
    GeminiErrorType,
    RotationState,
)


@pytest.fixture
def temp_credentials_file():
    """Create a temporary credentials file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        creds_file = Path(tmpdir) / "credentials.json"
        creds_file.write_text(
            json.dumps(
                {
                    "credentials": [
                        {"name": "key-1", "key": "test-key-1", "enabled": True, "type": "api_key"},
                        {"name": "key-2", "key": "test-key-2", "enabled": True, "type": "api_key"},
                        {"name": "key-3", "key": "test-key-3", "enabled": True, "type": "api_key"},
                    ]
                }
            )
        )
        yield creds_file


@pytest.fixture
def temp_state_file():
    """Create a temporary state file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "state.json"


class TestGeminiClientModelValidation:
    """Tests for model validation in GeminiClient."""

    def test_130_forbidden_model_rejected_flash(self):
        """Test that Flash model is rejected at initialization."""
        with pytest.raises(ValueError) as exc_info:
            GeminiClient(model="gemini-2.0-flash")

        assert "forbidden" in str(exc_info.value).lower()

    def test_130_forbidden_model_rejected_lite(self):
        """Test that Lite model is rejected at initialization."""
        with pytest.raises(ValueError) as exc_info:
            GeminiClient(model="gemini-2.5-lite")

        assert "forbidden" in str(exc_info.value).lower()

    def test_valid_pro_model_accepted(self, temp_credentials_file, temp_state_file):
        """Test that Pro model is accepted."""
        # Should not raise
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )
        assert client.model == "gemini-3-pro-preview"

    def test_non_gemini_model_rejected(self):
        """Test that non-Gemini models are rejected."""
        with pytest.raises(ValueError) as exc_info:
            GeminiClient(model="gpt-4")

        assert "not a valid Gemini model" in str(exc_info.value)

    def test_flash_preview_model_accepted(self, temp_credentials_file, temp_state_file):
        """Test that 3-flash-preview model is accepted."""
        # Should not raise
        client = GeminiClient(
            model="gemini-3-flash-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )
        assert client.model == "gemini-3-flash-preview"


class TestCredentialLoading:
    """Tests for credential loading."""

    def test_loads_credentials_from_file(self, temp_credentials_file, temp_state_file):
        """Test that credentials are loaded from file."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        creds = client._load_credentials()
        assert len(creds) == 3
        assert creds[0].name == "key-1"
        assert creds[0].key == "test-key-1"

    def test_missing_credentials_file_raises(self, temp_state_file):
        """Test that missing credentials file raises FileNotFoundError."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=Path("/nonexistent/creds.json"),
            state_file=temp_state_file,
        )

        with pytest.raises(FileNotFoundError):
            client._load_credentials()


class TestErrorClassification:
    """Tests for error classification."""

    def test_quota_exhausted_detection(self, temp_credentials_file, temp_state_file):
        """Test that 429/quota errors are classified correctly."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        assert (
            client._classify_error("TerminalQuotaError: exhausted")
            == GeminiErrorType.QUOTA_EXHAUSTED
        )
        assert (
            client._classify_error("You have exhausted your capacity")
            == GeminiErrorType.QUOTA_EXHAUSTED
        )
        assert (
            client._classify_error("429 Too Many Requests")
            == GeminiErrorType.QUOTA_EXHAUSTED
        )

    def test_capacity_exhausted_detection(self, temp_credentials_file, temp_state_file):
        """Test that 529/capacity errors are classified correctly."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        assert (
            client._classify_error("MODEL_CAPACITY_EXHAUSTED")
            == GeminiErrorType.CAPACITY_EXHAUSTED
        )
        assert (
            client._classify_error("503 Service Unavailable")
            == GeminiErrorType.CAPACITY_EXHAUSTED
        )
        assert (
            client._classify_error("The model is overloaded")
            == GeminiErrorType.CAPACITY_EXHAUSTED
        )

    def test_auth_error_detection(self, temp_credentials_file, temp_state_file):
        """Test that auth errors are classified correctly."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        assert (
            client._classify_error("API_KEY_INVALID") == GeminiErrorType.AUTH_ERROR
        )
        assert (
            client._classify_error("401 Unauthorized") == GeminiErrorType.AUTH_ERROR
        )
        assert (
            client._classify_error("PERMISSION_DENIED") == GeminiErrorType.AUTH_ERROR
        )


class TestRotationLogic:
    """Tests for credential rotation logic."""

    def test_090_429_triggers_rotation(self, temp_credentials_file, temp_state_file):
        """Test that 429 error causes rotation to next credential."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        call_sequence = []

        def mock_client_init(api_key):
            """Capture API key and return mock client."""
            call_sequence.append(api_key)
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception(
                "TerminalQuotaError: exhausted"
            )
            return mock_client

        with patch("assemblyzero.core.gemini_client.genai.Client") as mock_client_class:
            mock_client_class.side_effect = mock_client_init

            result = client.invoke("system", "content")

        # Should have tried all 3 credentials
        assert len(call_sequence) == 3
        assert call_sequence[0] == "test-key-1"
        assert call_sequence[1] == "test-key-2"
        assert call_sequence[2] == "test-key-3"

        # Result should indicate rotation occurred
        assert result.rotation_occurred is True
        assert result.success is False

    def test_100_529_triggers_backoff(self, temp_credentials_file, temp_state_file):
        """Test that 529 error causes backoff retry on same credential."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        attempts = [0]

        def mock_generate(*args, **kwargs):
            attempts[0] += 1
            if attempts[0] < 3:
                raise Exception("MODEL_CAPACITY_EXHAUSTED")
            # Succeed on 3rd attempt
            mock_response = MagicMock()
            mock_response.text = "Success"
            return mock_response

        def mock_client_init(api_key):
            """Return mock client with generate_content that tracks attempts."""
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = mock_generate
            return mock_client

        with patch("assemblyzero.core.gemini_client.genai.Client") as mock_client_class:
            mock_client_class.side_effect = mock_client_init

            with patch("time.sleep"):  # Skip actual delay
                result = client.invoke("system", "content")

        # Should have retried 3 times on same credential
        assert attempts[0] == 3
        assert result.success is True
        assert result.rotation_occurred is False

    def test_110_all_credentials_exhausted(self, temp_credentials_file, temp_state_file):
        """Test behavior when all credentials are exhausted."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        def mock_client_init(api_key):
            """Return mock client that always raises quota error."""
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception(
                "TerminalQuotaError: exhausted"
            )
            return mock_client

        with patch("assemblyzero.core.gemini_client.genai.Client") as mock_client_class:
            mock_client_class.side_effect = mock_client_init

            result = client.invoke("system", "content")

        assert result.success is False
        # When all credentials fail due to quota exhaustion, error type is QUOTA_EXHAUSTED
        assert result.error_type == GeminiErrorType.QUOTA_EXHAUSTED
        assert "All credentials failed" in result.error_message


class TestBackoffDelay:
    """Tests for backoff delay calculation."""

    def test_exponential_backoff(self, temp_credentials_file, temp_state_file):
        """Test that backoff delay is exponential."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        # Base is 2.0 seconds, exponential growth
        assert client._backoff_delay(0) == 2.0  # 2 * 2^0 = 2
        assert client._backoff_delay(1) == 4.0  # 2 * 2^1 = 4
        assert client._backoff_delay(2) == 8.0  # 2 * 2^2 = 8

    def test_backoff_max_cap(self, temp_credentials_file, temp_state_file):
        """Test that backoff is capped at maximum."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        # Should be capped at 60 seconds
        assert client._backoff_delay(10) == 60.0


class TestResetTimeParsing:
    """Tests for quota reset time parsing."""

    def test_parses_reset_time(self, temp_credentials_file, temp_state_file):
        """Test parsing of reset time from error message."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        result = client._parse_reset_time("Your quota will reset after 15h11m58s")
        assert result is not None
        assert abs(result - 15.2) < 0.1  # 15 hours + 11 minutes

    def test_returns_none_for_unparseable(self, temp_credentials_file, temp_state_file):
        """Test that unparseable messages return None."""
        client = GeminiClient(
            model="gemini-3-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        result = client._parse_reset_time("Some random error message")
        assert result is None
