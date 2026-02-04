# Issue #149: fix: Rate-limit backoff not implemented in CredentialCoordinator

## Severity: HIGH

## Problem

Rate-limit backoff is documented but not actually applied. Credentials hit with 429 are immediately reused, causing repeated failures.

## Location

**File:** `agentos/workflows/parallel/credential_coordinator.py`  
**Lines:** 72-76

```python
if rate_limited:
    print(f"[CREDENTIAL] Key {credential[:8]}... is rate-limited, backoff: {backoff_seconds}s")
    # In a real implementation, we'd delay adding back to pool
    # For testing purposes, we add it back immediately

self._available.add(credential)
```

## Impact

- Credentials hit with 429 are immediately reused
- Causes repeated rate-limit failures
- Defeats the purpose of the backoff parameter
- The comment literally says "For testing purposes" but this is production code

## Expected Behavior

The credential should NOT be added back to `_available` until `backoff_seconds` has elapsed.

## Suggested Fix

```python
if rate_limited:
    print(f"[CREDENTIAL] Key {credential[:8]}... is rate-limited, backoff: {backoff_seconds}s")
    # Schedule re-add after backoff (using threading.Timer or asyncio)
    # OR track cooldown timestamp and filter in get_credential()
else:
    self._available.add(credential)
```

## Found By

Comprehensive codebase scan for stub implementations.