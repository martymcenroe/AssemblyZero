"""The cascade detector's latency budget: 5 ms a call on average (#358, REQ-6).

Moved here from ``tests/unit/test_cascade_detector.py`` (#4190, #3731). A
wall-clock bound measures the machine as much as the code: on WSL the unit
tier's copy failed under full-suite load and passed alone, and failed alone in
one worktree while passing in another the same minute. A check that fails on
load alone cannot gate merges, so the unit tier now asserts what the code
controls (detection's cost against the bare scan of its own patterns, and
linear growth with input size), and the budget itself lives in this benchmark
tier, for a run with nothing else in flight:

    poetry run pytest tests/benchmark -m benchmark -p no:cacheprovider

``benchmark`` is deselected by the default ``addopts`` in ``pyproject.toml``,
so no tier runs these unless asked, and CI does not.

The calls take the hook's real path, user config included: the default config
is the checkout's tracked copy, read on every call as the hook reads it. On a
checkout under ``/mnt/c`` that read was 2.2 to 3.8 ms of the 5 ms budget,
measured 2026-10-30.
"""
from __future__ import annotations

import time

import pytest

from assemblyzero.hooks import cascade_patterns
from assemblyzero.hooks.cascade_detector import MAX_INPUT_LENGTH, detect_cascade_risk
from tests.checkout_telemetry_guard import CASCADE_CONFIG, CHECKOUT

pytestmark = pytest.mark.benchmark

BUDGET_SECONDS = 0.005
RUNS = 100


@pytest.fixture(autouse=True)
def the_checkouts_own_config(monkeypatch):
    """Undo the suite's redirect of the default config (#4249) for these
    timings only: the hook reads the checkout's copy, so the budget does.
    Reading it changes nothing; the session guard would fail a write."""
    monkeypatch.setattr(cascade_patterns, "_DEFAULT_CONFIG_PATH", CHECKOUT / CASCADE_CONFIG)


def _average_seconds(text: str) -> float:
    total = 0.0
    for _ in range(RUNS):
        start = time.perf_counter()
        detect_cascade_risk(text)
        total += time.perf_counter() - start
    return total / RUNS


def test_t200_typical_input_within_budget() -> None:
    """T200: 2000-char model output."""
    text = ("Here is a summary of the changes I made. " * 50)[:2000]

    average = _average_seconds(text)

    assert average < BUDGET_SECONDS, (
        f"Average detection time {average * 1000:.2f}ms exceeds 5ms limit"
    )


def test_t210_max_input_within_budget() -> None:
    """T210: 10000-char model output (max cap)."""
    text = ("Model output content with various words. " * 250)[:MAX_INPUT_LENGTH]

    average = _average_seconds(text)

    assert average < BUDGET_SECONDS, (
        f"Average detection time {average * 1000:.2f}ms exceeds 5ms limit"
    )
