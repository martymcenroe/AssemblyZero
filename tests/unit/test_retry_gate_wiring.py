"""Every retry gate asks the same question (#2423).

`test_retry_gate.py` pins the decision. These pin that the decision is actually
CONSULTED at each of the places that can spend money -- which matters because
the 2026-08-15 cost was multiplicative, not additive: a per-file loop inside a
stage loop. Fixing one and not the others would leave the product in place.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from assemblyzero.core import retry_gate as g
from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.utils.retry import RetryPolicy, with_retry

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


@pytest.fixture(autouse=True)
def _no_ambient_fail_fast(monkeypatch):
    monkeypatch.delenv(g.ENV_FAIL_FAST, raising=False)


CEILING_MESSAGE = (
    "claude -p timed out after 600s while still producing output "
    "(1421 events); raise AZ_FILE_TIMEOUT_FLOOR rather than treating this "
    "as a provider failure"
)


def _failure(message, **kw):
    return LLMCallResult(
        success=False, response=None, raw_response=None,
        error_message=message, provider="claude", model_used="sonnet",
        duration_ms=602_000, attempts=1, **kw,
    )


def _success():
    return LLMCallResult(
        success=True, response="ok", raw_response=None, error_message=None,
        provider="claude", model_used="sonnet", duration_ms=100, attempts=1,
    )


# ---------------------------------------------------------------------------
# Gate 1: assemblyzero/utils/retry.py -- the LLD and spec nodes
# ---------------------------------------------------------------------------


class TestUtilsRetryGate:
    def test_a_ceiling_kill_is_paid_for_once(self):
        calls = []

        def fn():
            calls.append(1)
            return _failure(CEILING_MESSAGE)

        with_retry(fn, policy=RetryPolicy(5, 0.0, 0.0, 1.0),
                   sleep_fn=lambda _s: None, description="N4")
        assert len(calls) == 1, f"paid {len(calls)} times for a ceiling kill"

    def test_the_structured_class_is_preferred_over_the_message(self):
        calls = []

        def fn():
            calls.append(1)
            # Message says nothing; the transport's own field says ceiling.
            return _failure("something went wrong",
                            failure_class=g.CEILING_TIMEOUT)

        with_retry(fn, policy=RetryPolicy(5, 0.0, 0.0, 1.0),
                   sleep_fn=lambda _s: None, description="N4")
        assert len(calls) == 1

    def test_an_idle_kill_is_paid_for_at_most_twice(self):
        calls = []

        def fn():
            calls.append(1)
            return _failure("claude -p timed out after 120s with no output "
                            "(idle limit 120s, 37 events received)")

        with_retry(fn, policy=RetryPolicy(5, 0.0, 0.0, 1.0),
                   sleep_fn=lambda _s: None, description="N4")
        assert len(calls) == 2, f"paid {len(calls)} times for an idle kill"

    def test_a_transient_failure_still_uses_the_full_budget(self):
        """The gate must not have become 'never retry'."""
        calls = []

        def fn():
            calls.append(1)
            return _failure("503 capacity exhausted")

        with_retry(fn, policy=RetryPolicy(3, 0.0, 0.0, 1.0),
                   sleep_fn=lambda _s: None, description="N4")
        assert len(calls) == 4  # initial + 3 retries

    def test_success_on_a_retry_still_works(self):
        calls = []

        def fn():
            calls.append(1)
            return _failure("503") if len(calls) == 1 else _success()

        result = with_retry(fn, policy=RetryPolicy(3, 0.0, 0.0, 1.0),
                            sleep_fn=lambda _s: None, description="N4")
        assert result.success is True
        assert len(calls) == 2

    def test_fail_fast_pays_once_for_a_transient_failure(self, monkeypatch):
        monkeypatch.setenv(g.ENV_FAIL_FAST, "1")
        calls = []

        def fn():
            calls.append(1)
            return _failure("503 capacity exhausted")

        with_retry(fn, policy=RetryPolicy(5, 0.0, 0.0, 1.0),
                   sleep_fn=lambda _s: None, description="N4")
        assert len(calls) == 1

    def test_the_halt_reason_is_printed(self, capsys):
        with_retry(lambda: _failure(CEILING_MESSAGE),
                   policy=RetryPolicy(5, 0.0, 0.0, 1.0),
                   sleep_fn=lambda _s: None, description="N4 implementer")
        out = capsys.readouterr().out
        assert "will NOT be retried" in out
        assert "ceiling_timeout" in out
        assert "AZ_FILE_TIMEOUT_FLOOR" in out

    def test_the_retry_line_reports_cumulative_spend(self, capsys):
        with_retry(lambda: _failure("503 capacity exhausted"),
                   policy=RetryPolicy(1, 0.0, 0.0, 1.0),
                   sleep_fn=lambda _s: None, description="N4")
        assert "cumulative=$" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Gate 2: the per-file loop -- where the 2026-08-15 payments actually happened
# ---------------------------------------------------------------------------


class TestPerFileGate:
    def _run(self, monkeypatch, api_error, max_retries=2):
        from assemblyzero.workflows.testing.nodes.implementation import (
            orchestrator as impl,
        )

        calls = []

        def fake_call(prompt, file_path=None, model=None, system_prompt=""):
            calls.append(1)
            return ("", api_error)

        monkeypatch.setattr(impl, "call_claude_for_file", fake_call)
        monkeypatch.setattr(impl, "select_model_for_file", lambda *_a: "sonnet")
        with pytest.raises(Exception) as exc:
            impl.generate_file_with_retry(
                filepath="src/x.py", base_prompt="p", max_retries=max_retries,
            )
        return calls, exc.value

    def test_a_ceiling_kill_is_paid_for_once(self, monkeypatch):
        calls, _ = self._run(monkeypatch, CEILING_MESSAGE)
        assert len(calls) == 1, f"paid {len(calls)} times for a ceiling kill"

    def test_the_error_names_the_class_and_the_lever(self, monkeypatch):
        _calls, error = self._run(monkeypatch, CEILING_MESSAGE)
        assert "ceiling_timeout" in str(error)
        assert "AZ_FILE_TIMEOUT_FLOOR" in str(error)

    def test_a_transient_failure_still_uses_its_budget(self, monkeypatch):
        calls, _ = self._run(monkeypatch, "503 capacity exhausted")
        assert len(calls) == 2

    def test_fail_fast_pays_once(self, monkeypatch):
        monkeypatch.setenv(g.ENV_FAIL_FAST, "1")
        calls, _ = self._run(monkeypatch, "503 capacity exhausted")
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# Gate 3: the launcher flag reaches the pipeline
# ---------------------------------------------------------------------------


class TestFailFastReachesTheChild:
    def test_the_flag_exists(self):
        import speedrun_roll as sr

        parser = sr.build_parser()
        args = parser.parse_args(["--repo", ".", "--issue", "1", "--fail-fast"])
        assert args.fail_fast is True

    def test_the_child_environment_carries_it(self, monkeypatch):
        """The pipeline is three processes deep with several independent retry
        gates. A flag threaded by hand is how a mode ends up honoured in some
        transports and silently ignored in others."""
        import speedrun_roll as sr

        monkeypatch.setenv(g.ENV_FAIL_FAST, "1")
        env = sr._child_env("run-issue1-090001", "2026-08-15 09:00:01")
        assert env[g.ENV_FAIL_FAST] == "1"

    def test_the_child_environment_omits_it_when_off(self, monkeypatch):
        import speedrun_roll as sr

        monkeypatch.delenv(g.ENV_FAIL_FAST, raising=False)
        env = sr._child_env("tag", "start")
        assert g.ENV_FAIL_FAST not in env


# ---------------------------------------------------------------------------
# The transport labels its own failures
# ---------------------------------------------------------------------------


class TestTransportClassifies:
    def test_the_result_carries_a_failure_class_field(self):
        assert _failure("x", failure_class=g.CEILING_TIMEOUT).failure_class == (
            g.CEILING_TIMEOUT
        )

    def test_the_default_is_empty_so_consumers_fall_back_to_the_message(self):
        assert _failure("x").failure_class == ""

    def test_the_log_line_shows_the_class(self, capsys):
        from assemblyzero.core.llm_provider import log_llm_call

        log_llm_call(_failure(CEILING_MESSAGE, failure_class=g.CEILING_TIMEOUT))
        assert "class=ceiling_timeout" in capsys.readouterr().out
