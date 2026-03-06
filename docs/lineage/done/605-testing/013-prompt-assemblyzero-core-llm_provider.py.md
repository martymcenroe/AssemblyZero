# Implementation Request: assemblyzero/core/llm_provider.py

## Task

Write the complete contents of `assemblyzero/core/llm_provider.py`.

Change type: Modify
Description: Mapping update

## LLD Specification

# Implementation Spec: 0605 - Systemic Model Refresh

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #605 |
| LLD | `docs/lld/active/LLD-605.md` |
| Generated | 2026-03-06 |
| Status | APPROVED |

## 1. Overview
Align models with Gemini 3.1.

## 2. Files to Implement
| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/core/config.py` | Modify | Default update |
| 2 | `assemblyzero/core/llm_provider.py` | Modify | Mapping update |
| 3 | `tools/gemini-rotate.py` | Modify | String update |
| 4 | `tools/gemini-model-check.sh` | Add | Check script |
| 5 | `tests/test_assemblyzero_config.py` | Modify | Test update |
| 6 | `tests/test_gemini_client.py` | Modify | Test update |

## 3. Requirements
1. Use Gemini 3.1.
2. Update Claude 4.6.

## 10. Test Mapping
| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | Model ID verification (REQ-1) | Success |
| T020 | Claude mapping verification (REQ-2) | Success |

## 10. Implementation Notes
None.


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  adversarial/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    death/
    issue_workflow/
    janitor/
      mock_repo/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    spelunking/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_death/
    test_gate/
    test_janitor/
    test_rag/
    test_spelunking/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 14 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  spelunking/
  telemetry/
  utils/
  workflows/
    death/
    implementation_spec/
      nodes/
    issue/
      nodes/
    janitor/
      probes/
    lld/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      runners/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  hourglass/
  unleashed/
```

Use these real paths — do NOT invent paths that don't exist.

## Existing File Contents

The file currently contains:

