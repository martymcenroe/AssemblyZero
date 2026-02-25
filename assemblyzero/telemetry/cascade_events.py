"""Structured logging for cascade_risk events.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Writes newline-delimited JSON (JSONL) for measurement and tuning
of cascade detection accuracy over time.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, TypedDict

from assemblyzero.hooks.types import CascadeDetectionResult, CascadeRiskLevel

logger = logging.getLogger(__name__)

# Default log file location
_DEFAULT_LOG_PATH = Path("tmp/cascade-events.jsonl")


class CascadeEvent(TypedDict):
    """Telemetry event for cascade detection."""

    timestamp: str
    event_type: Literal["cascade_risk"]
    risk_level: str
    action_taken: str
    matched_patterns: list[str]
    model_output_snippet: str
    session_id: str
    auto_approve_blocked: bool


def log_cascade_event(
    event: CascadeEvent,
    log_path: str | Path | None = None,
) -> None:
    """Append a cascade_risk event to the telemetry log.

    Events are written as newline-delimited JSON (JSONL) to enable
    measurement of cascade frequency over time.

    Args:
        event: The CascadeEvent to log.
        log_path: Path to JSONL log file. If None, uses default at
                  tmp/cascade-events.jsonl.
    """
    if log_path is None:
        path = _DEFAULT_LOG_PATH
    else:
        path = Path(log_path)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
    except OSError as exc:
        # Log to stderr but don't raise — telemetry must never block
        print(f"[cascade_events] Failed to write event: {exc}", file=sys.stderr)


def create_cascade_event(
    result: CascadeDetectionResult,
    session_id: str,
    model_output: str,
    action_taken: str,
) -> CascadeEvent:
    """Create a CascadeEvent from a detection result.

    Args:
        result: Detection result.
        session_id: Current session ID.
        model_output: Original model output (truncated to 200 chars).
        action_taken: The action that was taken ("allowed", "blocked", "alerted").

    Returns:
        CascadeEvent ready for logging.
    """
    risk_level = result["risk_level"]
    if isinstance(risk_level, CascadeRiskLevel):
        risk_str = risk_level.value
    else:
        risk_str = str(risk_level)

    # Truncate snippet to 200 chars
    snippet = model_output[:200] if model_output else ""

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "cascade_risk",
        "risk_level": risk_str,
        "action_taken": action_taken,
        "matched_patterns": result["matched_patterns"],
        "model_output_snippet": snippet,
        "session_id": session_id,
        "auto_approve_blocked": result["recommended_action"] != "allow",
    }


def get_cascade_stats(
    log_path: str | Path | None = None,
    since_hours: int = 24,
) -> dict[str, int]:
    """Retrieve cascade detection statistics from the event log.

    Args:
        log_path: Path to JSONL log file.
        since_hours: Only count events from the last N hours.
                     Use 0 to count all events regardless of time.

    Returns:
        Dict with keys: total_checks, detections, blocks, allowed.
    """
    if log_path is None:
        path = _DEFAULT_LOG_PATH
    else:
        path = Path(log_path)

    stats = {"total_checks": 0, "detections": 0, "blocks": 0, "allowed": 0}

    if not path.exists():
        return stats

    if since_hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    else:
        cutoff = None

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue  # Skip corrupt lines

                # Time filter
                if cutoff is not None:
                    try:
                        ts = datetime.fromisoformat(event.get("timestamp", ""))
                        if ts < cutoff:
                            continue
                    except (ValueError, TypeError):
                        continue  # Skip events with bad timestamps

                stats["total_checks"] += 1
                if event.get("auto_approve_blocked", False):
                    stats["detections"] += 1
                    stats["blocks"] += 1
                else:
                    stats["allowed"] += 1
    except OSError as exc:
        logger.warning("Failed to read cascade event log: %s", exc)

    return stats