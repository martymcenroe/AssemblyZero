"""A broken stderr does not stop the alert (#4247).

``alert_operator`` wrote its record to ``sys.stderr`` first, unprotected, so a
closed pipe or a detached console raised before the email and the alerts log
were attempted: the moment the process's own output is gone, the alert reached
no one. Writing to stderr is now one step like the others. Every step is
attempted, and the failures are raised together as ``AlertDeliveryError``.

``alert_operator`` is imported before the unit tier's ``operator_alerts``
fixture replaces it, so these tests drive the real function; the SES client is
a fake, as in ``test_alert.py``.
"""
from __future__ import annotations

import json
import sys

import pytest

from assemblyzero.core import alert
from assemblyzero.core.alert import AlertDeliveryError
from assemblyzero.core.alert import alert_operator as real_alert_operator

SENDER = "alerts@example.test"


class _FakeSes:
    def __init__(self, error: Exception | None = None):
        self.calls: list[dict] = []
        self._error = error

    def send_email(self, **kwargs):
        if self._error:
            raise self._error
        self.calls.append(kwargs)


class _BrokenStream:
    def __init__(self, error: Exception):
        self.error = error

    def write(self, text):
        raise self.error

    def flush(self):
        raise self.error


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv(alert.SENDER_ENV, SENDER)
    return tmp_path


def _logged(home) -> list[dict]:
    log = home / ".assemblyzero" / "alerts.jsonl"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def _alert():
    return real_alert_operator(
        what="draft failed", where="requirements N1", cause="ValueError: x",
        consequence="the run halts", issue=42,
    )


@pytest.mark.parametrize(
    "broken",
    [
        _BrokenStream(OSError(32, "Broken pipe")),
        _BrokenStream(ValueError("I/O operation on closed file.")),
        None,
    ],
    ids=["broken-pipe", "closed", "none"],
)
def test_t1_a_broken_stderr_still_emails_and_logs_then_raises(home, monkeypatch, broken):
    ses = _FakeSes()
    monkeypatch.setattr(alert, "_ses_client", lambda: ses)
    monkeypatch.setattr(sys, "stderr", broken)

    with pytest.raises(AlertDeliveryError, match="stderr"):
        _alert()

    assert len(ses.calls) == 1, "the email is still sent"
    assert [r["what"] for r in _logged(home)] == ["draft failed"], "and the log written"


def test_t1_a_broken_stderr_and_a_failed_email_are_both_raised(home, monkeypatch):
    monkeypatch.setattr(alert, "_ses_client", lambda: _FakeSes(error=RuntimeError("MessageRejected")))
    monkeypatch.setattr(sys, "stderr", _BrokenStream(OSError(32, "Broken pipe")))

    with pytest.raises(AlertDeliveryError) as raised:
        _alert()

    chain = []
    error: BaseException | None = raised.value
    while error is not None:
        chain.append(str(error))
        error = error.__context__
    said = " | ".join(chain)
    assert "stderr" in said and "MessageRejected" in said
    assert [r["what"] for r in _logged(home)] == ["draft failed"]


def test_t2_a_working_stderr_is_unchanged(home, monkeypatch, capsys):
    ses = _FakeSes()
    monkeypatch.setattr(alert, "_ses_client", lambda: ses)

    record = _alert()

    err = capsys.readouterr().err
    assert err.startswith("ERROR [ALERT] draft failed -- requirements N1: ValueError: x\n")
    assert "consequence: the run halts" in err
    assert "NOT DELIVERED" not in err
    assert len(ses.calls) == 1
    assert record["what"] == "draft failed"
    assert [r["what"] for r in _logged(home)] == ["draft failed"]


def test_t2_an_undelivered_email_is_still_reported_on_a_working_stderr(home, monkeypatch, capsys):
    monkeypatch.setattr(alert, "_ses_client", lambda: _FakeSes(error=RuntimeError("MessageRejected")))

    with pytest.raises(AlertDeliveryError, match="MessageRejected"):
        _alert()

    err = capsys.readouterr().err
    assert "NOT DELIVERED" in err and "MessageRejected" in err
