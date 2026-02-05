---
repo: martymcenroe/AgentOS
issue: 321
url: https://github.com/martymcenroe/AgentOS/issues/321
fetched: 2026-02-05T04:31:54.385348Z
---

# Issue #321: bug: Implementation workflow silently exits on API timeout (no error, no implementation)

## Summary

The implementation workflow silently exits with code 0 when the Claude API call times out or stalls, leaving no implementation generated and no error message.

## Observed Behavior

Running implementation for issues #312 and #306:

```
[N4] Implementing code file-by-file (iteration 0)...
    [1/2] agentos/workflows/requirements/nodes/validate_mechanical.py (Modify)...
        Calling Claude...
        # ... workflow sits here, then exits
        
Background command "Run implementation workflow for #306" completed (exit code 0)
```

The workflow:
1. ✅ Creates prompt file (e.g., `007-prompt-agentos-workflows-...`)
2. ❌ Never creates response file
3. ❌ Never creates implementation
4. ❌ Exits with code 0 (success!) instead of error

## Evidence

Lineage folder after stall shows prompt but no response:
```
docs/lineage/active/306-testing/
├── 001-issue.md
├── 002-test-plan.md
├── ...
├── 006-tests-red.md
└── 007-prompt-agentos-workflows-requirements-nodes-validate_mechanical.py.md  # ← LAST FILE
# No 008-response, no 009-implementation
```

## Root Cause (Suspected)

The API call in `implement_code.py` either:
1. Has no timeout configured, so it waits forever until some external timeout kills the process
2. Has a timeout but catches the exception and returns success instead of failure
3. The LangGraph/LangChain streaming response handler silently fails

## Expected Behavior

On API timeout:
1. Log clear error: `"API timeout after {N} seconds waiting for implementation"`
2. Exit with non-zero code
3. Optionally: retry with backoff before failing

## Impact

- Workflow appears successful but produces nothing
- User must manually check for missing files
- Wastes time waiting for output that never arrives
- No indication of what went wrong

## Proposed Fix

```python
# In implement_code.py or wherever API call happens:

import asyncio

IMPLEMENTATION_TIMEOUT = 120  # seconds

try:
    response = await asyncio.wait_for(
        call_claude_for_implementation(prompt),
        timeout=IMPLEMENTATION_TIMEOUT
    )
except asyncio.TimeoutError:
    raise ImplementationError(
        f"API timeout: No response after {IMPLEMENTATION_TIMEOUT}s. "
        "Check API status or try again."
    )
```

## Files to Investigate

| File | Reason |
|------|--------|
| `agentos/workflows/testing/nodes/implement_code.py` | Where Claude API is called |
| `agentos/workflows/testing/graph.py` | How errors propagate |
| `agentos/providers/claude_cli.py` | If using CLI provider, timeout handling |

## Related Issues

- #309 - Retry on validation failure (different: API responds but with bad code)
- #267 - Progress feedback during wait (UX, not the underlying bug)

## Labels

`bug`, `workflow`