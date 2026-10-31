"""Core telemetry emitter: event recording with a local buffer.

Design principles:
- Local JSONL buffer when DynamoDB is unreachable or not configured; the
  buffer is synced by ``flush``. A machine with no credentials file runs in
  local-only mode: every event is kept in the buffer, nothing is lost.
- Kill switch via ASSEMBLYZERO_TELEMETRY=0
- Every failure is loud (ADR 0236, #3585). An event that cannot be built, or
  that reaches neither DynamoDB nor the buffer, alerts the operator and
  raises. A credentials file that exists but cannot be loaded raises on every
  emit and flush, alerting once per process. A DynamoDB write that fails (the
  event is then buffered) logs ERROR every time and alerts once per process. A flush that cannot read or rewrite its buffer alerts and raises; a
  buffered event that fails to upload stays buffered, is logged at ERROR, and
  alerts once per process.
"""

import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

from assemblyzero.core import alert
from assemblyzero.telemetry.actor import detect_actor, detect_github_user, get_machine_id

logger = logging.getLogger(__name__)

# Kill switch
_ENABLED_ENV = "ASSEMBLYZERO_TELEMETRY"

# Buffer directory for offline fallback
_BUFFER_DIR = Path.home() / ".assemblyzero" / "telemetry-buffer"

# Lazy-initialized DynamoDB client
_dynamo_client: Optional[Any] = None
_dynamo_init_attempted = False

#: Failure kinds already alerted in this process. A DynamoDB outage fails every
#: emit; one alert says so, and each failure is still an ERROR line.
_alerted: set[str] = set()


class TelemetryConfigError(RuntimeError):
    """The telemetry credentials file exists but cannot be used (#3585)."""


def _is_enabled() -> bool:
    """Check if telemetry is enabled (default: yes)."""
    return os.environ.get(_ENABLED_ENV, "1") != "0"


def _error_line(message: str) -> None:
    logger.error("[TELEMETRY] %s", message)
    print(f"ERROR [TELEMETRY] {message}", file=sys.stderr, flush=True)


def _first_time(kind: str) -> bool:
    """True the first time this failure kind is seen in this process."""
    if kind in _alerted:
        return False
    _alerted.add(kind)
    return True


def _get_dynamo_client() -> Optional[Any]:
    """Lazy-initialize DynamoDB client from stored credentials.

    Returns None when there is no credentials file: local-only mode, in which
    every event is kept in the buffer, so nothing is lost (#3585 keeps this
    quiet by contract; the opt-out is ASSEMBLYZERO_TELEMETRY=0).

    Raises ``TelemetryConfigError`` when a credentials file exists but cannot
    be loaded, or the client cannot be built: an ERROR line every time and an
    alert once per process, naming the cause -- never the file's contents.
    Nothing is cached on failure, so every emit and flush refuses until the
    file is repaired or telemetry is switched off.
    """
    global _dynamo_client, _dynamo_init_attempted

    if _dynamo_init_attempted:
        return _dynamo_client

    creds_path = Path.home() / ".assemblyzero" / "aws-telemetry-credentials.json"
    if not creds_path.exists():
        _dynamo_init_attempted = True
        return None

    try:
        import boto3

        with open(creds_path) as f:
            creds = json.load(f)

        _dynamo_client = boto3.resource(
            "dynamodb",
            region_name=creds.get("region", "us-east-1"),
            aws_access_key_id=creds["access_key_id"],
            aws_secret_access_key=creds["secret_access_key"],
        ).Table(creds.get("table_name", "assemblyzero-telemetry"))

        _dynamo_init_attempted = True
        return _dynamo_client
    except Exception as exc:
        # The exception type only: a parse error's message can quote the
        # credentials file.
        cause = f"{type(exc).__name__} loading {creds_path}"
        _error_line(f"telemetry DynamoDB client unavailable: {cause}")
        if _first_time("client"):
            alert.alert_operator(
                what="build the telemetry DynamoDB client",
                where="assemblyzero/telemetry/emitter.py _get_dynamo_client",
                cause=cause,
                consequence=(
                    "every emit and flush refuses until the credentials file is "
                    "repaired, or ASSEMBLYZERO_TELEMETRY=0 switches telemetry off"
                ),
            )
        raise TelemetryConfigError(cause) from None


