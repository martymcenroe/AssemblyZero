"""Unit tests for LLM Provider abstraction.

Issue #101: Unified Governance Workflow
#2864: the paid Anthropic API path is removed

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
from unittest.mock import Mock, patch
import json
from pathlib import Path

from assemblyzero.core.llm_provider import (
    LLMCallResult,
    LLMProvider,
    ClaudeCLIProvider,
    GeminiProvider,
    MockProvider,
    get_cumulative_cost,
    get_provider,
    is_non_retryable_error,
    log_llm_call,
    parse_provider_spec,
    reset_cumulative_cost,
)


def _stream_proc(payload: str = "", stderr: str = "", returncode: int = 0, pid: int = 12345):
    """Shape a mock Popen the way the #2405 streaming transport reads it.

    Before #2405 the transport called ``proc.communicate()`` and parsed one
    buffered JSON object. It now reads NDJSON events off ``proc.stdout`` so it
    can tell a working call from a hung one, and takes its payload from the
    final ``result`` event. `payload` is the same JSON object the old mocks
    handed to ``communicate``, delivered where the new transport looks for it.

    Pass ``payload=""`` for a call that produced no usable output, which is what
    an error path looks like.
    """
    proc = Mock()
    proc.pid = pid
    lines = []
    if payload:
        event = json.loads(payload)
        event.setdefault("type", "result")
        lines.append(json.dumps(event))
    proc.stdout = iter(lines)
    proc.stderr = Mock()
    proc.stderr.read.return_value = stderr
    proc.stdin = Mock()
    proc.poll.return_value = returncode
    proc.returncode = returncode
    return proc


def _hanging_proc(pid: int = 12345):
    """A mock Popen that never exits and never produces output.

    ``poll()`` returning None forever is what a hung `claude -p` looks like to
    the watchdog. Tests using this must shrink the idle threshold, or they wait
    the full production two minutes.
    """
    proc = Mock()
    proc.pid = pid
    proc.stdout = iter(())
    proc.stderr = Mock()
    proc.stderr.read.return_value = ""
    proc.stdin = Mock()
    proc.poll.return_value = None
    proc.returncode = None
    return proc


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

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_invoke_success(self, mock_find_cli, mock_popen):
        """Test successful invocation."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc('{"result": "Generated content"}')
        mock_popen.return_value = mock_proc

        provider = ClaudeCLIProvider()
        result = provider.invoke(
            system_prompt="You are a helpful assistant",
            content="Hello!",
        )

        assert result.success is True
        assert result.response == "Generated content"
        assert result.provider == "claude"

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_invoke_failure(self, mock_find_cli, mock_popen):
        """Test invocation failure."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc("", stderr="Authentication failed", returncode=1)
        mock_popen.return_value = mock_proc

        provider = ClaudeCLIProvider()
        result = provider.invoke(
            system_prompt="Test",
            content="Test",
        )

        assert result.success is False
        assert "failed" in result.error_message.lower()

    @patch("assemblyzero.core.llm_provider._kill_process_tree")
    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_invoke_timeout(self, mock_find_cli, mock_popen, mock_kill, monkeypatch):
        """A hung call is killed process-tree-wise on Windows.

        #2405: the kill now fires on silence rather than on elapsed time, so the
        process is one that never exits and never speaks. The threshold is
        shrunk to a second so the test does not wait the production two minutes.
        """
        monkeypatch.setenv("AZ_LLM_IDLE_TIMEOUT", "1")
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _hanging_proc(pid=12345)
        mock_popen.return_value = mock_proc

        provider = ClaudeCLIProvider()
        result = provider.invoke(
            system_prompt="Test",
            content="Test",
            timeout_seconds=300,
        )

        assert result.success is False
        # The literal substring is a contract: analyze_requirements._is_timeout
        # classifies timeouts by matching it.
        assert "timed out" in result.error_message.lower()
        assert "no output" in result.error_message.lower()
        mock_kill.assert_called_once_with(12345)

    @patch("assemblyzero.core.llm_provider._kill_process_tree")
    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_timeout_messages_keep_the_substring_other_code_matches_on(
        self, mock_find_cli, mock_popen, mock_kill, monkeypatch
    ):
        """#2405: `_is_timeout` keys off "timed out", so both branches must say it.

        This coupling is invisible from either side. The provider returns a
        result object rather than raising, so the requirements gate classifies
        by substring; a reworded message would silently stop being recognised
        as a timeout and would be retried as though it were a content failure.
        """
        from assemblyzero.workflows.requirements.nodes.analyze_requirements import (
            _is_timeout,
        )

        monkeypatch.setenv("AZ_LLM_IDLE_TIMEOUT", "1")
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_popen.return_value = _hanging_proc()

        provider = ClaudeCLIProvider()
        idle_result = provider.invoke("Test", "Test", timeout_seconds=300)
        assert _is_timeout(idle_result), idle_result.error_message

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_small_system_prompt_uses_cli_arg(self, mock_find_cli, mock_popen):
        """Issue #787: System prompt under limit uses --system-prompt CLI arg."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc('{"result": "OK"}')
        mock_popen.return_value = mock_proc

        small_prompt = "You are a helpful assistant"
        provider = ClaudeCLIProvider()
        provider.invoke(system_prompt=small_prompt, content="Hello")

        cmd = mock_popen.call_args[0][0]
        assert "--system-prompt" in cmd
        assert small_prompt in cmd
        # cwd should be None (inherit parent)
        assert mock_popen.call_args[1].get("cwd") is None

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_large_system_prompt_uses_tempdir(self, mock_find_cli, mock_popen):
        """Issue #787: System prompt over limit writes CLAUDE.md to temp dir."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc('{"result": "OK"}')
        mock_popen.return_value = mock_proc

        large_prompt = "x" * (ClaudeCLIProvider.SYSTEM_PROMPT_CLI_LIMIT + 1)
        provider = ClaudeCLIProvider()
        provider.invoke(system_prompt=large_prompt, content="Hello")

        cmd = mock_popen.call_args[0][0]
        # --system-prompt should NOT be in cmd
        assert "--system-prompt" not in cmd
        # --setting-sources should be "user,project"
        idx = cmd.index("--setting-sources")
        assert cmd[idx + 1] == "user,project"
        # cwd should be set to a temp dir path (not None)
        cwd = mock_popen.call_args[1].get("cwd")
        assert cwd is not None

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_tempdir_cleanup_after_invoke(self, mock_find_cli, mock_popen):
        """Issue #787: Temp dir is cleaned up after invoke returns."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc('{"result": "OK"}')
        mock_popen.return_value = mock_proc

        large_prompt = "x" * (ClaudeCLIProvider.SYSTEM_PROMPT_CLI_LIMIT + 1)
        provider = ClaudeCLIProvider()
        result = provider.invoke(system_prompt=large_prompt, content="Hello")

        assert result.success is True
        # The temp dir that was used as cwd should be cleaned up
        cwd = mock_popen.call_args[1].get("cwd")
        assert not Path(cwd).exists()


