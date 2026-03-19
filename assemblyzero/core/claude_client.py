"""Claude CLI client with retry/backoff handling.

Issue #138: Add retry/backoff handling for Claude CLI invocations.

.. deprecated::
    This module has zero production callers as of issue #546.
    Use ``assemblyzero.core.llm_provider.ClaudeCLIProvider`` (for CLI access)
    or ``assemblyzero.core.llm_provider.AnthropicProvider`` (for API access)
    instead.  ``ClaudeRateLimitError`` maps to ``assemblyzero.core.errors.RateLimitError``.
    ``ClaudeClientError`` has no direct equivalent — use ``errors.APIError``.

This module provides a robust interface to the Claude CLI with:
- Exponential backoff on rate limit errors (429)
- Configurable retry attempts
- Jitter to avoid thundering herd
"""

import random
import subprocess
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from assemblyzero.core.text_sanitizer import strip_emoji

from assemblyzero.telemetry.llm_call_record import LLMInputParams, LLMOutputMetadata

if TYPE_CHECKING:
    from assemblyzero.telemetry.store import CallStore

# Configuration
MAX_RETRIES = 5
BASE_DELAY = 1.0  # seconds
MAX_DELAY = 60.0  # seconds
JITTER_FACTOR = 0.2  # ±20%


class ClaudeRateLimitError(Exception):
    """Raised when Claude CLI hits rate limit after all retries."""

    pass


class ClaudeClientError(Exception):
    """Raised for non-retryable Claude CLI errors."""

    pass


def invoke_claude(
    prompt: str,
    working_dir: Path | str,
    timeout: int = 300,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Invoke Claude CLI with retry/backoff on rate limits.

    Args:
        prompt: The prompt to send to Claude.
        working_dir: Directory to run Claude in.
        timeout: Timeout in seconds.
        max_retries: Maximum retry attempts on rate limit.

    Returns:
        Claude's response text.

    Raises:
        ClaudeRateLimitError: If rate limited after all retries.
        ClaudeClientError: For non-retryable errors (timeout, invalid config, etc).
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ["claude", "--print", "-p", prompt],
                cwd=str(working_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
            )

            if result.returncode == 0:
                # Issue #527: Strip emojis from CLI output
                return strip_emoji(result.stdout)

            # Check for rate limit (429)
            if _is_rate_limit_error(result):
                delay = _calculate_backoff(attempt)
                print(
                    f"  Rate limited, retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
                last_error = ClaudeRateLimitError(result.stderr)
                continue

            # Non-retryable error
            raise ClaudeClientError(f"Claude CLI failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            raise ClaudeClientError(f"Claude CLI timed out after {timeout}s")
        except FileNotFoundError:
            raise ClaudeClientError(
                "Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
            )

    # Exhausted retries
    raise last_error or ClaudeRateLimitError("Rate limited after max retries")


def _is_rate_limit_error(result: subprocess.CompletedProcess) -> bool:
    """Check if the error is a rate limit (429).

    Args:
        result: The subprocess result to check.

    Returns:
        True if this is a rate limit error, False otherwise.
    """
    stderr = result.stderr.lower()
    return (
        "429" in stderr
        or "rate limit" in stderr
        or "too many requests" in stderr
    )


def _calculate_backoff(attempt: int) -> float:
    """Calculate exponential backoff with jitter.

    Uses the formula: min(BASE_DELAY * 2^attempt, MAX_DELAY) ± JITTER_FACTOR

    Args:
        attempt: The current attempt number (0-indexed).

    Returns:
        The delay in seconds before the next retry.
    """
    delay = min(BASE_DELAY * (2**attempt), MAX_DELAY)
    jitter = delay * JITTER_FACTOR * (2 * random.random() - 1)
    return delay + jitter


def _parse_usage_from_cli_output(raw_json: dict) -> LLMOutputMetadata:
    """Extract token counts, stop reason, model from Claude CLI JSON response.

    Issue #774: Parse the JSON output from Claude CLI --output-format json.
    Uses .get() with None defaults so missing fields don't crash.
    """
    usage = raw_json.get("usage", {})
    return LLMOutputMetadata(
        model_used=raw_json.get("model", "unknown"),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        thinking_tokens=usage.get("thinking_tokens"),
        cache_read_tokens=usage.get("cache_read_input_tokens"),
        cache_write_tokens=usage.get("cache_creation_input_tokens"),
        stop_reason=raw_json.get("stop_reason", "unknown"),
    )


def call_claude_with_instrumentation(
    prompt: str,
    *,
    model: str,
    working_dir: str | Path = ".",
    effort: Optional[str] = None,
    max_budget_usd: Optional[float] = None,
    store: Optional["CallStore"] = None,
    workflow: str = "unknown",
    node: str = "unknown",
    issue_number: Optional[int] = None,
    timeout: int = 300,
) -> str:
    """Invoke Claude CLI with instrumentation. Wraps invoke_claude().

    Issue #774: Drop-in wrapper that adds telemetry around existing CLI calls.
    If store is None or store.enabled is False, behaves exactly like invoke_claude().
    """
    from assemblyzero.telemetry.instrumentation import InstrumentedCall
    from assemblyzero.telemetry.store import CallStore

    inputs: LLMInputParams = {
        "provider": "claude_cli",
        "model_requested": model,
        "workflow": workflow,
        "node": node,
        "user_prompt_len": len(prompt),
    }
    if effort is not None:
        inputs["effort_level"] = effort
    if max_budget_usd is not None:
        inputs["max_budget_usd"] = max_budget_usd
    if issue_number is not None:
        inputs["issue_number"] = issue_number

    if store is None:
        store = CallStore(enabled=False)

    with InstrumentedCall(store, inputs) as ic:
        result = invoke_claude(prompt, working_dir, timeout=timeout)
        # Note: invoke_claude returns a string, not JSON.
        # Full JSON parsing would require modifying invoke_claude itself.
        # For now, we record the call without detailed token counts from CLI.
        # Token parsing is available via _parse_usage_from_cli_output when
        # callers have access to the raw JSON response.
        return result