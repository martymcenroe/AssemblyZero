"""Tests for the Gemini client with rotation logic.

Test Scenarios from LLD:
- 090: 429 triggers rotation
- 100: 529 triggers backoff
- 110: All credentials exhausted
- 120: Model verification
- 130: Forbidden model rejected

Issue #605: Systemic Model Refresh — Gemini 3.1, Claude 4.6
"""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core.gemini_client import (
    GeminiClient,
    GeminiErrorType,
    _strip_ansi,
)


@pytest.fixture
def temp_credentials_file():
    """Create a temporary credentials file with OAuth credentials.

    #1605: api_key credentials are no longer loaded — governance is
    subscription/OAuth-only.  All fixture credentials are now type: oauth.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        creds_file = Path(tmpdir) / "credentials.json"
        creds_file.write_text(
            json.dumps(
                {
                    "credentials": [
                        {"name": "key-1", "enabled": True, "type": "oauth"},
                        {"name": "key-2", "enabled": True, "type": "oauth"},
                        {"name": "key-3", "enabled": True, "type": "oauth"},
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


    def test_130_forbidden_model_rejected_old_3_pro_ga(self):
        """Test that old gemini-3-pro is rejected after 3.1 refresh."""
        with pytest.raises(ValueError) as exc_info:
            GeminiClient(model="gemini-3-pro")

        assert "forbidden" in str(exc_info.value).lower()

    def test_valid_pro_model_accepted(self, temp_credentials_file, temp_state_file):
        """Test that Gemini 3.1 Pro model is accepted."""
        # Should not raise
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
        )
        assert client.model == "gemini-3.1-pro-preview"

    def test_non_gemini_model_rejected(self):
        """Test that non-Gemini models are rejected."""
        with pytest.raises(ValueError) as exc_info:
            GeminiClient(model="gpt-4")

        assert "not a valid Gemini model" in str(exc_info.value)

    def test_120_model_id_is_gemini_3_1(self, temp_credentials_file, temp_state_file):
        """T010: Verify Gemini 3.1 model ID is accepted (REQ-1)."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
        )
        assert "3.1" in client.model
        assert client.model == "gemini-3.1-pro-preview"




