"""Core telemetry emitter — fire-and-forget event recording.

Design principles:
- Never raise exceptions (telemetry must not break tools)
- Never block tool execution (DynamoDB writes are best-effort)
- Local JSONL fallback when DynamoDB is unreachable
- Kill switch via ASSEMBLYZERO_TELEMETRY=0
"""

import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

from assemblyzero.telemetry.actor import detect_actor, detect_github_user, get_machine_id

# Kill switch
_ENABLED_ENV = "ASSEMBLYZERO_TELEMETRY"

# Buffer directory for offline fallback
_BUFFER_DIR = Path.home() / ".assemblyzero" / "telemetry-buffer"

# Lazy-initialized DynamoDB client
_dynamo_client: Optional[Any] = None
_dynamo_init_attempted = False


def _is_enabled() -> bool:
    """Check if telemetry is enabled (default: yes)."""
    return os.environ.get(_ENABLED_ENV, "1") != "0"


def _get_dynamo_client() -> Optional[Any]:
    """Lazy-initialize DynamoDB client from stored credentials.

    Returns None if boto3 unavailable or credentials missing.
    Never raises.
    """
    global _dynamo_client, _dynamo_init_attempted

    if _dynamo_init_attempted:
        return _dynamo_client

    _dynamo_init_attempted = True

    try:
        import boto3

        creds_path = Path.home() / ".assemblyzero" / "aws-telemetry-credentials.json"
        if not creds_path.exists():
            return None

        with open(creds_path) as f:
            creds = json.load(f)

        _dynamo_client = boto3.resource(
            "dynamodb",
            region_name=creds.get("region", "us-east-1"),
            aws_access_key_id=creds["access_key_id"],
            aws_secret_access_key=creds["secret_access_key"],
        ).Table(creds.get("table_name", "assemblyzero-telemetry"))

        return _dynamo_client
    except Exception:
        return None


def _write_to_buffer(event: dict[str, Any]) -> None:
    """Write event to local JSONL buffer for later sync.

    Never raises — silently drops if buffer dir is not writable.
    """
    try:
        _BUFFER_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        buffer_file = _BUFFER_DIR / f"{date_str}.jsonl"
        with open(buffer_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()
    except Exception:
        pass  # Telemetry must never break tools


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
    """Emit a telemetry event. Fire-and-forget — never raises.

    Args:
        event_type: Event type (e.g., "workflow.start", "tool.error").
        repo: Repository name (e.g., "AssemblyZero").
        metadata: Optional additional data for the event.
    """
    if not _is_enabled():
        return

    try:
        event = _build_event(event_type, repo, metadata)

        client = _get_dynamo_client()
        if client is not None:
            try:
                client.put_item(Item=event)
                return  # Success — no need for buffer
            except Exception:
                pass  # Fall through to buffer

        # DynamoDB unavailable — write to local buffer
        _write_to_buffer(event)
    except Exception:
        pass  # Telemetry must never break tools


def flush() -> int:
    """Flush any buffered events to DynamoDB.

    Returns:
        Number of events successfully flushed.
    """
    if not _is_enabled():
        return 0

    client = _get_dynamo_client()
    if client is None:
        return 0

    flushed = 0
    try:
        if not _BUFFER_DIR.exists():
            return 0

        for buffer_file in sorted(_BUFFER_DIR.glob("*.jsonl")):
            remaining_lines: list[str] = []
            try:
                with open(buffer_file, encoding="utf-8") as f:
                    lines = f.readlines()

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        client.put_item(Item=event)
                        flushed += 1
                    except Exception:
                        remaining_lines.append(line)

                if remaining_lines:
                    with open(buffer_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(remaining_lines) + "\n")
                else:
                    buffer_file.unlink()
            except Exception:
                continue

    except Exception:
        pass

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
