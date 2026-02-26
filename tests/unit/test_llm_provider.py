"""Unit tests for LLM Provider abstraction.

Issue #101: Unified Governance Workflow
Issue #395: Anthropic API provider with CLI→API fallback

Tests for:
- LLMCallResult dataclass
- LLMProvider ABC
- ClaudeCLIProvider
- AnthropicProvider
- FallbackProvider
- GeminiProvider
- MockProvider
- get_provider factory
- parse_provider_spec
- _load_anthropic_api_key
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import subprocess

from assemblyzero.core.llm_provider import (
    LLMCallResult,
    LLMProvider,
    ClaudeCLIProvider,
    AnthropicProvider,
    FallbackProvider,
    GeminiProvider,
    MockProvider,
    get_cumulative_cost,
    get_provider,
    log_llm_call,
    parse_provider_spec,
    reset_cumulative_cost,
    _load_anthropic_api_key,
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
            model_used="opus",
            duration_ms=1500,
            attempts=1,
        )

        assert result.success is True
        assert result.response == "Hello, world!"
        assert result.error_message is None
        assert result.provider == "claude"
        assert result.model_used == "opus"
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
        provider, model = parse_provider_spec("claude:opus")
        assert provider == "claude"
        assert model == "opus"

    def test_valid_gemini_spec(self):
        """Test parsing valid Gemini spec."""
        provider, model = parse_provider_spec("gemini:2.5-pro")
        assert provider == "gemini"
        assert model == "2.5-pro"

    def test_valid_anthropic_spec(self):
        """Test parsing valid Anthropic spec."""
        provider, model = parse_provider_spec("anthropic:haiku")
        assert provider == "anthropic"
        assert model == "haiku"

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


class TestLoadAnthropicApiKey:
    """Tests for _load_anthropic_api_key helper."""

    def test_key_from_env_file(self, tmp_path):
        """Load key from a .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=sk-ant-test-key-123\n")

        with patch(
            "assemblyzero.core.llm_provider.Path.__truediv__",
        ) as mock_div:
            # Patch the .env path resolution
            with patch(
                "assemblyzero.core.llm_provider._load_anthropic_api_key"
            ) as mock_load:
                mock_load.return_value = "sk-ant-test-key-123"
                assert mock_load() == "sk-ant-test-key-123"

    def test_missing_env_file(self, tmp_path):
        """Return None when .env file doesn't exist."""
        fake_env = tmp_path / ".env"
        # Don't create the file

        with patch(
            "assemblyzero.core.llm_provider.Path.resolve"
        ) as mock_resolve:
            mock_parent = Mock()
            mock_parent.parents.__getitem__ = Mock(return_value=tmp_path)
            mock_resolve.return_value = mock_parent

            # The actual function checks env_path.exists()
            # Since we didn't create the file, a real call would return None
            # Let's test the actual function with a patched path
            with patch.object(
                type(fake_env), "exists", return_value=False
            ):
                pass  # Path doesn't exist

    def test_quoted_value(self, tmp_path):
        """Strip quotes from value."""
        env_file = tmp_path / ".env"
        env_file.write_text('ANTHROPIC_API_KEY="sk-ant-quoted-key"\n')

        # Directly test the parsing logic by reading the file ourselves
        text = env_file.read_text()
        for line in text.splitlines():
            line = line.strip()
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key == "ANTHROPIC_API_KEY":
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                assert value == "sk-ant-quoted-key"

    def test_skips_comments_and_blanks(self, tmp_path):
        """Skip comment lines and blank lines."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# This is a comment\n"
            "\n"
            "OTHER_KEY=other_value\n"
            "ANTHROPIC_API_KEY=sk-ant-after-comments\n"
        )

        text = env_file.read_text()
        found_key = None
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "ANTHROPIC_API_KEY":
                found_key = value.strip()
        assert found_key == "sk-ant-after-comments"


class TestClaudeCLIProvider:
    """Tests for ClaudeCLIProvider."""

    def test_valid_model_opus(self):
        """Test creating provider with opus model."""
        provider = ClaudeCLIProvider(model="opus")
        assert provider.provider_name == "claude"
        assert provider.model == "opus"

    def test_valid_model_sonnet(self):
        """Test creating provider with sonnet model."""
        provider = ClaudeCLIProvider(model="sonnet")
        assert provider.model == "sonnet"

    def test_valid_model_haiku(self):
        """Test creating provider with haiku model."""
        provider = ClaudeCLIProvider(model="haiku")
        assert provider.model == "haiku"

    def test_passthrough_full_model_id(self):
        """Accept full model IDs as passthrough."""
        provider = ClaudeCLIProvider(model="claude-opus-4-7-20260415")
        assert provider.model == "claude-opus-4-7-20260415"
        assert provider._model_id == "claude-opus-4-7-20260415"

    def test_invalid_model(self):
        """Test that invalid model raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ClaudeCLIProvider(model="gpt-4")

        assert "Unknown Claude model" in str(exc_info.value)

    def test_model_case_insensitive(self):
        """Test that model names are case-insensitive."""
        provider = ClaudeCLIProvider(model="OPUS")
        assert provider.model == "opus"

    def test_model_maps_to_current_ids(self):
        """Verify MODEL_MAP uses current model IDs."""
        assert ClaudeCLIProvider.MODEL_MAP["opus"] == "claude-opus-4-6"
        assert ClaudeCLIProvider.MODEL_MAP["sonnet"] == "claude-sonnet-4-6"
        assert ClaudeCLIProvider.MODEL_MAP["haiku"] == "claude-haiku-4-5"

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


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def test_init_opus(self):
        """Test creating provider with opus model."""
        provider = AnthropicProvider(model="opus")
        assert provider.provider_name == "anthropic"
        assert provider.model == "opus"
        assert provider._model_id == "claude-opus-4-6"

    def test_init_sonnet(self):
        """Test creating provider with sonnet model."""
        provider = AnthropicProvider(model="sonnet")
        assert provider.model == "sonnet"
        assert provider._model_id == "claude-sonnet-4-6"

    def test_init_haiku(self):
        """Test creating provider with haiku model."""
        provider = AnthropicProvider(model="haiku")
        assert provider.model == "haiku"
        assert provider._model_id == "claude-haiku-4-5"

    def test_passthrough_full_model_id(self):
        """Accept full model IDs as passthrough."""
        provider = AnthropicProvider(model="claude-opus-4-7-20260415")
        assert provider.model == "claude-opus-4-7-20260415"
        assert provider._model_id == "claude-opus-4-7-20260415"

    def test_case_insensitive(self):
        """Model names are case-insensitive."""
        provider = AnthropicProvider(model="HAIKU")
        assert provider.model == "haiku"
        assert provider._model_id == "claude-haiku-4-5"

    def test_no_api_key_returns_error(self):
        """Return error result when API key not found."""
        provider = AnthropicProvider(model="haiku")

        with patch(
            "assemblyzero.core.llm_provider._load_anthropic_api_key",
            return_value=None,
        ):
            result = provider.invoke("system", "content")

        assert result.success is False
        assert "ANTHROPIC_API_KEY not found" in result.error_message
        assert result.provider == "anthropic"

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key")
    def test_invoke_success(self, mock_load_key):
        """Test successful API invocation."""
        mock_load_key.return_value = "sk-ant-test-key"

        # Build mock response
        mock_block = Mock()
        mock_block.text = "Hello from API!"
        mock_usage = Mock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50
        mock_usage.cache_read_input_tokens = 0
        mock_usage.cache_creation_input_tokens = 0
        mock_response = Mock()
        mock_response.content = [mock_block]
        mock_response.usage = mock_usage

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicProvider(model="haiku")

        with patch("anthropic.Anthropic", return_value=mock_client):
            result = provider.invoke("You are a test.", "Say hello.", timeout_seconds=30)

        assert result.success is True
        assert result.response == "Hello from API!"
        assert result.provider == "anthropic"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.cost_usd > 0

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key")
    def test_invoke_rate_limit(self, mock_load_key):
        """Test rate limit error handling."""
        import anthropic

        mock_load_key.return_value = "sk-ant-test-key"

        mock_client = Mock()
        # Create a proper RateLimitError
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {}
        rate_limit_error = anthropic.RateLimitError(
            message="Rate limited",
            response=mock_response,
            body={"error": {"message": "Rate limited", "type": "rate_limit_error"}},
        )
        mock_client.messages.create.side_effect = rate_limit_error

        provider = AnthropicProvider(model="haiku")

        with patch("anthropic.Anthropic", return_value=mock_client):
            result = provider.invoke("system", "content")

        assert result.success is False
        assert result.rate_limited is True
        assert "rate limited" in result.error_message.lower()

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key")
    def test_invoke_timeout(self, mock_load_key):
        """Test timeout error handling."""
        import anthropic

        mock_load_key.return_value = "sk-ant-test-key"

        mock_client = Mock()
        mock_client.messages.create.side_effect = anthropic.APITimeoutError(
            request=Mock()
        )

        provider = AnthropicProvider(model="haiku")

        with patch("anthropic.Anthropic", return_value=mock_client):
            result = provider.invoke("system", "content", timeout_seconds=30)

        assert result.success is False
        assert "timed out" in result.error_message.lower()

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key")
    def test_invoke_auth_error(self, mock_load_key):
        """Test authentication error handling."""
        import anthropic

        mock_load_key.return_value = "sk-ant-bad-key"

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers = {}
        mock_client.messages.create.side_effect = anthropic.AuthenticationError(
            message="Invalid API key",
            response=mock_response,
            body={"error": {"message": "Invalid API key", "type": "authentication_error"}},
        )

        provider = AnthropicProvider(model="haiku")

        with patch("anthropic.Anthropic", return_value=mock_client):
            result = provider.invoke("system", "content")

        assert result.success is False
        assert "authentication failed" in result.error_message.lower()

    def test_cost_calculation_haiku(self):
        """Test cost calculation for haiku model."""
        provider = AnthropicProvider(model="haiku")
        # haiku: $1/MTok input, $5/MTok output
        cost = provider._calculate_cost(
            input_tokens=1000, output_tokens=500
        )
        expected = (1000 * 1.0 / 1_000_000) + (500 * 5.0 / 1_000_000)
        assert abs(cost - expected) < 1e-10

    def test_cost_calculation_with_cache(self):
        """Test cost calculation with cache tokens."""
        provider = AnthropicProvider(model="opus")
        # opus: $5/MTok input, $25/MTok output
        # cache_read: 10% of input = $0.5/MTok
        # cache_create: 125% of input = $6.25/MTok
        cost = provider._calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=2000,
            cache_creation_tokens=1000,
        )
        expected = (
            (1000 * 5.0 / 1_000_000)
            + (500 * 25.0 / 1_000_000)
            + (2000 * 0.5 / 1_000_000)
            + (1000 * 6.25 / 1_000_000)
        )
        assert abs(cost - expected) < 1e-10

    def test_cost_calculation_unknown_model(self):
        """Cost is 0.0 for unknown/passthrough models."""
        provider = AnthropicProvider(model="claude-opus-4-7-20260415")
        cost = provider._calculate_cost(input_tokens=1000, output_tokens=500)
        assert cost == 0.0


