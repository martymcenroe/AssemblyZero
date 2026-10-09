"""llm_provider.py under standard 0034, one test per sweep site (#3780, #3787).

ADR 0236: every failure is loud (an ERROR line on stderr), logged with details,
stops what depends on it, and alerts the operator. A provider's failed call is
its contract: the caller reads ``success`` and routes to HALT, which alerts. So
each site here either returns a failed result that is now loud, or raises.
Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import io
import json
import subprocess
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from assemblyzero.core import llm_provider, provider_storm
from assemblyzero.core.llm_provider import (
    AnthropicProvider,
    ClaudeCLIProvider,
    FallbackProvider,
    GeminiProvider,
    LLMCallResult,
    _stream_with_idle_timeout,
    _StreamOutcome,
)


@pytest.fixture(autouse=True)
def _clean_counters():
    provider_storm.reset()
    llm_provider.reset_circuit_breakers()
    yield
    provider_storm.reset()
    llm_provider.reset_circuit_breakers()


def _failed(message: str = "boom", provider: str = "mock") -> LLMCallResult:
    return LLMCallResult(
        success=False, response=None, raw_response=None, error_message=message,
        provider=provider, model_used="m", duration_ms=0, attempts=1,
    )


def _ok(text: str = "fine", provider: str = "mock") -> LLMCallResult:
    return LLMCallResult(
        success=True, response=text, raw_response=text, error_message=None,
        provider=provider, model_used="m", duration_ms=0, attempts=1,
    )


# --- the pumps of the streaming transport (487, 505, 510, 517, 553) ---------


class _FakeProc:
    """A finished child whose pipes do what the test says."""

    def __init__(self, stdin=None, stdout=(), stderr=""):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = io.StringIO(stderr) if isinstance(stderr, str) else stderr
        self.pid = 0

    def poll(self):
        return 0


class _BrokenWriter:
    def write(self, _data):
        raise BrokenPipeError("the child closed stdin")

    def close(self):
        pass


class _ReadFails:
    def __iter__(self):
        yield json.dumps({"type": "system"}) + "\n"
        raise OSError("read error on the stdout pipe")


class _StderrFails:
    def read(self):
        raise OSError("read error on the stderr pipe")


class _Blocks:
    def __init__(self):
        self.release = threading.Event()

    def __iter__(self):
        self.release.wait(10)
        return iter(())


def _run(proc) -> _StreamOutcome:
    return _stream_with_idle_timeout(proc, "prompt", idle_timeout=30, wall_timeout=30)


class TestThePumpsRecordWhatWentWrong:
    def test_487_a_prompt_that_could_not_be_written_is_recorded(self):
        outcome = _run(_FakeProc(stdin=_BrokenWriter(), stdout=iter(())))
        assert "the prompt could not be written to stdin" in outcome.stream_problems()
        assert "BrokenPipeError" in outcome.stream_problems()

    def test_505_a_line_that_is_not_json_is_counted_and_named(self):
        lines = iter(["this is not json\n", json.dumps({"type": "result", "result": "x"}) + "\n"])
        outcome = _run(_FakeProc(stdin=io.StringIO(), stdout=lines))
        assert outcome.undecodable_lines == 1
        assert "1 stream line(s) were not JSON" in outcome.stream_problems()
        assert "this is not json" in outcome.stream_problems()

    def test_510_stdout_that_cannot_be_read_to_the_end_is_recorded(self):
        outcome = _run(_FakeProc(stdin=io.StringIO(), stdout=_ReadFails()))
        assert "stdout could not be read to the end: OSError" in outcome.stream_problems()

    def test_517_stderr_that_cannot_be_read_is_recorded(self):
        outcome = _run(_FakeProc(stdin=io.StringIO(), stdout=iter(()), stderr=_StderrFails()))
        assert "stderr could not be read: OSError" in outcome.stream_problems()

    def test_553_a_pump_still_running_after_the_process_ended_is_recorded(self, monkeypatch):
        monkeypatch.setattr(llm_provider, "_PUMP_JOIN_SECONDS", 0.2)
        stdout = _Blocks()
        try:
            outcome = _run(_FakeProc(stdin=io.StringIO(), stdout=stdout))
        finally:
            stdout.release.set()
        assert "the stdout pump was still running" in outcome.stream_problems()

    def test_a_clean_stream_has_no_problems(self):
        lines = iter([json.dumps({"type": "result", "result": "x"}) + "\n"])
        outcome = _run(_FakeProc(stdin=io.StringIO(), stdout=lines))
        assert outcome.stream_problems() == ""


# --- ClaudeCLIProvider.invoke ----------------------------------------------


class _Outcome:
    """What `_stream_with_idle_timeout` hands back, shaped by the test."""

    def __init__(self, payload: str, problems: str = "", timed_out: bool = False):
        self._payload = payload
        self._problems = problems
        self.timed_out = timed_out
        self.timeout_kind = "idle" if timed_out else ""
        self.silent_seconds = 120.0
        self.total_events = 3
        self.stderr = ""

    def result_payload(self) -> str:
        return self._payload

    def stream_problems(self) -> str:
        return self._problems


def _invoke_claude(outcome, returncode: int = 0, stderr: str = ""):
    outcome.stderr = stderr
    proc = SimpleNamespace(returncode=returncode, pid=0)
    provider = ClaudeCLIProvider(model="haiku")
    with patch.object(ClaudeCLIProvider, "_find_cli", return_value="/usr/bin/claude"), \
         patch.object(llm_provider.subprocess, "Popen", return_value=proc), \
         patch.object(llm_provider, "_stream_with_idle_timeout", return_value=outcome), \
         patch("assemblyzero.core.capacity.clear_exhaustion"):
        return provider.invoke("system", "content")


class TestTheClaudeCliCallFailsLoudly:
    def test_826_no_cli_is_a_loud_failed_call(self, capsys):
        provider = ClaudeCLIProvider(model="haiku")
        with patch.object(ClaudeCLIProvider, "_find_cli", side_effect=RuntimeError("claude command not found")):
            result = provider.invoke("system", "content")
        assert result.success is False
        assert "ERROR [LLM]" in capsys.readouterr().err

    def test_953_a_timeout_is_loud(self, capsys):
        result = _invoke_claude(_Outcome("[]", timed_out=True))
        assert result.success is False
        assert "timed out" in result.error_message
        assert "ERROR [LLM]" in capsys.readouterr().err

    def test_1016_a_nonzero_exit_is_loud(self, capsys):
        result = _invoke_claude(_Outcome("[]"), returncode=1, stderr="bad request")
        assert result.success is False
        assert "ERROR [LLM]" in capsys.readouterr().err

    def test_1029_a_capacity_record_is_loud(self, capsys):
        recorded = SimpleNamespace(wait_summary=lambda: "claude exhausted until 5 PM")
        with patch("assemblyzero.core.capacity.record_exhaustion", return_value=recorded):
            _invoke_claude(_Outcome("[]"), returncode=1, stderr="You have hit your usage limit")
        assert "ERROR [LLM] [CAPACITY] claude exhausted until 5 PM" in capsys.readouterr().err

    def test_a_stream_with_problems_fails_even_on_exit_zero(self, capsys):
        payload = json.dumps({"type": "result", "result": "answer"})
        result = _invoke_claude(_Outcome(payload, problems="stdout could not be read to the end"))
        assert result.success is False
        assert "stream cannot be trusted" in result.error_message
        assert "ERROR [LLM]" in capsys.readouterr().err

    def test_1085_json_that_is_neither_an_object_nor_a_list_fails(self, capsys):
        result = _invoke_claude(_Outcome("42"))
        assert result.success is False
        assert "JSON of type int" in result.error_message
        assert "ERROR [LLM]" in capsys.readouterr().err

    def test_1103_an_empty_result_fails(self):
        result = _invoke_claude(_Outcome(json.dumps({"type": "result", "result": ""})))
        assert result.success is False
        assert "no result text" in result.error_message

    def test_an_event_list_with_no_text_fails(self):
        result = _invoke_claude(_Outcome(json.dumps([{"type": "system"}])))
        assert result.success is False
        assert "no result text" in result.error_message

    def test_1113_output_that_is_not_json_fails(self):
        result = _invoke_claude(_Outcome("Error: something odd"))
        assert result.success is False
        assert "output was not JSON" in result.error_message

    def test_a_real_answer_still_succeeds(self, capsys):
        result = _invoke_claude(_Outcome(json.dumps({"type": "result", "result": "answer"})))
        assert result.success is True
        assert result.response == "answer"
        assert "ERROR" not in capsys.readouterr().err

    def test_1145_a_transport_error_is_a_loud_failed_call(self, capsys):
        provider = ClaudeCLIProvider(model="haiku")
        with patch.object(ClaudeCLIProvider, "_find_cli", return_value="/usr/bin/claude"), \
             patch.object(llm_provider.subprocess, "Popen", side_effect=OSError("no such file")):
            result = provider.invoke("system", "content")
        assert result.success is False
        assert "could not be run: OSError" in result.error_message
        assert "ERROR [LLM]" in capsys.readouterr().err

    def test_1145_a_fault_in_this_code_is_raised(self):
        provider = ClaudeCLIProvider(model="haiku")
        with patch.object(ClaudeCLIProvider, "_find_cli", return_value="/usr/bin/claude"), \
             patch.object(llm_provider.subprocess, "Popen", side_effect=TypeError("bad argument")), \
             pytest.raises(TypeError, match="bad argument"):
            provider.invoke("system", "content")

    def test_412_a_bad_idle_override_stops_the_call(self, monkeypatch):
        monkeypatch.setenv(llm_provider.ENV_IDLE_TIMEOUT, "soon")
        provider = ClaudeCLIProvider(model="haiku")
        proc = SimpleNamespace(returncode=0, pid=0)
        with patch.object(ClaudeCLIProvider, "_find_cli", return_value="/usr/bin/claude"), \
             patch.object(llm_provider.subprocess, "Popen", return_value=proc), \
             pytest.raises(ValueError, match="AZ_LLM_IDLE_TIMEOUT='soon'"):
            provider.invoke("system", "content")

    def test_418_a_non_positive_idle_override_raises(self, monkeypatch):
        monkeypatch.setenv(llm_provider.ENV_IDLE_TIMEOUT, "-5")
        with pytest.raises(ValueError, match="is not a positive"):
            llm_provider.idle_timeout_seconds()


# --- the storm probe (723, 757, 769, 772) and provider_storm.diagnose -------


class TestTheProbeSaysWhyItCouldNotRun:
    def test_723_no_cli_raises_with_the_cause(self):
        provider = ClaudeCLIProvider(model="haiku")
        with patch.object(ClaudeCLIProvider, "_find_cli", side_effect=RuntimeError("claude command not found")), \
             pytest.raises(RuntimeError, match="claude command not found"):
            provider._probe_alive()

    def test_757_a_probe_that_cannot_start_raises(self):
        provider = ClaudeCLIProvider(model="haiku")
        with patch.object(ClaudeCLIProvider, "_find_cli", return_value="/usr/bin/claude"), \
             patch.object(llm_provider.subprocess, "Popen", side_effect=OSError("exec format error")), \
             pytest.raises(RuntimeError, match="could not start /usr/bin/claude: OSError"):
            provider._probe_alive()

    def test_772_a_probe_that_cannot_talk_raises(self):
        proc = Mock(pid=0)
        proc.communicate.side_effect = OSError("broken pipe")
        provider = ClaudeCLIProvider(model="haiku")
        with patch.object(ClaudeCLIProvider, "_find_cli", return_value="/usr/bin/claude"), \
             patch.object(llm_provider.subprocess, "Popen", return_value=proc), \
             pytest.raises(RuntimeError, match="could not talk to /usr/bin/claude: OSError"):
            provider._probe_alive()

    def test_769_a_probe_that_will_not_drain_after_its_kill_is_loud(self, capsys):
        proc = Mock(pid=0)
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired("claude", 60), OSError("pipe gone"),
        ]
        provider = ClaudeCLIProvider(model="haiku")
        with patch.object(ClaudeCLIProvider, "_find_cli", return_value="/usr/bin/claude"), \
             patch.object(llm_provider.subprocess, "Popen", return_value=proc), \
             patch.object(llm_provider, "_kill_process_tree"):
            answered = provider._probe_alive()
        assert answered is False
        assert "did not exit 5 s after it was killed" in capsys.readouterr().err

    def test_storm_147_a_probe_that_raises_alerts_and_the_storm_stands(self, operator_alerts):
        for _ in range(provider_storm.STORM_THRESHOLD):
            provider_storm.record_timeout(120)

        def probe():
            raise RuntimeError("claude command not found")

        assert provider_storm.diagnose(probe) == "storm"
        assert len(operator_alerts) == 1
        assert "could not run" in operator_alerts[0]["what"]
        assert "RuntimeError: claude command not found" in operator_alerts[0]["cause"]


# --- AnthropicProvider (291, 1248, 1372, 1387) -----------------------------


class TestTheApiProviderFailsLoudly:
    def test_291_an_unreadable_env_file_raises_with_its_path(self, monkeypatch):
        real_read = llm_provider.Path.read_text
        real_exists = llm_provider.Path.exists

        def read_text(self, *args, **kwargs):
            if self.name == ".env":
                raise PermissionError("permission denied")
            return real_read(self, *args, **kwargs)

        def exists(self):
            return True if self.name == ".env" else real_exists(self)

        monkeypatch.setattr(llm_provider.Path, "read_text", read_text)
        monkeypatch.setattr(llm_provider.Path, "exists", exists)
        with pytest.raises(RuntimeError, match=r"cannot read .*\.env .*PermissionError"):
            llm_provider._load_anthropic_api_key()

    def test_1248_an_unpriced_model_is_refused_before_any_call(self, capsys):
        provider = AnthropicProvider(model="claude-opus-4-7-20260415")
        with patch.object(AnthropicProvider, "_get_client") as client:
            result = provider.invoke("system", "content")
        client.assert_not_called()
        assert result.success is False
        assert "no price for claude-opus-4-7-20260415" in result.error_message
        assert "ERROR [LLM]" in capsys.readouterr().err

    def test_1372_no_key_is_a_loud_failed_call(self, capsys):
        provider = AnthropicProvider(model="haiku")
        with patch.object(llm_provider, "_load_anthropic_api_key", return_value=None), \
             patch.dict("sys.modules", {"anthropic": Mock()}):
            result = provider.invoke("system", "content")
        assert result.success is False
        assert "ANTHROPIC_API_KEY not found" in result.error_message
        assert "ERROR [LLM]" in capsys.readouterr().err

    def test_1387_an_api_error_is_a_loud_failed_call(self, capsys):
        import anthropic

        client = Mock()
        client.messages.stream.side_effect = anthropic.APITimeoutError(request=Mock())
        provider = AnthropicProvider(model="haiku")
        with patch.object(llm_provider, "_load_anthropic_api_key", return_value="sk-ant-test"), \
             patch("anthropic.Anthropic", return_value=client):
            result = provider.invoke("system", "content")
        assert result.success is False
        assert "ERROR [LLM]" in capsys.readouterr().err

    def test_1387_a_fault_in_this_code_is_raised(self):
        client = Mock()
        client.messages.stream.side_effect = TypeError("unexpected keyword")
        provider = AnthropicProvider(model="haiku")
        with patch.object(llm_provider, "_load_anthropic_api_key", return_value="sk-ant-test"), \
             patch("anthropic.Anthropic", return_value=client), \
             pytest.raises(TypeError, match="unexpected keyword"):
            provider.invoke("system", "content")


# --- FallbackProvider (1555, 1596, 1609, 1617) -----------------------------


def _pair(primary_result, fallback_result):
    primary = Mock(provider_name="claude", model="opus")
    primary.invoke.return_value = primary_result
    fallback = Mock(provider_name="anthropic", model="opus")
    fallback.invoke.return_value = fallback_result
    return FallbackProvider(primary=primary, fallback=fallback)


class TestTheFallbackIsLoud:
    def test_1555_an_open_breaker_is_a_loud_failed_call(self, capsys):
        provider = _pair(_ok(), _ok())
        llm_provider._circuit_breaker_registry[provider._breaker_key] = llm_provider._CIRCUIT_BREAKER_MAX
        result = provider.invoke("system", "content")
        assert result.success is False
        assert "[CIRCUIT BREAKER]" in capsys.readouterr().err

    def test_1596_a_failed_primary_says_the_fallback_is_spending(self, capsys):
        _pair(_failed("cli died"), _ok()).invoke("system", "content")
        assert "falling back to anthropic" in capsys.readouterr().err

    def test_1609_a_non_retryable_fallback_failure_is_loud(self, capsys):
        _pair(_failed("cli died"), _failed("invalid_api_key")).invoke("system", "content")
        assert "[CIRCUIT BREAKER] tripped" in capsys.readouterr().err

    def test_1617_both_failing_is_loud(self, capsys):
        _pair(_failed("cli died"), _failed("overloaded")).invoke("system", "content")
        assert "both claude and anthropic failed" in capsys.readouterr().err


# --- GeminiProvider (1729, 1756) -------------------------------------------


def _gemini_with(result=None, raises=None) -> GeminiProvider:
    client = Mock()
    if raises is not None:
        client.invoke.side_effect = raises
    else:
        client.invoke.return_value = result
    provider = GeminiProvider(model="3.1-pro")
    provider._client = client
    return provider


class TestTheGeminiProvider:
    def test_1729_the_rate_limit_is_read_from_error_type(self):
        from assemblyzero.core.gemini_client import GeminiCallResult, GeminiErrorType

        result = GeminiCallResult(
            success=False, response=None, raw_response=None,
            error_type=GeminiErrorType.QUOTA_EXHAUSTED, error_message="quota",
            attempts=1, duration_ms=0, model_verified="",
        )
        assert _gemini_with(result).invoke("s", "c").rate_limited is True

    def test_1729_a_result_without_error_type_is_not_read_as_unlimited(self):
        """The hasattr guard read a changed contract as "not rate-limited"."""
        bare = SimpleNamespace(success=False, response=None, raw_response=None,
                               error_message="x", model_verified="", duration_ms=0,
                               attempts=1)
        with pytest.raises(AttributeError):
            _gemini_with(bare).invoke("s", "c")

    def test_1756_an_agy_failure_is_a_loud_failed_call(self, capsys):
        result = _gemini_with(raises=RuntimeError("429 quota exhausted")).invoke("s", "c")
        assert result.success is False
        assert result.rate_limited is True
        assert "ERROR [LLM]" in capsys.readouterr().err

    def test_1756_a_fault_in_this_code_is_raised(self):
        with pytest.raises(TypeError, match="positional"):
            _gemini_with(raises=TypeError("takes 2 positional arguments")).invoke("s", "c")


# --- the recording wrap (2009, 2010) ---------------------------------------


class TestTheRecorderIsNeverSkipped:
    def test_2009_a_recorder_that_cannot_be_set_up_raises(self):
        with patch("assemblyzero.core.call_recording.recording_is_armed",
                   side_effect=RuntimeError("lineage directory unwritable")), \
             pytest.raises(RuntimeError, match="lineage directory unwritable"):
            llm_provider.get_provider("mock:test")

    def test_2010_the_withdrawn_tag_is_gone(self):
        import inspect

        assert "fail-open" not in inspect.getsource(llm_provider._recorded)
