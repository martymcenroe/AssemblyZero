"""Claude API client for code generation.

Handles CLI and SDK fallback, timeouts, and progress reporting.
"""

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from assemblyzero.core.config import CLAUDE_MODEL
from assemblyzero.core.text_sanitizer import strip_emoji
from assemblyzero.utils.shell import run_command


# Issue #321: Timeout constants
# Issue #373: Increased from 300s — large test file prompts need more time
CLI_TIMEOUT = 600  # 10 minutes base for CLI subprocess
SDK_TIMEOUT = 600  # 10 minutes base for SDK API call


class ProgressReporter:
    """Print elapsed time periodically during long operations.

    Issue #267: Prevents the workflow from appearing frozen during
    long Claude API calls. Prints every `interval` seconds.

    Usage:
        with ProgressReporter("Calling Claude", interval=15):
            response = call_claude_for_file(prompt)
    """

    def __init__(self, label: str = "Waiting", interval: int = 15):
        self.label = label
        self.interval = interval
        self._start: float = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self):
        self._start = time.monotonic()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        elapsed = int(time.monotonic() - self._start)
        status = "done" if not exc[0] else "error"
        print(f"        {self.label}... {status} ({elapsed}s)")
        return False

    def _run(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(self.interval)
            if not self._stop_event.is_set():
                elapsed = int(time.monotonic() - self._start)
                print(f"        {self.label}... ({elapsed}s)", flush=True)


class ImplementationError(Exception):
    """Raised when implementation fails mechanically.

    Graph runner should catch this and exit non-zero.
    """
    def __init__(self, filepath: str, reason: str, response_preview: str | None = None):
        self.filepath = filepath
        self.reason = reason
        self.response_preview = response_preview
        super().__init__(f"FATAL: Failed to implement {filepath}: {reason}")


def _find_claude_cli() -> str | None:
    """Find the Claude CLI executable."""
    cli = shutil.which("claude")
    if cli:
        return cli

    npm_paths = [
        Path.home() / "AppData" / "Roaming" / "npm" / "claude.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "claude",
        Path.home() / ".npm-global" / "bin" / "claude",
        Path("/c/Users") / os.environ.get("USERNAME", "") / "AppData" / "Roaming" / "npm" / "claude.cmd",
    ]

    for path in npm_paths:
        if path.exists():
            return str(path)

    return None


def compute_dynamic_timeout(prompt: str) -> int:
    """Compute timeout based on prompt size.

    Issue #373: Larger prompts need more time for Claude to generate
    correspondingly large responses. Scale linearly with a floor and cap.

    Args:
        prompt: The prompt string.

    Returns:
        Timeout in seconds (300-600 range).
    """
    base = 300
    # Add 1 second per 1000 characters of prompt
    scaled = base + len(prompt) // 1000
    return min(scaled, CLI_TIMEOUT)


def build_system_prompt(file_path: str) -> str:
    """Build a file-type-aware system prompt for Claude.

    Issue #447: Adjusts the language tag and framing based on file type.
    """
    from assemblyzero.utils.file_type import get_file_type_info

    info = get_file_type_info(file_path)
    tag = info["language_tag"]
    descriptor = info["content_descriptor"]

    if tag:
        block_instruction = f"Just the {descriptor} in a ```{tag} block"
    else:
        block_instruction = f"Just the {descriptor} in a fenced code block"

    return f"""You are a file generator. Output ONLY the complete file contents.

RULES:
1. Output a single fenced code block with the complete file contents
2. No explanations before or after the content
3. No summaries
4. No "I've implemented..." statements
5. {block_instruction}

If you output anything other than a fenced code block, the build will fail."""


def call_claude_for_file(
    prompt: str,
    file_path: str = "",
    model: str | None = None,
    system_prompt: str = "",
) -> tuple[str, str]:
    """Call Claude for a single file implementation.

    Issue #447: Added file_path parameter for file-type-aware system prompt.
    Issue #641: Added model parameter for Haiku routing.
    Issue #643: Added system_prompt parameter. When provided, this stable
    system prompt is used instead of the per-file build_system_prompt().
    For SDK path, it's passed as the ``system=`` kwarg to enable caching.

    Returns (response, error).
    NO RETRIES - if it fails, it fails.
    """
    claude_cli = _find_claude_cli()
    # Issue #373: Dynamic timeout based on prompt size
    timeout = compute_dynamic_timeout(prompt)

    # Issue #641: Resolve model — CLI uses short names, SDK uses full model IDs
    cli_model = model or "opus"

    # Issue #643: Use provided stable system prompt, fall back to per-file prompt
    effective_system_prompt = system_prompt or build_system_prompt(file_path)

    if claude_cli:
        try:
            cmd = [
                claude_cli,
                "--print",
                "--dangerously-skip-permissions",
                "--model", cli_model,
                "--system-prompt", effective_system_prompt,
            ]

            result = run_command(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,  # Issue #373: Dynamic timeout
            )

            if result.returncode == 0 and result.stdout.strip():
                # Issue #527: Strip emojis from code gen response
                return strip_emoji(result.stdout), ""
            else:
                stderr = result.stderr[:200] if result.stderr else "no stderr"
                # Fall through to SDK
                print(f"    [WARN] CLI failed (exit {result.returncode}): {stderr}")

        except subprocess.TimeoutExpired:
            return "", f"CLI timeout after {timeout}s waiting for response"
        except FileNotFoundError:
            print("    [WARN] Claude CLI not found, falling back to SDK")
        except OSError as e:
            print(f"    [WARN] CLI error: {e}")

    # Fallback to SDK with streaming (Issue #541)
    try:
        import anthropic
        import httpx

        # Issue #373: Dynamic timeout for SDK too
        client = anthropic.Anthropic(
            timeout=httpx.Timeout(timeout, connect=30.0)
        )

        # Issue #625: Pass system prompt as structured block with cache_control.
        # Mirrors the pattern in AnthropicProvider (llm_provider.py:662-670).
        # First file pays 125% (cache write), files 2+ pay 10% (cache read).
        sdk_system = [
            {
                "type": "text",
                "text": effective_system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        # Issue #541: Streaming eliminates timeout blindness — chunks
        # arrive incrementally so the connection stays active.  The old
        # client.messages.create() blocked for the entire generation
        # and httpx timeouts never fired on Windows/MSYS2.
        response_text = ""
        with client.messages.stream(
            model=model or CLAUDE_MODEL,
            max_tokens=32768,
            system=sdk_system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                response_text += text

        # Issue #625: Log cache metrics for cost visibility
        final_msg = stream.get_final_message()
        usage = final_msg.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
        if cache_read or cache_create:
            print(f"        [CACHE] read={cache_read} create={cache_create}")

        # Issue #527: Strip emojis from code gen response
        return strip_emoji(response_text), ""

    except ImportError:
        return "", "Neither Claude CLI nor Anthropic SDK available"
    except httpx.TimeoutException:
        return "", f"SDK timeout after {timeout}s waiting for response"
    except TimeoutError:
        return "", f"SDK timeout after {timeout}s waiting for response"
    except Exception as e:
        # Issue #546: Classify through the typed error hierarchy
        try:
            from assemblyzero.core.errors import classify_anthropic_error
            classified = classify_anthropic_error(e)
            status_code = classified.status_code
            prefix = "[NON-RETRYABLE] " if not classified.retryable else ""
            return "", f"{prefix}SDK error (status={status_code}): {e}"
        except Exception:
            return "", f"SDK error: {e}"
