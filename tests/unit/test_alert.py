"""The operator alert path (ADR 0236, #3728)."""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from assemblyzero.core import alert, operator_notify
from assemblyzero.core.alert import AlertDeliveryError, alert_operator, check_alert_channel, resolve_sender

from tests.unit.conftest import RealAlertTransportReached

SENDER = "alerts@example.test"


class _FakeSes:
    def __init__(self, error: Exception | None = None):
        self.calls: list[dict] = []
        self._error = error

    def send_email(self, **kwargs):
        if self._error:
            raise self._error
        self.calls.append(kwargs)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv(alert.SENDER_ENV, raising=False)
    return tmp_path


def _alert(**overrides):
    kwargs = dict(
        what="draft failed",
        where="requirements N1_generate_draft",
        cause="ValueError: unknown provider 'x'",
        consequence="the run halts",
        repo="example/repo",
        issue=42,
        spec="gemini:3.1-pro",
    )
    kwargs.update(overrides)
    return alert_operator(**kwargs)


def test_delivers_email_logs_and_is_loud(home, monkeypatch, capsys):
    monkeypatch.setenv(alert.SENDER_ENV, SENDER)
    ses = _FakeSes()
    with patch("assemblyzero.core.alert._ses_client", return_value=ses):
        record = _alert()

    assert len(ses.calls) == 1
    call = ses.calls[0]
    assert call["FromEmailAddress"] == SENDER
    assert call["Destination"] == {"ToAddresses": [operator_notify.OPERATOR_CONTACT]}
    subject = call["Content"]["Simple"]["Subject"]["Data"]
    assert "draft failed" in subject and "#42" in subject
    assert "ValueError: unknown provider 'x'" in call["Content"]["Simple"]["Body"]["Text"]["Data"]

    lines = (home / ".assemblyzero" / "alerts.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["what"] for line in lines] == ["draft failed"]
    assert record["spec"] == "gemini:3.1-pro"
    assert datetime.fromisoformat(record["time"]).utcoffset() is not None

    err = capsys.readouterr().err
    assert err.startswith("ERROR [ALERT] draft failed -- requirements N1_generate_draft")


def test_no_sender_raises_and_prints_the_undelivered_record(home, capsys):
    with pytest.raises(AlertDeliveryError, match="no alert sender configured"):
        _alert()
    err = capsys.readouterr().err
    assert "NOT DELIVERED" in err
    assert "cause: ValueError: unknown provider 'x'" in err


def test_ses_failure_raises(home, monkeypatch):
    monkeypatch.setenv(alert.SENDER_ENV, SENDER)
    ses = _FakeSes(error=RuntimeError("MessageRejected"))
    with patch("assemblyzero.core.alert._ses_client", return_value=ses):
        with pytest.raises(AlertDeliveryError, match="MessageRejected"):
            _alert()


def test_unwritable_log_raises_after_the_email(home, monkeypatch):
    monkeypatch.setenv(alert.SENDER_ENV, SENDER)
    (home / ".assemblyzero").write_text("not a directory", encoding="utf-8")
    ses = _FakeSes()
    with patch("assemblyzero.core.alert._ses_client", return_value=ses):
        with pytest.raises(AlertDeliveryError, match="alerts log"):
            _alert()
    assert len(ses.calls) == 1


def test_sender_env_wins_over_file(home, monkeypatch):
    (home / ".assemblyzero").mkdir()
    (home / ".assemblyzero" / "alert.json").write_text(json.dumps({"email_from": "file@example.test"}), encoding="utf-8")
    assert resolve_sender() == "file@example.test"
    monkeypatch.setenv(alert.SENDER_ENV, SENDER)
    assert resolve_sender() == SENDER


@pytest.mark.parametrize("content", ["{not json", json.dumps({"email_from": ""}), json.dumps(["x"])])
def test_unusable_sender_file_raises(home, content):
    (home / ".assemblyzero").mkdir()
    (home / ".assemblyzero" / "alert.json").write_text(content, encoding="utf-8")
    with pytest.raises(AlertDeliveryError):
        resolve_sender()


def test_channel_check_needs_a_sender(home):
    with pytest.raises(AlertDeliveryError, match="no alert sender"):
        check_alert_channel(credentials=object())


def test_channel_check_needs_credentials(home, monkeypatch):
    monkeypatch.setenv(alert.SENDER_ENV, SENDER)
    with patch("assemblyzero.core.alert._aws_credentials", return_value=None):
        with pytest.raises(AlertDeliveryError, match="no AWS credentials"):
            check_alert_channel()


def test_channel_check_returns_the_sender(home, monkeypatch):
    monkeypatch.setenv(alert.SENDER_ENV, SENDER)
    assert check_alert_channel(credentials=object()) == SENDER


def test_the_unit_tier_cannot_reach_real_ses(home, monkeypatch):
    monkeypatch.setenv(alert.SENDER_ENV, SENDER)
    with pytest.raises(RealAlertTransportReached):
        _alert()


def test_a_failed_email_still_toasts_on_windows(home, monkeypatch, capsys):
    """#3581 core batch 1: every channel is attempted, and every failure is printed."""
    monkeypatch.setenv(alert.SENDER_ENV, SENDER)
    monkeypatch.setattr(alert.sys, "platform", "win32")
    toasts: list[tuple] = []

    def fake_toast(title, body, url="", *, runner=None, platform=None):
        toasts.append((title, body))
        return "toast failed (exit 1): no notifier"

    ses = _FakeSes(error=RuntimeError("MessageRejected"))
    with patch("assemblyzero.core.alert._ses_client", return_value=ses), \
            patch("assemblyzero.core.alert._toast_runner", return_value=None), \
            patch.object(operator_notify, "show_toast", fake_toast), \
            pytest.raises(AlertDeliveryError, match="toast"):
        _alert()
    assert len(toasts) == 1
    err = capsys.readouterr().err
    assert "toast failed" in err and "MessageRejected" in err
