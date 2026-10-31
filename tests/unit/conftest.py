"""Shared fixtures for unit tests."""

import os
import sys
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

# #3708: the unit tier runs LangGraph's serializer in the strict mode it has
# announced as the future default, so a new unregistered type in a checkpoint
# fails a test here instead of printing a warning on every run and breaking on
# the next dependency bump. Production stays lenient so checkpoints written
# before #3708 still load.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")


@dataclass
class _FakePreflightResult:
    passed: bool = True
    available_credentials: int = 1
    total_credentials: int = 1
    exhausted_names: list[str] = field(default_factory=list)
    model_reachable: bool = True
    warnings: list[str] = field(default_factory=list)


@pytest.fixture(autouse=True)
def _bypass_gemini_preflight(monkeypatch):
    """Unit tests never depend on real Gemini credentials, and never make the
    real agy probe call (#3506's transport check). The per-process memo is
    reset so no test inherits another's answer.

    The stand-in goes through `monkeypatch`, not `patch()`: a test that sets
    `check_gemini_transport` again with `monkeypatch` is then undone in the
    same stack, in reverse order. With `patch()` the context exited first and
    `monkeypatch` then put the stand-in back for every later test in the
    process (#4239)."""
    from assemblyzero.core import preflight

    monkeypatch.setattr(preflight, "_TRANSPORT_RESULT", None)
    monkeypatch.setattr(
        preflight, "check_gemini_transport",
        MagicMock(return_value=_FakePreflightResult()),
    )
    yield
    preflight._TRANSPORT_RESULT = None


@pytest.fixture(autouse=True)
def _must_resolve_gate_answers_offline():
    """The launcher's open-question gate never calls GitHub in a unit test (#3585).

    Since #3585 the gate refuses the launch when GitHub cannot be asked: under
    ADR 0236 a check that could not run is a failure, never a pass. A unit
    test's target repo has no GitHub remote, so the real
    ``open_must_resolve_issues`` always fails there, and every test that drives
    ``speedrun_roll.main()`` for another reason was refused at the gate. This
    rebinds only the name ``speedrun_roll`` calls, to "GitHub answered, nothing
    open". The gate itself is tested with explicit runners in
    ``test_must_resolve_preflight.py`` and ``test_must_resolve_loud_failure.py``,
    and a test that patches the name still installs its own answer.
    """
    module = sys.modules.get("speedrun_roll")
    if module is None:
        yield
        return

    with patch.object(module, "open_must_resolve_issues", lambda *_a, **_k: ([], None)):
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
