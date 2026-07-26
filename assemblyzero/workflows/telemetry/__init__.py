"""Workflow telemetry — structured, record-only instrumentation.

Issue #1812: telemetry modules observe the pipeline; they never gate it.
Nothing exported here may alter workflow control flow, and sink failures
degrade to warnings — telemetry must never break the pipeline it measures.
"""

from assemblyzero.workflows.telemetry.hallucination_log import (
    build_hallucination_event,
    record_hallucination_event,
)

__all__ = [
    "build_hallucination_event",
    "record_hallucination_event",
]
