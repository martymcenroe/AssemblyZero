#!/usr/bin/env python3
"""
gemini-retry.py - Retry Gemini CLI with credential rotation and backoff

AssemblyZero Core Tool - Ensures gemini-3-pro-preview reviews succeed even under load.

Usage:
    python gemini-retry.py --prompt "Your prompt" [--model gemini-3-pro-preview]
    python gemini-retry.py --prompt-file /path/to/prompt.txt [--model gemini-3-pro-preview]

Features:
    - Credential rotation when account quota is exhausted
    - Exponential backoff for temporary capacity issues
    - Logs all attempts to logs/gemini-retry-TIMESTAMP.jsonl
    - Validates model used (rejects silent downgrades)
    - Auto-switches to stdin for large prompts (>10KB) to avoid CLI issues
    - Returns response on success, exits 1 on permanent failure

Key Insight:
    - QUOTA_EXHAUSTED (account limit) → Try other credentials via rotation
    - CAPACITY_EXHAUSTED (Google servers) → Exponential backoff makes sense
    - Exponential backoff is USELESS for account quota - rotation is the answer
    - Large prompts fail with -p flag → Use stdin instead (Issue #34)
    - UNKNOWN errors → STOP IMMEDIATELY and print raw output for human diagnosis
      (If you don't know the error, retrying will give the same unknown error!)

Environment Variables:
    GEMINI_RETRY_MAX              Max retry attempts (default: 20)
    GEMINI_RETRY_BASE_DELAY       Initial delay in seconds (default: 30)
    GEMINI_RETRY_MAX_DELAY        Max delay cap in seconds (default: 600)
    GEMINI_RETRY_LOG_DIR          Log directory (default: logs/)
    GEMINI_RETRY_PROMPT_THRESHOLD Prompt size threshold for stdin (default: 10240)

Exit Codes:
    0 - Success (response printed to stdout)
    1 - Permanent failure (all credentials exhausted, max retries exceeded)
    2 - Invalid arguments
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_MODEL = "gemini-3-pro-preview"
ALLOWED_MODELS = {"gemini-3-pro-preview", "gemini-3-pro"}

# Backoff parameters (can be overridden via environment)
MAX_RETRIES = int(os.environ.get("GEMINI_RETRY_MAX", "20"))
BASE_DELAY = float(os.environ.get("GEMINI_RETRY_BASE_DELAY", "30"))
MAX_DELAY = float(os.environ.get("GEMINI_RETRY_MAX_DELAY", "600"))
JITTER_FACTOR = 0.2  # ±20%

# Prompt size threshold for stdin vs -p flag (Issue #34)
# Large prompts (>10KB) use stdin to avoid command line issues
PROMPT_SIZE_THRESHOLD = int(os.environ.get("GEMINI_RETRY_PROMPT_THRESHOLD", str(10 * 1024)))

# Logging
LOG_DIR = Path(os.environ.get("GEMINI_RETRY_LOG_DIR", "logs"))


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GeminiResult:
    """Result from a Gemini CLI invocation."""
    success: bool
    response: str
    raw_output: str
    model_used: Optional[str] = None
    exit_code: int = 0


@dataclass
class ErrorClassification:
    """Classification of a Gemini error."""
    error_type: str
    retryable: bool
    fixed_wait: Optional[float] = None  # If set, use this instead of backoff
    message: str = ""


# =============================================================================
# Error Classification
# =============================================================================

def classify_error(output: str) -> ErrorClassification:
    """
    Classify the error type from Gemini CLI output.

    Returns:
        ErrorClassification with retry strategy

    Note: Order matters! Check most specific errors first.
    """
    # SERVER CAPACITY EXHAUSTED - most common, check FIRST
    # This appears as MODEL_CAPACITY_EXHAUSTED in the error details
    # The error also contains "rateLimitExceeded" so we must check this first!
    if "MODEL_CAPACITY_EXHAUSTED" in output:
        return ErrorClassification(
            error_type="capacity",
            retryable=True,
            message="Server capacity exhausted (will retry with backoff)"
        )

    # RESOURCE_EXHAUSTED without specific reason (generic - retryable)
    if "RESOURCE_EXHAUSTED" in output:
        return ErrorClassification(
            error_type="resource_exhausted",
            retryable=True,
            message="Resource exhausted (will retry)"
        )

    # True quota exhaustion (daily limit - NOT retryable)
    # Check multiple patterns - Gemini CLI error formats vary
    if "QUOTA_EXHAUSTED" in output:
        return ErrorClassification(
            error_type="quota",
            retryable=False,
            message="Daily quota exhausted - wait for reset"
        )

    # TerminalQuotaError - Gemini CLI specific format (NOT retryable)
    if "TerminalQuotaError" in output:
        return ErrorClassification(
            error_type="quota",
            retryable=False,
            message="Terminal quota error - quota exhausted, wait for reset"
        )

    # "exhausted your capacity" - another Gemini CLI format (NOT retryable)
    if "exhausted your capacity" in output.lower():
        return ErrorClassification(
            error_type="quota",
            retryable=False,
            message="Capacity exhausted - quota depleted, wait for reset"
        )

    # Per-minute rate limit (retryable with fixed wait)
    if "rateLimitExceeded" in output:
        if "per minute" in output.lower() or "per-minute" in output.lower():
            return ErrorClassification(
                error_type="rate_limit_minute",
                retryable=True,
                fixed_wait=60.0,
                message="Per-minute rate limit exceeded"
            )
        # Rate limit without "per minute" - assume retryable
        return ErrorClassification(
            error_type="rate_limit",
            retryable=True,
            message="Rate limit exceeded (will retry)"
        )

    # Generic 429 without specific reason (retryable)
    if "429" in output:
        return ErrorClassification(
            error_type="unknown_429",
            retryable=True,
            message="429 error (will retry)"
        )

    # Unknown error - DO NOT RETRY
    # If we don't know what the error is, retrying will give the same result.
    # Stop immediately and show the raw output so humans can diagnose.
    return ErrorClassification(
        error_type="unknown",
        retryable=False,
        message="Unknown error - STOPPING (see raw output below)"
    )


# =============================================================================
# Backoff Calculation
# =============================================================================

def calculate_delay(attempt: int) -> float:
    """
    Calculate delay with exponential backoff and jitter.

    Args:
        attempt: Current attempt number (1-indexed)

    Returns:
        Delay in seconds
    """
    # Exponential backoff: base * 2^(attempt-1), capped at max
    delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)

    # Add jitter: ±JITTER_FACTOR
    jitter = delay * JITTER_FACTOR * (random.random() * 2 - 1)

    return max(1.0, delay + jitter)  # Minimum 1 second


# =============================================================================
# Logging
# =============================================================================

class RetryLogger:
    """JSONL logger for retry events."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"gemini-retry-{timestamp}.jsonl"
        self._file = None

    def _ensure_open(self):
        if self._file is None:
            self._file = open(self.log_file, "a", encoding="utf-8")

    def log(self, event: str, **kwargs):
        """Log an event to the JSONL file."""
        self._ensure_open()
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **kwargs
        }
        self._file.write(json.dumps(entry) + "\n")
        self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None