class TestGeminiProvider:
    """Tests for GeminiProvider."""

    def test_valid_model_pro(self):
        """Test creating provider with pro model."""
        provider = GeminiProvider(model="2.5-pro")
        assert provider.provider_name == "gemini"
        assert provider.model == "2.5-pro"

    @pytest.mark.parametrize("alias", ["flash", "2.5-flash", "3.1-flash-preview"])
    def test_flash_aliases_are_refused(self, alias):
        """#3710: the Flash aliases named dead ids, one of them forbidden."""
        with pytest.raises(ValueError, match="Unknown Gemini model"):
            GeminiProvider(model=alias)

    @pytest.mark.parametrize("alias", ["2.5-pro", "pro"])
    def test_legacy_pro_aliases_resolve_to_living_id(self, alias):
        """#3710: gemini-2.5-pro is gone from agy; the aliases remap as #1764 did."""
        assert GeminiProvider.MODEL_MAP[alias] == "gemini-3.8-flash-high"

    def test_every_map_value_is_an_id_agy_serves(self):
        """#3710: one declared set of living ids, and the map stays inside it."""
        from assemblyzero.core.config import AGY_GEMINI_MODELS

        assert set(GeminiProvider.MODEL_MAP.values()) <= AGY_GEMINI_MODELS

    def test_no_map_value_is_forbidden(self):
        """#3710: no alias may resolve to a FORBIDDEN_MODELS id."""
        from assemblyzero.core.config import FORBIDDEN_MODELS

        assert set(GeminiProvider.MODEL_MAP.values()) & set(FORBIDDEN_MODELS) == set()

    def test_valid_model_3_pro_preview(self):
        """Test creating provider with 3.1-pro-preview model."""
        provider = GeminiProvider(model="3.1-pro-preview")
        assert provider.model == "3.1-pro-preview"

    def test_pro_aliases_resolve_to_living_catalog_ids(self):
        """#1764: agy retired the -preview IDs. Every Pro-line alias must
        resolve to a model the CLI actually serves (verified against
        `agy models` 2026-07-14) — a dead ID turns every pipeline LLM call
        into an error banner. #4178: the gemini-3.1-pro ids went the same
        way (read 2026-10-21) and Argon is forbidden, so the aliases remap
        to 3.8 Flash."""
        assert GeminiProvider.MODEL_MAP["3.1-pro-preview"] == "gemini-3.8-flash-high"
        assert GeminiProvider.MODEL_MAP["3.1-pro"] == "gemini-3.8-flash-high"
        assert GeminiProvider.MODEL_MAP["3.1-pro-high"] == "gemini-3.8-flash-high"
        assert GeminiProvider.MODEL_MAP["3.1-pro-low"] == "gemini-3.8-flash-low"

    def test_pro_preview_alias_maps_to_high_model_id(self):
        """The workflow default spec gemini:3.1-pro-preview must construct a
        provider whose resolved model ID is servable (#1764)."""
        provider = GeminiProvider(model="3.1-pro-preview")
        assert provider._model_id == "gemini-3.8-flash-high"

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

    def test_claude_spec_is_the_cli_provider_directly(self):
        """#2864: claude: is the subscription CLI and nothing wraps it."""
        provider = get_provider("claude:opus")
        assert type(provider) is ClaudeCLIProvider
        assert provider.model == "opus"

    def test_anthropic_spec_is_an_unknown_provider(self):
        """#2864: there is no paid API provider, so anthropic: cannot be built."""
        with pytest.raises(ValueError, match="Unknown provider 'anthropic'"):
            get_provider("anthropic:haiku")

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
        assert "Supported: claude, gemini, mock, scripted" in str(exc_info.value)

    def test_invalid_spec_format(self):
        """Test that invalid spec format raises ValueError."""
        with pytest.raises(ValueError):
            get_provider("invalid-spec")

    def test_claude_passthrough_model_id(self):
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

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_claude_parses_usage_from_json(self, mock_find_cli, mock_popen):
        """Claude provider extracts token counts from JSON response."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        json_stdout = json.dumps({
            "result": "Generated content",
            "total_cost_usd": 0.089,
            "usage": {
                "input_tokens": 1500,
                "output_tokens": 800,
                "cache_read_input_tokens": 5000,
                "cache_creation_input_tokens": 3000,
            },
        })
        mock_proc = _stream_proc(json_stdout)
        mock_popen.return_value = mock_proc

        provider = ClaudeCLIProvider()
        result = provider.invoke("system", "content")

        assert result.success is True
        assert result.input_tokens == 1500
        assert result.output_tokens == 800
        assert result.cache_read_tokens == 5000
        assert result.cache_creation_tokens == 3000
        assert result.cost_usd == 0.089

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_claude_handles_missing_usage(self, mock_find_cli, mock_popen):
        """Claude provider handles JSON without usage field."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc('{"result": "content"}')
        mock_popen.return_value = mock_proc

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
            model_used="3.1-pro-preview",
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
            model_used="3.1-pro-preview",
            duration_ms=500,
            attempts=1,
            rate_limited=True,
        )
        log_llm_call(result)
        output = capsys.readouterr().out
        assert "RATE_LIMITED=true" in output