```python
"""LLM Provider abstraction for pluggable model support.

Issue #101: Unified Governance Workflow
Issue #395: Anthropic API provider with CLI→API fallback

Provides a unified interface for calling different LLM providers:
- Claude CLI (via claude -p CLI, uses Max subscription)
- Anthropic API (direct API calls, requires ANTHROPIC_API_KEY in .env)
- Gemini (via GeminiClient with credential rotation)
- OpenAI (future)
- Ollama (future)

Spec format: provider:model (e.g. "claude:opus", "anthropic:haiku", "gemini:2.5-pro")

The "claude:" prefix uses CLI first (free via Max subscription), and automatically
falls back to the Anthropic API if an API key is configured in .env.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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
# creates a fresh instance each LangGraph iteration — resetting the counter.
# This module-level dict persists across all instances for the process lifetime.

_circuit_breaker_registry: dict[str, int] = {}
_CIRCUIT_BREAKER_MAX = 2


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

    print("    " + " ".join(parts))


def _load_anthropic_api_key() -> Optional[str]:
    """Load ANTHROPIC_API_KEY from the .env file at the repo root.

    Does NOT check os.environ — setting ANTHROPIC_API_KEY as an OS env var
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
    ) -> LLMCallResult:
        """Invoke the LLM with system prompt and content.

        Args:
            system_prompt: Instructions for the model.
            content: User content to process.
            timeout_seconds: Maximum time to wait for response.

        Returns:
            LLMCallResult with response or error information.
        """
        pass


def _kill_process_tree(pid: int) -> None:
    """Kill a process and all its children.

    On Windows, uses taskkill /T (tree-kill) to terminate the entire
    process group.  On Unix, kills the process group via os.killpg.
    Issue #526: subprocess.run timeout on Windows only kills the root
    process — grandchildren keep pipes open for hundreds of seconds.
    """
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=10,
            )
        else:
            os.killpg(os.getpgid(pid), 9)
    except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
        # Process already dead — that's fine
        pass


class ClaudeCLIProvider(LLMProvider):
    """Claude provider using claude -p CLI (Max subscription).

    Uses the user's logged-in Claude Code session, which works with
    Max subscription without requiring API credits.

    Supported models:
    - opus (default for governance)
    - sonnet (faster, lower quality)
    - haiku (fastest, lowest quality)
    """

    # Model mapping from friendly names to actual model specs
    MODEL_MAP = {
        "opus": "claude-opus-4-6",
        "sonnet": "claude-sonnet-4-6",
        "haiku": "claude-haiku-4-5",
    }

    def __init__(self, model: str = "opus"):
        """Initialize Claude CLI provider.

        Args:
            model: Model identifier (opus, sonnet, haiku) or full model ID.

        Raises:
            ValueError: If model is not recognized.
        """
        # Normalize model name
        model_lower = model.lower()
        if model_lower in self.MODEL_MAP:
            self._model = model_lower
            self._model_id = self.MODEL_MAP[model_lower]
        elif model_lower.startswith("claude-"):
            # Passthrough: accept full model IDs like claude-opus-4-7-20260415
            self._model = model_lower
            self._model_id = model_lower
        else:
            valid = ", ".join(self.MODEL_MAP.keys())
            raise ValueError(f"Unknown Claude model '{model}'. Valid: {valid}")

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

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
    ) -> LLMCallResult:
        """Invoke Claude via headless mode (claude -p).

        Args:
            system_prompt: System instructions for the model.
            content: User content to process.
            timeout_seconds: Maximum time to wait (default 5 minutes).

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
        cmd = [
            cli_path,
            "-p",
            "--output-format", "json",
            "--setting-sources", "user",  # Skip project CLAUDE.md context
            "--tools", "",  # Disable built-in tools
            "--strict-mcp-config",  # Disable MCP tools (issue #157)
            "--model", self._model_id,  # Use full model ID (e.g., claude-opus-4-5-20251101)
        ]

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        try:
            # Use Popen instead of subprocess.run so we can kill the entire
            # process tree on timeout.  subprocess.run + timeout on Windows
            # only kills the root process; grandchild processes keep the
            # pipes open, blocking for 200-400s after the timeout fires.
            # See issue #526.
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                creationflags=creation_flags,
            )
            try:
                stdout, stderr = proc.communicate(
                    input=content, timeout=timeout_seconds
                )
            except subprocess.TimeoutExpired:
                # Kill the entire process tree so pipes close immediately
                _kill_process_tree(proc.pid)
                # Drain any remaining pipe data
                try:
                    proc.communicate(timeout=5)
                except (subprocess.TimeoutExpired, OSError):
                    pass
                duration_ms = int((time.time() - start_time) * 1000)
                call_result = LLMCallResult(
                    success=False,
                    response=None,
                    raw_response=None,
                    error_message=f"claude -p timed out after {timeout_seconds}s",
                    provider=self.provider_name,
                    model_used=self._model,
                    duration_ms=duration_ms,
                    attempts=1,
                )
                log_llm_call(call_result)
                return call_result

            duration_ms = int((time.time() - start_time) * 1000)

            if proc.returncode != 0:
                error_msg = stderr or stdout or "Unknown error"
                # Check for non-retryable errors (like usage limits)
                retryable = not is_non_retryable_error(error_msg)
                
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
                )
                log_llm_call(call_result)
                return call_result

            # Parse JSON response — extract usage stats (Issue #398)
            input_tokens = 0
            output_tokens = 0
            cache_read_tokens = 0
            cache_creation_tokens = 0
            cost_usd = 0.0

            try:
                response_data = json.loads(stdout)
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

    Supported models:
    - opus (claude-opus-4-6)
    - sonnet (claude-sonnet-4-6)
    - haiku (claude-haiku-4-5)
    - Any full model ID as passthrough (e.g. claude-opus-4-7-20260415)
    """

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
    ) -> LLMCallResult:
        """Invoke Claude via the Anthropic API.

        Args:
            system_prompt: System instructions for the model.
            content: User content to process.
            timeout_seconds: Maximum time to wait (default 5 minutes).

        Returns:
            LLMCallResult with response or error.
        """
        start_time = time.time()

        try:
            import httpx

            client = self._get_client()

            # Issue #541: Use streaming to eliminate timeout blindness.
            # client.messages.create() blocks until the entire response is
            # ready — on Windows/MSYS2 the httpx read timeout never fires,
            # so calls hang indefinitely.  Streaming gets chunks as they're
            # generated: the connection stays active, and any real stall
            # surfaces as a read-timeout on a per-chunk basis.
            # Issue #488: cache_control directives still work with streaming.
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

    Issue #395: Wraps two providers — typically CLI (free) primary with
    API (paid) fallback for reliability.
    """

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        primary_timeout: int = 180,
    ):
        """Initialize fallback provider.

        Args:
            primary: First provider to try.
            fallback: Provider to use if primary fails.
            primary_timeout: Max timeout for primary (default 180s).
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
    ) -> LLMCallResult:
        """Invoke primary, fall back to secondary on failure.

        Issue #476: Circuit breaker trips after consecutive both-fail calls.

        Args:
            system_prompt: System instructions for the model.
            content: User content to process.
            timeout_seconds: Maximum time for fallback provider.

        Returns:
            LLMCallResult from whichever provider succeeded (or last failure).
        """
        # Issue #476/#542: Circuit breaker — module-level registry
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

        # Issue #539: Skip CLI for large prompts — they always time out.
        # LLD/spec prompts are 100K+ chars; the CLI subprocess overhead
        # guarantees a 180s timeout.  Go straight to the API.
        prompt_size = len(system_prompt) + len(content)
        if prompt_size > 50_000:
            print(
                f"    [LLM] Prompt {prompt_size:,} chars — "
                f"skipping CLI, using {self._fallback.provider_name} directly"
            )
        else:
            # Try primary with shorter timeout
            effective_timeout = min(timeout_seconds, self._primary_timeout)
            result = self._primary.invoke(system_prompt, content, effective_timeout)
            if result.success:
                _circuit_breaker_registry[self._breaker_key] = 0
                return result

            # Primary failed — try fallback with full timeout
            print(
                f"    [LLM] {self._primary.provider_name} failed "
                f"({result.error_message[:80] if result.error_message else 'unknown'}), "
                f"falling back to {self._fallback.provider_name}..."
            )
        fallback_result = self._fallback.invoke(system_prompt, content, timeout_seconds)
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

    Supported models:
    - 2.5-pro (alias: pro) - Pro-tier governance model
    - 2.5-flash (alias: flash) - Fast Flash model
    - 3.1-pro-preview - Latest Pro preview
    - 3-pro-preview - Previous Pro preview (EOL soon)
    - 3-pro - Production Pro model
    - 3-flash-preview - Latest Flash preview
    """

    # Model mapping from friendly names to actual model IDs
    MODEL_MAP = {
        "2.5-pro": "gemini-2.5-pro",
        "pro": "gemini-2.5-pro",
        "2.5-flash": "gemini-2.5-flash",
        "flash": "gemini-2.5-flash",
        "3-pro-preview": "gemini-3-pro-preview",
        "3.1-pro-preview": "gemini-3.1-pro-preview",
        "3-flash-preview": "gemini-3-flash-preview",
    }

    def __init__(self, model: str = "3.1-pro-preview"):
        """Initialize Gemini provider.

        Args:
            model: Model identifier (2.5-pro, flash, 3-pro-preview, etc.).

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
    ) -> LLMCallResult:
        """Invoke Gemini via GeminiClient.

        Args:
            system_prompt: System instructions for the model.
            content: User content to process.
            timeout_seconds: Maximum time to wait (not directly used - client has own timeout).
            response_schema: Optional JSON schema for structured output (Issue #492).

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
            )
            log_llm_call(call_result)
            return call_result

        except Exception as e:
            # Issue #546: Classify through the typed error hierarchy
            from assemblyzero.core.errors import classify_gemini_error

            classified = classify_gemini_error(e)
            is_rate_limit = isinstance(classified, RateLimitError)
            if is_rate_limit:
                print(f"    [LLM] RATE LIMITED: provider=gemini model={self._model} error={str(e)[:100]}")

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
            "## Final Verdict\n\n[X] **APPROVED** - Ready for implementation\n[ ] **REVISE** - Requires changes\n[ ] **DISCUSS** - Needs clarification\n\n### Strengths\n- Well-structured\n- Clear requirements\n\n### Recommendations\n- None required for approval",
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
    ) -> LLMCallResult:
        """Return mock response.

        Args:
            system_prompt: Ignored.
            content: Ignored.
            timeout_seconds: Ignored.

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
        spec: Provider spec like "claude:opus" or "gemini:2.5-pro".

    Returns:
        Tuple of (provider_name, model_name).

    Raises:
        ValueError: If spec is malformed.
    """
    if ":" not in spec:
        raise ValueError(
            f"Invalid provider spec '{spec}'. Expected format: provider:model "
            f"(e.g., 'claude:opus', 'gemini:2.5-pro')"
        )

    parts = spec.split(":", 1)
    provider = parts[0].lower()
    model = parts[1]

    return provider, model


def get_provider(spec: str) -> LLMProvider:
    """Factory function to create LLM provider from spec.

    Args:
        spec: Provider specification like "claude:opus", "anthropic:haiku",
              or "gemini:2.5-pro".

    Returns:
        Configured LLMProvider instance.

    Raises:
        ValueError: If provider or model is not recognized.

    Examples:
        >>> drafter = get_provider("claude:opus")
        >>> direct = get_provider("anthropic:haiku")
        >>> reviewer = get_provider("gemini:2.5-pro")
        >>> mock = get_provider("mock:test")
    """
    provider, model = parse_provider_spec(spec)

    if provider == "claude":
        cli = ClaudeCLIProvider(model=model)
        # If API key available, wrap with automatic fallback
        if _load_anthropic_api_key():
            api = AnthropicProvider(model=model)
            return FallbackProvider(primary=cli, fallback=api, primary_timeout=180)
        return cli
    elif provider == "anthropic":
        return AnthropicProvider(model=model)
    elif provider == "gemini":
        return GeminiProvider(model=model)
    elif provider == "mock":
        return MockProvider(model=model)
    else:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Supported: claude, anthropic, gemini, mock"
        )

```

