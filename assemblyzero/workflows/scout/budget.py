"""Budget tracking and token estimation for Scout workflow.

Implements pessimistic estimation with 1.2x safety buffer and adaptive truncation.
Uses tiktoken for local estimation, handling tokenizer mismatch with Gemini.
"""

import tiktoken

# Safety buffer factor to account for tokenizer mismatch between tiktoken (OpenAI) and Gemini
SAFETY_BUFFER = 1.2


def estimate_tokens(text: str) -> int:
    """Estimate token count using tiktoken.

    Args:
        text: Text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate of ~4 chars per token
        return len(text) // 4


def check_and_update_budget(
    current_usage: int,
    new_text: str,
    limit: int,
) -> tuple[int, bool]:
    """Calculate token count and check against budget limit.

    Applies 1.2x safety buffer factor internally to account for tokenizer mismatch.

    Args:
        current_usage: Current token usage.
        new_text: New text to add.
        limit: Maximum token budget.

    Returns:
        Tuple of (new_usage, is_within_limit).
    """
    # Estimate tokens with safety buffer
    raw_tokens = estimate_tokens(new_text)
    buffered_tokens = int(raw_tokens * SAFETY_BUFFER)

    new_usage = current_usage + buffered_tokens
    is_within_limit = new_usage <= limit

    return new_usage, is_within_limit


def adaptive_truncate(text: str, reduction_factor: float = 0.5) -> str:
    """Aggressively truncate text to recover from Context Window errors.

    Prioritizes retaining the beginning of the text.

    Args:
        text: Text to truncate.
        reduction_factor: How much to reduce (0.5 = keep 50%).

    Returns:
        Truncated text.
    """
    if not text:
        return text

    if reduction_factor <= 0 or reduction_factor >= 1:
        raise ValueError("reduction_factor must be between 0 and 1 exclusive")

    target_length = int(len(text) * reduction_factor)
    return text[:target_length]
