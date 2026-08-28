"""LLM Provider abstraction for pluggable model support.

Issue #101: Unified Governance Workflow
Issue #395: Anthropic API provider with CLI->API fallback
Issue #605: Systemic Model Refresh â€” Gemini 3.1, Claude 4.6

Provides a unified interface for calling different LLM providers:
- Claude CLI (via claude -p CLI, uses Max subscription)
- Anthropic API (direct API calls, requires ANTHROPIC_API_KEY in .env)
- Gemini (via GeminiClient with credential rotation)
- OpenAI (future)
- Ollama (future)

Spec format: provider:model (e.g. "claude:opus", "anthropic:haiku", "gemini:3.1-pro")

The "claude:" prefix uses CLI first (free via Max subscription), and automatically
falls back to the Anthropic API if an API key is configured in .env.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

# Closes #1495: llm_provider.py uses logger.warning at line 593 for the
# #1431 defensive non-dict-JSON branch, but no logger was ever defined at
# module scope. Every call through that branch raised
# `NameError: name 'logger' is not defined`, surfaced by the testing
# workflow's N4 (implement_code) as "API error: name 'logger' is not
# defined" -- halting the impl stage.
logger = logging.getLogger(__name__)
from abc import ABC, abstractmethod
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from assemblyzero.core import provider_storm, retry_gate
from assemblyzero.core.errors import (
    APIError,
    AuthenticationError,
    BillingError,
    RateLimitError,
    ServerError,
    TimeoutError_,
    classify_anthropic_error,
)
from assemblyzero.core.text_sanitizer import strip_emoji
from assemblyzero.utils.process import kill_process_tree


_PYDANTIC_WARNING_RE = re.compile(
    r".*PydanticDeprecatedSince\d+.*|.*pydantic.*(DeprecationWarning|UserWarning).*|.*Core Pydantic V1.*",
    re.IGNORECASE,
)


def _filter_stderr(stderr: str) -> str:
    """Filter known non-error warnings from subprocess stderr.

    Issue #826: Pydantic deprecation warnings in stderr cause subprocess
    error detection to false-positive. Strip them before error checking.
    """
    if not stderr:
        return stderr
    lines = stderr.splitlines()
    filtered = [line for line in lines if not _PYDANTIC_WARNING_RE.match(line)]
    return "\n".join(filtered).strip()


def _extract_text_from_stream_events(events: object, raw_stdout: str) -> str:
    """Extract the response text from claude -p's streaming-events array.

    Claude CLI v2.1.x returns `[{type: "system", ...}, {type: "assistant",
    message: {content: [{type: "text", text: "..."}]}}, {type: "result",
    result: "..."}]` on `--output-format json`. Closes #1498.

    Priority:
    1. The `result` event's `result` field (canonical, full final text).
    2. The first assistant message's text content (fallback if no result
       event is present in the array — happens on some error paths).
    3. The raw stdout (last resort, preserves the existing behavior for
       unknown shapes).
    """
    if not isinstance(events, list):
        return raw_stdout.strip()

    # 1. result event
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") == "result":
            result_text = event.get("result")
            if isinstance(result_text, str) and result_text:
                return result_text

    # 2. assistant message content
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") != "assistant":
            continue
        message = event.get("message", {})
        if not isinstance(message, dict):
            continue
        for content in message.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "text":
                text = content.get("text", "")
                if isinstance(text, str) and text:
                    return text

    # 3. last-resort raw stdout
    return raw_stdout.strip()


@dataclass
class LLMCallResult:
    """Result of an LLM API call with full observability.

    Attributes:
        success: Whether the call succeeded.
        response: Parsed response text (None on failure).
        raw_response: Full API response for debugging.
        error_message: Error description on failure.
        provider: Provider name ("claude", "gemini", "openai", "ollama").
        model_used: Actual model that generated the response.
        duration_ms: Total time including retries.
        attempts: Number of API call attempts made.
        credential_used: Which credential was used (for rotation tracking).
        rotation_occurred: True if we rotated from initial credential.
        input_tokens: Input token count (0 if unavailable).
        output_tokens: Output token count (0 if unavailable).
        cache_read_tokens: Prompt cache read tokens (claude -p only).
        cache_creation_tokens: Prompt cache creation tokens (claude -p only).
        cost_usd: Cost in USD (0.0 if unavailable).
        rate_limited: True if a 429 was encountered during this call.
    """

    success: bool
    response: Optional[str]
    raw_response: Optional[str]
    error_message: Optional[str]
    provider: str
    model_used: str
    duration_ms: int
    attempts: int
    credential_used: str = ""
    rotation_occurred: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    rate_limited: bool = False
    status_code: Optional[int] = None
    retry_after: Optional[float] = None
    retryable: bool = True
    #: #2423: WHICH failure this was, not merely whether the type is
    #: retryable. `retryable` cannot tell a provider outage from our own
    #: timeout ceiling, and those two want opposite decisions -- back off and
    #: try again, versus halt without a second payment. Empty means the
    #: producer did not classify; consumers fall back to the message.
    failure_class: str = ""


# =============================================================================
# Issue #476: Cumulative cost tracking
# =============================================================================

_cumulative_cost_usd: float = 0.0


def get_cumulative_cost() -> float:
    """Return the cumulative API cost in USD across all calls this session."""
    return _cumulative_cost_usd


def reset_cumulative_cost() -> None:
    """Reset the cumulative cost counter to zero."""
    global _cumulative_cost_usd
    _cumulative_cost_usd = 0.0


# =============================================================================
# Issue #542: Module-level circuit breaker registry
# =============================================================================
# FallbackProvider._consecutive_failures was per-instance, but get_provider()
# creates a fresh instance each LangGraph iteration â€” resetting the counter.
# This module-level dict persists across all instances for the process lifetime.

_circuit_breaker_registry: dict[str, int] = {}
_CIRCUIT_BREAKER_MAX = 2


# =============================================================================
# Issue #773: API policy â€” block Anthropic API usage by default
# =============================================================================
# Default: False (no API). Max subscription makes `claude -p` free.
# Anthropic API costs real money. Opt-in via `--allow-api` CLI flag.

_api_allowed: bool = False


def set_api_policy(allow: bool) -> None:
    """Set whether Anthropic API usage is allowed this session.

    Args:
        allow: True to allow API calls, False to block them.
    """
    global _api_allowed
    _api_allowed = allow


def is_api_allowed() -> bool:
    """Return whether Anthropic API usage is currently allowed."""
    return _api_allowed


def reset_circuit_breakers() -> None:
    """Reset all circuit breaker counters (for testing)."""
    _circuit_breaker_registry.clear()


def log_llm_call(result: LLMCallResult) -> None:
    """Log token usage and cost for an LLM call.

    Issue #398: Prints a structured line after every LLM call.
    Issue #399: Includes rate limit warning if 429 was hit.
    Issue #476: Accumulates cumulative cost and prints running total.
    """
    global _cumulative_cost_usd
    _cumulative_cost_usd += result.cost_usd

    duration_s = result.duration_ms / 1000.0
    parts = [
        f"[LLM] provider={result.provider}",
        f"model={result.model_used}",
    ]
    if result.input_tokens or result.output_tokens:
        parts.append(f"input={result.input_tokens}")
        parts.append(f"output={result.output_tokens}")
    if result.cache_read_tokens:
        parts.append(f"cache_read={result.cache_read_tokens}")
    if result.cache_creation_tokens:
        parts.append(f"cache_create={result.cache_creation_tokens}")
    if result.cost_usd > 0:
        parts.append(f"cost=${result.cost_usd:.4f}")
    if _cumulative_cost_usd > 0:
        parts.append(f"cumulative=${_cumulative_cost_usd:.2f}")
    parts.append(f"duration={duration_s:.1f}s")
    if not result.success:
        parts.append(f"ERROR={result.error_message or 'unknown'}")
    if result.status_code is not None:
        parts.append(f"status={result.status_code}")
    if result.rate_limited:
        parts.append("RATE_LIMITED=true")
    if result.retry_after is not None:
        parts.append(f"retry_after={result.retry_after:.1f}")
    if not result.retryable:
        parts.append("retryable=false")
    # #2423: the class is what decides whether this call is paid for again, so
    # it belongs on the line the operator is already watching.
    if result.failure_class:
        parts.append(f"class={result.failure_class}")

    print("    " + " ".join(parts))


def _load_anthropic_api_key() -> Optional[str]:
    """Load ANTHROPIC_API_KEY from the .env file at the repo root.

    Does NOT check os.environ â€” setting ANTHROPIC_API_KEY as an OS env var
    conflicts with Claude Code's auth. The .env file is the only source.

    Returns:
        The API key string, or None if .env is missing or key not found.
    """
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return None

    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return None

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "ANTHROPIC_API_KEY":
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            return value if value else None

    return None


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Implementations must provide the invoke() method for making API calls.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'claude', 'gemini')."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the model identifier."""
        pass

    @abstractmethod
    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        """Invoke the LLM with system prompt and content.

        Args:
            system_prompt: Instructions for the model.
            content: User content to process.
            timeout_seconds: Maximum time to wait for response.
            response_schema: Optional JSON schema for structured output.
            json_schema: JSON schema dict for structured output via --json-schema (Claude CLI).

        Returns:
            LLMCallResult with response or error information.
        """
        pass


