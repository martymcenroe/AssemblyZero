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
import sys
import tempfile
import types
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
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
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
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )
        assert "3.1" in client.model
        assert client.model == "gemini-3.1-pro-preview"


class TestCredentialLoading:
    """Tests for credential loading."""

    def test_loads_credentials_from_file(self, temp_credentials_file, temp_state_file):
        """Test that OAuth credentials are loaded from file.

        #1605: _load_credentials() now only loads type: oauth credentials.
        api_key credentials are silently skipped; key is always empty string.
        """
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        creds = client._load_credentials()
        assert len(creds) == 3
        assert creds[0].name == "key-1"
        assert creds[0].cred_type == "oauth"
        assert creds[0].key == ""  # OAuth credentials carry no API key

    def test_missing_credentials_file_raises(self, temp_state_file):
        """Test that missing credentials file raises FileNotFoundError."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=Path("/nonexistent/creds.json"),
            state_file=temp_state_file,
        )

        with pytest.raises(FileNotFoundError):
            client._load_credentials()


class _FakePty:
    """Minimal PtyProcess stand-in for _invoke_via_cli boundary tests (#1765)."""

    def __init__(self, chunks, exitstatus=0):
        self._chunks = list(chunks)
        self.exitstatus = exitstatus

    @classmethod
    def make_spawn(cls, chunks, exitstatus=0):
        instance = cls(chunks, exitstatus)
        spawner = MagicMock()
        spawner.spawn.return_value = instance
        return spawner, instance

    def read(self, n):
        if self._chunks:
            return self._chunks.pop(0)
        raise EOFError

    def isalive(self):
        return False

    def terminate(self, force=False):
        pass


class TestInvokeViaCliErrorBoundary:
    """#1765: CLI error banners must never be returned as model output.

    Hardening-run evidence: an 'Error: invalid --model' banner was saved as
    a draft and flowed through review and verdict as content.

    winpty is Windows-only and absent on the Linux CI runner, so these
    tests stub the whole module in sys.modules rather than patching into
    a real import.
    """

    @staticmethod
    def _patch_winpty(spawner):
        return patch.dict(
            sys.modules, {"winpty": types.SimpleNamespace(PtyProcess=spawner)}
        )

    def _client(self, temp_credentials_file, temp_state_file):
        return GeminiClient(
            model="gemini-3.1-pro-high",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

    def test_nonzero_exit_is_failure(self, temp_credentials_file, temp_state_file):
        client = self._client(temp_credentials_file, temp_state_file)
        banner = (
            'Error: invalid --model "gemini-3.1-pro-preview": model '
            "gemini-3.1-pro-preview is not recognized\nAvailable models:\n"
        )
        spawner, _ = _FakePty.make_spawn([banner], exitstatus=1)
        with self._patch_winpty(spawner):
            ok, text, err = client._invoke_via_cli("sys", "content")
        assert ok is False
        assert text == ""
        assert "agy exited 1" in err
        assert "invalid --model" in err

    def test_error_banner_with_clean_exit_is_failure(
        self, temp_credentials_file, temp_state_file
    ):
        """agy can print errors under a PTY with ambiguous status — the
        first-line 'Error:' shape alone must reject the output."""
        client = self._client(temp_credentials_file, temp_state_file)
        banner = "Error: something went sideways\ndetails...\n"
        spawner, _ = _FakePty.make_spawn([banner], exitstatus=0)
        with self._patch_winpty(spawner):
            ok, text, err = client._invoke_via_cli("sys", "content")
        assert ok is False
        assert text == ""
        assert "agy error output" in err

    def test_normal_output_still_succeeds(
        self, temp_credentials_file, temp_state_file
    ):
        client = self._client(temp_credentials_file, temp_state_file)
        spawner, _ = _FakePty.make_spawn(["## Draft\n\nA legitimate response.\n"])
        with self._patch_winpty(spawner):
            ok, text, err = client._invoke_via_cli("sys", "content")
        assert ok is True
        assert "legitimate response" in text
        assert err == ""

    def test_empty_output_is_failure(self, temp_credentials_file, temp_state_file):
        client = self._client(temp_credentials_file, temp_state_file)
        spawner, _ = _FakePty.make_spawn([""])
        with self._patch_winpty(spawner):
            ok, text, err = client._invoke_via_cli("sys", "content")
        assert ok is False
        assert "no output" in err


class TestErrorClassification:
    """Tests for error classification."""

    def test_quota_exhausted_detection(self, temp_credentials_file, temp_state_file):
        """Test that 429/quota errors are classified correctly."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
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
            model="gemini-3.1-pro-preview",
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
            model="gemini-3.1-pro-preview",
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
        """Test that 429 error causes rotation to next credential.

        #1605: the api_key/genai.Client path is gone.  Drive the rotation loop
        via _invoke_via_cli returning a 429-bearing error string so that
        classify_gemini_error → RateLimitError → QUOTA_EXHAUSTED → rotate.
        """
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        credentials_tried = []

        def mock_invoke_via_cli(system_instruction, content):
            # Count each _invoke_via_cli call — one per credential tried
            credentials_tried.append(len(credentials_tried))
            return (False, "", "429 TerminalQuotaError: exhausted")

        with patch.object(client, "_invoke_via_cli", side_effect=mock_invoke_via_cli):
            result = client.invoke("system", "content")

        # All 3 credentials should have been tried (rotation happened)
        assert len(credentials_tried) == 3

        # Result should indicate rotation occurred and overall failure
        assert result.rotation_occurred is True
        assert result.success is False

    def test_100_529_triggers_backoff(self, temp_credentials_file, temp_state_file):
        """Test that 529 error causes backoff retry on same credential.

        #1605: drive the backoff path via _invoke_via_cli returning a 529/capacity
        error string.  Succeed on the 3rd attempt so success=True, no rotation.
        """
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        attempts = [0]

        def mock_invoke_via_cli(system_instruction, content):
            attempts[0] += 1
            if attempts[0] < 3:
                return (False, "", "529 MODEL_CAPACITY_EXHAUSTED")
            # Succeed on 3rd attempt
            return (True, "Success", "")

        with patch.object(client, "_invoke_via_cli", side_effect=mock_invoke_via_cli), \
             patch("time.sleep"):  # Skip actual delay
            result = client.invoke("system", "content")

        # Should have retried 3 times on the same credential before succeeding
        assert attempts[0] == 3
        assert result.success is True
        assert result.rotation_occurred is False

    def test_110_all_credentials_exhausted(self, temp_credentials_file, temp_state_file):
        """Test behavior when all credentials are exhausted.

        #1605: drive the exhaustion path via _invoke_via_cli returning a quota
        error for every call so all three OAuth credentials get marked exhausted.
        """
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        def mock_invoke_via_cli(system_instruction, content):
            return (False, "", "429 TerminalQuotaError: exhausted")

        with patch.object(client, "_invoke_via_cli", side_effect=mock_invoke_via_cli):
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
            model="gemini-3.1-pro-preview",
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
            model="gemini-3.1-pro-preview",
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
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        result = client._parse_reset_time("Your quota will reset after 15h11m58s")
        assert result is not None
        assert abs(result - 15.2) < 0.1  # 15 hours + 11 minutes

    def test_returns_none_for_unparseable(self, temp_credentials_file, temp_state_file):
        """Test that unparseable messages return None."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        result = client._parse_reset_time("Some random error message")
        assert result is None


# ── Antigravity (agy) CLI transport (#1335) ──────────────────────────


class _FakeAgyProc:
    """Minimal pywinpty PtyProcess stand-in: replays chunks then EOFErrors."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.terminated = False

    def read(self, _size):
        if self._chunks:
            return self._chunks.pop(0)
        raise EOFError

    def isalive(self):
        return bool(self._chunks)

    def terminate(self, force=False):
        self.terminated = True


def _fake_winpty(chunks):
    """A fake `winpty` module whose PtyProcess.spawn yields the given chunks.

    Lets the agy pseudo-console path be tested without real pywinpty (so the
    tests run on Linux CI, where winpty is not installed).
    """
    mod = types.ModuleType("winpty")
    mod.PtyProcess = MagicMock()
    mod.PtyProcess.spawn.return_value = _FakeAgyProc(chunks)
    return mod


def test_strip_ansi_removes_codes_and_normalizes_newlines():
    assert _strip_ansi("\x1b[32mOK\x1b[0m\r\n") == "OK\n"
    assert _strip_ansi("a\r\nb\r\n") == "a\nb\n"
    assert _strip_ansi("plain") == "plain"


def test_find_agy_cli_uses_path():
    with patch("assemblyzero.core.gemini_client.shutil.which", return_value="/usr/bin/agy"):
        client = GeminiClient(model="gemini-3.1-pro-preview")
    assert client._agy_cli == "/usr/bin/agy"


def test_invoke_via_cli_agy_not_found():
    client = GeminiClient(model="gemini-3.1-pro-preview")
    client._agy_cli = None
    ok, resp, err = client._invoke_via_cli("sys", "content")
    assert ok is False and resp == "" and "not found" in err.lower()


def test_invoke_via_cli_rejects_oversized_prompt():
    client = GeminiClient(model="gemini-3.1-pro-preview")
    client._agy_cli = "agy"
    ok, resp, err = client._invoke_via_cli("sys", "x" * 31000)
    assert ok is False and "too large" in err


def test_invoke_via_cli_strips_ansi_and_returns_text():
    client = GeminiClient(model="gemini-3.1-pro-preview")
    client._agy_cli = "agy"
    chunks = ['\x1b[32m{"verdict":"APPROVE"}\x1b[0m\r\n']
    with patch.dict(sys.modules, {"winpty": _fake_winpty(chunks)}):
        ok, resp, err = client._invoke_via_cli("sys", "content")
    assert ok is True and err == ""
    assert resp == '{"verdict":"APPROVE"}'


def test_invoke_via_cli_empty_output_is_failure():
    client = GeminiClient(model="gemini-3.1-pro-preview")
    client._agy_cli = "agy"
    with patch.dict(sys.modules, {"winpty": _fake_winpty([])}):
        ok, resp, err = client._invoke_via_cli("sys", "content")
    assert ok is False and "no output" in err