Modify this file according to the LLD specification.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero-605\tests\test_issue_605.py
"""Test file for Issue #605.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from assemblyzero.core.config import *  # noqa: F401, F403


# Unit Tests
# -----------

def test_t010():
    """
    Model ID verification (REQ-1) | Success
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t010 works correctly
    assert False, 'TDD RED: test_t010 not implemented'


def test_t020():
    """
    Claude mapping verification (REQ-2) | Success
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t020 works correctly
    assert False, 'TDD RED: test_t020 not implemented'




```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/core/config.py (full)

```python
"""Configuration constants for AssemblyZero LLD review.

This module defines constants that control LLD review behavior,
including model hierarchy and credential paths.
"""

import os
from pathlib import Path

# =============================================================================
# Model Hierarchy (NEVER downgrade for reviews)
# =============================================================================

# Primary review model - highest reasoning tier available
REVIEWER_MODEL = os.environ.get("REVIEWER_MODEL", "gemini-3.1-pro-preview")

# Acceptable fallback models (Pro-tier only)
REVIEWER_MODEL_FALLBACKS = ["gemini-3.1-pro"]

# Forbidden models - fail closed rather than use these
FORBIDDEN_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash",
    "gemini-2.5-lite",
    "gemini-lite",
    "gemini-3-pro-preview",
    "gemini-3-pro",
]

# =============================================================================
# Claude Model (REQ-2: Claude 4.6)
# =============================================================================

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-4.6-sonnet")

# =============================================================================
# Credential Paths
# =============================================================================

CREDENTIALS_FILE = Path.home() / ".assemblyzero" / "gemini-credentials.json"
ROTATION_STATE_FILE = Path.home() / ".assemblyzero" / "gemini-rotation-state.json"
GEMINI_API_LOG_FILE = Path.home() / ".assemblyzero" / "gemini-api.jsonl"

# =============================================================================
# Retry Configuration
# =============================================================================

MAX_RETRIES_PER_CREDENTIAL = 3
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0

# =============================================================================
# Logging Paths (Issue #57: Session-Sharded Logging)
# =============================================================================

# Permanent audit trail (consolidated from shards)
DEFAULT_AUDIT_LOG_PATH = Path("logs/review_history.jsonl")

# Active session shards directory (gitignored, ephemeral)
LOGS_ACTIVE_DIR = Path("logs/active")

# =============================================================================
# Prompt Paths
# =============================================================================

LLD_REVIEW_PROMPT_PATH = Path("docs/skills/0702c-LLD-Review-Prompt.md")
LLD_GENERATOR_PROMPT_PATH = Path("docs/skills/0705-lld-generator.md")

# =============================================================================
# Output Paths
# =============================================================================

LLD_DRAFTS_DIR = Path("docs/llds/drafts")
```

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