def _kill_process_tree(pid: int) -> None:
    """Kill a process and all its children.

    Issue #526: subprocess.run timeout on Windows only kills the root
    process â€” grandchildren keep pipes open for hundreds of seconds.
    Issue #1874: the primitive now lives in assemblyzero.utils.process so
    the Gemini/agy transport kills tree-wise the same way this one does.
    """
    kill_process_tree(pid)


# --- #2405: streaming transport with an idle timeout -------------------------
#
# Every timeout in this file used to be wall-clock: `proc.communicate(timeout=N)`
# blocks until the child closes its pipes, so the only question it can answer is
# "has N seconds passed", never "is anything still happening". A wall-clock
# ceiling keyed to nothing observable gets overtaken every time the work grows —
# #373 raised it, #2026 raised it, #2405 is the third occurrence — because the
# quantity it bounds is not the quantity that matters.
#
# A call that is emitting tokens is alive by definition. `claude -p
# --output-format stream-json --include-partial-messages` emits a
# content_block_delta per chunk; measured on 2026-08-15 the gaps ran 0.28-0.86s
# with a ~0.65s median across a 150-line generation. So silence is a signal with
# an enormous margin: two minutes of it is roughly 180 missed events, which no
# live generation produces, while a hung process produces nothing but silence.

#: Seconds of total silence before a call is killed. Sits ~180x above the
#: measured inter-event gap, so it separates "stopped" from "slow" without
#: needing to know how long the work legitimately takes.
IDLE_TIMEOUT_SECONDS = 120

#: Override so a pathological-but-real workload never needs a merge to survive.
ENV_IDLE_TIMEOUT = "AZ_LLM_IDLE_TIMEOUT"

#: How often the watchdog checks. Small enough to be precise, large enough to
#: cost nothing over a call measured in minutes.
_IDLE_POLL_SECONDS = 0.5

#: Event types retained for parsing. `stream_event` deltas are the liveness
#: signal and arrive in the thousands, so they are counted and discarded rather
#: than accumulated — the final `result` event carries the complete text anyway.
_DELTA_EVENT_TYPE = "stream_event"


def idle_timeout_seconds() -> int:
    """Idle threshold in seconds, environment-overridable.

    A missing, unparseable, or non-positive override falls back to the default:
    an operator setting this is usually rescuing a stalled run, and a typo must
    not make every call immortal or instantly fatal.
    """
    raw = os.environ.get(ENV_IDLE_TIMEOUT, "").strip()
    if not raw:
        return IDLE_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "%s=%r is not an integer; using %ss",
            ENV_IDLE_TIMEOUT, raw, IDLE_TIMEOUT_SECONDS,
        )
        return IDLE_TIMEOUT_SECONDS
    if value <= 0:
        logger.warning(
            "%s=%s is not positive; using %ss",
            ENV_IDLE_TIMEOUT, value, IDLE_TIMEOUT_SECONDS,
        )
        return IDLE_TIMEOUT_SECONDS
    return value


@dataclass
class _StreamOutcome:
    """What a streamed child process produced, and how it ended."""

    events: list = field(default_factory=list)
    stderr: str = ""
    returncode: int | None = None
    timeout_kind: str = ""  # "" | "idle" | "wall"
    silent_seconds: float = 0.0
    total_events: int = 0

    @property
    def timed_out(self) -> bool:
        return bool(self.timeout_kind)

    def result_payload(self) -> str:
        """The bytes the existing parser expects.

        The final ``result`` event carries the same keys the old
        ``--output-format json`` dict did (``result``, ``usage``,
        ``total_cost_usd``, ``structured_output``), so handing it back as a
        JSON object leaves every downstream branch untouched. Without one —
        an error path, or a kill mid-stream — the retained events go back as
        an array, which the #1498 list branch already knows how to read.
        """
        for event in reversed(self.events):
            if isinstance(event, dict) and event.get("type") == "result":
                return json.dumps(event)
        return json.dumps(self.events)


