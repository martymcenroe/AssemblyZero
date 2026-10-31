"""operator_notify.py under standard 0034, one test per sweep site (#3783).

These are the alert path's transports. A toast or an email that does not reach
the operator raises ``AlertDeliveryError``, never a reason string a caller may
drop; ``alert_operator`` then prints the undelivered record and raises, so the
process exits non-zero. A toast asked for on a host that is not Windows is an
ERROR line: there is no toast on that host, and the email is its channel. Line
numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import inspect
import sys

import pytest

from assemblyzero.core import alert, operator_notify
from assemblyzero.core.alert import AlertDeliveryError
from assemblyzero.core.alert import alert_operator as real_alert_operator
from assemblyzero.core.operator_notify import EMAIL_FROM_ENV, send_email, show_toast

SENDER = "alerts@example.test"


class _Done:
    def __init__(self, returncode=0, stderr="", stdout=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


class _Ses:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.sent: list[dict] = []

    def send_email(self, **kwargs):
        if self.error:
            raise self.error
        self.sent.append(kwargs)
        return {"MessageId": "m-1"}


def _forbidden(cmd, **kwargs):
    raise AssertionError("nothing must spawn off Windows")


class TestTheToast:
    def test_183_a_non_windows_host_is_an_error_line_and_spawns_nothing(
        self, capsys, caplog, operator_alerts
    ):
        result = show_toast("Visual gate awaiting you", "b", runner=_forbidden, platform="linux")

        assert result is None
        err = capsys.readouterr().err
        assert "ERROR [NOTIFY]" in err
        assert "Visual gate awaiting you" in err
        assert "linux" in err
        assert any(r.levelname == "ERROR" for r in caplog.records)
        assert operator_alerts == []

    def test_199_a_toast_that_cannot_be_spawned_raises(self):
        def runner(cmd, **kwargs):
            raise OSError("powershell missing")

        with pytest.raises(AlertDeliveryError, match="powershell missing") as raised:
            show_toast("t", "b", runner=runner, platform="win32")
        assert "OSError" in str(raised.value)
        assert isinstance(raised.value.__cause__, OSError)

    def test_205_a_toast_that_exits_nonzero_raises(self):
        def runner(cmd, **kwargs):
            return _Done(returncode=1, stderr="no notifier registered")

        with pytest.raises(AlertDeliveryError, match="exit 1") as raised:
            show_toast("t", "b", runner=runner, platform="win32")
        assert "no notifier registered" in str(raised.value)

    def test_a_toast_that_works_returns_nothing(self):
        """Kept: success is quiet."""
        assert not show_toast("t", "b", runner=lambda cmd, **k: _Done(), platform="win32")


class TestTheEmail:
    def test_231_no_sender_raises(self):
        with pytest.raises(AlertDeliveryError, match="no sender identity configured") as raised:
            send_email(sender="", to="x@y", subject="s", text_body="b")
        assert EMAIL_FROM_ENV in str(raised.value)

    def test_255_a_failing_send_raises(self):
        with pytest.raises(AlertDeliveryError, match="SES says no") as raised:
            send_email(
                sender=SENDER, to="x@y", subject="s", text_body="b",
                client=_Ses(error=RuntimeError("SES says no")),
            )
        assert "RuntimeError" in str(raised.value)
        assert SENDER in str(raised.value)
        assert isinstance(raised.value.__cause__, RuntimeError)

    def test_a_send_that_works_returns_nothing(self):
        """Kept: success is quiet."""
        ses = _Ses()
        assert not send_email(sender=SENDER, to="x@y", subject="s", text_body="b", client=ses)
        assert len(ses.sent) == 1


def test_200_256_no_fail_open_tag_remains():
    assert "fail-open" not in inspect.getsource(operator_notify)


class TestThroughTheAlertPath:
    """When the thing that reports a failure fails: the real alert_operator
    over these transports prints the undelivered record and raises."""

    @pytest.fixture
    def home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv(alert.SENDER_ENV, SENDER)
        return tmp_path

    def _alert(self):
        return real_alert_operator(
            what="draft failed", where="requirements N1", cause="ValueError: x",
            consequence="the run halts", issue=42,
        )

    def test_a_failed_send_is_undelivered_and_raises(self, home, monkeypatch, capsys):
        monkeypatch.setattr(alert, "_ses_client", lambda: _Ses(error=RuntimeError("MessageRejected")))

        with pytest.raises(AlertDeliveryError, match="MessageRejected"):
            self._alert()
        err = capsys.readouterr().err
        assert "NOT DELIVERED" in err
        assert (home / ".assemblyzero" / "alerts.jsonl").is_file(), "the record is still logged"

    def test_a_failed_toast_on_windows_is_undelivered_and_raises(
        self, home, monkeypatch, capsys
    ):
        ses = _Ses()
        monkeypatch.setattr(alert, "_ses_client", lambda: ses)
        monkeypatch.setattr(
            alert, "_toast_runner",
            lambda: (lambda cmd, **k: _Done(returncode=1, stderr="no notifier")),
        )
        with monkeypatch.context() as windows:
            windows.setattr(sys, "platform", "win32")
            with pytest.raises(AlertDeliveryError, match="no notifier"):
                self._alert()
        err = capsys.readouterr().err
        assert "NOT DELIVERED" in err
        assert len(ses.sent) == 1, "the email is still sent"
