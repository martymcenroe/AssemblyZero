"""Tests for ClaudeCLIProvider json_schema kwarg.

Issue #775: Verify that ClaudeCLIProvider.invoke() correctly appends
--json-schema flag to CLI args when json_schema kwarg is provided.
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from assemblyzero.core.verdict_schema import FEEDBACK_SCHEMA, VERDICT_SCHEMA


class TestClaudeCLIProviderJsonSchema:
    """Tests for json_schema kwarg in ClaudeCLIProvider.invoke()."""

    def _make_provider(self):
        from assemblyzero.core.llm_provider import ClaudeCLIProvider
        provider = ClaudeCLIProvider.__new__(ClaudeCLIProvider)
        provider._model_id = "claude-opus-4-6"
        provider._model = "opus"
        provider._effort = None
        return provider

    def _mock_popen(self, stdout_data):
        """Create a MagicMock that mimics subprocess.Popen behavior."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (stdout_data, "")
        mock_proc.returncode = 0
        return mock_proc

    @patch("subprocess.Popen")
    @patch("assemblyzero.core.llm_provider.ClaudeCLIProvider._find_cli")
    def test_json_schema_appended_to_cmd(self, mock_find_cli, mock_popen):
        """T070/test_080: CLI command includes --json-schema flag when json_schema provided."""
        mock_find_cli.return_value = "claude"
        stdout = json.dumps({"result": '{"verdict": "APPROVED", "rationale": "ok"}', "type": "result"})
        mock_popen.return_value = self._mock_popen(stdout)

        provider = self._make_provider()
        provider.invoke("system", "prompt", json_schema=FEEDBACK_SCHEMA)

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--json-schema" in cmd
        idx = cmd.index("--json-schema")
        assert cmd[idx + 1] == json.dumps(FEEDBACK_SCHEMA)

    @patch("subprocess.Popen")
    @patch("assemblyzero.core.llm_provider.ClaudeCLIProvider._find_cli")
    def test_no_json_schema_flag_when_none(self, mock_find_cli, mock_popen):
        """T080/test_090: CLI command does NOT include --json-schema when json_schema=None."""
        mock_find_cli.return_value = "claude"
        stdout = json.dumps({"result": "some response", "type": "result"})
        mock_popen.return_value = self._mock_popen(stdout)

        provider = self._make_provider()
        provider.invoke("system", "prompt", json_schema=None)

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--json-schema" not in cmd

    @patch("subprocess.Popen")
    @patch("assemblyzero.core.llm_provider.ClaudeCLIProvider._find_cli")
    def test_json_schema_serialized_correctly(self, mock_find_cli, mock_popen):
        """Schema dict is JSON-serialized and passed as string argument."""
        mock_find_cli.return_value = "claude"
        stdout = json.dumps({"result": "{}", "type": "result"})
        mock_popen.return_value = self._mock_popen(stdout)

        provider = self._make_provider()
        schema = {"type": "object", "properties": {"verdict": {"type": "string"}}}
        provider.invoke("system", "prompt", json_schema=schema)

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        idx = cmd.index("--json-schema")
        passed_schema_str = cmd[idx + 1]
        parsed_back = json.loads(passed_schema_str)
        assert parsed_back == schema

    @patch("subprocess.Popen")
    @patch("assemblyzero.core.llm_provider.ClaudeCLIProvider._find_cli")
    def test_verdict_schema_passed(self, mock_find_cli, mock_popen):
        """VERDICT_SCHEMA can be passed as json_schema without errors."""
        mock_find_cli.return_value = "claude"
        stdout = json.dumps({"result": '{"verdict": "REVISE", "rationale": "needs work"}', "type": "result"})
        mock_popen.return_value = self._mock_popen(stdout)

        provider = self._make_provider()
        provider.invoke("system", "prompt", json_schema=VERDICT_SCHEMA)

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--json-schema" in cmd

    @patch("subprocess.Popen")
    @patch("assemblyzero.core.llm_provider.ClaudeCLIProvider._find_cli")
    def test_json_schema_and_response_schema_coexist(self, mock_find_cli, mock_popen):
        """Both response_schema and json_schema can be passed; json_schema is used for CLI."""
        mock_find_cli.return_value = "claude"
        stdout = json.dumps({"result": "{}", "type": "result"})
        mock_popen.return_value = self._mock_popen(stdout)

        provider = self._make_provider()
        # response_schema is ignored for Claude CLI, json_schema is used
        provider.invoke(
            "system", "prompt",
            response_schema={"type": "object"},
            json_schema=FEEDBACK_SCHEMA,
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--json-schema" in cmd


class TestFallbackProviderJsonSchema:
    """Tests for json_schema kwarg passthrough in FallbackProvider."""

    def test_json_schema_passed_to_primary(self):
        """FallbackProvider passes json_schema kwarg to primary provider."""
        from assemblyzero.core.llm_provider import FallbackProvider

        mock_primary = MagicMock()
        mock_primary.invoke.return_value = MagicMock(content='{"verdict": "APPROVED"}')
        mock_fallback = MagicMock()

        provider = FallbackProvider.__new__(FallbackProvider)
        provider._primary = mock_primary
        provider._fallback = mock_fallback
        provider._primary_timeout = 300
        provider._breaker_key = "mock:test"
        provider._logger = MagicMock()

        provider.invoke("system", "prompt", json_schema=FEEDBACK_SCHEMA)

        mock_primary.invoke.assert_called_once()
        call_kwargs = mock_primary.invoke.call_args[1]
        assert "json_schema" in call_kwargs
        assert call_kwargs["json_schema"] == FEEDBACK_SCHEMA

    def test_json_schema_passed_to_fallback_on_primary_failure(self):
        """FallbackProvider passes json_schema to fallback when primary fails."""
        from assemblyzero.core.llm_provider import FallbackProvider

        mock_primary = MagicMock()
        mock_primary.provider_name = "claude"
        mock_primary.invoke.return_value = MagicMock(
            success=False, error_message="CLI error", content=""
        )
        mock_fallback = MagicMock()
        mock_fallback.provider_name = "anthropic"
        mock_fallback.invoke.return_value = MagicMock(
            success=True, content='{"verdict": "REVISE"}'
        )

        provider = FallbackProvider.__new__(FallbackProvider)
        provider._primary = mock_primary
        provider._fallback = mock_fallback
        provider._primary_timeout = 300
        provider._breaker_key = "mock:test"
        provider._logger = MagicMock()

        provider.invoke("system", "prompt", json_schema=FEEDBACK_SCHEMA)

        mock_fallback.invoke.assert_called_once()
        call_kwargs = mock_fallback.invoke.call_args[1]
        assert "json_schema" in call_kwargs
        assert call_kwargs["json_schema"] == FEEDBACK_SCHEMA


class TestOtherProvidersJsonSchema:
    """Tests that other providers accept json_schema kwarg without error."""

    def test_gemini_provider_accepts_json_schema(self):
        """GeminiProvider.invoke() accepts json_schema kwarg (ignores it, uses response_schema)."""
        from assemblyzero.core.llm_provider import GeminiProvider
        import inspect

        sig = inspect.signature(GeminiProvider.invoke)
        assert "json_schema" in sig.parameters

    def test_anthropic_provider_accepts_json_schema(self):
        """AnthropicProvider.invoke() accepts json_schema kwarg for interface compliance."""
        from assemblyzero.core.llm_provider import AnthropicProvider
        import inspect

        sig = inspect.signature(AnthropicProvider.invoke)
        assert "json_schema" in sig.parameters

    def test_mock_provider_accepts_json_schema(self):
        """MockProvider.invoke() accepts json_schema kwarg for interface compliance."""
        from assemblyzero.core.llm_provider import MockProvider
        import inspect

        sig = inspect.signature(MockProvider.invoke)
        assert "json_schema" in sig.parameters

    def test_claude_cli_provider_accepts_json_schema(self):
        """ClaudeCLIProvider.invoke() accepts json_schema kwarg."""
        from assemblyzero.core.llm_provider import ClaudeCLIProvider
        import inspect

        sig = inspect.signature(ClaudeCLIProvider.invoke)
        assert "json_schema" in sig.parameters

    def test_fallback_provider_accepts_json_schema(self):
        """FallbackProvider.invoke() accepts json_schema kwarg."""
        from assemblyzero.core.llm_provider import FallbackProvider
        import inspect

        sig = inspect.signature(FallbackProvider.invoke)
        assert "json_schema" in sig.parameters
