"""Acceptance tests for provider-storm detection and backoff (#2086).

The eight tests named in the issue body are the acceptance criteria.

The shape being prevented: 2026-08-01, `claude -p timed out after 602s`
eighteen times in one roll. Each failed attempt self-healed and redrew straight
into the same wall, so with `--attempts 8` a storm could legally consume a day.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_roll  # noqa: E402

from assemblyzero.core import provider_storm  # noqa: E402
from assemblyzero.core.provider_storm import (  # noqa: E402
    BACKOFF_MINUTES,
    STORM_EXIT_CODE,
    STORM_THRESHOLD,
    backoff_minutes,
    is_storm,
    record_success,
    record_timeout,
    storm_message,
)


@pytest.fixture(autouse=True)
def _clean_counter():
    provider_storm.reset()
    yield
    provider_storm.reset()


# --- "three consecutive timeouts storm; a success resets" ---------------


def test_three_consecutive_timeouts_is_a_storm():
    assert not is_storm()
    record_timeout(602)
    assert not is_storm(), "one timeout is bad luck"
    record_timeout(602)
    assert not is_storm(), "two is still not a wall"
    count = record_timeout(602)

    assert count == STORM_THRESHOLD
    assert is_storm()


def test_a_success_between_timeouts_resets_the_counter():
    record_timeout(602)
    record_timeout(602)
    record_success()
    record_timeout(602)
    record_timeout(602)

    assert not is_storm(), "two, a success, then two more is not a storm"
    assert provider_storm.consecutive_timeouts() == 2


def test_the_counter_keeps_climbing_past_the_threshold():
    for _ in range(18):  # the 2026-08-01 shape
        record_timeout(602)
    assert provider_storm.consecutive_timeouts() == 18
    assert is_storm()


# --- "non-timeout provider errors never trip the counter" ---------------


def test_non_timeout_errors_do_not_trip_the_storm_counter(monkeypatch, tmp_path):
    """Only the timeout path calls record_timeout; a CLI error must not."""
    import inspect

    from assemblyzero.core import llm_provider

    source = inspect.getsource(llm_provider)
    timeout_block = source[source.index("except subprocess.TimeoutExpired"):]
    timeout_block = timeout_block[: timeout_block.index("return call_result")]

    assert "record_timeout" in timeout_block, "the timeout path must count"

    # And the non-zero-returncode path must not.
    rc_block = source[source.index("if proc.returncode != 0:"):]
    rc_block = rc_block[:2000]
    assert "record_timeout" not in rc_block, (
        "a 400 is a bug in what we sent; waiting fifteen minutes would not help"
    )


def test_only_completed_calls_clear_the_counter():
    record_timeout(602)
    record_timeout(602)
    assert provider_storm.consecutive_timeouts() == 2
    record_success()
    assert provider_storm.consecutive_timeouts() == 0


# --- "backoff sequence is 15, 30, 60, 60 (the cap holds)" ---------------


def test_backoff_sequence_and_cap():
    assert [backoff_minutes(n) for n in (1, 2, 3, 4)] == [15, 30, 60, 60]
    assert backoff_minutes(9) == 60, "the cap holds rather than doubling"
    assert BACKOFF_MINUTES == (15, 30, 60)


def test_backoff_of_a_non_storm_attempt_is_zero():
    assert backoff_minutes(0) == 0
    assert backoff_minutes(-1) == 0


# --- "a storm attempt delays; a non-storm failure redraws immediately" ---


@pytest.fixture
def target_repo(tmp_path) -> Path:
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@e.com"],
                 ["config", "user.name", "T"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True)
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "b"], capture_output=True)
    return tmp_path


@pytest.fixture
def launcher(monkeypatch, target_repo):
    """speedrun_roll.main with the gates stubbed and sleeps recorded."""
    from assemblyzero.speedrun.box_health import BoxHealth

    state = {"slept": [], "codes": [], "attempts": 0}

    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda _r: [])
    monkeypatch.setattr(speedrun_roll, "check_box_health",
                        lambda *_a, **_k: BoxHealth(True, [], ""))
    monkeypatch.setattr(speedrun_roll, "open_must_resolve_issues", lambda _r: ([], None))
    monkeypatch.setattr(speedrun_roll, "sweep_pipeline_worktrees",
                        lambda *_a, **_k: type("S", (), {"problems": []})())
    monkeypatch.setattr(speedrun_roll, "install_signal_handlers", lambda _s: None)
    monkeypatch.setattr(speedrun_roll, "restore_repo", lambda *_a, **_k: [])
    monkeypatch.setattr(speedrun_roll, "_interruptible_sleep",
                        lambda seconds, tick=5: state["slept"].append(seconds))
    monkeypatch.setattr(speedrun_roll.time, "sleep", lambda _s: None)

    def fake_roll(repo_root, issue, log_dir, az_root, extra):
        state["attempts"] += 1
        return state["codes"].pop(0) if state["codes"] else 1

    monkeypatch.setattr(speedrun_roll, "roll_issue", fake_roll)
    return state


def _argv(repo, attempts=1):
    return ["--repo", str(repo), "--issue", "4", "--attempts", str(attempts),
            "--log-dir", str(repo / "logs")]


def test_a_storm_ends_the_issue_without_waiting(launcher, target_repo):
    """#2206: with one roll per issue there is nothing to back off FOR. The
    wait existed to keep the next redraw off the same wall; with no next
    redraw, waiting only delays the operator learning the provider is down."""
    launcher["codes"] = [STORM_EXIT_CODE, 0]

    code = speedrun_roll.main(_argv(target_repo))

    assert launcher["slept"] == [], "no redraw to protect, so no wait"
    assert code == STORM_EXIT_CODE


def test_a_non_storm_failure_also_ends_the_issue(launcher, target_repo):
    launcher["codes"] = [1, 0]

    code = speedrun_roll.main(_argv(target_repo))

    assert launcher["slept"] == []
    assert code == 1


def test_the_storm_is_named_in_the_events_log(launcher, target_repo):
    """A watcher must still be able to tell a dead provider from a dead run."""
    launcher["codes"] = [STORM_EXIT_CODE]

    speedrun_roll.main(_argv(target_repo))

    log = (target_repo / "logs" / "session-events.log").read_text(encoding="utf-8")
    assert "STORM ended #4" in log
    assert "#2206" in log


# --- backoff_minutes remains, as the storm classifier's pure helper ----


def test_backoff_helper_survives_for_future_use():
    """The redraw loop is gone but the escalation curve is still the right
    answer if a bounded wait is ever reintroduced deliberately."""
    assert backoff_minutes(1) == 15
    assert backoff_minutes(4) == 60


# --- "a launcher in backoff is stopped cleanly (no orphaned sleep)" -----


def test_the_backoff_sleep_is_ticked_not_one_long_block(monkeypatch):
    """A single long sleep leaves nothing checking signals between kill and wake."""
    slept: list[int] = []
    monkeypatch.setattr(speedrun_roll.time, "sleep", lambda s: slept.append(s))

    speedrun_roll._interruptible_sleep(60, tick=5)

    assert len(slept) == 12, "the wait is decomposed into ticks"
    assert max(slept) <= 5, "no single blocking call longer than one tick"
    assert sum(slept) == 60


def test_interruptible_sleep_handles_a_signal_between_ticks(monkeypatch):
    """A stop raised inside a tick propagates instead of being swallowed."""
    calls = {"n": 0}

    def exploding(_seconds):
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(speedrun_roll.time, "sleep", exploding)

    with pytest.raises(KeyboardInterrupt):
        speedrun_roll._interruptible_sleep(3600, tick=5)

    assert calls["n"] == 2, "it stopped at the second tick, not after an hour"


def test_zero_and_negative_waits_do_not_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(speedrun_roll.time, "sleep", lambda s: slept.append(s))
    speedrun_roll._interruptible_sleep(0)
    speedrun_roll._interruptible_sleep(-10)
    assert slept == []


# --- "the storm halt message is plain English" --------------------------


def test_storm_message_names_the_count_and_the_duration():
    for _ in range(3):
        record_timeout(602)

    message = storm_message()

    assert "3" in message
    assert "602" in message
    lowered = message.lower()
    assert "provider" in lowered and "no reply" in lowered
    for jargon in ("subprocess", "exit code", "92", "llm_provider",
                   "claude -p", "#2086", "traceback", "stderr"):
        assert jargon not in lowered, f"{jargon!r} is internal jargon"


def test_storm_message_says_the_target_code_is_not_at_fault():
    for _ in range(3):
        record_timeout(602)
    assert "nothing is wrong with the code" in storm_message().lower(), (
        "otherwise a storm reads as a target-repo failure, which is the "
        "evidence-poisoning this family of issues is about"
    )


def test_storm_message_without_a_recorded_duration_still_reads():
    record_timeout(0)
    assert "time limit" in storm_message(count=3, timeout_seconds=0)


# --- exit code plumbing --------------------------------------------------


def test_the_storm_exit_code_is_distinct_from_the_others():
    assert STORM_EXIT_CODE not in (0, 1, 91, 130), (
        "the launcher tells a storm from every other outcome by this number"
    )


def test_orchestrate_exits_with_the_storm_code():
    import inspect

    import orchestrate

    source = inspect.getsource(orchestrate.main)
    assert "provider_storm.is_storm()" in source
    assert "STORM_EXIT_CODE" in source


def test_launcher_reads_the_storm_code_not_a_text_marker():
    import inspect

    source = inspect.getsource(speedrun_roll.main)
    assert "STORM_EXIT_CODE" in source
    # `storm_streak` went with the redraw loop (#2206) — with one roll per
    # issue there is no streak to count. Classification by exit code rather
    # than by scraping prose is what this test actually protects.
    assert "code == STORM_EXIT_CODE" in source