def _stream_with_idle_timeout(
    proc: subprocess.Popen,
    content: str,
    idle_timeout: int,
    wall_timeout: int | None,
) -> _StreamOutcome:
    """Feed `content` to `proc` and read its stream, killing it when it goes quiet.

    The child is killed when it has produced no output for `idle_timeout`
    seconds. `wall_timeout` remains as an outer backstop for a process that
    streams forever; reaching it is pathological rather than routine, which is
    the inversion this function exists to perform.
    """
    outcome = _StreamOutcome()
    state = {"last": time.monotonic()}
    lock = threading.Lock()

    def _touch() -> None:
        with lock:
            state["last"] = time.monotonic()

    def _last_activity() -> float:
        with lock:
            return state["last"]

    def _pump_stdin() -> None:
        try:
            if proc.stdin:
                proc.stdin.write(content)
                proc.stdin.close()
        except (OSError, ValueError):
            # Child died before consuming stdin; the watchdog reports why.
            pass

    def _pump_stdout() -> None:
        try:
            if not proc.stdout:
                return
            for line in proc.stdout:
                # Liveness is per LINE, before any parsing: a line we cannot
                # decode is still proof the process is running.
                _touch()
                outcome.total_events += 1
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    event = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("type") == _DELTA_EVENT_TYPE:
                    continue
                outcome.events.append(event)
        except (OSError, ValueError):
            pass

    def _pump_stderr() -> None:
        try:
            if proc.stderr:
                outcome.stderr = proc.stderr.read() or ""
        except (OSError, ValueError):
            pass

    threads = [
        threading.Thread(target=_pump_stdin, daemon=True),
        threading.Thread(target=_pump_stdout, daemon=True),
        threading.Thread(target=_pump_stderr, daemon=True),
    ]
    for thread in threads:
        thread.start()

    started = time.monotonic()
    while True:
        returncode = proc.poll()
        if returncode is not None:
            outcome.returncode = returncode
            break

        now = time.monotonic()
        silent_for = now - _last_activity()
        if silent_for >= idle_timeout:
            outcome.timeout_kind = "idle"
            outcome.silent_seconds = silent_for
            _kill_process_tree(proc.pid)
            break
        if wall_timeout is not None and (now - started) >= wall_timeout:
            outcome.timeout_kind = "wall"
            outcome.silent_seconds = silent_for
            _kill_process_tree(proc.pid)
            break

        time.sleep(_IDLE_POLL_SECONDS)

    # Let the readers drain what is already buffered. They are daemons on
    # pipes that are closing, so a bounded join cannot hang the caller.
    for thread in threads:
        thread.join(timeout=5)

    if outcome.returncode is None:
        outcome.returncode = proc.poll()

    return outcome


