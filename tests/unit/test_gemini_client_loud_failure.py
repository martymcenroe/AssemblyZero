"""gemini_client.py under standard 0034, one test per sweep site (#3777).

The agy transport every default target run uses. A failed call stays a failed
``GeminiCallResult`` (the provider's contract, which the caller routes to
HALT); what changes is that each failure is loud with its cause, a missing CLI
fails at once, and a fault in this code is raised instead of being handed back
as a failed call. Line numbers in the names are ledger 0908's, at ``79e18ad1``.
"""
from __future__ import annotations

import inspect
import logging
import subprocess
from unittest.mock import Mock, patch

import pytest

from assemblyzero.core import gemini_client
from assemblyzero.core.gemini_client import GeminiClient


@pytest.fixture(autouse=True)
def _fresh_wsl_cache():
    gemini_client._find_wsl_agy.cache_clear()
    yield
    gemini_client._find_wsl_agy.cache_clear()


def _client(agy: str | None = "/home/u/.local/bin/agy") -> GeminiClient:
    with patch.object(GeminiClient, "_find_agy_cli", return_value=agy):
        return GeminiClient(model="gemini-3.1-pro-high")


@pytest.fixture
def no_waiting(monkeypatch):
    monkeypatch.setattr(GeminiClient, "_backoff_delay", lambda self, attempt: 0)
    monkeypatch.setattr(gemini_client.time, "sleep", lambda s: None)


@pytest.mark.real_agy_lookup  # #4253: these test the lookup itself
class TestFindingAgy:
    def test_174_a_windows_agy_on_path_is_refused_out_loud(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(gemini_client.Path, "home", classmethod(lambda cls: tmp_path))
        monkeypatch.setattr(gemini_client.shutil, "which", lambda name: "/mnt/c/Tools/agy.exe")
        assert gemini_client._find_linux_agy() is None
        err = capsys.readouterr().err
        assert "ERROR [agy]" in err and "/mnt/c/Tools/agy.exe" in err

    def test_199_a_wsl_that_cannot_run_raises_and_is_not_cached(self, monkeypatch):
        monkeypatch.setattr(gemini_client.shutil, "which", lambda name: "/usr/bin/wsl.exe")
        monkeypatch.setattr(gemini_client.subprocess, "run", Mock(side_effect=OSError("exec format error")))
        with pytest.raises(RuntimeError, match="could not run .*which agy.*OSError"):
            gemini_client._find_wsl_agy()
        assert gemini_client._find_wsl_agy.cache_info().currsize == 0

    def test_200_the_withdrawn_tag_is_gone(self):
        assert "fail-open" not in inspect.getsource(gemini_client._find_wsl_agy)

    def test_208_a_home_that_cannot_be_read_is_said(self, monkeypatch, capsys):
        monkeypatch.setattr(gemini_client.shutil, "which", lambda name: "/usr/bin/wsl.exe")

        def run(argv, **kwargs):
            if argv[2:] == ["which", "agy"]:
                return subprocess.CompletedProcess(argv, 1, "", "")
            return subprocess.CompletedProcess(argv, 1, "", "printenv: HOME not set")

        monkeypatch.setattr(gemini_client.subprocess, "run", run)
        assert gemini_client._find_wsl_agy() is None
        err = capsys.readouterr().err
        assert "WSL's HOME could not be read" in err and "HOME not set" in err


class TestTheCall:
    def test_454_no_agy_fails_at_once_without_retrying(self, capsys):
        client = _client(agy=None)
        with patch.object(GeminiClient, "_invoke_via_cli") as call:
            result = client.invoke("system", "content")
        call.assert_not_called()
        assert result.success is False
        assert result.attempts == 0
        assert "not found" in result.error_message
        assert "ERROR [agy]" in capsys.readouterr().err

    def test_514_a_killed_agy_that_will_not_drain_is_loud(self, monkeypatch, capsys):
        proc = Mock(pid=4242)
        proc.communicate.side_effect = [subprocess.TimeoutExpired("agy", 600), OSError("pipe gone")]
        monkeypatch.setattr(gemini_client.subprocess, "Popen", Mock(return_value=proc))
        monkeypatch.setattr(gemini_client, "kill_process_tree", lambda pid: None)
        ok, text, error = _client()._invoke_via_stdin("prompt", timeout_seconds=1)
        assert ok is False and "timeout" in error
        assert "did not exit 10 s after it was killed" in capsys.readouterr().err

    def test_520_598_every_failed_attempt_is_loud_with_its_cause(self, monkeypatch, no_waiting, capsys):
        monkeypatch.setattr(gemini_client.subprocess, "Popen", Mock(side_effect=OSError("no such file")))
        result = _client().invoke("system", "content")
        assert result.success is False
        err = capsys.readouterr().err
        assert err.count("attempt ") >= 2
        assert "agy stdin invocation failed: no such file" in err

    def test_601_a_fault_in_this_code_is_raised_not_returned(self):
        client = _client()
        with patch.object(GeminiClient, "_invoke_via_cli", side_effect=TypeError("bad keyword")), \
             pytest.raises(TypeError, match="bad keyword"):
            client.invoke("system", "content")

    def test_660_a_retry_is_said_with_its_wait(self, monkeypatch, caplog):
        monkeypatch.setattr(GeminiClient, "_backoff_delay", lambda self, attempt: 7)
        monkeypatch.setattr(gemini_client.time, "sleep", lambda s: None)
        calls = iter([(False, "", "503 overloaded"), (True, "the answer", "")])
        client = _client()
        with patch.object(GeminiClient, "_invoke_via_cli", side_effect=lambda *a, **k: next(calls)), \
             caplog.at_level(logging.WARNING, logger="assemblyzero.core.gemini_client"):
            result = client.invoke("system", "content")
        assert result.success is True
        assert any("retrying attempt 2 in 7s" in r.getMessage() for r in caplog.records)

    def test_671_a_call_that_fails_for_good_is_loud_with_every_cause(self, no_waiting, capsys):
        client = _client()
        with patch.object(GeminiClient, "_invoke_via_cli", return_value=(False, "", "503 overloaded")):
            result = client.invoke("system", "content")
        assert result.success is False
        err = capsys.readouterr().err
        assert "the call failed after" in err and "503 overloaded" in err

    def test_a_good_answer_is_quiet(self, capsys):
        client = _client()
        with patch.object(GeminiClient, "_invoke_via_cli", return_value=(True, "the answer", "")):
            result = client.invoke("system", "content")
        assert result.success is True and result.response == "the answer"
        assert "ERROR" not in capsys.readouterr().err


class TestUsageMetadata:
    def test_730_a_response_with_no_model_raises(self):
        with pytest.raises(ValueError, match="names no modelVersion"):
            gemini_client._parse_usage_from_gemini_response({"usageMetadata": {}})