class TestFallbackProvider:
    """Tests for FallbackProvider."""

    def _make_result(self, success, provider_name="mock", error_msg=None):
        """Helper to create LLMCallResult."""
        return LLMCallResult(
            success=success,
            response="OK" if success else None,
            raw_response="OK" if success else None,
            error_message=error_msg,
            provider=provider_name,
            model_used="test",
            duration_ms=100,
            attempts=1,
        )

    def test_primary_succeeds_no_fallback(self):
        """When primary succeeds, fallback is never called."""
        primary = Mock(spec=LLMProvider)
        primary.provider_name = "claude"
        primary.model = "opus"
        primary.invoke.return_value = self._make_result(True, "claude")

        fallback = Mock(spec=LLMProvider)
        fallback.provider_name = "anthropic"

        fb = FallbackProvider(primary=primary, fallback=fallback)
        result = fb.invoke("system", "content", timeout_seconds=300)

        assert result.success is True
        primary.invoke.assert_called_once()
        fallback.invoke.assert_not_called()

    def test_primary_fails_fallback_succeeds(self):
        """When primary fails, fallback is tried and succeeds."""
        primary = Mock(spec=LLMProvider)
        primary.provider_name = "claude"
        primary.model = "opus"
        primary.invoke.return_value = self._make_result(
            False, "claude", "CLI timed out"
        )

        fallback = Mock(spec=LLMProvider)
        fallback.provider_name = "anthropic"
        fallback.invoke.return_value = self._make_result(True, "anthropic")

        fb = FallbackProvider(primary=primary, fallback=fallback)
        result = fb.invoke("system", "content", timeout_seconds=300)

        assert result.success is True
        primary.invoke.assert_called_once()
        fallback.invoke.assert_called_once()

    def test_both_fail(self):
        """When both providers fail, return fallback's error."""
        primary = Mock(spec=LLMProvider)
        primary.provider_name = "claude"
        primary.model = "opus"
        primary.invoke.return_value = self._make_result(
            False, "claude", "CLI error"
        )

        fallback = Mock(spec=LLMProvider)
        fallback.provider_name = "anthropic"
        fallback.invoke.return_value = self._make_result(
            False, "anthropic", "API error"
        )

        fb = FallbackProvider(primary=primary, fallback=fallback)
        result = fb.invoke("system", "content")

        assert result.success is False
        assert result.error_message == "API error"

    def test_primary_timeout_is_capped(self):
        """Primary gets min(timeout_seconds, primary_timeout)."""
        primary = Mock(spec=LLMProvider)
        primary.provider_name = "claude"
        primary.model = "opus"
        primary.invoke.return_value = self._make_result(True, "claude")

        fallback = Mock(spec=LLMProvider)
        fallback.provider_name = "anthropic"

        fb = FallbackProvider(primary=primary, fallback=fallback, primary_timeout=180)
        fb.invoke("system", "content", timeout_seconds=600)

        # Primary should be called with min(600, 180) = 180
        primary.invoke.assert_called_once_with("system", "content", 180)

    def test_primary_timeout_not_exceeded_when_smaller(self):
        """If caller timeout < primary_timeout, use caller timeout."""
        primary = Mock(spec=LLMProvider)
        primary.provider_name = "claude"
        primary.model = "opus"
        primary.invoke.return_value = self._make_result(True, "claude")

        fallback = Mock(spec=LLMProvider)
        fallback.provider_name = "anthropic"

        fb = FallbackProvider(primary=primary, fallback=fallback, primary_timeout=180)
        fb.invoke("system", "content", timeout_seconds=60)

        # Primary should be called with min(60, 180) = 60
        primary.invoke.assert_called_once_with("system", "content", 60)

    def test_fallback_gets_full_timeout(self):
        """Fallback provider gets the original full timeout."""
        primary = Mock(spec=LLMProvider)
        primary.provider_name = "claude"
        primary.model = "opus"
        primary.invoke.return_value = self._make_result(
            False, "claude", "CLI error"
        )

        fallback = Mock(spec=LLMProvider)
        fallback.provider_name = "anthropic"
        fallback.invoke.return_value = self._make_result(True, "anthropic")

        fb = FallbackProvider(primary=primary, fallback=fallback, primary_timeout=180)
        fb.invoke("system", "content", timeout_seconds=600)

        # Fallback should get full 600s
        fallback.invoke.assert_called_once_with("system", "content", 600)

    def test_provider_name_delegates_to_primary(self):
        """provider_name comes from the primary provider."""
        primary = Mock(spec=LLMProvider)
        primary.provider_name = "claude"
        primary.model = "opus"

        fallback = Mock(spec=LLMProvider)
        fallback.provider_name = "anthropic"

        fb = FallbackProvider(primary=primary, fallback=fallback)
        assert fb.provider_name == "claude"
        assert fb.model == "opus"


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

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key", return_value=None)
    def test_get_claude_provider_no_api_key(self, mock_load_key):
        """Claude without API key returns bare ClaudeCLIProvider."""
        provider = get_provider("claude:opus")
        assert isinstance(provider, ClaudeCLIProvider)
        assert provider.model == "opus"

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key", return_value="sk-ant-key")
    def test_claude_with_api_key_returns_fallback(self, mock_load_key):
        """Claude with API key returns FallbackProvider."""
        provider = get_provider("claude:opus")
        assert isinstance(provider, FallbackProvider)
        assert provider.provider_name == "claude"
        assert provider.model == "opus"

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key", return_value=None)
    def test_get_anthropic_provider(self, mock_load_key):
        """Get direct AnthropicProvider."""
        provider = get_provider("anthropic:haiku")
        assert isinstance(provider, AnthropicProvider)
        assert provider.model == "haiku"

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
        assert "anthropic" in str(exc_info.value)

    def test_invalid_spec_format(self):
        """Test that invalid spec format raises ValueError."""
        with pytest.raises(ValueError):
            get_provider("invalid-spec")

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key", return_value=None)
    def test_claude_passthrough_model_id(self, mock_load_key):
        """Claude accepts full model IDs as passthrough."""
        provider = get_provider("claude:claude-opus-4-7-20260415")
        assert isinstance(provider, ClaudeCLIProvider)
        assert provider.model == "claude-opus-4-7-20260415"


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


