"""Idle-timeout transport and storm/ceiling classification (#2405).

The defect class: every timeout in the Claude CLI transport was wall-clock, so
the only question it could answer was "has N seconds passed", never "is anything
still happening". #373 raised the ceiling, #2026 raised it again, and #2405 is
the third occurrence of the same wall in the same file family. A ceiling keyed
to nothing observable gets overtaken every time the work grows.

The two halves of the acceptance, both asserted here:

- a call that is still producing output is never killed, however long it runs;
- a call that has gone silent is killed at the idle threshold, promptly.

Timings are scaled down (seconds, not minutes) so the suite stays fast. The
full-scale demonstration, a synthetic call streaming past the old 600s ceiling,
lives in ``tools/prove_idle_timeout.py`` and its measured output is recorded on
the issue.
"""
from __future__ import annotations

import subprocess
import sys
import time

import pytest

from assemblyzero.core import provider_storm
from assemblyzero.core.llm_provider import (
    IDLE_TIMEOUT_SECONDS,
    ENV_IDLE_TIMEOUT,
    _stream_with_idle_timeout,
    idle_timeout_seconds,
)
from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
    ENV_TIMEOUT_CAP,
    ENV_TIMEOUT_FLOOR,
    FILE_TIMEOUT_CAP,
    FILE_TIMEOUT_FLOOR,
    compute_dynamic_timeout,
)


# --- helpers ---------------------------------------------------------------

#: Emits `count` JSON lines `interval` seconds apart, then exits 0. Stands in
#: for `claude -p --include-partial-messages`, which emits a delta per chunk.
_STREAMER = (
    "import sys, time\n"
    "count, interval = int(sys.argv[1]), float(sys.argv[2])\n"
    "for i in range(count):\n"
    "    print('{\"type\": \"stream_event\", \"i\": %d}' % i, flush=True)\n"
    "    time.sleep(interval)\n"
    "print('{\"type\": \"result\", \"result\": \"done\", \"usage\": {}}', flush=True)\n"
)

#: Produces nothing at all, then would exit. Stands in for a hung call.
_SILENT = "import time, sys; time.sleep(float(sys.argv[1]))"


