"""AssemblyZero telemetry — structured event emission.

Fire-and-forget telemetry that never raises, never blocks tool execution.
Events go to DynamoDB with local JSONL fallback when offline.

Usage:
    from assemblyzero.telemetry import emit, track_tool

    # Direct event emission
    emit("workflow.start", repo="AssemblyZero", metadata={"issue": 42})

    # Context manager for tool tracking
    with track_tool("run_audit", repo="AssemblyZero"):
        do_work()  # emits tool.start, tool.complete (or tool.error)

Kill switch: set ASSEMBLYZERO_TELEMETRY=0 to disable all emission.
"""

from assemblyzero.telemetry.emitter import emit, flush, track_tool
from assemblyzero.telemetry.cascade_events import (
    CascadeEvent,
    create_cascade_event,
    get_cascade_stats,
    log_cascade_event,
)

__all__ = [
    "CascadeEvent",
    "create_cascade_event",
    "emit",
    "flush",
    "get_cascade_stats",
    "log_cascade_event",
    "track_tool",
]