# =============================================================================
# Gemini Invocation
# =============================================================================

def invoke_gemini(prompt: str, model: str, no_tools: bool = False) -> GeminiResult:
    """
    Invoke Gemini CLI with the given prompt.

    Args:
        prompt: The prompt to send
        model: The model to use
        no_tools: If True, disable agentic tools (file search, code execution)

    Returns:
        GeminiResult with success/failure info

    Note:
        For large prompts (>PROMPT_SIZE_THRESHOLD), uses stdin instead of -p flag
        to avoid command line length limits and shell escaping issues. (Issue #34)
    """
    import shutil

    # Find gemini executable
    gemini_path = shutil.which("gemini")
    if not gemini_path:
        return GeminiResult(
            success=False,
            response="",
            raw_output="gemini not found in PATH",
            exit_code=-1
        )

    # Determine whether to use stdin or -p flag based on prompt size (Issue #34)
    use_stdin = len(prompt) > PROMPT_SIZE_THRESHOLD

    if use_stdin:
        # Large prompt: use stdin (avoids command line length limits)
        cmd = [
            gemini_path,
            "--model", model,
            "--output-format", "json"
        ]
        if os.environ.get("GEMINI_RETRY_DEBUG"):
            print(f"[DEBUG] Using stdin for large prompt ({len(prompt)} bytes > {PROMPT_SIZE_THRESHOLD})", file=sys.stderr)
    else:
        # Small prompt: use -p flag (simpler)
        cmd = [
            gemini_path,
            "-p", prompt,
            "--model", model,
            "--output-format", "json"
        ]

    # Disable agentic tools if requested (for reviews)
    if no_tools:
        cmd.extend(["--sandbox", "false"])

    try:
        result = subprocess.run(
            cmd,
            input=prompt if use_stdin else None,
            capture_output=True,
            text=True,
            encoding='utf-8',  # Explicit UTF-8 for Unicode characters (box drawing, emojis, etc.)
            timeout=300  # 5 minute timeout per attempt
        )

        output = result.stdout + result.stderr

        # Debug: show what we captured (only if GEMINI_RETRY_DEBUG is set)
        if os.environ.get("GEMINI_RETRY_DEBUG"):
            print(f"[DEBUG] exit={result.returncode}, stdout_len={len(result.stdout)}, stderr_len={len(result.stderr)}", file=sys.stderr)
            # Show first 200 chars of stdout for debugging
            print(f"[DEBUG] stdout_start: {result.stdout[:200]!r}", file=sys.stderr)

        # Check for errors
        # IMPORTANT: Gemini CLI has its own retry mechanism. When it eventually succeeds,
        # stderr may still contain error messages from failed internal attempts.
        # So: if exit=0 AND stdout has JSON, trust it as success.
        #     Only check stderr for errors if exit!=0 or stdout is empty.

        # First, try to detect success: exit=0 and stdout contains JSON
        # Note: stdout may start with "Loaded cached credentials." or other prefix
        if result.returncode == 0 and "{" in result.stdout:
            # Likely success - proceed to JSON parsing below
            pass
        else:
            # Check for errors in combined output
            is_error = (
                result.returncode != 0 or
                "429" in output or
                '"code": 429' in output or
                "CAPACITY_EXHAUSTED" in output or
                "QUOTA_EXHAUSTED" in output or
                "GaxiosError" in output
            )

            if is_error:
                return GeminiResult(
                    success=False,
                    response="",
                    raw_output=output,
                    exit_code=result.returncode
                )

        # Try to parse JSON response
        try:
            # Skip non-JSON prefix (e.g., "Loaded cached credentials.")
            json_start = output.find("{")
            if json_start == -1:
                # No JSON found - Gemini might be in agentic mode returning plain text
                # If exit=0 and we have stdout, treat it as success with plain text response
                if result.returncode == 0 and result.stdout.strip():
                    if os.environ.get("GEMINI_RETRY_DEBUG"):
                        print(f"[DEBUG] No JSON, but exit=0 - treating as plain text success", file=sys.stderr)
                    return GeminiResult(
                        success=True,
                        response=result.stdout.strip(),
                        raw_output=output,
                        model_used=None,  # Can't determine model from plain text
                        exit_code=result.returncode
                    )
                if os.environ.get("GEMINI_RETRY_DEBUG"):
                    print(f"[DEBUG] No JSON found in output", file=sys.stderr)
                return GeminiResult(
                    success=False,
                    response="",
                    raw_output=output,
                    exit_code=result.returncode
                )

            json_str = output[json_start:]

            # Find end of JSON (handle trailing stderr content)
            # Count braces to find the complete JSON object
            brace_count = 0
            json_end = 0
            for i, char in enumerate(json_str):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break

            if json_end > 0:
                json_str = json_str[:json_end]

            data = json.loads(json_str)
            if os.environ.get("GEMINI_RETRY_DEBUG"):
                print(f"[DEBUG] JSON parsed successfully, response_len={len(data.get('response', ''))}", file=sys.stderr)

            # Extract model used from stats
            model_used = None
            if "stats" in data and "models" in data["stats"]:
                models = list(data["stats"]["models"].keys())
                if models:
                    model_used = models[0]

            return GeminiResult(
                success=True,
                response=data.get("response", ""),
                raw_output=output,
                model_used=model_used,
                exit_code=result.returncode
            )
        except json.JSONDecodeError:
            return GeminiResult(
                success=False,
                response="",
                raw_output=output,
                exit_code=result.returncode
            )

    except subprocess.TimeoutExpired:
        return GeminiResult(
            success=False,
            response="",
            raw_output="Timeout after 300 seconds",
            exit_code=-1
        )
    except Exception as e:
        return GeminiResult(
            success=False,
            response="",
            raw_output=str(e),
            exit_code=-1
        )