class ClaudeCLIProvider(LLMProvider):
    """Claude provider using claude -p CLI (Max subscription).

    Uses the user's logged-in Claude Code session, which works with
    Max subscription without requiring API credits.

    Issue #605: Updated to Claude 4.6 model IDs (REQ-2).

    Supported models:
    - opus (claude-opus-4-6)
    - sonnet (claude-sonnet-4-6)
    - haiku (claude-haiku-4-5)
    """

    # Issue #787: Windows CreateProcessW limit is 32,767 chars for the entire
    # command line. Large system prompts (LLD + tests + repo structure) blow
    # this. When exceeded, write to temp dir CLAUDE.md instead of --system-prompt.
    SYSTEM_PROMPT_CLI_LIMIT = 20_000

    # Model mapping from friendly names to actual model specs
    # Issue #605: Claude 4.6 (REQ-2)
    MODEL_MAP = {
        "opus": "claude-opus-4-6",
        "sonnet": "claude-sonnet-4-6",
        "haiku": "claude-haiku-4-5",
    }

    def __init__(self, model: str = "opus", effort: str | None = None):
        """Initialize Claude CLI provider.

        Args:
            model: Model identifier (opus, sonnet, haiku) or full model ID.
            effort: Effort level for claude -p (low/medium/high/max). None omits flag.

        Raises:
            ValueError: If model is not recognized.
        """
        # Normalize model name
        model_lower = model.lower()
        if model_lower in self.MODEL_MAP:
            self._model = model_lower
            self._model_id = self.MODEL_MAP[model_lower]
        elif model_lower.startswith("claude-"):
            # Passthrough: accept full model IDs like claude-opus-4-6-20260415
            self._model = model_lower
            self._model_id = model_lower
        else:
            valid = ", ".join(self.MODEL_MAP.keys())
            raise ValueError(f"Unknown Claude model '{model}'. Valid: {valid}")

        self._effort = effort
        self._cli_path: Optional[str] = None

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model(self) -> str:
        return self._model

    def _find_cli(self) -> str:
        """Find the claude CLI executable.

        Returns:
            Path to claude executable.

        Raises:
            RuntimeError: If claude not found.
        """
        if self._cli_path:
            return self._cli_path

        # Check if claude is in PATH
        claude_path = shutil.which("claude")
        if claude_path:
            self._cli_path = claude_path
            return claude_path

        # Check common npm global install locations
        home = Path.home()
        common_locations = [
            home / "AppData" / "Roaming" / "npm" / "claude.cmd",  # Windows npm
            home / "AppData" / "Roaming" / "npm" / "claude",  # Windows npm (no ext)
            home / ".npm-global" / "bin" / "claude",  # Custom npm prefix
            Path("/usr/local/bin/claude"),  # macOS/Linux global
            home / ".local" / "bin" / "claude",  # Linux local
        ]

        for loc in common_locations:
            if loc.exists():
                self._cli_path = str(loc)
                return self._cli_path

        raise RuntimeError(
            "claude command not found. Ensure Claude Code is installed.\n"
            "Install with: npm install -g @anthropic-ai/claude-code"
        )

    def _probe_alive(self) -> bool:
        """Ask the provider one trivial question. True if it answered (#2405).

        Deliberately uses the plain buffered path with a wall-clock timeout
        rather than the streaming transport it is diagnosing: the probe must be
        able to indict that transport, so it cannot depend on it. A trivial
        prompt answers in seconds, which is the one case where wall-clock is
        the right instrument.
        """
        try:
            cli_path = self._find_cli()
        except RuntimeError:
            return False

        cmd = [
            cli_path,
            "-p",
            "--output-format", "json",
            "--setting-sources", "user",
            "--tools", "",
            "--strict-mcp-config",
            "--model", self._model_id,
        ]
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "ignore"

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                creationflags=creation_flags,
                # See the note in invoke(): off Windows this keeps a tree-kill
                # from taking down the calling process's own group.
                start_new_session=sys.platform != "win32",
                env=env,
            )
        except OSError:
            return False

        try:
            stdout, _ = proc.communicate(
                input=provider_storm.PROBE_PROMPT,
                timeout=provider_storm.PROBE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc.pid)
            try:
                proc.communicate(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                pass
            return False
        except OSError:
            return False

        return proc.returncode == 0 and bool(stdout and stdout.strip())

    def _classify_storm(self, message: str, consecutive: int) -> str:
        """Append the right verdict to a timeout message (#2405).

        Counting consecutive timeouts cannot distinguish a provider that
        stopped answering from a ceiling sitting inside the call's duration.
        One probe can, and it costs seconds against a storm branch that
        otherwise halts the roll for fifteen minutes or more.
        """
        verdict = provider_storm.diagnose(self._probe_alive)
        if verdict == "ceiling":
            # ASCII only: this reaches a cp1252 console, where a dash renders
            # as a literal "?" (the exposure #2367/#2369 are about).
            return (
                f"{message} ({consecutive} consecutive, but a probe was "
                f"answered: {provider_storm.CEILING_MARKER})"
            )
        return (
            f"{message} ({consecutive} consecutive — "
            f"{provider_storm.STORM_MARKER})"
        )

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        """Invoke Claude via headless mode (claude -p).

        Args:
            system_prompt: System instructions for the model.
            content: User content to process.
            timeout_seconds: Maximum time to wait (default 5 minutes).
            response_schema: Ignored for Claude CLI (use json_schema instead).
            json_schema: JSON schema dict for structured output.
                When provided, appends --json-schema '<json>' to CLI args.

        Returns:
            LLMCallResult with response or error.
        """
        start_time = time.time()

        try:
            cli_path = self._find_cli()
        except RuntimeError as e:
            return LLMCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_message=str(e),
                provider=self.provider_name,
                model_used=self._model,
                duration_ms=0,
                attempts=0,
            )

        # Build command - prompt passed via stdin
        # #2405: stream-json instead of json, so the transport can see progress
        # rather than only elapsed time. --include-partial-messages is what makes
        # the stream continuous: without it the assistant event does not arrive
        # until the message is complete, and a long generation would look
        # identical to a hang. --verbose is required for stream-json under -p.
        cmd = [
            cli_path,
            "-p",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--setting-sources", "user",  # Skip project CLAUDE.md context
            "--tools", "",  # Disable built-in tools
            "--strict-mcp-config",  # Disable MCP tools (issue #157)
            "--model", self._model_id,  # Use full model ID (e.g., claude-opus-4-6)
        ]

        # Issue #787: Large system prompts exceed Windows' 32,767-char
        # CreateProcessW limit. Write to temp dir CLAUDE.md instead.
        use_tempdir_prompt = (
            system_prompt
            and len(system_prompt) > self.SYSTEM_PROMPT_CLI_LIMIT
        )

        if system_prompt and not use_tempdir_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        # Issue #773: Effort level (low/medium/high/max)
        if self._effort:
            cmd.extend(["--effort", self._effort])

        # Issue #773: Structured output via --json-schema (legacy response_schema support)
        if json_schema is not None:
            cmd.extend(["--json-schema", json.dumps(json_schema)])
        elif response_schema:
            cmd.extend(["--json-schema", json.dumps(response_schema)])

        try:
            # Use Popen instead of subprocess.run so we can kill the entire
            # process tree on timeout.  subprocess.run + timeout on Windows
            # only kills the root process; grandchild processes keep the
            # pipes open, blocking for 200-400s after the timeout fires.
            # See issue #526.
            # #2037: CREATE_NO_WINDOW or this opens a console window per model
            # call. Whether that shows depends on the PARENT: under the agent's
            # shell the child inherited an existing console and nothing
            # appeared, but a roll running under Task Scheduler (#2015) has no
            # console, so every call allocated its own -- continuously, for the
            # length of an unattended run. Composes with CREATE_NEW_PROCESS_GROUP,
            # which #526 needs to tree-kill on timeout.
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                )

            # #2405: the POSIX counterpart of CREATE_NEW_PROCESS_GROUP, and it is
            # not cosmetic. kill_process_tree() does
            # `os.killpg(os.getpgid(pid), 9)` off Windows, and a child spawned
            # without a new session INHERITS this process's group — so the kill
            # lands on us as well as on the child. Windows never showed it
            # because that path shells out to `taskkill /T /PID`, which is
            # scoped to the one tree. Caught when CI (Linux) hung on the first
            # test that let a real idle timeout fire against a real subprocess.
            start_new_session = sys.platform != "win32"

            # Issue #787: When using temp dir, wrap in TemporaryDirectory
            # context manager so cleanup is guaranteed.
            if use_tempdir_prompt:
                _dir_ctx = tempfile.TemporaryDirectory()
            else:
                _dir_ctx = nullcontext(None)

            with _dir_ctx as temp_path:
                if temp_path:
                    # Write system prompt as CLAUDE.md so claude -p reads it
                    # as project context â€” preserves system prompt caching.
                    Path(temp_path, "CLAUDE.md").write_text(
                        system_prompt, encoding="utf-8"
                    )
                    # Marker so claude finds the project root here
                    Path(temp_path, ".git").mkdir()
                    # Switch from "user" to "user,project" to load CLAUDE.md
                    idx = cmd.index("--setting-sources")
                    cmd[idx + 1] = "user,project"

                env = os.environ.copy()
                env["PYTHONWARNINGS"] = "ignore"

                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    cwd=temp_path,  # None when not using temp dir (= inherit)
                    creationflags=creation_flags,
                    start_new_session=start_new_session,
                    env=env,
                )
                # #2405: the idle threshold is the operative limit; the caller's
                # timeout_seconds survives only as an outer backstop against a
                # process that streams forever.
                idle_limit = idle_timeout_seconds()
                outcome = _stream_with_idle_timeout(
                    proc,
                    content=content,
                    idle_timeout=idle_limit,
                    wall_timeout=timeout_seconds,
                )
                stdout = outcome.result_payload()
                stderr = outcome.stderr

                if outcome.timed_out:
                    duration_ms = int((time.time() - start_time) * 1000)
                    # The literal "timed out" is a contract, not prose:
                    # analyze_requirements._is_timeout classifies by substring
                    # because the provider returns a result rather than raising.
                    # Both branches keep it; only what follows differs.
                    if outcome.timeout_kind == "idle":
                        message = (
                            f"claude -p timed out after "
                            f"{int(outcome.silent_seconds)}s with no output "
                            f"(idle limit {idle_limit}s, {outcome.total_events} "
                            f"events received before it went quiet)"
                        )
                    else:
                        message = (
                            f"claude -p timed out after {timeout_seconds}s while "
                            f"still producing output ({outcome.total_events} "
                            f"events); raise AZ_FILE_TIMEOUT_FLOOR rather than "
                            f"treating this as a provider failure"
                        )
                    # #2086: consecutive timeouts are a provider storm, not a
                    # run of bad luck. Eighteen in one roll on 2026-08-01 killed
                    # two rolls; the counter is what lets the launcher wait
                    # instead of redrawing straight into the same wall.
                    #
                    # #2405: a wall-clock backstop hit by a call that was still
                    # streaming says nothing about provider health, so it must
                    # not feed the storm counter at all. Only silence counts.
                    if outcome.timeout_kind == "idle":
                        consecutive = provider_storm.record_timeout(idle_limit)
                        if provider_storm.is_storm():
                            message = self._classify_storm(message, consecutive)
                    # #2423: the transport is the only place that KNOWS which
                    # wall was hit, so it says so structurally rather than
                    # leaving every retry gate to re-derive it from prose. A
                    # wall-clock kill with the stream alive is deterministic:
                    # the same call runs just as long next time.
                    call_result = LLMCallResult(
                        success=False,
                        response=None,
                        raw_response=stdout,
                        error_message=message,
                        provider=self.provider_name,
                        model_used=self._model,
                        duration_ms=duration_ms,
                        attempts=1,
                        failure_class=retry_gate.classify_failure(
                            message, timeout_kind=outcome.timeout_kind
                        ),
                    )
                    log_llm_call(call_result)
                    return call_result

                duration_ms = int((time.time() - start_time) * 1000)

                # #2086: only a completed call clears the storm counter. A
                # non-timeout error keeps its own classification and leaves the
                # counter alone -- a 400 is a bug in what we sent, and waiting
                # fifteen minutes would not improve it.
                provider_storm.record_success()

                filtered_stderr = _filter_stderr(stderr)

                if proc.returncode != 0:
                    error_msg = filtered_stderr if filtered_stderr else f"CLI exited with code {proc.returncode}"
                    # Check for non-retryable errors (like usage limits)
                    retryable = not is_non_retryable_error(error_msg)

                    # #1883: remember the exhaustion instead of discarding it.
                    # The claude CLI has no usage subcommand, so a failure is
                    # the only signal there is — dropping it meant the next
                    # run started blind and burned Gemini quota finding out.
                    if _is_capacity_message(error_msg):
                        from assemblyzero.core.capacity import record_exhaustion

                        recorded = record_exhaustion("claude", error_msg)
                        print(f"    [CAPACITY] {recorded.wait_summary()}")

                    call_result = LLMCallResult(
                        success=False,
                        response=None,
                        raw_response=stdout,
                        error_message=f"claude -p failed: {error_msg}",
                        provider=self.provider_name,
                        model_used=self._model,
                        duration_ms=duration_ms,
                        attempts=1,
                        retryable=retryable,
                        failure_class=retry_gate.classify_failure(
                            error_msg, retryable=retryable
                        ),
                    )
                    log_llm_call(call_result)
                    return call_result

                # Parse JSON response â€” extract usage stats (Issue #398)
                input_tokens = 0
                output_tokens = 0
                cache_read_tokens = 0
                cache_creation_tokens = 0
                cost_usd = 0.0

                # Determine which schema was used for structured output detection
                active_schema = json_schema if json_schema is not None else response_schema

                try:
                    response_data = json.loads(stdout)

                    # #1431: Defensive — claude -p sometimes returns a top-level
                    # JSON array (rare; observed under certain --json-schema /
                    # error conditions). Calling .get() on a list raises
                    # AttributeError that the bare-except below swallows with a
                    # cryptic "'list' object has no attribute 'get'" message.
                    # Treat any non-dict shape as "use raw stdout" so the call
                    # still completes with a useful response and the raw bytes
                    # are preserved for debugging.
                    if isinstance(response_data, list):
                        # #1767: the streaming-events array IS the current
                        # CLI's normal `--output-format json` shape (#1498) —
                        # it is the primary path, not a surprise. No warning;
                        # every call was paying a scary log line for normal
                        # operation.
                        logger.debug(
                            "claude -p streaming-events array (%d events)",
                            len(response_data),
                        )
                        response_text = _extract_text_from_stream_events(
                            response_data, stdout
                        )
                    elif not isinstance(response_data, dict):
                        # Genuinely unexpected shape (neither dict nor list) —
                        # this one deserves the warning. #1431.
                        logger.warning(
                            "claude -p returned unexpected JSON shape "
                            "(type=%s); attempting stream extraction. "
                            "stdout[:500]=%r",
                            type(response_data).__name__, stdout[:500]
                        )
                        response_text = _extract_text_from_stream_events(
                            response_data, stdout
                        )
                    else:
                        # Issue #779: When --json-schema is used, claude -p puts the
                        # structured output in "structured_output" (dict), not "result"
                        # (which is empty). Serialize it back to JSON string so
                        # downstream consumers (parse_structured_verdict) can parse it.
                        structured_out = response_data.get("structured_output")
                        if structured_out is not None and active_schema:
                            response_text = json.dumps(structured_out)
                        else:
                            response_text = response_data.get("result", "")

                        # Extract usage from claude -p JSON
                        usage = response_data.get("usage", {})
                        input_tokens = usage.get("input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)
                        cache_read_tokens = usage.get("cache_read_input_tokens", 0)
                        cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)
                        cost_usd = response_data.get("total_cost_usd", 0.0)

                except json.JSONDecodeError:
                    # Fall back to raw stdout if not valid JSON
                    response_text = stdout.strip()

                # Issue #527: Strip emojis from response (preserve raw_response)
                response_text = strip_emoji(response_text)

                # #1883: a provider that just answered is not exhausted. This
                # is what makes the gate self-healing when a reset time was
                # unparseable or the window ended early.
                from assemblyzero.core.capacity import clear_exhaustion

                clear_exhaustion("claude")

                call_result = LLMCallResult(
                    success=True,
                    response=response_text,
                    raw_response=stdout,
                    error_message=None,
                    provider=self.provider_name,
                    model_used=self._model,
                    duration_ms=duration_ms,
                    attempts=1,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    cost_usd=cost_usd,
                )
                log_llm_call(call_result)
                return call_result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            call_result = LLMCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_message=str(e),
                provider=self.provider_name,
                model_used=self._model,
                duration_ms=duration_ms,
                attempts=1,
            )
            log_llm_call(call_result)
            return call_result


