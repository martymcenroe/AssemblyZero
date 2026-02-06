"""Unit tests for LLM Provider abstraction.

Issue #101: Unified Governance Workflow

Tests for:
- LLMCallResult dataclass
- LLMProvider ABC
- ClaudeCLIProvider
- GeminiProvider
- MockProvider
- get_provider factory
- parse_provider_spec
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import subprocess

from assemblyzero.core.llm_provider import (
    LLMCallResult,
    LLMProvider,
    ClaudeCLIProvider,
    GeminiProvider,
    MockProvider,
    get_provider,
    parse_provider_spec,
)


class TestLLMCallResult:
    """Tests for LLMCallResult dataclass."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = LLMCallResult(
            success=True,
            response="Hello, world!",
            raw_response='{"result": "Hello, world!"}',
            error_message=None,
            provider="claude",
            model_used="opus-4.5",
            duration_ms=1500,
            attempts=1,
        )

        assert result.success is True
        assert result.response == "Hello, world!"
        assert result.error_message is None
        assert result.provider == "claude"
        assert result.model_used == "opus-4.5"
        assert result.duration_ms == 1500
        assert result.attempts == 1

    def test_failure_result(self):
        """Test creating a failure result."""
        result = LLMCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_message="API timeout",
            provider="gemini",
            model_used="2.5-pro",
            duration_ms=30000,
            attempts=3,
        )

        assert result.success is False
        assert result.response is None
        assert result.error_message == "API timeout"
        assert result.attempts == 3

    def test_rotation_fields(self):
        """Test credential rotation observability fields."""
        result = LLMCallResult(
            success=True,
            response="OK",
            raw_response="OK",
            error_message=None,
            provider="gemini",
            model_used="2.5-pro",
            duration_ms=500,
            attempts=2,
            credential_used="account-2",
            rotation_occurred=True,
        )

        assert result.credential_used == "account-2"
        assert result.rotation_occurred is True


class TestParseProviderSpec:
    """Tests for parse_provider_spec function."""

    def test_valid_claude_spec(self):
        """Test parsing valid Claude spec."""
        provider, model = parse_provider_spec("claude:opus-4.5")
        assert provider == "claude"
        assert model == "opus-4.5"

    def test_valid_gemini_spec(self):
        """Test parsing valid Gemini spec."""
        provider, model = parse_provider_spec("gemini:2.5-pro")
        assert provider == "gemini"
        assert model == "2.5-pro"

    def test_case_insensitive_provider(self):
        """Test that provider is case-insensitive."""
        provider, model = parse_provider_spec("CLAUDE:opus")
        assert provider == "claude"

    def test_invalid_spec_no_colon(self):
        """Test that spec without colon raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_provider_spec("claude-opus")

        assert "Invalid provider spec" in str(exc_info.value)
        assert "provider:model" in str(exc_info.value)

    def test_empty_spec(self):
        """Test that empty spec raises ValueError."""
        with pytest.raises(ValueError):
            parse_provider_spec("")


class TestClaudeCLIProvider:
    """Tests for ClaudeCLIProvider."""

    def test_valid_model_opus(self):
        """Test creating provider with opus model."""
        provider = ClaudeCLIProvider(model="opus-4.5")
        assert provider.provider_name == "claude"
        assert provider.model == "opus-4.5"

    def test_valid_model_sonnet(self):
        """Test creating provider with sonnet model."""
        provider = ClaudeCLIProvider(model="sonnet")
        assert provider.model == "sonnet"

    def test_valid_model_haiku(self):
        """Test creating provider with haiku model."""
        provider = ClaudeCLIProvider(model="haiku")
        assert provider.model == "haiku"

    def test_invalid_model(self):
        """Test that invalid model raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ClaudeCLIProvider(model="gpt-4")

        assert "Unknown Claude model" in str(exc_info.value)

    def test_model_case_insensitive(self):
        """Test that model names are case-insensitive."""
        provider = ClaudeCLIProvider(model="OPUS-4.5")
        assert provider.model == "opus-4.5"

    @patch("shutil.which")
    def test_find_cli_in_path(self, mock_which):
        """Test finding claude CLI in PATH."""
        mock_which.return_value = "/usr/local/bin/claude"
        provider = ClaudeCLIProvider()
        cli_path = provider._find_cli()
        assert cli_path == "/usr/local/bin/claude"

    def test_invoke_returns_error_when_cli_not_found(self):
        """Test that invoke returns error result when CLI not found."""
        provider = ClaudeCLIProvider()
        # Force _find_cli to raise by setting cached path to None and mocking
        provider._cli_path = None

        with patch.object(provider, "_find_cli", side_effect=RuntimeError("claude command not found")):
            result = provider.invoke("system", "content")

        assert result.success is False
        assert "claude command not found" in result.error_message

    @patch("subprocess.run")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_invoke_success(self, mock_find_cli, mock_run):
        """Test successful invocation."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"result": "Generated content"}',
            stderr="",
        )

        provider = ClaudeCLIProvider()
        result = provider.invoke(
            system_prompt="You are a helpful assistant",
            content="Hello!",
        )

        assert result.success is True
        assert result.response == "Generated content"
        assert result.provider == "claude"

    @patch("subprocess.run")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_invoke_failure(self, mock_find_cli, mock_run):
        """Test invocation failure."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Authentication failed",
        )

        provider = ClaudeCLIProvider()
        result = provider.invoke(
            system_prompt="Test",
            content="Test",
        )

        assert result.success is False
        assert "failed" in result.error_message.lower()

    @patch("subprocess.run")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_invoke_timeout(self, mock_find_cli, mock_run):
        """Test invocation timeout."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=300)

        provider = ClaudeCLIProvider()
        result = provider.invoke(
            system_prompt="Test",
            content="Test",
            timeout_seconds=300,
        )

        assert result.success is False
        assert "timed out" in result.error_message.lower()


class TestGeminiProvider:
    """Tests for GeminiProvider."""

    def test_valid_model_pro(self):
        """Test creating provider with pro model."""
        provider = GeminiProvider(model="2.5-pro")
        assert provider.provider_name == "gemini"
        assert provider.model == "2.5-pro"

    def test_valid_model_flash(self):
        """Test creating provider with flash model."""
        provider = GeminiProvider(model="flash")
        assert provider.model == "flash"

    def test_valid_model_3_pro_preview(self):
        """Test creating provider with 3-pro-preview model."""
        provider = GeminiProvider(model="3-pro-preview")
        assert provider.model == "3-pro-preview"

    def test_valid_model_3_flash_preview(self):
        """Test creating provider with 3-flash-preview model."""
        provider = GeminiProvider(model="3-flash-preview")
        assert provider.model == "3-flash-preview"

    def test_invalid_model(self):
        """Test that invalid model raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            GeminiProvider(model="gpt-4")

        assert "Unknown Gemini model" in str(exc_info.value)

    def test_model_case_insensitive(self):
        """Test that model names are case-insensitive."""
        provider = GeminiProvider(model="PRO")
        assert provider.model == "pro"

    @patch("assemblyzero.core.llm_provider.GeminiProvider._get_client")
    def test_invoke_success(self, mock_get_client):
        """Test successful invocation."""
        mock_client = Mock()
        mock_client.invoke.return_value = Mock(
            success=True,
            response="Reviewed content",
            raw_response="Reviewed content",
            error_message=None,
            model_verified="gemini-2.5-pro",
            duration_ms=1000,
            attempts=1,
            credential_used="account-1",
            rotation_occurred=False,
        )
        mock_get_client.return_value = mock_client

        provider = GeminiProvider(model="2.5-pro")
        result = provider.invoke(
            system_prompt="You are a reviewer",
            content="Review this",
        )

        assert result.success is True
        assert result.response == "Reviewed content"
        assert result.provider == "gemini"

    @patch("assemblyzero.core.llm_provider.GeminiProvider._get_client")
    def test_invoke_with_rotation(self, mock_get_client):
        """Test invocation with credential rotation."""
        mock_client = Mock()
        mock_client.invoke.return_value = Mock(
            success=True,
            response="OK",
            raw_response="OK",
            error_message=None,
            model_verified="gemini-2.5-pro",
            duration_ms=2000,
            attempts=2,
            credential_used="account-2",
            rotation_occurred=True,
        )
        mock_get_client.return_value = mock_client

        provider = GeminiProvider()
        result = provider.invoke(
            system_prompt="Test",
            content="Test",
        )

        assert result.success is True
        assert result.rotation_occurred is True
        assert result.credential_used == "account-2"


