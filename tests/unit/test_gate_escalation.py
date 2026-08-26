"""Escalating notification while the gate waits — never a timeout (#2529).

"i always have a lot going on so if i get distracted the program could sit
there for days waiting for me." The wait stays infinite — human priority,
fleet hard rule — but it asks louder over time: toasts on a slow backoff,
then ONE backstop email per round, ever, enforced on disk so a resume cannot
re-send it. Every notification failure is a logged line the wait survives.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.core import operator_notify
from assemblyzero.core.operator_notify import (
    EMAIL_FROM_ENV,
    EscalationSchedule,
    NotifyConfig,
    send_email,
    show_toast,
    toast_script,
)
from assemblyzero.visual_gate import bundle as bundle_mod
from assemblyzero.visual_gate.server import EMAIL_SENT_NAME, wait_for_feedback


class TestTheSchedule:
    """Pure timing bookkeeping, driven by plain numbers."""

    def _config(self, **kw) -> NotifyConfig:
        return NotifyConfig(
            toast_backoff_seconds=kw.pop("backoff", (10.0, 30.0, 60.0)),
            email_after_seconds=kw.pop("email_after", 100.0),
            **kw,
        )

    def test_nothing_is_due_before_the_first_interval(self):
        schedule = EscalationSchedule(self._config())
        assert schedule.due(9.9) == []

    def test_the_first_toast_lands_at_the_first_interval(self):
        schedule = EscalationSchedule(self._config())
        assert schedule.due(10.0) == ["toast"]
        assert schedule.due(10.1) == [], "the same toast must not repeat"

    def test_the_backoff_slows_and_the_last_step_repeats_forever(self):
        schedule = EscalationSchedule(self._config())
        assert schedule.due(10.0) == ["toast"]     # first: at 10
        assert schedule.due(39.9) == []
        assert schedule.due(40.0) == ["toast"]     # +30
        assert schedule.due(99.9) == []
        due_100 = schedule.due(100.0)              # +60, and the email is due
        assert "toast" in due_100
        assert schedule.due(160.0) == ["toast"]    # +60 again: last step repeats
        assert schedule.due(220.0) == ["toast"]    # ... forever

    def test_the_email_is_offered_exactly_once(self):
        schedule = EscalationSchedule(self._config(backoff=(1000.0,)))
        assert schedule.due(100.0) == ["email"]
        assert schedule.due(200.0) == []

    def test_disabled_means_silent(self):
        schedule = EscalationSchedule(self._config(enabled=False))
        assert schedule.due(10_000.0) == []

    def test_from_mapping_defaults(self, monkeypatch):
        monkeypatch.delenv(EMAIL_FROM_ENV, raising=False)
        config = NotifyConfig.from_mapping(None)
        assert config.enabled is True
        assert config.toast_backoff_seconds == (600.0, 1800.0, 3600.0)
        assert config.email_after_seconds == 4 * 3600.0
        assert config.email_to == operator_notify.OPERATOR_CONTACT
        assert config.email_from == ""

    def test_from_mapping_env_overrides_the_sender(self, monkeypatch):
        monkeypatch.setenv(EMAIL_FROM_ENV, "gate@verified.example")
        config = NotifyConfig.from_mapping({"email_from": "other@x"})
        assert config.email_from == "gate@verified.example"


class TestTheToast:
    def test_the_script_carries_the_facts_and_the_click_through(self):
        script = toast_script(
            "Visual gate awaiting your review",
            "boostgauge #331, round-001 — waiting 10m",
            "http://127.0.0.1:9999/",
        )
        assert "Visual gate awaiting your review" in script
        assert "boostgauge #331, round-001" in script
        assert 'launch="http://127.0.0.1:9999/"' in script
        assert 'activationType="protocol"' in script
        assert "WindowsPowerShell" in script  # the registered AppId

    def test_the_script_escapes_both_layers(self):
        script = toast_script("a <b> & 'c'", "d", "http://x/?a=1&b=2")
        assert "a &lt;b&gt; &amp; ''c''" in script  # XML then PS single-quote
        assert "a=1&amp;b=2" in script

    def test_show_toast_runs_powershell_windowless(self):
        calls = {}

        def runner(cmd, **kwargs):
            calls["cmd"] = cmd
            calls["kwargs"] = kwargs

            class _Done:
                returncode = 0
                stdout = stderr = ""

            return _Done()

        assert show_toast("t", "b", "http://x/", runner=runner) == ""
        assert calls["cmd"][0] == "powershell"
        assert "-NonInteractive" in calls["cmd"]
        import subprocess
        assert calls["kwargs"]["creationflags"] == getattr(
            subprocess, "CREATE_NO_WINDOW", 0
        ), "a toast must never flash a console window"

    def test_a_failing_toast_is_a_reason_not_a_raise(self):
        def runner(cmd, **kwargs):
            raise OSError("powershell missing")

        reason = show_toast("t", "b", runner=runner)
        assert "toast failed" in reason


class TestTheEmail:
    class _Client:
        def __init__(self, fail=False):
            self.fail = fail
            self.sent: list[dict] = []

        def send_email(self, **kwargs):
            if self.fail:
                raise RuntimeError("SES says no")
            self.sent.append(kwargs)
            return {"MessageId": "m-1"}

    def test_a_send_carries_the_facts(self):
        client = self._Client()
        error = send_email(
            sender="gate@verified.example", to="operator@example.com",
            subject="s", text_body="b", client=client,
        )
        assert error == ""
        [call] = client.sent
        assert call["FromEmailAddress"] == "gate@verified.example"
        assert call["Destination"] == {"ToAddresses": ["operator@example.com"]}

    def test_no_sender_identity_is_a_named_reason(self):
        reason = send_email(sender="", to="x@y", subject="s", text_body="b")
        assert "no sender identity configured" in reason
        assert EMAIL_FROM_ENV in reason

    def test_a_failing_send_is_a_reason_not_a_raise(self):
        reason = send_email(
            sender="gate@verified.example", to="x@y", subject="s",
            text_body="b", client=self._Client(fail=True),
        )
        assert "email send failed" in reason


class TestTheWaitEscalates:
    """The loop wiring, with a real wait over real files and fake deliverers."""

    def _round(self, tmp_path) -> Path:
        d = tmp_path / "round-001"
        d.mkdir()
        bundle_mod.write_pending(d, "http://127.0.0.1:9999/")
        return d

    def _config(self, email_after=0.15) -> NotifyConfig:
        return NotifyConfig(
            toast_backoff_seconds=(0.05,),
            email_after_seconds=email_after,
            email_from="gate@verified.example",
            email_to="operator@example.com",
        )

    def _wait(self, round_dir, config, toasts, emails, deadline=0.4):
        def toaster(title, body, url=""):
            toasts.append({"title": title, "body": body, "url": url})
            return ""

        def emailer(**kwargs):
            emails.append(kwargs)
            return ""

        with pytest.raises(TimeoutError):
            wait_for_feedback(
                round_dir, poll_seconds=0.01, reminder_every=999,
                deadline=deadline, log=lambda _l: None,
                notify_config=config,
                context={"repo": "boostgauge", "issue": 331},
                toaster=toaster, emailer=emailer,
            )

    def test_toasts_repeat_and_carry_the_facts(self, tmp_path):
        round_dir = self._round(tmp_path)
        toasts: list[dict] = []
        self._wait(round_dir, self._config(email_after=999), toasts, [])
        assert len(toasts) >= 2, "the backoff must re-ask, not ask once"
        assert toasts[0]["url"] == "http://127.0.0.1:9999/"
        assert "boostgauge #331" in toasts[0]["body"]

    def test_the_email_goes_once_and_the_sentinel_survives_a_resume(self, tmp_path):
        round_dir = self._round(tmp_path)
        emails: list[dict] = []
        self._wait(round_dir, self._config(), [], emails)
        assert len(emails) == 1, "one backstop email per round, ever"
        [sent] = emails
        assert sent["sender"] == "gate@verified.example"
        assert sent["to"] == "operator@example.com"
        assert "round-001" in sent["text_body"]
        assert "http://127.0.0.1:9999/" in sent["text_body"]
        sentinel = round_dir / EMAIL_SENT_NAME
        assert sentinel.is_file()

        # The resume: a fresh wait on the same round must NOT email again.
        self._wait(round_dir, self._config(), [], emails)
        assert len(emails) == 1, "a resumed wait re-sent the one-ever email"

    def test_a_failing_deliverer_never_breaks_the_wait(self, tmp_path):
        round_dir = self._round(tmp_path)
        lines: list[str] = []

        def broken_toaster(title, body, url=""):
            return "toast failed: no shell"

        def broken_emailer(**kwargs):
            return "email send failed: SES says no"

        with pytest.raises(TimeoutError):
            wait_for_feedback(
                round_dir, poll_seconds=0.01, reminder_every=999,
                deadline=0.3, log=lines.append,
                notify_config=self._config(email_after=0.1),
                toaster=broken_toaster, emailer=broken_emailer,
            )
        assert any("toast failed" in line for line in lines)
        assert any("email send failed" in line for line in lines)
        assert not (round_dir / EMAIL_SENT_NAME).is_file(), (
            "a failed email must not claim its once-ever slot"
        )

    def test_an_answer_ends_the_wait_not_the_schedule(self, tmp_path):
        """Escalation never decides: feedback arriving returns the answer,
        however deep the backoff was."""
        round_dir = self._round(tmp_path)
        bundle_mod.write_feedback(round_dir, "approve", "ship it")
        answer = wait_for_feedback(
            round_dir, poll_seconds=0.01,
            notify_config=self._config(),
            toaster=lambda *a, **k: "", emailer=lambda **k: "",
        )
        assert answer["verb"] == "approve"