def _write_to_buffer(event: dict[str, Any]) -> None:
    """Write event to local JSONL buffer for later sync.

    A buffer that cannot take the event alerts the operator and raises: the
    event would otherwise be lost entirely (#3585).
    """
    buffer_file: Path | None = None
    try:
        _BUFFER_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        buffer_file = _BUFFER_DIR / f"{date_str}.jsonl"
        with open(buffer_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()
    except Exception as exc:
        alert.alert_operator(
            what="buffer a telemetry event",
            where="assemblyzero/telemetry/emitter.py _write_to_buffer",
            cause=(
                f"{type(exc).__name__}: {exc} (buffer {buffer_file or _BUFFER_DIR}, "
                f"event {event.get('event_type', '')})"
            ),
            consequence="the event reached neither DynamoDB nor the buffer; it is raised",
        )
        raise


def _build_event(
    event_type: str,
    repo: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a structured telemetry event dict."""
    now = datetime.now(timezone.utc)
    event_id = uuid.uuid4().hex[:12]
    timestamp = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")
    actor = detect_actor()
    github_user = detect_github_user()
    ttl_epoch = int(now.timestamp()) + (90 * 86400)  # 90-day expiry

    event = {
        # DynamoDB keys
        "pk": f"REPO#{repo}" if repo else "REPO#unknown",
        "sk": f"EVENT#{timestamp}#{event_id}",
        "gsi1pk": f"ACTOR#{actor}",
        "gsi1sk": timestamp,
        "gsi2pk": f"USER#{github_user}",
        "gsi2sk": timestamp,
        "gsi3pk": f"DATE#{date_str}",
        "gsi3sk": f"REPO#{repo}#EVENT#{timestamp}" if repo else f"REPO#unknown#EVENT#{timestamp}",
        # Event data
        "event_type": event_type,
        "actor": actor,
        "repo": repo or "unknown",
        "github_user": github_user,
        "machine_id": get_machine_id(),
        "timestamp": timestamp,
        "ttl": ttl_epoch,
    }

    if metadata:
        event["metadata"] = metadata

    return event


def emit(
    event_type: str,
    repo: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Emit a telemetry event to DynamoDB, or to the local buffer.

    Raises when the event cannot be built, or reaches neither DynamoDB nor
    the buffer, after alerting the operator (#3585). A failed DynamoDB write
    falls back to the buffer, logged at ERROR and alerted once per process.

    Args:
        event_type: Event type (e.g., "workflow.start", "tool.error").
        repo: Repository name (e.g., "AssemblyZero").
        metadata: Optional additional data for the event.
    """
    if not _is_enabled():
        return

    try:
        event = _build_event(event_type, repo, metadata)
    except Exception as exc:
        alert.alert_operator(
            what=f"build the telemetry event {event_type}",
            where="assemblyzero/telemetry/emitter.py emit",
            cause=f"{type(exc).__name__}: {exc}",
            consequence="the event is not recorded; the failure is raised",
            repo=repo,
        )
        raise

    client = _get_dynamo_client()
    if client is not None:
        try:
            client.put_item(Item=event)
            return  # Success — no need for buffer
        except Exception as exc:
            _error_line(
                f"DynamoDB put_item failed for {event_type}: "
                f"{type(exc).__name__}: {exc}; buffering the event"
            )
            if _first_time("put_item"):
                alert.alert_operator(
                    what="upload a telemetry event to DynamoDB",
                    where="assemblyzero/telemetry/emitter.py emit",
                    cause=f"{type(exc).__name__}: {exc} (event {event_type})",
                    consequence=(
                        "this and later failed uploads in this process are "
                        "kept in the local buffer for flush; each is an ERROR line"
                    ),
                    repo=repo,
                )

    # DynamoDB unavailable, unconfigured or failed — write to local buffer
    _write_to_buffer(event)


def flush() -> int:
    """Flush any buffered events to DynamoDB.

    With no client (local-only mode) nothing is uploaded and 0 is the true
    count. A buffer file that cannot be read or rewritten alerts the operator
    and raises (#3585). An event that fails to upload stays in the buffer for
    the next flush, logged at ERROR, alerting once per process.

    Returns:
        Number of events successfully flushed.
    """
    if not _is_enabled():
        return 0

    client = _get_dynamo_client()
    if client is None:
        return 0

    flushed = 0
    if not _BUFFER_DIR.exists():
        return 0

    for buffer_file in sorted(_BUFFER_DIR.glob("*.jsonl")):
        remaining_lines: list[str] = []
        try:
            with open(buffer_file, encoding="utf-8") as f:
                lines = f.readlines()

            for lineno, line in enumerate(lines, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    client.put_item(Item=event)
                    flushed += 1
                except Exception as exc:
                    remaining_lines.append(line)
                    _error_line(
                        f"buffered event {buffer_file}:{lineno} not uploaded: "
                        f"{type(exc).__name__}: {exc}; kept for the next flush"
                    )
                    if _first_time("flush_event"):
                        alert.alert_operator(
                            what="upload a buffered telemetry event",
                            where="assemblyzero/telemetry/emitter.py flush",
                            cause=f"{type(exc).__name__}: {exc} ({buffer_file}:{lineno})",
                            consequence=(
                                "the event stays in the buffer for the next flush; "
                                "each further failure is an ERROR line"
                            ),
                        )

            if remaining_lines:
                with open(buffer_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(remaining_lines) + "\n")
            else:
                buffer_file.unlink()
        except OSError as exc:
            alert.alert_operator(
                what="read or rewrite a telemetry buffer file",
                where="assemblyzero/telemetry/emitter.py flush",
                cause=f"{type(exc).__name__}: {exc} ({buffer_file})",
                consequence=(
                    f"{flushed} event(s) were uploaded before it; the flush stops "
                    f"and the file is left as it was"
                ),
            )
            raise

    return flushed


@contextmanager
def track_tool(
    tool_name: str,
    repo: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> Generator[None, None, None]:
    """Context manager that emits start/complete/error events with duration.

    Usage:
        with track_tool("run_audit", repo="AssemblyZero"):
            do_work()

    Emits:
        - tool.start on entry
        - tool.complete on success (with duration_ms)
        - tool.error on exception (with duration_ms and error info)
    """
    start_time = time.monotonic()
    tool_meta = dict(metadata or {})
    tool_meta["tool_name"] = tool_name

    emit("tool.start", repo=repo, metadata=tool_meta)

    try:
        yield
        duration_ms = int((time.monotonic() - start_time) * 1000)
        tool_meta["duration_ms"] = duration_ms
        emit("tool.complete", repo=repo, metadata=tool_meta)
    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        tool_meta["duration_ms"] = duration_ms
        tool_meta["error_type"] = type(exc).__name__
        tool_meta["error_message"] = str(exc)[:500]
        emit("tool.error", repo=repo, metadata=tool_meta)
        raise  # Re-raise — telemetry must not swallow exceptions
