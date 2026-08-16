"""Stage stall visibility (#1886) and non-retryable programming errors (#1875).

Both come from the same hour of the 2026-07-28 campaign: a 15-second-nominal
stage ran 17.5 minutes with nothing in the log saying so, and a single bad
call signature burned 9 attempts and 84 seconds of backoff before reporting
"All credentials failed" for what was a bug in the caller.
"""

import time
from unittest.mock import patch

from assemblyzero.core.stage_watchdog import (
    SLOW_RATIO,
    STAGE_NOMINAL_SECONDS,
    STALLED_RATIO,
    StageWatchdog,
)


class TestStatusLine:
    """The line says what a human would have had to work out by hand."""

    def test_reports_stage_and_elapsed(self):
        line = StageWatchdog("impl", nominal_seconds=40).status_line(60)
        assert "impl" in line
        assert "60s" in line

    def test_quiet_below_the_slow_ratio(self):
        line = StageWatchdog("impl", nominal_seconds=40).status_line(60)
        assert "SLOW" not in line
        assert "STALLED" not in line

    def test_marks_slow_at_the_ratio(self):
        watchdog = StageWatchdog("impl", nominal_seconds=40)
        line = watchdog.status_line(40 * SLOW_RATIO)
        assert "SLOW" in line
        assert "nominal" in line

    def test_escalates_to_stalled(self):
        watchdog = StageWatchdog("impl", nominal_seconds=40)
        line = watchdog.status_line(40 * STALLED_RATIO)
        assert "STALLED" in line
        assert "SLOW" not in line

    def test_the_17_minute_hang_would_have_been_labelled(self):
        """The regression in one line: 1050s against a 15s nominal."""
        line = StageWatchdog("review", nominal_seconds=15).status_line(1050)
        assert "STALLED" in line
        assert "70x" in line

    def test_unknown_stage_still_reports_elapsed(self):
        line = StageWatchdog("mystery", nominal_seconds=None).status_line(90)
        assert "mystery" in line and "90s" in line
        assert "nominal" not in line

    def test_measured_stages_have_nominals(self):
        """#2410 dropped `triage`: it has no passing samples in the corpus, so
        its 20.0 was a guess that would have called a 61-second triage
        STALLED. A stage the fleet cannot measure now reports elapsed time
        without a verdict rather than being judged against an invention."""
        for stage in ("lld", "spec", "impl", "pr", "cleanup"):
            assert STAGE_NOMINAL_SECONDS[stage] > 0
        assert "triage" not in STAGE_NOMINAL_SECONDS


class TestWatchdogLifecycle:
    def test_prints_on_interval_then_stops(self, capsys):
        with StageWatchdog("impl", nominal_seconds=1, interval=0.05):
            time.sleep(0.2)
        out = capsys.readouterr().out
        assert "[STAGE] impl running" in out

        # After the context exits, no further lines appear.
        time.sleep(0.15)
        assert "[STAGE]" not in capsys.readouterr().out

    def test_quiet_when_the_stage_finishes_fast(self, capsys):
        with StageWatchdog("pr", interval=5):
            pass
        assert "[STAGE]" not in capsys.readouterr().out

    def test_exception_in_the_stage_still_stops_the_thread(self, capsys):
        try:
            with StageWatchdog("impl", interval=0.05):
                raise RuntimeError("stage blew up")
        except RuntimeError:
            pass
        time.sleep(0.15)
        capsys.readouterr()
        time.sleep(0.15)
        assert "[STAGE]" not in capsys.readouterr().out


class TestProgrammingErrorsAreNotRetried:
    """#1875: retrying a TypeError cannot fix it and hides the real defect."""

    def _client(self, tmp_path):
        from assemblyzero.core.gemini_client import GeminiClient

        creds = tmp_path / "creds.json"
        creds.write_text(
            '{"credentials": [{"name": "c1", "type": "oauth", "enabled": true}]}',
            encoding="utf-8",
        )
        return GeminiClient(
            model="gemini-3.1-pro-high",
            credentials_file=creds,
            state_file=tmp_path / "state.json",
        )

    def test_type_error_fails_immediately_without_sleeping(self, tmp_path):
        client = self._client(tmp_path)

        def boom(*args, **kwargs):
            raise TypeError("got an unexpected keyword argument 'timeout_seconds'")

        with patch.object(client, "_invoke_via_cli", side_effect=boom), \
             patch("assemblyzero.core.gemini_client.time.sleep") as slept:
            result = client.invoke("system", "content")

        assert result.success is False
        assert "Programming error" in result.error_message
        assert "TypeError" in result.error_message
        assert result.attempts == 1, "must not retry a defect in our own code"
        slept.assert_not_called()

    def test_attribute_error_is_also_immediate(self, tmp_path):
        client = self._client(tmp_path)

        def boom(*args, **kwargs):
            raise AttributeError("'LLMCallResult' object has no attribute 'content'")

        with patch.object(client, "_invoke_via_cli", side_effect=boom):
            result = client.invoke("system", "content")

        assert result.success is False
        assert result.attempts == 1

    def test_ordinary_runtime_error_still_retries(self, tmp_path):
        """The narrowing must not disable the retry path it lives in."""
        client = self._client(tmp_path)
        calls = []

        def flaky(*args, **kwargs):
            calls.append(1)
            raise RuntimeError("503 capacity exhausted")

        with patch.object(client, "_invoke_via_cli", side_effect=flaky), \
             patch("assemblyzero.core.gemini_client.time.sleep"):
            client.invoke("system", "content")

        assert len(calls) > 1, "transient failures must still be retried"