class TestIsNonRetryableError:
    """Tests for Issue #516: Non-retryable error detection."""

    def test_billing_error(self):
        """Credit balance error is non-retryable."""
        assert is_non_retryable_error("Your credit balance is too low") is True

    def test_invalid_api_key(self):
        """Invalid API key is non-retryable."""
        assert is_non_retryable_error("invalid_api_key") is True
        assert is_non_retryable_error("Error: invalid api key provided") is True

    def test_authentication_error(self):
        """Authentication errors are non-retryable."""
        assert is_non_retryable_error("authentication_error") is True
        assert is_non_retryable_error("Authentication failed for account") is True

    def test_permission_denied(self):
        """Permission denied is non-retryable."""
        assert is_non_retryable_error("permission_denied") is True
        assert is_non_retryable_error("Permission denied for resource") is True

    def test_account_disabled(self):
        """Disabled account is non-retryable."""
        assert is_non_retryable_error("account has been disabled") is True

    def test_transient_errors_are_retryable(self):
        """Timeout, rate limit, and server errors are retryable."""
        assert is_non_retryable_error("Connection timed out") is False
        assert is_non_retryable_error("rate limit exceeded") is False
        assert is_non_retryable_error("Internal server error") is False
        assert is_non_retryable_error("503 Service Unavailable") is False

    def test_none_and_empty(self):
        """None and empty strings are retryable (not non-retryable)."""
        assert is_non_retryable_error(None) is False
        assert is_non_retryable_error("") is False

    def test_case_insensitive(self):
        """Detection is case-insensitive."""
        assert is_non_retryable_error("CREDIT BALANCE IS TOO LOW") is True
        assert is_non_retryable_error("Invalid_API_Key") is True


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


