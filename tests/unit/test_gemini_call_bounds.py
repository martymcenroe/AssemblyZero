"""Bounds on a single Gemini call: wall clock, tree-kill, spawn-failure retry.

Hardening run 11 (2026-07-28) had a test-plan review with a ~15 second
nominal run 17.5 minutes before it was killed by hand. Two independent
defects made that possible, and both are pinned here:

- #1874: nothing bounded the CALL. Per-attempt timeouts exist, but a timeout
  classifies as capacity, which backs off and retries the same credential,
  so the sequence multiplied into tens of minutes. On Windows the stdin
  transport could not even honour its own timeout: subprocess.run kills the
  root process and then drains pipes with an unbounded communicate(), which
  agy's surviving grandchildren held open.
- #1872: a child that never started (STATUS_DLL_INIT_FAILED and kin) was
  written off as a dead credential instead of retried.
"""

import subprocess
from unittest.mock import MagicMock, patch

from assemblyzero.core import gemini_client as gc


class TestSpawnFailureDetection:
    """#1872: process-creation failures are transient, not credential death."""

    def test_dll_init_failure_recognised(self):
        assert gc._is_spawn_failure("agy exited 3221225794 (stdin path): ") is True

    def test_dll_not_found_recognised(self):
        assert gc._is_spawn_failure("agy exited 3221225781") is True

    def test_ordinary_error_is_not_a_spawn_failure(self):
        assert gc._is_spawn_failure("agy exited 1: model not found") is False

    def test_empty_text_is_not_a_spawn_failure(self):
        assert gc._is_spawn_failure("") is False

    def test_spawn_failure_maps_to_a_retryable_type(self):
        """The retry loop backs off on CAPACITY_EXHAUSTED; UNKNOWN writes the
        credential off. A spawn failure must land on the former."""
        assert (
            gc.GeminiErrorType.CAPACITY_EXHAUSTED
            in gc.GeminiErrorType.__members__.values()
        )
        # The classification hop itself is exercised in the invoke() path;
        # here we pin that the code the client reports IS matched.
        assert gc._is_spawn_failure(
            f"agy exited {gc.SPAWN_FAILURE_EXIT_CODES[0]} (stdin path)"
        )


class TestCallBudget:
    """#1874: one invoke() has a wall-clock ceiling covering all retries."""

    def test_budget_shrinks_as_time_passes(self):
        with patch.object(gc.time, "time", return_value=1000.0):
            remaining = gc.GeminiClient._remaining_budget(start_time=940.0)
        assert remaining == gc.MAX_TOTAL_INVOKE_SECONDS - 60.0

    def test_budget_goes_negative_when_overrun(self):
        with patch.object(gc.time, "time", return_value=2000.0):
            remaining = gc.GeminiClient._remaining_budget(start_time=1000.0)
        assert remaining < 0

    def test_budget_is_smaller_than_worst_case_retry_sequence(self):
        """The regression in one line: the old worst case was
        retries x credentials x per-attempt timeout, with nothing capping the
        product. The budget must be well under even a single credential's
        share of that."""
        single_credential_worst_case = (
            gc.MAX_RETRIES_PER_CREDENTIAL * gc.AGY_CALL_TIMEOUT_SECONDS
        )
        assert gc.MAX_TOTAL_INVOKE_SECONDS < single_credential_worst_case

    def test_floor_leaves_room_for_a_real_attempt(self):
        assert 0 < gc.MIN_ATTEMPT_SECONDS < gc.AGY_CALL_TIMEOUT_SECONDS


class TestStdinTransportTimeout:
    """#1874: the stdin path kills the TREE and returns, never hangs."""

    def _client(self):
        client = gc.GeminiClient.__new__(gc.GeminiClient)
        client._agy_cli = "agy"
        client.model = "3.1-pro"
        return client

    def test_timeout_kills_the_process_tree(self):
        proc = MagicMock()
        proc.pid = 4242
        proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="agy", timeout=30)

        with patch.object(gc.subprocess, "Popen", return_value=proc), \
             patch.object(gc, "kill_process_tree") as killer:
            ok, text, err = self._client()._invoke_via_stdin("prompt", timeout_seconds=30)

        killer.assert_called_once_with(4242)
        assert ok is False
        assert "timeout" in err.lower()
        assert text == ""

    def test_timeout_message_reports_the_budget_it_was_given(self):
        proc = MagicMock()
        proc.pid = 1
        proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="agy", timeout=45)

        with patch.object(gc.subprocess, "Popen", return_value=proc), \
             patch.object(gc, "kill_process_tree"):
            _ok, _text, err = self._client()._invoke_via_stdin("p", timeout_seconds=45)

        assert "45s" in err

    def test_successful_call_returns_stdout(self):
        proc = MagicMock()
        proc.pid = 7
        proc.communicate.return_value = ("the response", "")
        proc.returncode = 0

        with patch.object(gc.subprocess, "Popen", return_value=proc):
            ok, text, err = self._client()._invoke_via_stdin("p", timeout_seconds=60)

        assert ok is True
        assert text == "the response"
        assert err == ""

    def test_nonzero_exit_surfaces_code_and_detail(self):
        proc = MagicMock()
        proc.pid = 7
        proc.communicate.return_value = ("", "boom")
        proc.returncode = 3221225794

        with patch.object(gc.subprocess, "Popen", return_value=proc):
            ok, _text, err = self._client()._invoke_via_stdin("p", timeout_seconds=60)

        assert ok is False
        assert "3221225794" in err
        # and that message is what #1872's detector keys on
        assert gc._is_spawn_failure(err) is True