class AnthropicProvider(LLMProvider):
    """Anthropic API provider for direct Claude API calls.

    Issue #395: Provides direct API access with proper token tracking,
    cost calculation, and error handling. Requires ANTHROPIC_API_KEY in .env.

    Issue #605: Updated to Claude 4.6 model IDs (REQ-2).

    Supported models:
    - opus (claude-opus-4-6)
    - sonnet (claude-sonnet-4-6)
    - haiku (claude-haiku-4-5)
    - Any full model ID as passthrough (e.g. claude-opus-4-6-20260415)
    """

    # Issue #605: Claude 4.6 (REQ-2)
    MODEL_MAP = {
        "opus": "claude-opus-4-6",
        "sonnet": "claude-sonnet-4-6",
        "haiku": "claude-haiku-4-5",
    }

    MAX_TOKENS = 65536

    # Pricing per million tokens (input, output)
    _PRICING: dict[str, tuple[float, float]] = {
        "claude-opus-4-6": (5.0, 25.0),
        "claude-sonnet-4-6": (3.0, 15.0),
        "claude-haiku-4-5": (1.0, 5.0),
    }

    def __init__(self, model: str = "opus"):
        """Initialize Anthropic API provider.

        Args:
            model: Model alias (opus, sonnet, haiku) or full model ID.
        """
        model_lower = model.lower()
        if model_lower in self.MODEL_MAP:
            self._model = model_lower
            self._model_id = self.MODEL_MAP[model_lower]
        else:
            # Passthrough for full model IDs
            self._model = model_lower
            self._model_id = model_lower

        self._client = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    def _get_client(self):
        """Get or create Anthropic client.

        Raises:
            RuntimeError: If API key not found in .env.
        """
        if self._client is None:
            import anthropic

            api_key = _load_anthropic_api_key()
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not found in .env file. "
                    "Add it to the .env file at the repo root."
                )
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """Calculate cost in USD for a call.

        Cache read tokens are charged at 10% of input price.
        Cache creation tokens are charged at 125% of input price.
        """
        pricing = self._PRICING.get(self._model_id)
        if not pricing:
            return 0.0
        input_price, output_price = pricing
        cost = (input_tokens * input_price / 1_000_000) + (
            output_tokens * output_price / 1_000_000
        )
        if cache_read_tokens:
            cost += cache_read_tokens * (input_price * 0.1) / 1_000_000
        if cache_creation_tokens:
            cost += cache_creation_tokens * (input_price * 1.25) / 1_000_000
        return cost

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        """Invoke Claude via the Anthropic API.

        Args:
            system_prompt: System instructions for the model.
            content: User content to process.
            timeout_seconds: Maximum time to wait (default 5 minutes).
            response_schema: Optional JSON schema (accepted for interface
                compatibility but not currently used by Anthropic API).
            json_schema: JSON schema dict (accepted for interface compatibility
                but not currently used by Anthropic API).

        Returns:
            LLMCallResult with response or error.
        """
        start_time = time.time()

        try:
            import httpx

            client = self._get_client()

            # Issue #541: Use streaming to eliminate timeout blindness.
            # client.messages.create() blocks until the entire response is
            # ready â€” on Windows/MSYS2 the httpx read timeout never fires,
            # so calls hang indefinitely.  Streaming gets chunks as they're
            # generated: the connection stays active, and any real stall
            # surfaces as a read-timeout on a per-chunk basis.
            # Issue #488: cache_control directives still work with streaming.
            # Issue #645: Pre-call cost estimate
            est_input_tokens = (len(system_prompt) + len(content)) // 4
            pricing = self._PRICING.get(self._model_id)
            if pricing:
                est_cost = est_input_tokens * pricing[0] / 1_000_000
                print(f"    [COST EST] ~${est_cost:.2f} input ({est_input_tokens:,} tokens, {self._model_id})")
            response_text = ""
            last_progress = time.time()
            with client.messages.stream(
                model=self._model_id,
                max_tokens=self.MAX_TOKENS,
                system=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": [{
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }]}],
                timeout=httpx.Timeout(timeout_seconds, connect=30.0),
            ) as stream:
                for text in stream.text_stream:
                    response_text += text
                    # Progress indicator every 30s
                    now = time.time()
                    if now - last_progress >= 30:
                        chars = len(response_text)
                        elapsed = int(now - start_time)
                        print(
                            f"    [STREAM] {chars:,} chars received "
                            f"({elapsed}s elapsed)",
                            flush=True,
                        )
                        last_progress = now
                response = stream.get_final_message()

            duration_ms = int((time.time() - start_time) * 1000)

            # Issue #527: Strip emojis from response (preserve raw_response)
            response_text = strip_emoji(response_text)

            # Extract usage
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
            cache_create = (
                getattr(response.usage, "cache_creation_input_tokens", 0) or 0
            )

            cost = self._calculate_cost(
                input_tokens, output_tokens, cache_read, cache_create
            )

            call_result = LLMCallResult(
                success=True,
                response=response_text,
                raw_response=str(response),
                error_message=None,
                provider=self.provider_name,
                model_used=self._model,
                duration_ms=duration_ms,
                attempts=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_create,
                cost_usd=cost,
            )
            log_llm_call(call_result)
            return call_result

        except RuntimeError as e:
            # No API key
            duration_ms = int((time.time() - start_time) * 1000)
            call_result = LLMCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_message=str(e),
                provider=self.provider_name,
                model_used=self._model,
                duration_ms=duration_ms,
                attempts=0,
            )
            log_llm_call(call_result)
            return call_result
        except Exception as e:
            import anthropic

            duration_ms = int((time.time() - start_time) * 1000)

            # Issue #542/#546: Classify through the typed error hierarchy
            # and propagate status_code, retry_after, retryable to LLMCallResult
            if isinstance(e, (anthropic.APIError, anthropic.APITimeoutError)):
                classified = classify_anthropic_error(e)
                rate_limited = isinstance(classified, RateLimitError)
                error_msg = str(classified)
                status_code = classified.status_code
                retry_after = classified.retry_after
                retryable = classified.retryable
            else:
                rate_limited = False
                error_msg = f"Anthropic API error: {e}"
                status_code = None
                retry_after = None
                retryable = False

            call_result = LLMCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_message=error_msg,
                provider=self.provider_name,
                model_used=self._model,
                duration_ms=duration_ms,
                attempts=1,
                rate_limited=rate_limited,
                status_code=status_code,
                retry_after=retry_after,
                retryable=retryable,
            )
            log_llm_call(call_result)
            return call_result


