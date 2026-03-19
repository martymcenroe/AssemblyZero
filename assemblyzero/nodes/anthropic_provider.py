"""Anthropic SDK call wrapper with instrumentation.

Issue #774: Provides _parse_usage_from_message for extracting usage blocks
from Anthropic Message responses, and an instrumented call wrapper.

Note: This module wraps the Anthropic SDK directly. The existing
ClaudeCLIProvider and AnthropicProvider in assemblyzero.core.llm_provider
handle the primary provider logic. This module provides standalone
instrumented call capability for direct SDK usage.
"""

import logging
from typing import TYPE_CHECKING, Optional

from assemblyzero.telemetry.llm_call_record import LLMInputParams, LLMOutputMetadata

if TYPE_CHECKING:
    from assemblyzero.telemetry.store import CallStore

logger = logging.getLogger(__name__)


def _parse_usage_from_message(message: dict) -> LLMOutputMetadata:
    """Extract usage block, stop reason, model from Anthropic Message response.

    Accepts either a dict representation or an anthropic.types.Message object
    that has been converted to dict via .model_dump() or similar.

    Args:
        message: Dict with keys 'model', 'usage', 'stop_reason'.

    Returns:
        LLMOutputMetadata with extracted fields. Missing fields are None.
    """
    usage = message.get("usage", {})
    return LLMOutputMetadata(
        model_used=message.get("model", "unknown"),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        thinking_tokens=usage.get("thinking_tokens"),
        cache_read_tokens=usage.get("cache_read_input_tokens"),
        cache_write_tokens=usage.get("cache_creation_input_tokens"),
        stop_reason=message.get("stop_reason", "unknown"),
    )


def call_anthropic_with_instrumentation(
    prompt: str,
    *,
    model: str,
    system_prompt: str = "",
    store: Optional["CallStore"] = None,
    workflow: str = "unknown",
    node: str = "unknown",
    issue_number: Optional[int] = None,
) -> str:
    """Anthropic API call wrapped with InstrumentedCall.

    Issue #774: Provides an instrumented wrapper for direct Anthropic SDK calls.
    If store is None, instrumentation is effectively disabled (no-op store).
    """
    import anthropic

    from assemblyzero.telemetry.instrumentation import InstrumentedCall
    from assemblyzero.telemetry.store import CallStore

    inputs: LLMInputParams = {
        "provider": "anthropic_api",
        "model_requested": model,
        "workflow": workflow,
        "node": node,
        "user_prompt_len": len(prompt),
    }
    if system_prompt:
        inputs["system_prompt_len"] = len(system_prompt)
    if issue_number is not None:
        inputs["issue_number"] = issue_number

    if store is None:
        store = CallStore(enabled=False)

    with InstrumentedCall(store, inputs) as ic:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt if system_prompt else anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": prompt}],
        )
        # Parse usage from the response
        message_dict = message.model_dump() if hasattr(message, "model_dump") else {}
        outputs = _parse_usage_from_message(message_dict)
        ic.record_outputs(outputs)

        # Extract text content
        text_parts = [
            block.text for block in message.content if hasattr(block, "text")
        ]
        return "\n".join(text_parts)