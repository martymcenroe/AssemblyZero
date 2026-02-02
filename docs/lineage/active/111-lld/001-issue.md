# Issue #111: fix: test_gemini_client exhausted credentials returns wrong error type

## Bug Description

`test_110_all_credentials_exhausted` expects `UNKNOWN` error type when all credentials are exhausted, but gets `QUOTA_EXHAUSTED`.

## Test Location
`tests/test_gemini_client.py:284`

## Failure Details
```
AssertionError: assert <GeminiErrorType.QUOTA_EXHAUSTED: 'quota'> == <GeminiErrorType.UNKNOWN: 'unknown'>
```

## Context
This test may be a case where the **test expectation is wrong**, not the code. When all credentials are exhausted due to quota limits, `QUOTA_EXHAUSTED` is arguably the correct error type.

## Investigation Needed
1. Review original intent of the test
2. Determine if `QUOTA_EXHAUSTED` or `UNKNOWN` is the correct error type when all credentials fail
3. Either fix the code or update the test expectation

## Related Issues
Part of Gemini client credential rotation test cluster:
- #108 (credential loading) - may be root cause if client isn't initializing
- #109 (429 rotation)
- #110 (529 backoff)

## Acceptance Criteria
- [ ] Determine correct error type for "all credentials exhausted" scenario
- [ ] Update code or test to match correct behavior
- [ ] Test passes

## Labels
`bug`, `testing`