class TestInvokeViaStdin:
    """Every prompt rides stdin (#1772; the only path since #3624).

    `agy --model X` with no -p reads the prompt from stdin and prints to a
    plain pipe (verified live with a 39,954-char prompt). #1765: a CLI error
    banner must never be returned as model output -- hardening-run evidence
    had an 'Error: invalid --model' banner saved as a draft and carried
    through review and verdict as content.
    """

    def _client(self, temp_credentials_file, temp_state_file):
        client = GeminiClient(
            model="gemini-3.1-pro-high",
        )
        client._agy_cli = "/fake/agy"
        return client

    @staticmethod
    def _proc(stdout="", stderr="", returncode=0):
        """A Popen double. #1874 moved this path off subprocess.run, whose
        Windows timeout kills the root and then drains pipes unbounded."""
        proc = MagicMock()
        proc.pid = 4242
        proc.communicate.return_value = (stdout, stderr)
        proc.returncode = returncode
        return proc

    @patch("assemblyzero.core.gemini_client.subprocess.Popen")
    def test_oversize_prompt_routes_to_stdin_path(
        self, mock_popen, temp_credentials_file, temp_state_file
    ):
        """_invoke_via_cli must route >30K prompts to stdin — never reject
        them, never put them in argv."""
        proc = self._proc(stdout="A fine review.\n")
        mock_popen.return_value = proc
        client = self._client(temp_credentials_file, temp_state_file)

        big_content = "x" * 31000
        ok, text, err = client._invoke_via_cli("sys", big_content)

        assert ok is True
        assert "fine review" in text
        argv = mock_popen.call_args[0][0]
        assert "-p" not in argv, "oversize prompt must NOT ride argv"
        assert argv[0] == "/fake/agy"
        # #3612: the pipeline's own tool-less agent, then the model; no
        # --sandbox anywhere (#3608, #3605: it requested Windows elevation).
        assert argv[1:5] == ["--agent", "assemblyzero-text", "--model", "gemini-3.1-pro-high"]
        assert mock_popen.call_args[1]["cwd"], "stdin path keeps temp-cwd isolation"
        sent = proc.communicate.call_args[1]["input"]
        assert len(sent) > 31000  # full composed prompt on stdin

    @patch("assemblyzero.core.gemini_client.subprocess.Popen")
    def test_stdin_nonzero_exit_is_failure(
        self, mock_popen, temp_credentials_file, temp_state_file
    ):
        mock_popen.return_value = self._proc(
            stderr="Error: invalid --model", returncode=1
        )
        client = self._client(temp_credentials_file, temp_state_file)
        ok, text, err = client._invoke_via_stdin("p" * 31000)
        assert ok is False
        assert "agy exited 1" in err

    @patch("assemblyzero.core.gemini_client.subprocess.Popen")
    def test_stdin_error_banner_is_failure(
        self, mock_popen, temp_credentials_file, temp_state_file
    ):
        mock_popen.return_value = self._proc(stdout="Error: something odd\n")
        client = self._client(temp_credentials_file, temp_state_file)
        ok, text, err = client._invoke_via_stdin("p" * 31000)
        assert ok is False
        assert "agy error output" in err

    @patch("assemblyzero.core.gemini_client.subprocess.Popen")
    def test_short_prompt_rides_stdin_and_succeeds(
        self, mock_popen, temp_credentials_file, temp_state_file
    ):
        """#3624: a short prompt no longer takes a PTY path; it rides stdin."""
        proc = self._proc(stdout="## Draft\n\nA legitimate response.\n")
        mock_popen.return_value = proc
        client = self._client(temp_credentials_file, temp_state_file)
        ok, text, err = client._invoke_via_cli("sys", "content")
        assert ok is True and err == ""
        assert "legitimate response" in text
        assert "-p" not in mock_popen.call_args[0][0]
        assert "content" in proc.communicate.call_args[1]["input"]

    @patch("assemblyzero.core.gemini_client.subprocess.Popen")
    def test_ansi_is_stripped(self, mock_popen, temp_credentials_file, temp_state_file):
        mock_popen.return_value = self._proc(stdout='\x1b[32m{"verdict":"APPROVE"}\x1b[0m\r\n')
        client = self._client(temp_credentials_file, temp_state_file)
        ok, text, err = client._invoke_via_cli("sys", "content")
        assert ok is True and err == ""
        assert text == '{"verdict":"APPROVE"}'

    @patch("assemblyzero.core.gemini_client.subprocess.Popen")
    def test_empty_output_is_failure(self, mock_popen, temp_credentials_file, temp_state_file):
        mock_popen.return_value = self._proc(stdout="")
        client = self._client(temp_credentials_file, temp_state_file)
        ok, text, err = client._invoke_via_cli("sys", "content")
        assert ok is False and "no output" in err

    @patch("assemblyzero.core.gemini_client.subprocess.Popen")
    def test_agent_warning_on_stdout_is_failure(
        self, mock_popen, temp_credentials_file, temp_state_file
    ):
        """#3624: the removed PTY path saw both streams merged; stdin reads both."""
        mock_popen.return_value = self._proc(
            stdout="Warning: --agent assemblyzero-text not found\nI ran whoami\n"
        )
        client = self._client(temp_credentials_file, temp_state_file)
        ok, text, err = client._invoke_via_cli("sys", "content")
        assert ok is False and text == ""
        assert "did not run as assemblyzero-text" in err

    @patch("assemblyzero.core.gemini_client.kill_process_tree")
    @patch("assemblyzero.core.gemini_client.subprocess.Popen")
    def test_stdin_timeout_is_failure(
        self, mock_popen, mock_kill, temp_credentials_file, temp_state_file
    ):
        proc = self._proc()
        proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="agy", timeout=300
        )
        mock_popen.return_value = proc
        client = self._client(temp_credentials_file, temp_state_file)
        ok, text, err = client._invoke_via_stdin("p" * 31000)
        assert ok is False
        assert "timeout" in err.lower()
        # #1874: the whole tree dies, not just the root holding the pipes
        mock_kill.assert_called_once_with(4242)


