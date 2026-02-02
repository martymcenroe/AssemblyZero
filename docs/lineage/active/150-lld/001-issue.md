# Issue #150: fix: OAuth test not implemented in gemini-test-credentials-v2.py

## Severity: MEDIUM

## Problem

OAuth credential testing returns hardcoded failure instead of actual implementation.

## Location

**File:** `tools/gemini-test-credentials-v2.py`  
**Lines:** 114-117

```python
elif cred_type == "oauth":
    # OAuth is handled differently in the new SDK; 
    # for this tool, we'll focus on API Keys first.
    success, message = False, "OAuth test not implemented in v2 yet"
```

## Impact

- Users cannot test OAuth credentials with the new google-genai SDK
- Tool silently fails for OAuth credential type
- No way to verify OAuth setup is correct

## Expected Behavior

Either:
1. Implement actual OAuth testing with google-genai SDK
2. Or clearly document this limitation and remove OAuth as an option

## Found By

Comprehensive codebase scan for stub implementations.