# Issue #108: fix: test_gemini_client credential loading returns empty list

## Bug Description

`test_loads_credentials_from_file` expects 3 credentials loaded from a mock credentials file, but gets 0.

## Test Location
`tests/test_gemini_client.py:110`

## Failure Details
```
assert 0 == 3
  where 0 = len([])
```

## Expected Behavior
When a credentials file with 3 API keys is provided, the client should load all 3 credentials.

## Actual Behavior
Credentials list is empty despite file existing with valid content.

## Probable Cause
- Mock/patch not correctly intercepting file read
- Credential file path resolution changed
- Credential loading logic changed

## Acceptance Criteria
- [ ] Mock credentials file with 3 keys results in 3 loaded credentials
- [ ] Test passes

## Labels
`bug`, `testing`