def _is_capacity_message(error_msg: str | None) -> bool:
    """True when an error says the subscription is out of capacity (#1883).

    Narrower than is_non_retryable_error, which also covers billing and auth
    failures — recording those as "exhausted until" would block runs for a
    condition that no amount of waiting fixes.
    """
    if not error_msg:
        return False
    lower = error_msg.lower()
    return any(
        pattern in lower
        for pattern in ("usage limit", "usage has been exhausted", "wait until")
    )


def is_non_retryable_error(error_msg: str | None) -> bool:
    """Check if an error message indicates a non-retryable condition.

    Issue #516: Billing, auth, and permission errors should halt immediately
    instead of entering the retry loop. Retrying these is guaranteed to fail.

    Issue #542: Now delegates to the typed error hierarchy.  We construct a
    synthetic exception and attempt classification; if the result maps to a
    non-retryable type (BillingError, AuthenticationError), we return True.

    Args:
        error_msg: Error message string from a failed LLM call.

    Returns:
        True if the error is non-retryable (halt immediately).
    """
    if not error_msg:
        return False

    # Try to classify through the hierarchy
    from assemblyzero.core.errors import _is_billing_message

    if _is_billing_message(error_msg):
        return True

    # Pattern match for auth errors (kept for backward compat with string messages)
    msg = error_msg.lower()
    auth_patterns = [
        "invalid_api_key",
        "invalid api key",
        "authentication_error",
        "authentication failed",
        "permission_denied",
        "permission denied",
        "account is not authorized",
    ]
    return any(pattern in msg for pattern in auth_patterns)


