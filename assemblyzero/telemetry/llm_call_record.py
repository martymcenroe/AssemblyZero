"""Core data structures for LLM call instrumentation.

Issue #774: Full LLM call instrumentation — input parameters + output metadata.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional, TypedDict


ProviderName = Literal["claude_cli", "anthropic_api", "gemini", "fallback"]
EffortLevel = Literal["low", "medium", "high", "max"]
StopReason = Literal["end_turn", "max_tokens", "stop_sequence", "tool_use", "error", "unknown"]


class LLMInputParams(TypedDict, total=False):
    """Parameters that were sent to the LLM. All fields optional — log what is known."""

    provider: str
    model_requested: str
    effort_level: Optional[EffortLevel]
    max_budget_usd: Optional[float]
    fallback_model: Optional[str]
    json_schema: Optional[dict]
    temperature: Optional[float]
    max_tokens: Optional[int]
    system_prompt_len: Optional[int]
    user_prompt_len: Optional[int]
    workflow: Optional[str]
    node: Optional[str]
    issue_number: Optional[int]


class LLMOutputMetadata(TypedDict, total=False):
    """Metadata read from the API/CLI response. All fields optional."""

    model_used: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    thinking_tokens: Optional[int]
    cache_read_tokens: Optional[int]
    cache_write_tokens: Optional[int]
    stop_reason: Optional[StopReason]
    context_window_used: Optional[int]
    latency_ms: Optional[float]
    cost_usd_estimate: Optional[float]


class LLMCallRecord(TypedDict):
    """A single instrumented LLM invocation record. Written as one JSONL line."""

    record_id: str
    timestamp_utc: str
    inputs: LLMInputParams
    outputs: LLMOutputMetadata
    success: bool
    error: Optional[str]


def make_record_id() -> str:
    """Return a UUID4 string."""
    return str(uuid.uuid4())


def now_utc_iso() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")