def validate_model(result: GeminiResult, required_model: str) -> bool:
    """
    Validate that the correct model was used.

    Args:
        result: The Gemini result
        required_model: The model that was requested

    Returns:
        True if model is acceptable, False if downgraded
    """
    if not result.model_used:
        return True  # Can't validate, assume OK

    # Accept the required model or known equivalents
    if result.model_used in ALLOWED_MODELS:
        return True

    if result.model_used == required_model:
        return True

    return False


# =============================================================================
# Credential Rotation
# =============================================================================

def try_credential_rotation(prompt: str, model: str, logger: RetryLogger) -> tuple[bool, str]:
    """
    Try to get a response using credential rotation.

    When the current credential's quota is exhausted, this function
    uses gemini-rotate.py to try other available credentials.

    Args:
        prompt: The prompt to send
        model: The model to use
        logger: Logger for events

    Returns:
        (success, response_or_error)
    """
    import shutil

    # Find the rotation script
    script_dir = Path(__file__).parent
    rotate_script = script_dir / "gemini-rotate.py"

    if not rotate_script.exists():
        return False, f"Rotation script not found: {rotate_script}"

    python_path = shutil.which("python") or shutil.which("python3") or sys.executable

    # Create a temp file for the prompt (handles long prompts better)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        cmd = [
            python_path,
            str(rotate_script),
            "--model", model,
        ]

        # Use stdin for the prompt
        with open(prompt_file, 'r', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                capture_output=True,
                text=True,
                timeout=300
            )

        if result.returncode == 0 and result.stdout.strip():
            logger.log("ROTATION_SUCCESS", model=model)
            return True, result.stdout.strip()
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown rotation error"
            return False, error_msg

    except subprocess.TimeoutExpired:
        return False, "Rotation timeout after 300 seconds"
    except Exception as e:
        return False, str(e)
    finally:
        # Clean up temp file
        try:
            os.unlink(prompt_file)
        except OSError:
            pass


