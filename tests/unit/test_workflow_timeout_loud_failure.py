"""A workflow that runs out of wall clock alerts the operator before it exits (ADR 0236, #3585).

``WorkflowTimeout`` ends a stuck run with ``os._exit(42)`` from a timer thread,
because the main thread may be blocked where an exception cannot reach it. It
printed a banner to stderr and exited, and never reached ``alert_operator``, so
a run that died on its timeout told nobody who was not watching the console.
The timer now alerts first, with the limit and whatever issue and workflow the
runner named, and exits 42 even when the alert itself cannot be delivered.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import os

import pytest

from assemblyzero.core import alert
from assemblyzero.utils.workflow_timeout import WorkflowTimeout


class _Exited(Exception):
    pass


@pytest.fixture
def exits(monkeypatch):
    codes: list[int] = []

    def _exit(code):
        codes.append(code)
        raise _Exited(code)

    monkeypatch.setattr(os, "_exit", _exit)
    return codes


def _expire(timeout: WorkflowTimeout) -> None:
    # The handler the timer thread runs, called on this thread.
    with pytest.raises(_Exited):
        timeout._expire()


def test_74_the_timeout_alerts_before_it_exits(exits, operator_alerts, capsys):
    _expire(WorkflowTimeout(minutes=90, issue=7, workflow="lld"))

    assert exits == [42]
    assert len(operator_alerts) == 1
    record = operator_alerts[0]
    assert "90-minute" in record["cause"]
    assert "lld" in record["where"]
    assert record["issue"] == 7
    assert "exits 42" in record["consequence"]
    assert "[TIMEOUT]" in capsys.readouterr().err


def test_74_the_timeout_still_exits_when_the_alert_cannot_be_delivered(exits, monkeypatch, capsys):
    def _undeliverable(**_kwargs):
        raise alert.AlertDeliveryError("no SES credentials")

    monkeypatch.setattr(alert, "alert_operator", _undeliverable)

    _expire(WorkflowTimeout(minutes=5))

    assert exits == [42]


def test_a_disabled_timeout_arms_nothing(operator_alerts):
    with WorkflowTimeout(minutes=0) as timeout:
        assert timeout._timer is None
    assert operator_alerts == []