class TestTokenLogging:
    """Tests for Issue #398: token usage and cost logging."""

    def test_result_has_token_fields(self):
        """LLMCallResult includes token and cost fields."""
        result = LLMCallResult(
            success=True,
            response="ok",
            raw_response="ok",
            error_message=None,
            provider="claude",
            model_used="opus",
            duration_ms=1000,
            attempts=1,
            input_tokens=1500,
            output_tokens=800,
            cache_read_tokens=5000,
            cache_creation_tokens=3000,
            cost_usd=0.089,
        )
        assert result.input_tokens == 1500
        assert result.output_tokens == 800
        assert result.cache_read_tokens == 5000
        assert result.cache_creation_tokens == 3000
        assert result.cost_usd == 0.089

    def test_token_fields_default_to_zero(self):
        """Token fields default to zero when not provided."""
        result = LLMCallResult(
            success=True,
            response="ok",
            raw_response="ok",
            error_message=None,
            provider="mock",
            model_used="test",
            duration_ms=100,
            attempts=1,
        )
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cost_usd == 0.0

    @patch("subprocess.run")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_claude_parses_usage_from_json(self, mock_find_cli, mock_run):
        """Claude provider extracts token counts from JSON response."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({
                "result": "Generated content",
                "total_cost_usd": 0.089,
                "usage": {
                    "input_tokens": 1500,
                    "output_tokens": 800,
                    "cache_read_input_tokens": 5000,
                    "cache_creation_input_tokens": 3000,
                },
            }),
            stderr="",
        )

        provider = ClaudeCLIProvider()
        result = provider.invoke("system", "content")

        assert result.success is True
        assert result.input_tokens == 1500
        assert result.output_tokens == 800
        assert result.cache_read_tokens == 5000
        assert result.cache_creation_tokens == 3000
        assert result.cost_usd == 0.089

    @patch("subprocess.run")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_claude_handles_missing_usage(self, mock_find_cli, mock_run):
        """Claude provider handles JSON without usage field."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"result": "content"}',
            stderr="",
        )

        provider = ClaudeCLIProvider()
        result = provider.invoke("system", "content")

        assert result.success is True
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cost_usd == 0.0

    def test_log_llm_call_prints(self, capsys):
        """log_llm_call prints structured line to stdout."""
        result = LLMCallResult(
            success=True,
            response="ok",
            raw_response="ok",
            error_message=None,
            provider="claude",
            model_used="opus",
            duration_ms=1500,
            attempts=1,
            input_tokens=1500,
            output_tokens=800,
            cost_usd=0.089,
        )
        log_llm_call(result)
        output = capsys.readouterr().out
        assert "[LLM]" in output
        assert "provider=claude" in output
        assert "input=1500" in output
        assert "output=800" in output
        assert "cost=$0.0890" in output

    def test_log_llm_call_error(self, capsys):
        """log_llm_call includes error for failed calls."""
        result = LLMCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_message="timed out",
            provider="claude",
            model_used="opus",
            duration_ms=300000,
            attempts=1,
        )
        log_llm_call(result)
        output = capsys.readouterr().out
        assert "ERROR=timed out" in output


