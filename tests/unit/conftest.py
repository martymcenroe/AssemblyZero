"""Shared fixtures for unit tests."""

import os
import sys
from dataclasses import dataclass, field
from unittest.mock import patch

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
def _bypass_gemini_preflight():
    """Unit tests never depend on real Gemini credentials, and never make the
    real agy probe call (#3506's transport check). The per-process memo is
    reset so no test inherits another's answer."""
    from assemblyzero.core import preflight

    preflight._TRANSPORT_RESULT = None
    with patch(
        "assemblyzero.core.preflight.check_gemini_transport",
        return_value=_FakePreflightResult(),
    ):
        yield
    preflight._TRANSPORT_RESULT = None


class RealAlertTransportReached(BaseException):
    """A unit test reached SES or the toast runner for real (#3728).

    BaseException, not Exception: ``alert_operator`` catches ``Exception``
    around the send to report it, and that must not swallow this.
    """


def _refuse_real_alert_transport(*_args, **_kwargs):
    raise RealAlertTransportReached(
        "a unit test reached the real alert transport; inject a fake SES client "
        "by patching assemblyzero.core.alert._ses_client"
    )


@pytest.fixture(autouse=True)
def _no_real_alert_transport():
    """The unit tier never emails the operator or raises a real toast (#3728).

    ``alert_operator`` builds its SES client and toast runner through two
    module functions; both are replaced here with one that fails the test, so
    a failure path reached in a test cannot send real mail. A test of the
    alert path patches ``_ses_client`` with its own fake inside this.
    """
    with patch(
        "assemblyzero.core.alert._ses_client", _refuse_real_alert_transport
    ), patch(
        "assemblyzero.core.alert._toast_runner", _refuse_real_alert_transport
    ):
        yield


@pytest.fixture(autouse=True)
def operator_alerts(request):
    """Every ``alert_operator`` call a test makes, recorded instead of sent (#3724).

    Failure paths now alert (the HALT node does on every halt), so the unit tier
    replaces ``assemblyzero.core.alert.alert_operator`` with a recorder: no
    stderr record, no alerts log under the real home, no SES client. A test
    asserts on the list by naming this fixture. ``test_alert.py`` is exempt: it
    tests the real function, with fake transports.
    """
    if request.module.__name__.endswith("test_alert"):
        yield None
        return
    calls: list[dict] = []

    def record(**kwargs):
        calls.append(kwargs)
        return kwargs

    with patch("assemblyzero.core.alert.alert_operator", record):
        yield calls


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