class TestEffortFlag:
    """Tests for Issue #773: --effort flag on ClaudeCLIProvider."""

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_effort_max_in_command(self, mock_find_cli, mock_popen):
        """--effort max appears in subprocess command."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc('{"result": "ok"}')
        mock_popen.return_value = mock_proc

        provider = ClaudeCLIProvider(model="opus", effort="max")
        provider.invoke("system", "content")

        cmd = mock_popen.call_args[0][0]
        assert "--effort" in cmd
        idx = cmd.index("--effort")
        assert cmd[idx + 1] == "max"

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_effort_none_omits_flag(self, mock_find_cli, mock_popen):
        """effort=None omits --effort from command."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc('{"result": "ok"}')
        mock_popen.return_value = mock_proc

        provider = ClaudeCLIProvider(model="opus")
        provider.invoke("system", "content")

        cmd = mock_popen.call_args[0][0]
        assert "--effort" not in cmd

    def test_effort_passed_through_get_provider(self):
        """get_provider passes effort kwarg to ClaudeCLIProvider."""
        provider = get_provider("claude:opus", effort="high")
        assert isinstance(provider, ClaudeCLIProvider)
        assert provider._effort == "high"


class TestResponseSchema:
    """Tests for Issue #773: response_schema on invoke()."""

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_json_schema_in_command_when_provided(self, mock_find_cli, mock_popen):
        """--json-schema appears in subprocess command when schema provided."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc('{"result": "ok"}')
        mock_popen.return_value = mock_proc

        schema = {"type": "object", "properties": {"verdict": {"type": "string"}}}
        provider = ClaudeCLIProvider(model="opus")
        provider.invoke("system", "content", response_schema=schema)

        cmd = mock_popen.call_args[0][0]
        assert "--json-schema" in cmd
        idx = cmd.index("--json-schema")
        parsed = json.loads(cmd[idx + 1])
        assert parsed == schema

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_json_schema_omitted_when_none(self, mock_find_cli, mock_popen):
        """--json-schema omitted when response_schema is None."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc('{"result": "ok"}')
        mock_popen.return_value = mock_proc

        provider = ClaudeCLIProvider(model="opus")
        provider.invoke("system", "content")

        cmd = mock_popen.call_args[0][0]
        assert "--json-schema" not in cmd

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_structured_output_extracted_when_schema_provided(self, mock_find_cli, mock_popen):
        """Issue #781: When --json-schema is used, response comes from structured_output, not result."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        # Real claude -p output when --json-schema is used:
        # result is empty, structured_output has the actual response
        mock_proc = _stream_proc(
            json.dumps({
                "result": "",
                "structured_output": {"verdict": "APPROVED", "feedback": []},
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "total_cost_usd": 0.01,
            })
        )
        mock_popen.return_value = mock_proc

        schema = {"type": "object", "properties": {"verdict": {"type": "string"}}}
        provider = ClaudeCLIProvider(model="opus")
        result = provider.invoke("system", "content", response_schema=schema)

        assert result.success is True
        parsed = json.loads(result.response)
        assert parsed["verdict"] == "APPROVED"

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_result_used_when_no_schema(self, mock_find_cli, mock_popen):
        """Without response_schema, response comes from result field as before."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_proc = _stream_proc(
            json.dumps({
                "result": "Hello world",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "total_cost_usd": 0.001,
            })
        )
        mock_popen.return_value = mock_proc

        provider = ClaudeCLIProvider(model="opus")
        result = provider.invoke("system", "content")

        assert result.success is True
        assert result.response == "Hello world"

    def test_mock_provider_accepts_response_schema(self):
        """MockProvider.invoke() accepts response_schema without error."""
        provider = MockProvider(model="test")
        result = provider.invoke("sys", "content", response_schema={"type": "object"})
        assert result.success is True

    def test_gemini_provider_accepts_response_schema(self):
        """GeminiProvider.invoke() accepts response_schema in signature."""
        import inspect
        sig = inspect.signature(GeminiProvider.invoke)
        assert "response_schema" in sig.parameters


