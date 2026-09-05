"""Claude API client for code generation.

Uses the unified provider gate (get_provider) for all LLM calls.
Issue #783: Sealed API gate — no more direct CLI/SDK fallback.
"""

import os
import threading
import time

from assemblyzero.core.llm_provider import get_provider


# Issue #321: Timeout constants
# Issue #373: Increased from 300s — large test file prompts need more time
CLI_TIMEOUT = 600  # 10 minutes base (historical; no longer the floor)

# #2026: what a file generation gets at minimum, and at most. The floor is what
# matters: generation time tracks the RESPONSE, and a compact prompt can ask for
# a very large file. The costs are asymmetric — an over-long timeout waits out
# one slow call, while an under-long one kills the stage and stalls the arc.
#
# #2405: the floor was CLI_TIMEOUT (600) and boostgauge #1 died against it five
# times, four of them reading "timed out after 602s". That 602 is the whole
# story of why this moved. The scaling below grants one second per 1000
# characters, so a 2.5 KB fix-loop prompt bought two seconds over the floor;
# reaching the 1200 cap from a 600 floor needs a 600,000-character prompt, which
# nothing here produces. The cap had therefore never once bound, and the floor
# had silently been the entire timeout since #373 introduced the scaling. The
# floor now starts where the cap was, and both are environment-overridable so
# that the next time the distribution outgrows a constant, the remedy is a
# variable rather than a merge.
#
# #2843: at 1200 this "backstop for silence" killed two calls in one green
# iteration of boostgauge run 15 that were still streaming (1,674 and 1,804
# events), each costing the twenty minutes spent plus a whole-file
# regeneration. The idle timeout is the guard against a dead call; a call
# still producing output is not stuck, and the wall clock protects nothing
# the cost budget does not. An hour is the outer bound for one file.
FILE_TIMEOUT_FLOOR = 3600
FILE_TIMEOUT_CAP = 3600

#: Override names. Values are whole seconds. A missing, unparseable, or
#: non-positive value falls back to the default rather than failing the call:
#: an operator reaching for these is usually unblocking a stalled run, and a
#: typo must not turn a slow call into a dead one.
ENV_TIMEOUT_FLOOR = "AZ_FILE_TIMEOUT_FLOOR"
ENV_TIMEOUT_CAP = "AZ_FILE_TIMEOUT_CAP"


def _env_seconds(name: str, default: int) -> int:
    """Read a positive whole-second count from the environment."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        print(f"    [TIMEOUT] {name}={raw!r} is not an integer; using {default}s")
        return default
    if value <= 0:
        print(f"    [TIMEOUT] {name}={value} is not positive; using {default}s")
        return default
    return value


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

    #2026: that premise only ever held one way round. Generation time tracks the
    RESPONSE, and prompt size does not predict it — a compact spec can ask for a
    very large file. boostgauge #1 died on `skins/stingray.py`, a big renderer
    described in about 1.5 KB: it computed 301s, the old floor, and every one of
    15 attempts hit the same deterministic wall for 11m28s before the stage gave
    up and stalled the arc at phase 3 of 6.

    So the floor now carries the weight and the scaling is left as a bonus for
    genuinely large prompts. A too-long timeout costs waiting on one slow call;
    a too-short one costs the stage.

    #2405: this is now the outer wall-clock backstop, not the operative limit.
    A call is killed for going quiet (see the idle timeout in
    ``ClaudeCLIProvider.invoke``), and reaching this value at all means the
    process stayed silent for the whole window. The floor and cap are
    environment-overridable via ``AZ_FILE_TIMEOUT_FLOOR`` / ``AZ_FILE_TIMEOUT_CAP``.

    That also retires the "bonus for genuinely large prompts" above: the floor
    now starts at the cap, so the scaling term can no longer change the result.
    It was never doing the work anyway. The prompt that killed boostgauge #1 was
    about 2.5 KB, which bought two seconds, and the run's log records the limit
    as 602s for exactly that reason.

    Args:
        prompt: The prompt string.

    Returns:
        Timeout in seconds (floor–cap range, both overridable).
    """
    floor = _env_seconds(ENV_TIMEOUT_FLOOR, FILE_TIMEOUT_FLOOR)
    # A cap below the floor would silently undo an operator's floor override,
    # which is the opposite of what they reached for the variable to do.
    cap = max(_env_seconds(ENV_TIMEOUT_CAP, FILE_TIMEOUT_CAP), floor)

    # Add 1 second per 1000 characters of prompt
    scaled = floor + len(prompt) // 1000
    return min(scaled, cap)


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
