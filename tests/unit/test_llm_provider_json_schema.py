"""Tests for ClaudeCLIProvider json_schema kwarg.

Issue #775: Verify that ClaudeCLIProvider.invoke() correctly appends
--json-schema flag to CLI args when json_schema kwarg is provided.
"""

import json
from unittest.mock import MagicMock, patch

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
        # Given both, json_schema is the one used
        provider.invoke(
            "system", "prompt",
            response_schema={"type": "object"},
            json_schema=FEEDBACK_SCHEMA,
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--json-schema" in cmd


class TestOtherProvidersJsonSchema:
    """Tests that other providers accept json_schema kwarg without error."""

    def test_gemini_provider_accepts_json_schema(self):
        """GeminiProvider.invoke() accepts json_schema kwarg (delivered, #4483)."""
        from assemblyzero.core.llm_provider import GeminiProvider
        import inspect

        sig = inspect.signature(GeminiProvider.invoke)
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
