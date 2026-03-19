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

from assemblyzero.telemetry.llm_call_record import (
    LLMCallRecord,
    LLMInputParams,
    LLMOutputMetadata,
)
from assemblyzero.telemetry.instrumentation import InstrumentedCall
from assemblyzero.telemetry.store import CallStore
from assemblyzero.telemetry.cost import estimate_cost

__all__ = [
    "CallStore",
    "CascadeEvent",
    "create_cascade_event",
    "emit",
    "estimate_cost",
    "flush",
    "get_cascade_stats",
    "InstrumentedCall",
    "LLMCallRecord",
    "LLMInputParams",
    "LLMOutputMetadata",
    "log_cascade_event",
    "track_tool",
]