class FallbackProvider(LLMProvider):
    """Tries primary provider first, falls back to secondary on failure.

    Issue #395: Wraps two providers â€” typically CLI (free) primary with
    API (paid) fallback for reliability.
    """

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        primary_timeout: int = 300,
    ):
        """Initialize fallback provider.

        Args:
            primary: First provider to try.
            fallback: Provider to use if primary fails.
            primary_timeout: Max timeout for primary (default 300s).
        """
        self._primary = primary
        self._fallback = fallback
        self._primary_timeout = primary_timeout
        # Issue #542: Circuit breaker uses module-level registry so failures
        # persist across instances (get_provider() creates fresh instances
        # each LangGraph iteration).
        self._breaker_key = f"{primary.provider_name}:{primary.model}"

    @property
    def provider_name(self) -> str:
        return self._primary.provider_name

    @property
    def model(self) -> str:
        return self._primary.model

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        """Invoke primary, fall back to secondary on failure.

        Issue #476: Circuit breaker trips after consecutive both-fail calls.

        Args:
            system_prompt: System instructions for the model.
            content: User content to process.
            timeout_seconds: Maximum time for fallback provider.
            response_schema: Optional JSON schema, passed through to underlying providers.
            json_schema: JSON schema dict for structured output, passed through to underlying providers.

        Returns:
            LLMCallResult from whichever provider succeeded (or last failure).
        """
        # Issue #476/#542: Circuit breaker â€” module-level registry
        failures = _circuit_breaker_registry.get(self._breaker_key, 0)
        if failures >= _CIRCUIT_BREAKER_MAX:
            n = failures
            msg = (
                f"[CIRCUIT BREAKER] {n} consecutive failures. "
                f"Use --resume after API recovers."
            )
            print(f"    {msg}")
            return LLMCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_message=msg,
                provider=self.provider_name,
                model_used=self.model,
                duration_ms=0,
                attempts=0,
            )

        # Issue #539: Skip CLI for large prompts â€” they always time out.
        # LLD/spec prompts are 100K+ chars; the CLI subprocess overhead
        # guarantees a timeout.  Go straight to the API.
        prompt_size = len(system_prompt) + len(content)
        if prompt_size > 50_000:
            print(
                f"    [LLM] Prompt {prompt_size:,} chars â€” "
                f"skipping CLI, using {self._fallback.provider_name} directly"
            )
        else:
            # Try primary with shorter timeout
            effective_timeout = min(timeout_seconds, self._primary_timeout)
            result = self._primary.invoke(
                system_prompt, content, effective_timeout,
                response_schema=response_schema, json_schema=json_schema,
            )
            if result.success:
                _circuit_breaker_registry[self._breaker_key] = 0
                return result

            # Primary failed â€” try fallback with full timeout
            print(
                f"    [LLM] {self._primary.provider_name} failed "
                f"({result.error_message[:80] if result.error_message else 'unknown'}), "
                f"falling back to {self._fallback.provider_name}..."
            )
        fallback_result = self._fallback.invoke(
            system_prompt, content, timeout_seconds,
            response_schema=response_schema, json_schema=json_schema,
        )
        if fallback_result.success:
            _circuit_breaker_registry[self._breaker_key] = 0
        else:
            # Issue #516: Non-retryable errors trip breaker immediately
            if is_non_retryable_error(fallback_result.error_message):
                _circuit_breaker_registry[self._breaker_key] = _CIRCUIT_BREAKER_MAX
                print(
                    f"    [CIRCUIT BREAKER] Non-retryable error detected: "
                    f"{fallback_result.error_message[:100]}"
                )
            else:
                current = _circuit_breaker_registry.get(self._breaker_key, 0)
                _circuit_breaker_registry[self._breaker_key] = current + 1
                print(
                    f"    [CIRCUIT] {current + 1}/"
                    f"{_CIRCUIT_BREAKER_MAX} consecutive failures"
                )
        return fallback_result


class GeminiProvider(LLMProvider):
    """Gemini provider using GeminiClient with credential rotation.

    Wraps the existing GeminiClient to provide the unified LLMProvider interface.
    Inherits all rotation and retry logic from GeminiClient.

    Issue #605: Updated to Gemini 3.1 models (REQ-1). Removed deprecated
    3-pro-preview and 3-flash-preview entries superseded by 3.1 equivalents.

    Supported models:
    - 2.5-pro (alias: pro) - Pro-tier governance model (legacy)
    - 2.5-flash (alias: flash) - Fast Flash model (legacy)
    - 3.1-pro-preview - Latest Pro preview (default)
    - 3.1-pro - Production Pro model
    - 3.1-flash-preview - Latest Flash preview
    """

    # Model mapping from friendly names to actual model IDs
    # Issue #605: Gemini 3.1 (REQ-1) â€” removed deprecated 3.0 entries
    # Issue #1764: agy retired the -preview IDs (catalog verified 2026-07-14
    # via `agy models` + live probe). Pro-line aliases remap to the living
    # gemini-3.1-pro-{low,high} so persisted states and older configs keep
    # working instead of erroring at the CLI. Legacy flash/2.5 entries are
    # untouched (already dead at the CLI; flash is forbidden for governance).
    MODEL_MAP = {
        "2.5-pro": "gemini-2.5-pro",
        "pro": "gemini-2.5-pro",
        "2.5-flash": "gemini-2.5-flash",
        "flash": "gemini-2.5-flash",
        "3.1-pro-preview": "gemini-3.1-pro-high",  # superseded preview (#1764)
        "3.1-pro": "gemini-3.1-pro-high",
        "3.1-pro-high": "gemini-3.1-pro-high",
        "3.1-pro-low": "gemini-3.1-pro-low",
        "3.1-flash-preview": "gemini-3.1-flash-preview",
    }

    def __init__(self, model: str = "3.1-pro"):
        """Initialize Gemini provider.

        Args:
            model: Model identifier (2.5-pro, flash, 3.1-pro-preview, etc.).

        Raises:
            ValueError: If model is not recognized.
        """
        # Normalize model name
        model_lower = model.lower()
        if model_lower not in self.MODEL_MAP:
            valid = ", ".join(self.MODEL_MAP.keys())
            raise ValueError(f"Unknown Gemini model '{model}'. Valid: {valid}")

        self._model = model_lower
        self._model_id = self.MODEL_MAP[model_lower]
        self._client = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    def _get_client(self):
        """Get or create GeminiClient instance."""
        if self._client is None:
            from assemblyzero.core.gemini_client import GeminiClient

            self._client = GeminiClient(model=self._model_id)
        return self._client

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        """Invoke Gemini via GeminiClient.

        Args:
            system_prompt: System instructions for the model.
            content: User content to process.
            timeout_seconds: Maximum time to wait (not directly used - client has own timeout).
            response_schema: Optional JSON schema for structured output (Issue #492).
            json_schema: JSON schema dict (accepted for interface compatibility
                but not used by Gemini â€” use response_schema instead).

        Returns:
            LLMCallResult with response or error.
        """
        try:
            client = self._get_client()
            result = client.invoke(
                system_instruction=system_prompt,
                content=content,
                response_schema=response_schema,
            )

            # Issue #399: detect 429 from error type
            was_rate_limited = (
                result.error_type is not None
                and str(result.error_type) == "GeminiErrorType.QUOTA_EXHAUSTED"
            ) if hasattr(result, "error_type") else False

            # Issue #527: Strip emojis from response (preserve raw_response)
            sanitized_response = strip_emoji(result.response) if result.response else result.response

            call_result = LLMCallResult(
                success=result.success,
                response=sanitized_response,
                raw_response=result.raw_response,
                error_message=result.error_message,
                provider=self.provider_name,
                model_used=result.model_verified or self._model,
                duration_ms=result.duration_ms,
                attempts=result.attempts,
                credential_used=result.credential_used,
                rotation_occurred=result.rotation_occurred,
                rate_limited=was_rate_limited,
                # #1907: a failure GeminiClient.invoke() REPORTS is
                # post-exhaustion — it already retried per credential,
                # rotated across all of them, and enforced its own wall
                # clock (#1874). The dataclass default (retryable=True)
                # invited with_retry(5) to stack five more full gauntlets
                # (~50 min worst case) on top. Riding out longer storms
                # is the stage retry's job (#1909), not another lap here.
                retryable=result.success,
            )
            log_llm_call(call_result)
            return call_result

        except Exception as e:
            # Issue #546: Classify through the typed error hierarchy
            from assemblyzero.core.errors import classify_gemini_error

            classified = classify_gemini_error(e)
            is_rate_limit = isinstance(classified, RateLimitError)
            if is_rate_limit:
                # #2476: name the transport. This prints when something has
                # already failed, and "provider=gemini" beside a gemini-* model
                # id reads as the CLI retired on 2026-06-18 -- which is a
                # different problem with a different next action.
                from assemblyzero.core.gemini_client import PROVIDER_LOG_ID

                print(
                    f"    [LLM] RATE LIMITED: {PROVIDER_LOG_ID} "
                    f"model={self._model} error={str(e)[:100]}"
                )

            call_result = LLMCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_message=str(classified),
                provider=self.provider_name,
                model_used=self._model,
                duration_ms=0,
                attempts=0,
                rate_limited=is_rate_limit,
                status_code=classified.status_code,
                retry_after=classified.retry_after,
                retryable=classified.retryable,
            )
            log_llm_call(call_result)
            return call_result


