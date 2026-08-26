"""Escalating notification while a gate waits on the operator (#2529).

The gate's infinite patience is correct — human priority always, no timeout
that overrides the human (fleet hard rule). What was missing is that the
patience was SILENT: the run holds, the operator forgets, and the machine has
no sanctioned way to re-request attention. The operator's own projection:
"if i get distracted the program could sit there for days waiting for me."

So the wait asks louder over time, and never decides:

* **Toast, on a slow backoff.** After a configurable idle interval (default
  10 minutes) a Windows toast names the repo, issue, round and URL; clicking
  it opens the review page. It repeats — 30 minutes later, then hourly —
  because the first toast lands while the operator is precisely the thing
  they said: busy. Toasts are the OS's sanctioned attention channel, not a
  window flash (the spawn is CREATE_NO_WINDOW; nothing steals focus).
* **One email, ever, as the backstop.** After a long threshold (default 4
  hours) one message goes to the operator's contact address via the fleet's
  canonical outbound stack (AWS SES v2, us-east-1, boto3 default credential
  chain). The sender identity must be an SES-verified address and is supplied
  by config or environment — it is deliberately not hardcoded here.
* **Never a timeout.** Nothing in this module ends a wait. Escalation is
  louder asking, not deciding.

Every failure in this module is non-fatal by construction: each entry point
returns "" on success or a one-line reason string the caller logs and moves
past. A notification must never damage the wait it decorates.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape as _xml_escape

#: The operator's contact inbox (fleet identity). NEVER an account-login
#: address — the CloudFlare/AWS account emails are not contact addresses.
OPERATOR_CONTACT = "martymcenroe@gmail.com"

#: Environment override for the SES-verified sender identity, so it never
#: has to be written into a repo's tracked declaration.
EMAIL_FROM_ENV = "AZ_OPERATOR_EMAIL_FROM"

DEFAULT_TOAST_BACKOFF: tuple[float, ...] = (600.0, 1800.0, 3600.0)
DEFAULT_EMAIL_AFTER: float = 4 * 3600.0


@dataclass(frozen=True)
class NotifyConfig:
    """The escalation declaration; every interval configurable, all of it
    disableable, none of it a timeout."""

    enabled: bool = True
    #: Seconds of idle before the FIRST toast, then between subsequent
    #: toasts; the last entry repeats forever (default: 10m, then 30m
    #: later, then hourly).
    toast_backoff_seconds: tuple[float, ...] = DEFAULT_TOAST_BACKOFF
    #: Seconds of idle before the single backstop email.
    email_after_seconds: float = DEFAULT_EMAIL_AFTER
    email_to: str = OPERATOR_CONTACT
    #: SES-verified sender identity. Empty means the email backstop is
    #: disabled (and says so, once); the environment override wins.
    email_from: str = ""

    @classmethod
    def from_mapping(cls, data: dict | None) -> "NotifyConfig":
        data = data or {}
        backoff = tuple(
            float(v) for v in data.get("toast_backoff_seconds", [])
        ) or DEFAULT_TOAST_BACKOFF
        return cls(
            enabled=bool(data.get("enabled", True)),
            toast_backoff_seconds=backoff,
            email_after_seconds=float(
                data.get("email_after_seconds", DEFAULT_EMAIL_AFTER)
            ),
            email_to=str(data.get("email_to", OPERATOR_CONTACT)),
            email_from=(
                os.environ.get(EMAIL_FROM_ENV, "").strip()
                or str(data.get("email_from", ""))
            ),
        )


class EscalationSchedule:
    """Which escalations are due at a given elapsed idle time.

    Pure bookkeeping over a monotonic elapsed-seconds value the caller
    supplies, so tests drive it with plain numbers and no clock mocking.
    Each action is returned exactly once; the toast cursor then advances by
    the next backoff entry (last entry repeating). The email is offered once
    per schedule — the caller enforces once-per-ROUND across resumes with an
    on-disk sentinel, because this object dies with the process and the wait
    does not.
    """

    def __init__(self, config: NotifyConfig) -> None:
        self._config = config
        self._backoff = config.toast_backoff_seconds
        self._index = 0
        self._next_toast_at = self._backoff[0] if self._backoff else None
        self._email_offered = False

    def due(self, elapsed_seconds: float) -> list[str]:
        if not self._config.enabled:
            return []
        actions: list[str] = []
        if (
            self._next_toast_at is not None
            and elapsed_seconds >= self._next_toast_at
        ):
            actions.append("toast")
            self._index += 1
            step = self._backoff[min(self._index, len(self._backoff) - 1)]
            self._next_toast_at += step
        if (
            not self._email_offered
            and elapsed_seconds >= self._config.email_after_seconds
        ):
            actions.append("email")
            self._email_offered = True
        return actions


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------

#: PowerShell's registered AppUserModelID — the one AppId every Windows box
#: already has, so the toast needs no registration step of its own.
_POWERSHELL_APP_ID = (
    "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}"
    "\\WindowsPowerShell\\v1.0\\powershell.exe"
)

_TOAST_PS_TEMPLATE = """$ErrorActionPreference = 'Stop'
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime]
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('{payload}')
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}').Show([Windows.UI.Notifications.ToastNotification]::new($xml))
"""


def toast_script(title: str, body: str, url: str = "") -> str:
    """The PowerShell that shows one toast; pure, so tests read it.

    Clicking the toast opens ``url`` (protocol activation) — the review page
    is one click away even when the terminal is buried. All three fields are
    XML-escaped, and the finished payload has its single quotes doubled for
    PowerShell's single-quoted string, in that order, so neither layer can
    reinterpret the other's characters.
    """
    launch = (
        f' activationType="protocol" launch="{_xml_escape(url, {'"': "&quot;"})}"'
        if url else ""
    )
    payload = (
        f"<toast{launch}><visual><binding template=\"ToastGeneric\">"
        f"<text>{_xml_escape(title)}</text>"
        f"<text>{_xml_escape(body)}</text>"
        f"</binding></visual></toast>"
    )
    return _TOAST_PS_TEMPLATE.format(
        payload=payload.replace("'", "''"), app_id=_POWERSHELL_APP_ID
    )


def show_toast(
    title: str, body: str, url: str = "", *,
    runner=subprocess.run, platform: str | None = None,
) -> str:
    """Show a Windows toast. Returns "" on success, a reason string otherwise.

    ``platform`` is a test seam (defaults to the real ``sys.platform``) so the
    composition and spawn wiring stay testable on the Linux CI runner, where
    the real guard below would otherwise short-circuit them.
    """
    if (platform or sys.platform) != "win32":
        return "toast skipped: not a Windows host"
    try:
        result = runner(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                toast_script(title, body, url),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:  # noqa: BLE001
        # fail-open: #2529 — a notification must never damage the wait it
        # decorates. The failure is returned as a reason string the caller
        # logs, so it is visible, and the wait (the thing that matters)
        # continues.
        return f"toast failed: {exc}"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return f"toast failed (exit {result.returncode}): {detail[:200]}"
    return ""


# ---------------------------------------------------------------------------
# Email (the fleet's canonical outbound stack: SES v2, us-east-1)
# ---------------------------------------------------------------------------


def send_email(
    *,
    sender: str,
    to: str,
    subject: str,
    text_body: str,
    region: str = "us-east-1",
    client: Any = None,
) -> str:
    """One plain-text email via SES v2. Returns "" on success, else a reason.

    ``sender`` must be an SES-verified identity; empty disables with a reason
    the caller logs once. ``client`` is the test seam — production builds a
    real boto3 client from the default credential chain.
    """
    if not sender:
        return (
            f"email backstop disabled: no sender identity configured "
            f"(set {EMAIL_FROM_ENV} or the gate declaration's "
            f"notify.email_from to an SES-verified address)"
        )
    try:
        if client is None:
            import boto3

            client = boto3.client("sesv2", region_name=region)
        client.send_email(
            FromEmailAddress=sender,
            Destination={"ToAddresses": [to]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": text_body, "Charset": "UTF-8"}
                    },
                }
            },
        )
        return ""
    except Exception as exc:  # noqa: BLE001
        # fail-open: #2529 — same ruling as the toast: the backstop email is
        # a courtesy, the wait is the contract. The reason string is logged
        # by the caller, and a failed send does not claim the once-ever
        # sentinel, so a resumed wait can still deliver the backstop.
        return f"email send failed: {exc}"
