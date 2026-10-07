"""The operator alert path: one function every failure calls (ADR 0236, #3728).

ADR 0236 gives every failure four properties: loud, logged with details, stops
the processing that depends on it, and alerts the operator. This module is the
fourth. ``alert_operator`` does four things, in order:

* writes one loud ``ERROR`` line and the detail record to standard error;
* sends one email through SES v2 to the operator's contact address, which
  reaches him from Ubuntu as well as Windows and when he is not at the terminal;
* shows a toast when the host is Windows;
* appends the record to ``~/.assemblyzero/alerts.jsonl``.

A failure to deliver the alert is itself a failure. Every step is attempted;
if any did not work, the undelivered record and every reason go to standard
error and ``AlertDeliveryError`` is raised. Nothing here returns a reason
string for a caller to discard, which is what ``operator_notify`` does for the
waits it decorates.

The sender identity is never written into code: it comes from
``AZ_OPERATOR_EMAIL_FROM``, then from ``~/.assemblyzero/alert.json``
(``{"email_from": "..."}``), and must be an address at an SES-verified
identity. ``check_alert_channel`` proves a sender and AWS credentials resolve
without sending anything; a workflow's start-up check calls it.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from assemblyzero.core import operator_notify

#: Same variable ``operator_notify`` already reads for the wait escalation.
SENDER_ENV = operator_notify.EMAIL_FROM_ENV

SES_REGION = "us-east-1"


class AlertDeliveryError(RuntimeError):
    """The alert did not reach the operator. Raised, never returned."""


def _state_dir() -> Path:
    # Resolved per call, so a test that points HOME elsewhere is honoured.
    return Path.home() / ".assemblyzero"


def sender_config_path() -> Path:
    return _state_dir() / "alert.json"


def alerts_log_path() -> Path:
    return _state_dir() / "alerts.jsonl"


def resolve_sender(environ: dict[str, str] | None = None) -> str:
    """The SES sender for alerts: the environment first, then ``alert.json``.

    Raises ``AlertDeliveryError`` naming both places when neither holds one.
    """
    env = (environ if environ is not None else os.environ).get(SENDER_ENV, "").strip()
    if env:
        return env
    path = sender_config_path()
    if not path.is_file():
        raise AlertDeliveryError(
            f"no alert sender configured: set {SENDER_ENV}, or write {path} "
            f'as {{"email_from": "<address at an SES-verified identity>"}}'
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AlertDeliveryError(f"cannot read the alert sender from {path}: {exc}") from exc
    sender = str(data.get("email_from", "")).strip() if isinstance(data, dict) else ""
    if not sender:
        raise AlertDeliveryError(f"{path} has no non-empty email_from")
    return sender


def _ses_client() -> Any:
    """The real SES v2 client. The unit tier replaces this function (#3728)."""
    import boto3

    return boto3.client("sesv2", region_name=SES_REGION)


def _toast_runner() -> Any:
    """The real process runner for the toast. The unit tier replaces it too."""
    return subprocess.run


def _aws_credentials() -> Any:
    import boto3

    return boto3.Session().get_credentials()


def check_alert_channel(*, credentials: Any = None) -> str:
    """Prove the alert channel can work, without sending. Returns the sender.

    Raises ``AlertDeliveryError`` when no sender resolves or no AWS
    credentials resolve. ``credentials`` is a test seam; production asks boto3.
    """
    sender = resolve_sender()
    creds = credentials if credentials is not None else _aws_credentials()
    if creds is None:
        raise AlertDeliveryError(
            "no AWS credentials resolve on this machine; SES cannot send the alert"
        )
    return sender


def _subject(record: dict) -> str:
    where = record["where"]
    issue = f" #{record['issue']}" if record.get("issue") else ""
    return f"[AssemblyZero] FAILED{issue}: {record['what']} ({where})"


def _body(record: dict) -> str:
    lines = [f"{key}: {value}" for key, value in record.items() if value not in ("", None)]
    return "\n".join(lines) + "\n"


def alert_operator(
    *,
    what: str,
    where: str,
    cause: str,
    consequence: str,
    repo: str = "",
    issue: int | None = None,
    spec: str = "",
) -> dict:
    """Tell the operator a failure happened. Returns the record on delivery.

    ``what``: the operation that failed, in words. ``where``: module and
    function, plus workflow, node or seat. ``cause``: exception type and
    message, or return code and stderr. ``consequence``: what stops.
    """
    record = {
        # Local time with its offset: Central on the operator's machines.
        "time": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
        "host": platform.node(),
        "what": what,
        "where": where,
        "cause": cause,
        "consequence": consequence,
        "repo": repo,
        "issue": issue,
        "spec": spec,
    }
    sys.stderr.write(f"ERROR [ALERT] {what} -- {where}: {cause}\n")
    sys.stderr.write(_body(record))
    sys.stderr.flush()

    try:
        try:
            _send_email(record)
            if sys.platform == "win32":
                _show_toast(record)
        finally:
            # The record reaches the log even when the email did not.
            _append_log(record)
    except AlertDeliveryError as exc:
        sys.stderr.write(f"ERROR [ALERT] NOT DELIVERED to the operator: {exc}\n")
        if exc.__context__ is not None:
            sys.stderr.write(f"  and before it: {exc.__context__}\n")
        sys.stderr.flush()
        raise
    return record


def _send_email(record: dict) -> None:
    sender = resolve_sender()
    try:
        reason = operator_notify.send_email(
            sender=sender,
            to=operator_notify.OPERATOR_CONTACT,
            subject=_subject(record),
            text_body=_body(record),
            region=SES_REGION,
            client=_ses_client(),
        )
    except Exception as exc:
        raise AlertDeliveryError(f"email: {type(exc).__name__}: {exc}") from exc
    if reason:
        raise AlertDeliveryError(f"email: {reason}")


def _show_toast(record: dict) -> None:
    reason = operator_notify.show_toast(
        f"AssemblyZero: {record['what']}",
        f"{record['where']}: {record['cause']}",
        runner=_toast_runner(),
    )
    if reason:
        raise AlertDeliveryError(f"toast: {reason}")


def _append_log(record: dict) -> None:
    log = alerts_log_path()
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError as exc:
        raise AlertDeliveryError(f"alerts log {log}: {exc}") from exc
