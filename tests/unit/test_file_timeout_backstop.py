"""#2843: the per-file wall clock is a backstop, not a limit on productive output.

Run 15 (2026-09-05) lost two streaming calls in one green iteration to the
1200 s wall clock -- "timed out after 1200s while still producing output
(1804 events)". The idle timeout kills a dead call; the wall clock's job is
the outer bound, and it now sits at an hour.
"""

from __future__ import annotations

from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
    ENV_TIMEOUT_CAP,
    ENV_TIMEOUT_FLOOR,
    FILE_TIMEOUT_CAP,
    FILE_TIMEOUT_FLOOR,
    compute_dynamic_timeout as calculate_timeout,
)


def test_the_default_is_an_hour(monkeypatch):
    monkeypatch.delenv(ENV_TIMEOUT_FLOOR, raising=False)
    monkeypatch.delenv(ENV_TIMEOUT_CAP, raising=False)
    assert FILE_TIMEOUT_FLOOR == 3600
    assert FILE_TIMEOUT_CAP == 3600
    assert calculate_timeout("tiny") == 3600
    assert calculate_timeout("x" * 500_000) == 3600


def test_the_two_run_15_calls_would_have_been_allowed_to_finish(monkeypatch):
    """Both were killed at 1200 s while streaming; neither reaches the new bound."""
    monkeypatch.delenv(ENV_TIMEOUT_FLOOR, raising=False)
    monkeypatch.delenv(ENV_TIMEOUT_CAP, raising=False)
    for killed_at in (1200, 1200):
        assert killed_at < calculate_timeout("a green-iteration edit prompt")


def test_the_overrides_still_apply(monkeypatch):
    monkeypatch.setenv(ENV_TIMEOUT_FLOOR, "100")
    monkeypatch.setenv(ENV_TIMEOUT_CAP, "100")
    assert calculate_timeout("tiny") == 100
    monkeypatch.setenv(ENV_TIMEOUT_FLOOR, "7200")
    monkeypatch.delenv(ENV_TIMEOUT_CAP, raising=False)
    # A cap below an operator's floor never undoes the floor.
    assert calculate_timeout("tiny") == 7200
