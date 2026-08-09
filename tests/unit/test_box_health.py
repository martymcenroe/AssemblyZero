"""Acceptance tests for the degraded-box launch gate (#1920).

The seven tests named in the issue body are the acceptance criteria.

The canary and the resource reader are both injected, so no test depends on the
health of the machine running it -- which would make this suite the very thing
it is meant to detect.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_roll  # noqa: E402

from assemblyzero.speedrun.box_health import (  # noqa: E402
    CANARY_CEILING_SECONDS,
    ROLLING_WINDOW,
    check_box_health,
    health_file,
    nominal_from,
    read_samples,
    record_sample,
    run_canary,
)

HEALTHY_RESOURCES = (
    {"memory in use": 60.0, "running programs": 320.0, "console windows": 4.0},
    [],
)


def _canary(seconds=None, problem=""):
    def canary(_az_root, **_kw):
        return seconds, problem
    return canary


def _resources(values=None, unreadable=None):
    def reader():
        return (values if values is not None else HEALTHY_RESOURCES[0]), (unreadable or [])
    return reader


# --- "healthy box: preflight passes and the roll proceeds" ---------------


def test_healthy_box_passes(tmp_path):
    record_sample(tmp_path, 1.0)

    health = check_box_health(
        tmp_path, tmp_path, canary=_canary(1.1), resources=_resources()
    )

    assert health.ok
    assert health.failures == []
    assert health.message == ""


# --- "canary >3x nominal: exit 91, names measured and nominal" -----------


def test_canary_over_three_times_nominal_fails_and_names_both(tmp_path):
    for _ in range(3):
        record_sample(tmp_path, 2.0)

    health = check_box_health(
        tmp_path, tmp_path, canary=_canary(6.5), resources=_resources()
    )

    assert not health.ok
    failure = health.failures[0]
    assert failure.value == 6.5
    assert failure.nominal == 2.0
    assert "6.5" in health.message and "2.0" in health.message


def test_canary_exactly_at_the_multiplier_still_passes(tmp_path):
    record_sample(tmp_path, 2.0)
    health = check_box_health(
        tmp_path, tmp_path, canary=_canary(6.0), resources=_resources()
    )
    assert health.ok, "the threshold is 'more than 3x', not '3x or more'"


# --- "a slow first run earns a retry, not a refusal" (#2141) --------------


def _canary_sequence(*results):
    """A canary whose consecutive calls replay `results`, counting calls."""
    calls = {"n": 0}

    def canary(_az_root, **_kw):
        result = results[min(calls["n"], len(results) - 1)]
        calls["n"] += 1
        return result

    canary.calls = calls
    return canary


def test_a_cold_first_run_passes_when_the_retry_is_fast(tmp_path):
    """The live 2026-08-09 false positive: idle machine, warm-only nominal,
    first launch in days pays cold caches and AV rescans once. The retry is
    warm and must clear the box."""
    for _ in range(3):
        record_sample(tmp_path, 2.0)

    health = check_box_health(
        tmp_path, tmp_path,
        canary=_canary_sequence((6.5, ""), (2.1, "")),
        resources=_resources(),
    )

    assert health.ok, "a cold start is not a sick machine"
    assert read_samples(tmp_path)[-1] == 2.1, (
        "the WARM measurement feeds the nominal; recording the cold 6.5 "
        "would loosen the threshold the retry just defended"
    )


def test_slow_twice_blocks_and_names_both_measurements(tmp_path):
    for _ in range(3):
        record_sample(tmp_path, 2.0)

    health = check_box_health(
        tmp_path, tmp_path,
        canary=_canary_sequence((6.5, ""), (7.0, "")),
        resources=_resources(),
    )

    assert not health.ok
    assert health.failures[0].value == 7.0
    assert "6.5" in health.message and "7.0" in health.message
    assert "cold start" in health.message


def test_a_passing_first_run_spends_exactly_one_canary(tmp_path):
    record_sample(tmp_path, 2.0)
    canary = _canary_sequence((2.2, ""))

    health = check_box_health(
        tmp_path, tmp_path, canary=canary, resources=_resources()
    )

    assert health.ok
    assert canary.calls["n"] == 1, "the retry is for suspects, not for everyone"


def test_a_retry_that_cannot_be_timed_blocks(tmp_path):
    record_sample(tmp_path, 2.0)

    health = check_box_health(
        tmp_path, tmp_path,
        canary=_canary_sequence((6.5, ""), (None, "the quick self-check died")),
        resources=_resources(),
    )

    assert not health.ok
    assert "the quick self-check died" in health.message


# --- "canary that never completes aborts at the ceiling" -----------------


def test_canary_timeout_aborts_and_does_not_hang(tmp_path):
    def hanging(_az_root, ceiling=CANARY_CEILING_SECONDS, **_kw):
        # This is what run_canary returns on subprocess.TimeoutExpired.
        return None, f"the quick self-check did not finish within {ceiling} seconds"

    health = check_box_health(
        tmp_path, tmp_path, canary=hanging, resources=_resources()
    )

    assert not health.ok
    assert "did not finish within" in health.message
    assert str(CANARY_CEILING_SECONDS) in health.message


def test_run_canary_passes_a_timeout_to_the_subprocess(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

    monkeypatch.setattr(subprocess, "run", fake_run)

    seconds, problem = run_canary(tmp_path, ceiling=7)

    assert captured["timeout"] == 7, "without a timeout a hung canary hangs the launcher"
    assert seconds is None and "7 seconds" in problem


def test_run_canary_reports_a_failing_suite_as_untrustworthy(monkeypatch, tmp_path):
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "boom"),
    )
    seconds, problem = run_canary(tmp_path)
    assert seconds is None and "did not pass" in problem


# --- "memory above the threshold: exit 91, names memory and percentage" --


def test_memory_over_threshold_fails_and_names_the_percentage(tmp_path):
    health = check_box_health(
        tmp_path, tmp_path,
        canary=_canary(1.0),
        resources=_resources({"memory in use": 94.3, "running programs": 300.0}),
    )

    assert not health.ok
    assert "memory in use" in health.message
    assert "94.3" in health.message


def test_memory_is_checked_before_the_canary_is_spent(tmp_path):
    spent = {"canary": False}

    def canary(_az_root, **_kw):
        spent["canary"] = True
        return 1.0, ""

    check_box_health(
        tmp_path, tmp_path, canary=canary,
        resources=_resources({"memory in use": 99.0}),
    )

    assert not spent["canary"], "a box already out of memory must not pay for a canary"


# --- "no stored nominal: the run records one and proceeds" ---------------


def test_missing_baseline_records_one_and_does_not_block(tmp_path):
    assert read_samples(tmp_path) == []

    health = check_box_health(
        tmp_path, tmp_path, canary=_canary(4.2), resources=_resources()
    )

    assert health.ok, "a missing baseline must never block a roll"
    assert read_samples(tmp_path) == [4.2]
    assert health_file(tmp_path).is_file()


def test_nominal_is_a_rolling_median_not_the_last_value(tmp_path):
    for seconds in (1.0, 1.0, 1.0, 1.0, 9.0):
        record_sample(tmp_path, seconds)

    assert nominal_from(read_samples(tmp_path)) == 1.0, (
        "one slow run must not loosen the threshold forever"
    )


def test_rolling_window_is_bounded(tmp_path):
    for i in range(ROLLING_WINDOW + 5):
        record_sample(tmp_path, float(i))
    assert len(read_samples(tmp_path)) == ROLLING_WINDOW


def test_a_corrupt_health_file_is_treated_as_no_baseline(tmp_path):
    health_file(tmp_path).write_text("{not json", encoding="utf-8")

    health = check_box_health(
        tmp_path, tmp_path, canary=_canary(3.0), resources=_resources()
    )

    assert health.ok
    assert read_samples(tmp_path) == [3.0]


def test_recorded_file_is_readable_json(tmp_path):
    record_sample(tmp_path, 2.5)
    data = json.loads(health_file(tmp_path).read_text(encoding="utf-8"))
    assert data["canary_seconds"] == [2.5]
    assert data["nominal_seconds"] == 2.5


# --- "a metric that cannot be read: exit 91, names it" -------------------


def test_unreadable_metric_aborts_and_names_it(tmp_path):
    health = check_box_health(
        tmp_path, tmp_path,
        canary=_canary(1.0),
        resources=_resources({"running programs": 300.0}, ["memory in use"]),
    )

    assert not health.ok, "unknown is not healthy"
    assert "memory in use" in health.message
    assert "could not be read" in health.message


def test_missing_psutil_is_unreadable_not_healthy(monkeypatch, tmp_path):
    import builtins

    real_import = builtins.__import__

    def no_psutil(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("no psutil")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_psutil)

    from assemblyzero.speedrun.box_health import snapshot_resources

    values, unreadable = snapshot_resources()
    assert values == {}
    assert "memory in use" in unreadable


# --- "the abort message contains no internal identifiers" ----------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"canary": _canary(9.0), "resources": _resources()},
        {"canary": _canary(1.0), "resources": _resources({"memory in use": 99.0})},
        {"canary": _canary(None, "the quick self-check did not finish within 120 seconds"),
         "resources": _resources()},
        {"canary": _canary(1.0),
         "resources": _resources({"running programs": 1.0}, ["memory in use"])},
    ],
)
def test_abort_messages_are_plain_english(tmp_path, kwargs):
    record_sample(tmp_path, 1.0)
    health = check_box_health(tmp_path, tmp_path, **kwargs)

    assert not health.ok
    lowered = health.message.lower()
    for jargon in ("psutil", "canary", "nominal", "preflight", "conpty",
                   "#1920", "#2007", "exit 91", "metric", "threshold",
                   "virtual_memory", "subprocess"):
        assert jargon not in lowered, f"{jargon!r} is internal jargon"

    assert "machine" in lowered


# --- launcher wiring ------------------------------------------------------


@pytest.fixture
def target_repo(tmp_path) -> Path:
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@e.com"],
                 ["config", "user.name", "T"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True)
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "b"], capture_output=True)
    return tmp_path


def test_launcher_refuses_on_a_degraded_box(monkeypatch, target_repo, capsys):
    from assemblyzero.speedrun.box_health import BoxHealth, Metric

    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda _r: [])
    rolled = []
    monkeypatch.setattr(
        speedrun_roll, "roll_issue", lambda *a: rolled.append(a) or 0
    )
    monkeypatch.setattr(
        speedrun_roll, "check_box_health",
        lambda *_a, **_k: BoxHealth(
            False, [Metric("memory in use", 99.0, ok=False)],
            "BLOCKED: this machine is not healthy enough to run right now.",
        ),
    )

    code = speedrun_roll.main(
        ["--repo", str(target_repo), "--issue", "4",
         "--log-dir", str(target_repo / "logs")]
    )

    assert code == 91
    assert rolled == [], "nothing may be spent on a degraded box"
    assert "not healthy" in capsys.readouterr().out


def test_launcher_health_check_runs_before_the_detach_handoff(monkeypatch, target_repo):
    from assemblyzero.speedrun.box_health import BoxHealth, Metric

    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda _r: [])
    detached = []
    monkeypatch.setattr(
        speedrun_roll, "launch_detached", lambda *a: detached.append(a) or 0
    )
    monkeypatch.setattr(
        speedrun_roll, "check_box_health",
        lambda *_a, **_k: BoxHealth(False, [Metric("memory in use", 99.0, ok=False)], "BLOCKED"),
    )

    code = speedrun_roll.main(
        ["--repo", str(target_repo), "--issue", "4", "--detach",
         "--log-dir", str(target_repo / "logs")]
    )

    assert code == 91
    assert detached == [], "otherwise the refusal lands in a task nobody watches"


# --- the canary suite itself ---------------------------------------------


def test_the_canary_suite_exists_and_passes():
    """If this file goes missing every roll on the fleet blocks."""
    root = Path(__file__).resolve().parents[2]
    canary_path = root / "tests" / "canary" / "test_box_canary.py"
    assert canary_path.is_file(), "the health check times this file by path"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(canary_path), "-q", "--no-header"],
        cwd=str(root), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=CANARY_CEILING_SECONDS,
    )
    assert result.returncode == 0, result.stdout + result.stderr
