# ADR 0208: LLM Invocation Strategy

**Status:** Accepted
**Date:** 2026-02-19
**Deciders:** Orchestrator
**Context:** Documenting the multi-provider LLM invocation architecture used across all workflows

---

## Context

AssemblyZero orchestrates multiple LLM providers for different purposes: drafting designs, implementing code, reviewing quality, and adversarial verification. The invocation strategy must balance cost, reliability, speed, and the principle that **different model families catch different mistakes**.

Key constraints:
- Claude Max subscription provides free `claude -p` usage (headless CLI)
- Anthropic API is pay-per-token (fallback only)
- Gemini must be a *different model family* for adversarial review value
- MCP tools must be disabled in workflow subprocesses to prevent side effects
- Workflows must survive rate limits, timeouts, and credential rotation

---

## Decision

### Four Providers, Three Roles

| Provider | Class | Role | Cost Model |
|----------|-------|------|------------|
| **Claude CLI** | `ClaudeCLIProvider` | Primary drafter/implementer | Free (Max subscription) |
| **Anthropic API** | `AnthropicProvider` | Paid fallback for CLI failures | Per-token ($5-25/M output) |
| **Fallback** | `FallbackProvider` | CLI→API automatic failover | Free first, paid if needed |
| **Gemini** | `GeminiProvider` | Adversarial reviewer | Free (API preview/quota) |

### Provider Selection

The `get_provider(spec)` factory resolves provider specs like `claude:opus` or `gemini:3-pro-preview`:

1. **Claude specs** (`claude:opus`, `claude:sonnet`, `claude:haiku`):
   - If `ANTHROPIC_API_KEY` exists in `.env`: returns `FallbackProvider(CLI→API)`
   - Otherwise: returns `ClaudeCLIProvider` alone
2. **Gemini specs** (`gemini:3-pro-preview`): returns `GeminiProvider`
3. **Anthropic specs** (`anthropic:opus`): returns `AnthropicProvider` directly

### Claude CLI Invocation

`ClaudeCLIProvider` runs `claude -p` as a subprocess with these flags:

```
claude -p
  --output-format json       # Structured JSON response with token counts
  --setting-sources user     # Skip project CLAUDE.md context
  --tools ""                 # Disable all built-in tools
  --strict-mcp-config        # Disable MCP tool loading (Issue #157)
  --model <full-model-id>    # Exact model ID (e.g., claude-opus-4-6)
  --system-prompt <text>     # System instructions
```

Critical flags:
- `--tools ""` prevents the CLI from executing file operations or web searches
- `--strict-mcp-config` prevents loading `.claude/tools.yaml` MCP configurations
- Together, these ensure deterministic, side-effect-free LLM calls

### Fallback Behavior

`FallbackProvider` wraps CLI + API with automatic failover:

1. Try CLI with 180-second timeout (shorter window)
2. On any failure (timeout, parse error, rate limit): fall back to API with 300-second timeout
3. Return whichever succeeds, or the last error

This is transparent to callers — they receive a unified `LLMCallResult` regardless of which provider actually served the request.

### Gemini: Adversarial Review Only

Gemini is used exclusively for review, never for drafting or implementation:
- Different model family catches different blind spots than Claude
- Credential rotation across multiple API keys handles quota exhaustion
- Model verification detects silent downgrades (Pro requested, Flash returned)
- Supported models: `gemini-3-pro-preview`, `gemini-3-pro`, `gemini-2.5-pro`, `gemini-2.5-flash`

### MCP in Workflow Context

MCP (Model Context Protocol) is **explicitly disabled** in all workflow subprocesses via `--strict-mcp-config`. MCP tools remain active only in interactive Claude Code sessions where the human orchestrator is present. This prevents:
- Unintended file modifications during drafting
- Network calls during review
- Non-deterministic behavior in governance workflows

---

## LangGraph Integration

All five workflows are implemented as LangGraph `StateGraph` state machines:

| Workflow | Nodes | Checkpointed | Database |
|----------|-------|-------------|----------|
| Issue | 7 (N0→N6) | Yes (SQLite) | `~/.assemblyzero/issue_workflow.db` |
| Requirements (LLD) | 10 (N0→N5 + sub-nodes) | Via runner | `~/.assemblyzero/requirements_workflow.db` |
| Implementation Spec | 7 (N0→N6) | Per-issue | `~/.assemblyzero/impl_spec_{N}.db` |
| TDD Implementation | 13 (N0→N8) | Via runner | Per-issue partitioned |
| Scout | Variable | No | N/A |

Key patterns:
- **SqliteSaver** from `langgraph.checkpoint.sqlite` provides checkpoint persistence
- **Thread ID** = issue number or workflow slug, enabling resume after interruption
- **Per-issue databases** prevent deadlocks when running concurrent workflows (Issue #373)
- **Recursion limits** scale with max iterations: `(max_iters * edges_per_loop) + buffer`

---

## Unified Result Type

All providers return `LLMCallResult`:

```python
@dataclass
class LLMCallResult:
    success: bool
    response: Optional[str]           # Parsed response text
    provider: str                     # "claude", "gemini", "anthropic"
    model_used: str
    duration_ms: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int            # Claude prompt cache
    cache_creation_tokens: int
    cost_usd: float
    rate_limited: bool
```

This enables consistent token accounting, cost tracking, and rate-limit detection across all providers.

---

## Consequences

### Positive
- **Zero marginal cost** for Claude drafting via Max subscription
- **Automatic resilience** via CLI→API fallback
- **Adversarial value** from cross-family review (Claude builds, Gemini reviews)
- **Deterministic workflows** via MCP/tool disabling in subprocesses
- **Resume capability** via LangGraph checkpointing
- **Concurrent safety** via per-issue database partitioning

### Negative
- Claude CLI subprocess adds ~2-5s startup overhead per call vs. direct API
- `.env`-only API key loading prevents use of environment variables (conflicts with Claude Code auth)
- Gemini model availability depends on preview program access

### Risks
- Claude Max subscription terms could change (mitigated by API fallback)
- Gemini preview models may be deprecated (mitigated by model mapping layer)
- SQLite databases grow over time (mitigated by archive tooling)

---

## Related

- [ADR 0201: Adversarial Audit Philosophy](0201-adversarial-audit-philosophy.md)
- [ADR 0205: Test-First Philosophy](0205-test-first-philosophy.md)
- Source: `assemblyzero/core/llm_provider.py`
