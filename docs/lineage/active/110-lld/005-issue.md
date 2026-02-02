# Issue #110: fix: test_gemini_client 529 backoff not recording attempts

## Bug Description

`test_100_529_triggers_backoff` expects 3 retry attempts when encountering 529 (overloaded) errors, but sees 0 attempts.

## Test Location
`tests/test_gemini_client.py:260`

## Failure Details
```
assert 0 == 3
```

## Expected Behavior
When the API returns 529 (overloaded), the client should:
1. Implement exponential backoff
2. Retry up to max attempts (3)
3. Record each attempt

## Actual Behavior
No attempts recorded, suggesting client initialization or mock setup failure.

## Related Issues
Part of Gemini client credential rotation test cluster:
- #108 (credential loading) - likely root cause
- #109 (429 rotation)
- #110 (exhausted credentials)

## Acceptance Criteria
- [ ] 529 response triggers backoff retry
- [ ] 3 retry attempts recorded
- [ ] Test passes

## Labels
`bug`, `testing`