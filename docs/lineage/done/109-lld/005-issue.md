# Issue #109: fix: test_gemini_client 429 rotation not triggering credential rotation

## Bug Description

`test_090_429_triggers_rotation` expects 3 API calls when encountering 429 (rate limit) errors, but sees 0 calls.

## Test Location
`tests/test_gemini_client.py:222`

## Failure Details
```
assert 0 == 3
  where 0 = len([])
```

## Expected Behavior
When the API returns 429 (quota exceeded), the client should:
1. Rotate to next credential
2. Retry the request
3. Continue through all available credentials

## Actual Behavior
No API calls are being recorded, suggesting the mock setup or client initialization is failing silently.

## Related Issues
This is part of a cluster of Gemini client credential rotation test failures:
- #108 (credential loading)
- #109 (529 backoff)
- #110 (exhausted credentials)

## Probable Cause
Root cause likely in credential loading (Issue #108). If no credentials load, no calls can be made.

## Acceptance Criteria
- [ ] 429 response triggers rotation to next credential
- [ ] 3 credentials = 3 retry attempts
- [ ] Test passes

## Labels
`bug`, `testing`