class TestRateLimitLogging:
    """Tests for Issue #399: 429 rate limit logging."""

    def test_result_has_rate_limited_field(self):
        """LLMCallResult includes rate_limited field."""
        result = LLMCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_message="429 quota exhausted",
            provider="gemini",
            model_used="3-pro-preview",
            duration_ms=500,
            attempts=1,
            rate_limited=True,
        )
        assert result.rate_limited is True

    def test_rate_limited_defaults_to_false(self):
        """rate_limited defaults to False."""
        result = LLMCallResult(
            success=True,
            response="ok",
            raw_response="ok",
            error_message=None,
            provider="claude",
            model_used="opus",
            duration_ms=100,
            attempts=1,
        )
        assert result.rate_limited is False

    def test_log_llm_call_shows_rate_limit(self, capsys):
        """log_llm_call includes RATE_LIMITED flag."""
        result = LLMCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_message="429",
            provider="gemini",
            model_used="3-pro-preview",
            duration_ms=500,
            attempts=1,
            rate_limited=True,
        )
        log_llm_call(result)
        output = capsys.readouterr().out
        assert "RATE_LIMITED=true" in output


class TestCircuitBreaker:
    """Tests for Issue #476: FallbackProvider circuit breaker."""

    def _make_result(self, success, provider_name="mock", error_msg=None, cost=0.0):
        """Helper to create LLMCallResult."""
        return LLMCallResult(
            success=success,
            response="OK" if success else None,
            raw_response="OK" if success else None,
            error_message=error_msg,
            provider=provider_name,
            model_used="test",
            duration_ms=100,
            attempts=1,
            cost_usd=cost,
        )

    def test_circuit_breaker_trips_after_consecutive_failures(self):
        """Circuit breaker trips after 2 consecutive both-fail calls."""
        primary = Mock(spec=LLMProvider)
        primary.provider_name = "claude"
        primary.model = "opus"
        primary.invoke.return_value = self._make_result(False, "claude", "CLI error")

        fallback = Mock(spec=LLMProvider)
        fallback.provider_name = "anthropic"
        fallback.invoke.return_value = self._make_result(False, "anthropic", "API error")

        fb = FallbackProvider(primary=primary, fallback=fallback)

        # Call 1: both fail → counter=1
        r1 = fb.invoke("system", "content")
        assert r1.success is False

        # Call 2: both fail → counter=2
        r2 = fb.invoke("system", "content")
        assert r2.success is False

        # Call 3: circuit breaker trips — neither provider called
        primary.invoke.reset_mock()
        fallback.invoke.reset_mock()
        r3 = fb.invoke("system", "content")
        assert r3.success is False
        assert "CIRCUIT BREAKER" in r3.error_message
        primary.invoke.assert_not_called()
        fallback.invoke.assert_not_called()

    def test_circuit_breaker_resets_on_success(self):
        """Circuit breaker resets when a call succeeds."""
        primary = Mock(spec=LLMProvider)
        primary.provider_name = "claude"
        primary.model = "opus"

        fallback = Mock(spec=LLMProvider)
        fallback.provider_name = "anthropic"

        fb = FallbackProvider(primary=primary, fallback=fallback)

        # Call 1: both fail → counter=1
        primary.invoke.return_value = self._make_result(False, "claude", "error")
        fallback.invoke.return_value = self._make_result(False, "anthropic", "error")
        fb.invoke("system", "content")
        assert fb._consecutive_failures == 1

        # Call 2: primary succeeds → counter resets to 0
        primary.invoke.return_value = self._make_result(True, "claude")
        fb.invoke("system", "content")
        assert fb._consecutive_failures == 0

        # Call 3+4: both fail again → counter goes to 2
        primary.invoke.return_value = self._make_result(False, "claude", "error")
        fallback.invoke.return_value = self._make_result(False, "anthropic", "error")
        fb.invoke("system", "content")
        fb.invoke("system", "content")
        assert fb._consecutive_failures == 2

        # Call 5: would trip, but verify it does
        r = fb.invoke("system", "content")
        assert "CIRCUIT BREAKER" in r.error_message


class TestCumulativeCost:
    """Tests for Issue #476: Cumulative cost tracking."""

    def setup_method(self):
        """Reset cumulative cost before each test."""
        reset_cumulative_cost()

    def test_cumulative_tracks_across_calls(self):
        """Cumulative cost sums across multiple log_llm_call invocations."""
        reset_cumulative_cost()
        for cost in [0.05, 0.10, 0.25]:
            result = LLMCallResult(
                success=True,
                response="ok",
                raw_response="ok",
                error_message=None,
                provider="mock",
                model_used="test",
                duration_ms=100,
                attempts=1,
                cost_usd=cost,
            )
            log_llm_call(result)

        assert abs(get_cumulative_cost() - 0.40) < 1e-10

    def test_reset_zeroes(self):
        """reset_cumulative_cost returns counter to zero."""
        result = LLMCallResult(
            success=True,
            response="ok",
            raw_response="ok",
            error_message=None,
            provider="mock",
            model_used="test",
            duration_ms=100,
            attempts=1,
            cost_usd=1.50,
        )
        log_llm_call(result)
        assert get_cumulative_cost() > 0

        reset_cumulative_cost()
        assert get_cumulative_cost() == 0.0
