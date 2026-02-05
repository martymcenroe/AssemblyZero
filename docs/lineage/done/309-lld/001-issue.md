---
repo: martymcenroe/AgentOS
issue: 309
url: https://github.com/martymcenroe/AgentOS/issues/309
fetched: 2026-02-05T02:18:38.829858Z
---

# Issue #309: bug: Implementation workflow lacks retry on validation failure

## Summary

The implementation workflow hard-fails when Claude generates invalid code instead of retrying.

## Observed Behavior

Running implementation for issue #99:
```
[N4] Implementing code file-by-file (iteration 0)...
    [2/3] tools/new-repo-setup.py (Modify)...
        Calling Claude...

IMPLEMENTATION FAILED
File: tools/new-repo-setup.py
Reason: Validation failed: Python syntax error: unterminated triple-quoted f-string literal
```

The workflow caught the bad response (good!) but then died (bad!).

## Root Cause

`implement_code.py` line 280:
```python
NO RETRIES - if it fails, it fails.
```

When `validate_code_response()` fails, an `ImplementationError` is raised and the workflow ends.

## Expected Behavior

On validation failure:
1. Log the error
2. Retry with error context in prompt (up to N attempts)
3. Only hard-fail after exhausting retries

## Proposed Fix

Add retry loop around single-file generation:

```python
MAX_FILE_RETRIES = 3

for attempt in range(MAX_FILE_RETRIES):
    response, error = call_claude_for_file(prompt)
    
    if error:
        if attempt < MAX_FILE_RETRIES - 1:
            print(f"        [RETRY {attempt+1}] API error: {error}")
            continue
        raise ImplementationError(...)
    
    code = extract_code_block(response)
    valid, validation_error = validate_code_response(code, filepath)
    
    if not valid:
        if attempt < MAX_FILE_RETRIES - 1:
            # Add error to prompt for next attempt
            prompt += f"\n\n## Previous Attempt Failed\nError: {validation_error}\n"
            print(f"        [RETRY {attempt+1}] {validation_error}")
            continue
        raise ImplementationError(...)
    
    # Success - write file
    break
```

## Files to Modify

| File | Change |
|------|--------|
| `agentos/workflows/testing/nodes/implement_code.py` | Add retry loop |

## Labels

`bug`, `workflow`