class TestExtractTextFromStreamEvents:
    """Closes #1498. Claude CLI v2.1.x returns streaming-events JSON arrays
    on --output-format json. The provider must extract the actual response
    text from the events list (priority: result event -> assistant message
    -> raw stdout) instead of discarding the structure.
    """

    def test_extracts_from_result_event(self):
        from assemblyzero.core.llm_provider import _extract_text_from_stream_events
        events = [
            {"type": "system", "subtype": "init"},
            {"type": "result", "result": "```python\nprint('hi')\n```"},
        ]
        result = _extract_text_from_stream_events(events, raw_stdout="ignored")
        assert result == "```python\nprint('hi')\n```"

    def test_falls_back_to_assistant_message_text(self):
        from assemblyzero.core.llm_provider import _extract_text_from_stream_events
        events = [
            {"type": "system", "subtype": "init"},
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "asst-text-here"}]},
            },
            # no result event
        ]
        result = _extract_text_from_stream_events(events, raw_stdout="ignored")
        assert result == "asst-text-here"

    def test_result_event_takes_priority_over_assistant(self):
        from assemblyzero.core.llm_provider import _extract_text_from_stream_events
        events = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "asst"}]},
            },
            {"type": "result", "result": "canonical-result"},
        ]
        assert (
            _extract_text_from_stream_events(events, raw_stdout="ignored")
            == "canonical-result"
        )

    def test_no_extractable_event_gives_nothing_not_raw_stdout(self):
        """#3780: the raw stdout used to come back as the model's answer."""
        from assemblyzero.core.llm_provider import _extract_text_from_stream_events
        events = [
            {"type": "system", "subtype": "init"},
            {"type": "rate_limit_event"},
        ]
        result = _extract_text_from_stream_events(events, raw_stdout="raw-fallback")
        assert result == ""

    def test_non_list_gives_nothing_not_raw_stdout(self):
        from assemblyzero.core.llm_provider import _extract_text_from_stream_events
        # Defensive: only lists carry the streaming-events shape.
        result = _extract_text_from_stream_events(
            "not a list", raw_stdout="raw-fallback"
        )
        assert result == ""

    def test_smoke_build_iter05_repro(self):
        """Verbatim shape from Chiron iter05's 091-response-...md."""
        from assemblyzero.core.llm_provider import _extract_text_from_stream_events
        code = (
            "```python\n"
            "from dataclasses import dataclass\n"
            "\n"
            "@dataclass(frozen=True)\n"
            "class Citation:\n"
            "    document: str\n"
            "```"
        )
        events = [
            {"type": "system", "subtype": "init", "cwd": "/tmp"},
            {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}},
            {
                "type": "assistant",
                "message": {
                    "model": "claude-sonnet-4-6",
                    "content": [{"type": "text", "text": code}],
                },
            },
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": code,
            },
        ]
        result = _extract_text_from_stream_events(events, raw_stdout="ignored")
        assert "Citation" in result
        assert "```python" in result


class TestModuleLoggerDefined:
    """Regression for #1495. llm_provider used logger.warning at the
    #1431 defensive branch (non-dict JSON) but never imported logging or
    defined logger at module scope. Every code path that touched that
    branch raised NameError. The smoke-build empirical surface was the
    testing N4 (implement_code) halting impl.
    """

    def test_module_defines_logger(self):
        import assemblyzero.core.llm_provider as mod
        assert hasattr(mod, "logger"), (
            "llm_provider must define a module-level `logger` so the "
            "#1431 logger.warning branch does not NameError"
        )
        import logging
        assert isinstance(mod.logger, logging.Logger)

    def test_logger_name_matches_module(self):
        import assemblyzero.core.llm_provider as mod
        assert mod.logger.name == "assemblyzero.core.llm_provider"
