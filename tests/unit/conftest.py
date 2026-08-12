"""Shared fixtures for unit tests."""

import sys
from dataclasses import dataclass, field
from unittest.mock import patch

import pytest


@dataclass
class _FakePreflightResult:
    passed: bool = True
    available_credentials: int = 1
    total_credentials: int = 1
    exhausted_names: list[str] = field(default_factory=list)
    model_reachable: bool = True
    warnings: list[str] = field(default_factory=list)


@pytest.fixture(autouse=True)
def _bypass_gemini_preflight():
    """Unit tests never depend on real Gemini credentials."""
    with patch(
        "assemblyzero.core.preflight.check_gemini_available",
        return_value=_FakePreflightResult(),
    ):
        yield


@pytest.fixture(autouse=True)
def _bypass_box_health_preflight():
    """Unit tests never depend on the health of the machine running them (#2248).

    `speedrun_roll.main()` runs the real #1920 preflight, which reads live memory
    with psutil and refuses above 90%, and then spends a full pytest subprocess on
    the canary. So a test's verdict became a statement about how loaded the box
    was: two concurrent `pytest tests/unit -k speedrun` runs failed 16 and 17
    tests, each alone passed, and the failing set differed every time because the
    second pytest process was itself the load.

    That is the no-false-alarms rule turned on the suite. The gate is right and
    must stay right for real rolls -- what was missing is the test's isolation --
    so this stubs the gate rather than loosening it. Ruling the noise out cost
    about fifteen minutes of control runs while shipping #2234.

    Autouse rather than a per-file `patch.object` because three of the seven
    speedrun test files already stubbed it by hand and four did not: the eighth
    file, written next month, would forget too.

    `test_box_health.py` is deliberately unaffected -- it imports
    `check_box_health` from `assemblyzero.speedrun.box_health` directly, and this
    rebinds only the name `speedrun_roll` calls through.
    """
    module = sys.modules.get("speedrun_roll")
    if module is None:
        # Nothing in this session imports the launcher. Test modules are imported
        # at collection, before any fixture runs, so absence here is real.
        yield
        return

    from assemblyzero.speedrun.box_health import BoxHealth

    with patch.object(
        module, "check_box_health", lambda *a, **k: BoxHealth(True, [], "")
    ):
        yield