class TestErrorClassification:
    """Tests for error classification."""

    def test_quota_exhausted_detection(self, temp_credentials_file, temp_state_file):
        """Test that 429/quota errors are classified correctly."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
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
            model="gemini-3.1-pro-preview",
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
            model="gemini-3.1-pro-preview",
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




class TestBackoffDelay:
    """Tests for backoff delay calculation."""

    def test_exponential_backoff(self, temp_credentials_file, temp_state_file):
        """Test that backoff delay is exponential."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
        )

        # Base is 2.0 seconds, exponential growth
        assert client._backoff_delay(0) == 2.0  # 2 * 2^0 = 2
        assert client._backoff_delay(1) == 4.0  # 2 * 2^1 = 4
        assert client._backoff_delay(2) == 8.0  # 2 * 2^2 = 8

    def test_backoff_max_cap(self, temp_credentials_file, temp_state_file):
        """Test that backoff is capped at maximum."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
        )

        # Should be capped at 60 seconds
        assert client._backoff_delay(10) == 60.0


class TestResetTimeParsing:
    """Tests for quota reset time parsing."""

    def test_parses_reset_time(self, temp_credentials_file, temp_state_file):
        """Test parsing of reset time from error message."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
        )

        result = client._parse_reset_time("Your quota will reset after 15h11m58s")
        assert result is not None
        assert abs(result - 15.2) < 0.1  # 15 hours + 11 minutes

    def test_returns_none_for_unparseable(self, temp_credentials_file, temp_state_file):
        """Test that unparseable messages return None."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
        )

        result = client._parse_reset_time("Some random error message")
        assert result is None


# ── Antigravity (agy) CLI transport (#1335) ──────────────────────────


def test_strip_ansi_removes_codes_and_normalizes_newlines():
    assert _strip_ansi("\x1b[32mOK\x1b[0m\r\n") == "OK\n"
    assert _strip_ansi("a\r\nb\r\n") == "a\nb\n"
    assert _strip_ansi("plain") == "plain"


def test_find_agy_cli_uses_path():
    # Off Windows only: on Windows agy is found inside WSL (#3623,
    # tests/unit/test_agy_wsl_transport.py).
    with patch("assemblyzero.core.gemini_client._ON_WINDOWS", False), \
         patch("assemblyzero.core.gemini_client.os.access", return_value=False), \
         patch("assemblyzero.core.gemini_client.shutil.which", return_value="/usr/bin/agy"):
        client = GeminiClient(model="gemini-3.1-pro-preview")
    assert client._agy_cli == "/usr/bin/agy"


def test_linux_agy_prefers_local_bin_over_path(tmp_path, monkeypatch):
    """#3651: ~/.local/bin/agy is found even when PATH lacks it (a non-login shell)."""
    from assemblyzero.core import gemini_client as gc

    agy = tmp_path / ".local" / "bin" / "agy"
    agy.parent.mkdir(parents=True)
    agy.write_text("#!/bin/sh\n")
    agy.chmod(0o755)
    monkeypatch.setattr(gc.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(gc.os, "access", lambda p, mode: True)
    monkeypatch.setattr(gc.shutil, "which", lambda name: None)
    assert gc._find_linux_agy() == str(agy)


def test_linux_agy_never_takes_a_windows_build(tmp_path, monkeypatch):
    from assemblyzero.core import gemini_client as gc

    monkeypatch.setattr(gc.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(gc.shutil, "which", lambda name: "/mnt/c/Users/x/AppData/Local/agy/bin/agy")
    assert gc._find_linux_agy() is None
    monkeypatch.setattr(gc.shutil, "which", lambda name: "/usr/bin/agy")
    assert gc._find_linux_agy() == "/usr/bin/agy"


def test_invoke_via_cli_agy_not_found():
    client = GeminiClient(model="gemini-3.1-pro-preview")
    client._agy_cli = None
    ok, resp, err = client._invoke_via_cli("sys", "content")
    assert ok is False and resp == "" and "not found" in err.lower()


def test_invoke_via_cli_routes_oversized_prompt_to_stdin():
    """#1772: oversize prompts are no longer rejected — they ride stdin.
    (Supersedes the pre-#1772 'too large' rejection this test used to pin.)"""
    client = GeminiClient(model="gemini-3.1-pro-preview")
    client._agy_cli = "agy"
    with patch.object(
        client, "_invoke_via_stdin", return_value=(True, "ok", "")
    ) as mock_stdin:
        ok, resp, err = client._invoke_via_cli("sys", "x" * 31000)
    assert ok is True and resp == "ok"
    mock_stdin.assert_called_once()
    assert len(mock_stdin.call_args[0][0]) > 31000  # full composed prompt