class TestMockProvider:
    """Tests for MockProvider."""

    def test_default_response(self):
        """Test default mock response."""
        provider = MockProvider()
        result = provider.invoke("system", "content")

        assert result.success is True
        assert result.response == "Mock response"
        assert result.provider == "mock"

    def test_custom_responses(self):
        """Test custom mock responses."""
        provider = MockProvider(responses=["First", "Second", "Third"])

        r1 = provider.invoke("s", "c")
        r2 = provider.invoke("s", "c")
        r3 = provider.invoke("s", "c")

        assert r1.response == "First"
        assert r2.response == "Second"
        assert r3.response == "Third"

    def test_responses_cycle(self):
        """Test that responses cycle when exhausted."""
        provider = MockProvider(responses=["A", "B"])

        r1 = provider.invoke("s", "c")
        r2 = provider.invoke("s", "c")
        r3 = provider.invoke("s", "c")

        assert r1.response == "A"
        assert r2.response == "B"
        assert r3.response == "A"  # Cycles back

    def test_fail_on_call(self):
        """Test failure on specific call."""
        provider = MockProvider(fail_on_call=2)

        r1 = provider.invoke("s", "c")
        r2 = provider.invoke("s", "c")
        r3 = provider.invoke("s", "c")

        assert r1.success is True
        assert r2.success is False
        assert "Mock failure on call 2" in r2.error_message
        assert r3.success is True


class TestGetProvider:
    """Tests for get_provider factory function."""

    def test_get_claude_provider(self):
        """Test getting Claude provider."""
        provider = get_provider("claude:opus-4.5")
        assert isinstance(provider, ClaudeCLIProvider)
        assert provider.model == "opus-4.5"

    def test_get_gemini_provider(self):
        """Test getting Gemini provider."""
        provider = get_provider("gemini:2.5-pro")
        assert isinstance(provider, GeminiProvider)
        assert provider.model == "2.5-pro"

    def test_get_mock_provider(self):
        """Test getting Mock provider."""
        provider = get_provider("mock:test")
        assert isinstance(provider, MockProvider)
        assert provider.model == "test"

    def test_invalid_provider(self):
        """Test that invalid provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_provider("openai:gpt-4")

        assert "Unknown provider" in str(exc_info.value)

    def test_invalid_spec_format(self):
        """Test that invalid spec format raises ValueError."""
        with pytest.raises(ValueError):
            get_provider("invalid-spec")


class TestLLMProviderABC:
    """Tests to ensure LLMProvider is a proper ABC."""

    def test_cannot_instantiate_abc(self):
        """Test that LLMProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            LLMProvider()

    def test_must_implement_all_methods(self):
        """Test that subclass must implement all abstract methods."""

        class IncompleteProvider(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "incomplete"

            # Missing model property and invoke method

        with pytest.raises(TypeError):
            IncompleteProvider()
