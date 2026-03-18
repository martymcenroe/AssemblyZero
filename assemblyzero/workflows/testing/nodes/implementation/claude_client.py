"""Claude API client for code generation.

Uses the unified provider gate (get_provider) for all LLM calls.
Issue #783: Sealed API gate — no more direct CLI/SDK fallback.
"""

import threading
import time

from assemblyzero.core.llm_provider import get_provider


# Issue #321: Timeout constants
# Issue #373: Increased from 300s — large test file prompts need more time
CLI_TIMEOUT = 600  # 10 minutes base (used by compute_dynamic_timeout)


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

    Issue #783: Uses unified provider gate (get_provider) instead of
    rolling its own CLI/SDK fallback. Respects --no-api policy.
    """
    # Issue #373: Dynamic timeout based on prompt size
    timeout = compute_dynamic_timeout(prompt)

    # Issue #643: Use provided stable system prompt, fall back to per-file prompt
    effective_system_prompt = system_prompt or build_system_prompt(file_path)

    # Issue #783: Use unified provider — respects API policy gate
    try:
        provider = get_provider(f"claude:{model or 'opus'}")
        result = provider.invoke(
            system_prompt=effective_system_prompt,
            content=prompt,
            timeout_seconds=timeout,
        )
        if result.success:
            return result.response, ""
        else:
            error_msg = result.error_message or "Unknown error"
            if not result.retryable:
                return "", f"[NON-RETRYABLE] {error_msg}"
            return "", error_msg
    except Exception as e:
        return "", f"Provider error: {e}"
