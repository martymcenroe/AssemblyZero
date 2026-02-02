# Issue #138: Add retry/backoff handling for Claude CLI invocations

## Problem

Claude CLI calls in the TDD workflow (`implement_code.py`) have no retry or backoff handling. If Claude returns a rate limit error (429), the workflow fails immediately.

Gemini has robust handling:
- Credential rotation (OAuth â†’ API keys)
- Exponential backoff for 529 (capacity)
- Error classification (429/529/auth separated)
- Pool exhaustion returns `earliest_reset` for graceful pause
- JSONL logging for visibility

Claude CLI has: nothing.

## Requirements

### Must Have
1. **Exponential backoff with retry** - detect 429, wait `BASE * 2^attempt`, retry
2. **Max retries cap** - configurable, default ~5 attempts
3. **Graceful pause** - if max retries exceeded, return "try again later" state, not hard failure
4. **Error classification** - distinguish rate limit from other errors

### Nice to Have
1. **JSONL logging** - audit trail like Gemini has
2. **Jitter** - Â±20% randomization to avoid thundering herd

## Scope

Since Claude is single-credential per user (API key/subscription), credential rotation is NOT applicable. Focus on backoff + retry.

## Files to Modify

- `agentos/workflows/testing/nodes/implement_code.py` - primary consumer
- Consider: shared utility in `agentos/core/claude_client.py` (similar pattern to `gemini_client.py`)

## Context

The parallel workflow coordinator (`agentos/workflows/parallel/credential_coordinator.py`) has scaffolding for rate-limit tracking but the backoff isn't implemented (line 74-75: "For testing purposes, we add it back immediately"). This issue focuses on the Claude CLI specifically.

## Acceptance Criteria

- [ ] Claude CLI calls retry on 429 with exponential backoff
- [ ] Max retries configurable via environment variable
- [ ] Workflow pauses gracefully instead of failing on sustained rate limits
- [ ] Tests verify retry behavior