"""Claude CLI client with retry/backoff handling.

Issue #138: Add retry/backoff handling for Claude CLI invocations.

This module provides a robust interface to the Claude CLI with:
- Exponential backoff on rate limit errors (429)
- Configurable retry attempts
- Jitter to avoid thundering herd
"""

import random
import subprocess
import time
from pathlib import Path

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
                return result.stdout

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