# =============================================================================
# Main Retry Loop
# =============================================================================

def retry_gemini(prompt: str, model: str, logger: RetryLogger, no_tools: bool = False) -> tuple[bool, str]:
    """
    Retry Gemini with exponential backoff.

    Args:
        prompt: The prompt to send
        model: The model to use
        logger: Logger for events
        no_tools: If True, disable agentic tools (file search, code execution)

    Returns:
        (success, response_or_error)
    """
    logger.log("START", model=model, max_retries=MAX_RETRIES, no_tools=no_tools)

    for attempt in range(1, MAX_RETRIES + 1):
        logger.log("ATTEMPT", attempt=attempt, model=model)
        print(f"[GEMINI-RETRY] Attempt {attempt}/{MAX_RETRIES}...", file=sys.stderr)

        result = invoke_gemini(prompt, model, no_tools=no_tools)

        if result.success:
            # Validate model wasn't downgraded
            if not validate_model(result, model):
                logger.log(
                    "MODEL_DOWNGRADE",
                    attempt=attempt,
                    requested=model,
                    actual=result.model_used
                )
                print(
                    f"[GEMINI-RETRY] Model downgrade detected: {result.model_used} "
                    f"(wanted {model}). Retrying...",
                    file=sys.stderr
                )
                # Continue to retry for correct model
            else:
                logger.log(
                    "SUCCESS",
                    attempt=attempt,
                    model_used=result.model_used
                )
                print(
                    f"[GEMINI-RETRY] Success on attempt {attempt} "
                    f"(model: {result.model_used})",
                    file=sys.stderr
                )
                return True, result.response

        # Classify the error
        classification = classify_error(result.raw_output)
        logger.log(
            "ERROR",
            attempt=attempt,
            error_type=classification.error_type,
            retryable=classification.retryable,
            message=classification.message
        )

        if not classification.retryable:
            # Quota exhausted - try credential rotation instead of giving up
            if classification.error_type == "quota":
                logger.log(
                    "QUOTA_EXHAUSTED_TRY_ROTATION",
                    attempt=attempt,
                    error_type=classification.error_type
                )
                print(
                    f"[GEMINI-RETRY] Quota exhausted - attempting credential rotation...",
                    file=sys.stderr
                )

                # Try rotation
                rotation_success, rotation_response = try_credential_rotation(prompt, model, logger)
                if rotation_success:
                    return True, rotation_response
                else:
                    logger.log(
                        "ROTATION_FAILED",
                        attempt=attempt,
                        message=rotation_response
                    )
                    print(
                        f"[GEMINI-RETRY] Rotation failed: {rotation_response}",
                        file=sys.stderr
                    )
                    return False, f"All credentials exhausted: {rotation_response}"

            # Non-quota permanent failure
            logger.log(
                "PERMANENT_FAILURE",
                attempt=attempt,
                error_type=classification.error_type,
                raw_output=result.raw_output[:2000] if result.raw_output else ""
            )
            print(
                f"[GEMINI-RETRY] Permanent failure: {classification.message}",
                file=sys.stderr
            )

            # For unknown errors, print the raw output so humans can diagnose
            if classification.error_type == "unknown":
                print(
                    f"\n{'='*60}\n"
                    f"RAW OUTPUT (so you can see what went wrong):\n"
                    f"{'='*60}\n"
                    f"{result.raw_output}\n"
                    f"{'='*60}\n",
                    file=sys.stderr
                )

            return False, f"Permanent failure: {classification.message}"

        # Calculate delay
        if classification.fixed_wait:
            delay = classification.fixed_wait
        else:
            delay = calculate_delay(attempt)

        # Don't wait after last attempt
        if attempt < MAX_RETRIES:
            logger.log("RETRY_SCHEDULED", attempt=attempt + 1, delay_s=round(delay, 1))
            print(
                f"[GEMINI-RETRY] {classification.message}. "
                f"Retrying in {delay:.0f}s...",
                file=sys.stderr
            )
            time.sleep(delay)

    logger.log("MAX_RETRIES_EXCEEDED", attempts=MAX_RETRIES)
    print(
        f"[GEMINI-RETRY] Max retries ({MAX_RETRIES}) exceeded",
        file=sys.stderr
    )
    return False, f"Max retries ({MAX_RETRIES}) exceeded"


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Retry Gemini CLI with exponential backoff",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  GEMINI_RETRY_MAX              Max retry attempts (default: 20)
  GEMINI_RETRY_BASE_DELAY       Initial delay in seconds (default: 30)
  GEMINI_RETRY_MAX_DELAY        Max delay cap in seconds (default: 600)
  GEMINI_RETRY_LOG_DIR          Log directory (default: logs/)
  GEMINI_RETRY_PROMPT_THRESHOLD Prompt size for stdin switch (default: 10240)