class MockProvider(LLMProvider):
    """Mock provider for testing without API calls.

    Returns configurable responses for testing workflows.
    """

    # Default responses based on model name
    DEFAULT_RESPONSES = {
        "draft": [
            "# Mock Issue Title\n\n## Summary\n\nThis is a mock draft for testing.\n\n## Requirements\n\n- Mock requirement 1\n- Mock requirement 2\n\n## Acceptance Criteria\n\n- [ ] Mock criteria met",
        ],
        "review": [
            # Standard 0028: mock providers honor the structured contract
            # like every other provider — a schema-valid verdict, never
            # markdown for the retired scrapers. The shape satisfies both
            # FEEDBACK_SCHEMA and REVIEW_SPEC_SCHEMA required keys.
            '{"verdict": "APPROVED", "rationale": "Ready for implementation.'
            ' Well-structured, clear requirements.", "feedback_items": [],'
            ' "open_questions": [], "resolved_issues": []}',
        ],
    }

    def __init__(
        self,
        model: str = "mock",
        responses: list[str] | None = None,
        fail_on_call: int | None = None,
    ):
        """Initialize mock provider.

        Args:
            model: Model identifier (for display).
            responses: List of responses to return in order. Cycles if exhausted.
            fail_on_call: If set, fail on this call number (1-indexed).
        """
        self._model = model
        # Use model-specific defaults if no responses provided
        if responses is None:
            self._responses = self.DEFAULT_RESPONSES.get(model, ["Mock response"])
        else:
            self._responses = responses
        self._fail_on_call = fail_on_call
        self._call_count = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model(self) -> str:
        return self._model

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        """Return mock response.

        Args:
            system_prompt: Ignored.
            content: Ignored.
            timeout_seconds: Ignored.
            response_schema: Ignored.
            json_schema: Ignored.

        Returns:
            LLMCallResult with mock response or error.
        """
        self._call_count += 1

        if self._fail_on_call and self._call_count == self._fail_on_call:
            return LLMCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_message=f"Mock failure on call {self._call_count}",
                provider=self.provider_name,
                model_used=self._model,
                duration_ms=0,
                attempts=1,
            )

        # Cycle through responses
        response_idx = (self._call_count - 1) % len(self._responses)
        response = self._responses[response_idx]

        return LLMCallResult(
            success=True,
            response=response,
            raw_response=response,
            error_message=None,
            provider=self.provider_name,
            model_used=self._model,
            duration_ms=100,  # Simulated latency
            attempts=1,
        )


def parse_provider_spec(spec: str) -> tuple[str, str]:
    """Parse provider:model specification.

    Args:
        spec: Provider spec like "claude:opus" or "gemini:3.1-pro".

    Returns:
        Tuple of (provider_name, model_name).

    Raises:
        ValueError: If spec is malformed.
    """
    if ":" not in spec:
        raise ValueError(
            f"Invalid provider spec '{spec}'. Expected format: provider:model "
            f"(e.g., 'claude:opus', 'gemini:3.1-pro')"
        )

    parts = spec.split(":", 1)
    provider = parts[0].lower()
    model = parts[1]

    return provider, model


def get_provider(spec: str, effort: str | None = None) -> LLMProvider:
    """Factory function to create LLM provider from spec.

    Issue #773: Respects API policy. When API is blocked (default),
    ``claude:`` specs return bare ClaudeCLIProvider (no FallbackProvider),
    and ``anthropic:`` specs raise ValueError.

    Args:
        spec: Provider specification like "claude:opus", "anthropic:haiku",
              or "gemini:3.1-pro".
        effort: Effort level for Claude CLI (low/medium/high/max). None omits flag.

    Returns:
        Configured LLMProvider instance.

    Raises:
        ValueError: If provider or model is not recognized, or if
            ``anthropic:`` is used when API is blocked.

    Examples:
        >>> drafter = get_provider("claude:opus")
        >>> direct = get_provider("anthropic:haiku")  # requires --allow-api
        >>> reviewer = get_provider("gemini:3.1-pro")
        >>> mock = get_provider("mock:test")
    """
    provider, model = parse_provider_spec(spec)

    if provider == "claude":
        cli = ClaudeCLIProvider(model=model, effort=effort)
        # Only wrap with FallbackProvider if API is allowed AND key exists
        if _api_allowed and _load_anthropic_api_key():
            api = AnthropicProvider(model=model)
            return FallbackProvider(primary=cli, fallback=api, primary_timeout=300)
        return cli
    elif provider == "anthropic":
        if not _api_allowed:
            raise ValueError(
                f"Anthropic API usage is blocked (default). "
                f"Use --allow-api to enable paid API calls."
            )
        return AnthropicProvider(model=model)
    elif provider == "gemini":
        return GeminiProvider(model=model)
    elif provider == "mock":
        return MockProvider(model=model)
    elif provider == "scripted":
        # #2567: the end-to-end mock roll. The ACTIVE instance is returned to
        # every caller in one roll on purpose -- a roll has one drafter and
        # one reviewer, and fresh instances would reset the call counters the
        # recorded path and per-rule `on_call` numbering depend on.
        from assemblyzero.core.scripted_provider import get_active

        active = get_active()
        if active is None:
            raise ValueError(
                "provider spec 'scripted:' requires an active "
                "ScriptedProvider. Use the scripted_roll fixture, or call "
                "scripted_provider.set_active(...) first (#2567)."
            )
        return active
    else:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Supported: claude, anthropic, gemini, mock, scripted"
        )
