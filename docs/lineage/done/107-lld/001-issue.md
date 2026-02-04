# Issue #107: fix: test_audit_sharding history/shard merge returns wrong count

## Bug Description

`test_merges_history_and_shards` expects 5 entries after merging history file and active shards, but only gets 2.

## Test Location
`tests/test_audit_sharding.py:299`

## Failure Details
```
AssertionError: assert 2 == 5
  where 2 = len([...])
```

## Expected Behavior
The `tail()` method should merge:
- 3 entries from `governance_history.jsonl` (created directly via file write)
- 2 entries from active shards (created via `ReviewAuditLog.log()`)

Total: 5 entries

## Actual Behavior
Only 2 entries returned (the shard entries). History entries are not being merged.

## Probable Cause
The test writes directly to the history file before creating the `ReviewAuditLog` instance. The history file path or loading logic may not be finding the pre-existing history entries.

## Acceptance Criteria
- [ ] `log.tail(n=10)` returns all 5 entries (3 history + 2 shard)
- [ ] Test passes without modification to test expectations

## Labels
`bug`, `testing`