def _spawn(script: str, *args: str) -> subprocess.Popen:
    """Spawn a stand-in child, isolated from this process's process group.

    `start_new_session` is not optional here. `kill_process_tree` does
    `os.killpg(os.getpgid(pid), 9)` off Windows, and a child that inherited
    pytest's process group would take the whole test session down with it the
    first time an idle timeout fired for real. That is exactly what happened on
    Linux CI, while Windows passed throughout because its path shells out to
    `taskkill /T /PID`, scoped to the one tree.
    """
    return subprocess.Popen(
        [sys.executable, "-u", "-c", script, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        start_new_session=sys.platform != "win32",
    )


@pytest.fixture(autouse=True)
def _clean_counter():
    provider_storm.reset()
    yield
    provider_storm.reset()


# --- half one: a call still producing output is never killed ---------------


def test_a_streaming_call_is_not_killed_however_long_it_runs():
    """12 seconds of output under a 3-second idle threshold survives.

    This is the half that the old transport got wrong. Under a wall-clock
    ceiling, a call is killed for taking too long; under an idle threshold it is
    killed only for going quiet, so elapsed time stops being the question.
    """
    proc = _spawn(_STREAMER, "12", "1.0")
    started = time.monotonic()
    outcome = _stream_with_idle_timeout(
        proc, content="", idle_timeout=3, wall_timeout=None
    )
    elapsed = time.monotonic() - started

    assert not outcome.timed_out, "a call that never went quiet was killed"
    assert outcome.returncode == 0
    assert elapsed >= 12, "the call should have been allowed to finish"
    # 4x over the idle threshold, and it lived, because output kept arriving.
    assert elapsed > 4 * 3


def test_the_result_event_survives_the_delta_flood():
    """Deltas are counted for liveness and discarded; the result is kept.

    The final `result` event carries the same keys the old buffered
    `--output-format json` dict did, so the whole downstream parse is unchanged.
    """
    proc = _spawn(_STREAMER, "6", "0.05")
    outcome = _stream_with_idle_timeout(
        proc, content="", idle_timeout=10, wall_timeout=None
    )

    assert not outcome.timed_out
    assert outcome.total_events == 7, "every line counts toward liveness"
    assert len(outcome.events) == 1, "only the non-delta event is retained"

    import json

    payload = json.loads(outcome.result_payload())
    assert isinstance(payload, dict), "the parser is handed an object, not an array"
    assert payload["result"] == "done"


# --- half two: a call that has gone silent is killed -----------------------


def test_a_silent_call_is_killed_at_the_idle_threshold():
    """A process producing nothing dies at the threshold, not at the backstop."""
    proc = _spawn(_SILENT, "60")
    started = time.monotonic()
    outcome = _stream_with_idle_timeout(
        proc, content="", idle_timeout=2, wall_timeout=600
    )
    elapsed = time.monotonic() - started

    assert outcome.timed_out
    assert outcome.timeout_kind == "idle"
    assert outcome.silent_seconds >= 2
    # The point of the mechanism: it did not wait out the 600s backstop.
    assert elapsed < 15, f"idle kill took {elapsed:.1f}s"


def test_a_call_that_goes_quiet_mid_stream_is_still_killed():
    """Output then silence. Liveness is about now, not about having once lived."""
    proc = _spawn(_STREAMER, "3", "0.1")  # 3 quick lines, then result, then exit
    outcome = _stream_with_idle_timeout(
        proc, content="", idle_timeout=5, wall_timeout=None
    )
    assert not outcome.timed_out, "this one exits cleanly; it is the control"

    # Now the same shape, but the process hangs after its burst.
    hangs_after_burst = (
        "import sys, time\n"
        "print('{\"type\": \"stream_event\"}', flush=True)\n"
        "time.sleep(60)\n"
    )
    proc = _spawn(hangs_after_burst)
    started = time.monotonic()
    outcome = _stream_with_idle_timeout(
        proc, content="", idle_timeout=2, wall_timeout=None
    )
    elapsed = time.monotonic() - started

    assert outcome.timed_out
    assert outcome.timeout_kind == "idle"
    assert outcome.total_events == 1, "it did produce something, once"
    assert elapsed < 15


def test_the_wall_backstop_still_exists_for_a_call_that_streams_forever():
    """A pathological forever-streamer is bounded, and says so distinctly.

    The backstop is not the operative limit any more, so hitting it is reported
    as a ceiling problem rather than as a provider failure.
    """
    proc = _spawn(_STREAMER, "1000", "0.05")
    outcome = _stream_with_idle_timeout(
        proc, content="", idle_timeout=60, wall_timeout=3
    )

    assert outcome.timed_out
    assert outcome.timeout_kind == "wall"


# --- layer 2: the ceiling is raised, and overridable without a merge -------


def test_the_floor_no_longer_sits_at_600():
    """#2405: 602s killed boostgauge #1 five times. The floor moved past it.
    #2843: and past 1200, which killed two streaming calls on run 15."""
    assert FILE_TIMEOUT_FLOOR == 3600
    assert compute_dynamic_timeout("x" * 2500) == 3600


def test_the_scaling_never_reached_the_cap_which_is_why_the_floor_had_to_move():
    """One second per 1000 characters cannot move a real prompt meaningfully.

    The 2.5 KB fix-loop prompt that died bought two seconds over the floor.
    Reaching the old 1200 cap from a 600 floor needed 600,000 characters.
    """
    old_floor = 600
    old_cap = 1200
    realistic_prompt_chars = 2500
    assert old_floor + realistic_prompt_chars // 1000 == 602
    assert (old_cap - old_floor) * 1000 == 600_000
    assert FILE_TIMEOUT_CAP >= old_cap


def test_the_floor_is_overridable_by_environment(monkeypatch):
    monkeypatch.setenv(ENV_TIMEOUT_FLOOR, "1800")
    monkeypatch.setenv(ENV_TIMEOUT_CAP, "1800")
    assert compute_dynamic_timeout("x" * 2500) == 1800


def test_a_cap_below_the_floor_does_not_silently_undo_the_override(monkeypatch):
    monkeypatch.setenv(ENV_TIMEOUT_FLOOR, "1800")
    monkeypatch.setenv(ENV_TIMEOUT_CAP, "900")
    assert compute_dynamic_timeout("x" * 2500) == 1800


@pytest.mark.parametrize("bad", ["banana", "-5", "0", ""])
def test_a_bad_override_falls_back_rather_than_failing_the_call(monkeypatch, bad):
    """An operator setting this is rescuing a stalled run. A typo must not
    convert a slow call into a dead one."""
    monkeypatch.setenv(ENV_TIMEOUT_FLOOR, bad)
    assert compute_dynamic_timeout("x" * 2500) == FILE_TIMEOUT_FLOOR


def test_the_idle_threshold_is_overridable_too(monkeypatch):
    assert idle_timeout_seconds() == IDLE_TIMEOUT_SECONDS
    monkeypatch.setenv(ENV_IDLE_TIMEOUT, "45")
    assert idle_timeout_seconds() == 45
    monkeypatch.setenv(ENV_IDLE_TIMEOUT, "not-a-number")
    assert idle_timeout_seconds() == IDLE_TIMEOUT_SECONDS


# --- the flag the whole mechanism rests on --------------------------------


def test_the_child_is_spawned_into_its_own_process_group_off_windows():
    """A tree-kill must not reach the process that ordered it (#2405).

    `kill_process_tree` signals `os.getpgid(pid)` off Windows. Without
    `start_new_session`, the child inherits our group, so killing an idle call
    SIGKILLs AssemblyZero itself. Windows hid this completely: that path shells
    out to `taskkill /F /T /PID`, which is scoped to the single tree, so the
    defect was invisible until Linux CI hung on the first real idle kill.

    The idle timeout makes this far easier to reach than the old wall-clock
    ceiling did, because idle kills fire on hangs rather than only on very long
    calls.
    """
    from unittest.mock import Mock, patch

    from assemblyzero.core.llm_provider import ClaudeCLIProvider

    proc = Mock()
    proc.pid = 1
    proc.stdout = iter(['{"type": "result", "result": "ok"}'])
    proc.stderr = Mock()
    proc.stderr.read.return_value = ""
    proc.stdin = Mock()
    proc.poll.return_value = 0
    proc.returncode = 0

    with patch("subprocess.Popen", return_value=proc) as popen, patch.object(
        ClaudeCLIProvider, "_find_cli", return_value="/usr/local/bin/claude"
    ):
        ClaudeCLIProvider().invoke("system", "content")

    expected = sys.platform != "win32"
    assert popen.call_args.kwargs.get("start_new_session") is expected


def test_the_streaming_flags_are_passed_to_the_cli():
    """Removing --include-partial-messages would silently invert the fix.

    Without it the CLI still emits stream-json, but the `assistant` event does
    not arrive until the message is complete. A long generation would then look
    like total silence, and the idle timeout would kill exactly the live calls
    it exists to protect — a worse failure than the wall it replaced, and an
    invisible one, because the transport would still appear to work on short
    calls. Measured 2026-08-15: with the flag, deltas arrive every ~0.65s.
    """
    from unittest.mock import Mock, patch

    from assemblyzero.core.llm_provider import ClaudeCLIProvider

    proc = Mock()
    proc.pid = 1
    proc.stdout = iter(['{"type": "result", "result": "ok"}'])
    proc.stderr = Mock()
    proc.stderr.read.return_value = ""
    proc.stdin = Mock()
    proc.poll.return_value = 0
    proc.returncode = 0

    with patch("subprocess.Popen", return_value=proc) as popen, patch.object(
        ClaudeCLIProvider, "_find_cli", return_value="/usr/local/bin/claude"
    ):
        ClaudeCLIProvider().invoke("system", "content")

    cmd = popen.call_args[0][0]
    assert "--include-partial-messages" in cmd, (
        "without this flag the idle timeout kills live calls"
    )
    assert "stream-json" in cmd
    assert "--verbose" in cmd, "stream-json under -p requires it"


# --- layer 4: weather or a wall -------------------------------------------


def test_a_probe_that_answers_overturns_the_storm_reading():
    """The measured case. boostgauge #1 declared a storm, then the next call
    succeeded in 16.9s, with ten Claude calls completing in 6.3-31.6s through
    the same window."""
    for _ in range(provider_storm.STORM_THRESHOLD):
        provider_storm.record_timeout(1200)
    assert provider_storm.is_storm()

    assert provider_storm.diagnose(lambda: True) == "ceiling"

    # The counter clears, so the launcher's is_storm() halt does not fire.
    assert not provider_storm.is_storm()


def test_a_probe_that_fails_confirms_a_genuine_storm():
    for _ in range(provider_storm.STORM_THRESHOLD):
        provider_storm.record_timeout(1200)

    assert provider_storm.diagnose(lambda: False) == "storm"
    assert provider_storm.is_storm(), "a real storm must still halt the roll"


def test_a_probe_that_raises_is_a_failed_probe():
    """If we cannot reach the provider to ask, we cannot overturn the reading."""

    def _boom() -> bool:
        raise RuntimeError("probe transport died")

    for _ in range(provider_storm.STORM_THRESHOLD):
        provider_storm.record_timeout(1200)

    assert provider_storm.diagnose(_boom) == "storm"
    assert provider_storm.is_storm()


def test_no_probe_is_fired_when_there_is_no_storm():
    """The probe costs a real call, so it only runs at the decision point."""
    fired = []

    def _probe() -> bool:
        fired.append(1)
        return True

    provider_storm.record_timeout(1200)
    assert provider_storm.diagnose(_probe) == "none"
    assert not fired


def test_the_two_verdicts_say_different_things_in_plain_english():
    for _ in range(provider_storm.STORM_THRESHOLD):
        provider_storm.record_timeout(1200)

    storm = provider_storm.storm_message()
    assert provider_storm.STORM_MARKER in storm

    assert provider_storm.diagnose(lambda: True) == "ceiling"
    ceiling = provider_storm.ceiling_message()

    assert provider_storm.CEILING_MARKER in ceiling
    assert "provider" in ceiling.lower() and "up" in ceiling.lower()
    # The ceiling verdict must point at the lever that actually helps.
    assert ENV_TIMEOUT_FLOOR in ceiling


def test_the_ceiling_message_survives_the_counter_reset_that_produced_it():
    """diagnose() clears the counter on its way to the verdict.

    A message defaulting to the live counter would therefore report "0 requests
    in a row" in exactly the case it exists to explain.
    """
    for _ in range(provider_storm.STORM_THRESHOLD):
        provider_storm.record_timeout(1200)

    assert provider_storm.diagnose(lambda: True) == "ceiling"
    assert not provider_storm.is_storm(), "the counter is cleared by the verdict"

    ceiling = provider_storm.ceiling_message()
    assert str(provider_storm.STORM_THRESHOLD) in ceiling
    assert "1200" in ceiling
    assert "0 requests" not in ceiling
