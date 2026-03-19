"""Cost estimation for LLM calls.

Issue #774: Per-model token cost lookup and estimate calculation.

Cost table covers all Claude models known at time of implementation.
Unknown models return 0.0 and log a warning.
Gemini cost estimation is deferred to a separate issue.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# (input_cost_per_1k, output_cost_per_1k, cache_read_per_1k, cache_write_per_1k)
TOKEN_COSTS: dict[str, tuple[float, float, float, float]] = {
    # Opus
    "claude-opus-4-5-20250514": (0.015, 0.075, 0.0015, 0.01875),
    # Sonnet
    "claude-sonnet-4-5-20250514": (0.003, 0.015, 0.0003, 0.00375),
    "claude-sonnet-4-6-20250514": (0.003, 0.015, 0.0003, 0.00375),
    "claude-sonnet-4-6": (0.003, 0.015, 0.0003, 0.00375),
    # Haiku
    "claude-haiku-4-5-20251001": (0.0008, 0.004, 0.00008, 0.001),
}

MODEL_ALIASES: dict[str, str] = {
    "claude:opus": "claude-opus-4-5-20250514",
    "claude:sonnet": "claude-sonnet-4-6",
    "claude:haiku": "claude-haiku-4-5-20251001",
    "claude-opus-4-5": "claude-opus-4-5-20250514",
    "claude-sonnet-4-5": "claude-sonnet-4-5-20250514",
    "claude-sonnet-4-6": "claude-sonnet-4-6-20250514",
}


def normalize_model_id(model: str) -> str:
    """Normalize model ID variants to canonical key.

    Examples:
        >>> normalize_model_id("claude:opus")
        'claude-opus-4-5-20250514'
        >>> normalize_model_id("claude-opus-4-5-20250514")
        'claude-opus-4-5-20250514'
        >>> normalize_model_id("unknown-model")
        'unknown-model'
    """
    return MODEL_ALIASES.get(model, model)


def get_model_costs(model: str) -> Optional[tuple[float, float, float, float]]:
    """Return (input, output, cache_read, cache_write) cost per 1K tokens, or None."""
    canonical = normalize_model_id(model)
    return TOKEN_COSTS.get(canonical)


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    thinking_tokens: int = 0,
) -> float:
    """Return estimated USD cost. Returns 0.0 for unknown models (logs warning).

    Thinking tokens are billed at the output token rate.
    """
    canonical = normalize_model_id(model)
    costs = TOKEN_COSTS.get(canonical)
    if costs is None:
        logger.warning("Unknown model '%s' for cost estimation, returning 0.0", model)
        return 0.0

    inp_rate, out_rate, cr_rate, cw_rate = costs

    # Clamp negatives to 0
    input_tokens = max(input_tokens, 0)
    output_tokens = max(output_tokens, 0)
    cache_read_tokens = max(cache_read_tokens, 0)
    cache_write_tokens = max(cache_write_tokens, 0)
    thinking_tokens = max(thinking_tokens, 0)

    cost = (
        (input_tokens / 1000) * inp_rate
        + (output_tokens / 1000) * out_rate
        + (thinking_tokens / 1000) * out_rate  # thinking billed as output
        + (cache_read_tokens / 1000) * cr_rate
        + (cache_write_tokens / 1000) * cw_rate
    )
    return round(cost, 8)