Examples:
  # Simple prompt
  python gemini-retry.py --prompt "Review this code"

  # From file (large prompts auto-use stdin)
  python gemini-retry.py --prompt-file review-prompt.txt

  # For reviews: disable agentic tools (prevents file searching)
  python gemini-retry.py --prompt-file review.txt --no-tools

  # With faster delays for testing
  GEMINI_RETRY_BASE_DELAY=5 python gemini-retry.py --prompt "Hello"
"""
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--prompt", "-p",
        help="The prompt to send to Gemini"
    )
    group.add_argument(
        "--prompt-file", "-f",
        help="Path to file containing the prompt"
    )

    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"Model to use (default: {DEFAULT_MODEL})"
    )

    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable Gemini's agentic tools (file search, code execution). Use for reviews."
    )

    args = parser.parse_args()

    # Get prompt
    if args.prompt_file:
        try:
            with open(args.prompt_file, "r", encoding="utf-8") as f:
                prompt = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.prompt_file}", file=sys.stderr)
            sys.exit(2)
    else:
        prompt = args.prompt

    # Initialize logger
    logger = RetryLogger(LOG_DIR)

    try:
        success, result = retry_gemini(prompt, args.model, logger, no_tools=args.no_tools)

        if success:
            print(result)  # Response to stdout
            sys.exit(0)
        else:
            print(f"Error: {result}", file=sys.stderr)
            sys.exit(1)
    finally:
        logger.close()


if __name__ == "__main__":
    main()
