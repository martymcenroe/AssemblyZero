---
repo: martymcenroe/AgentOS
issue: 311
url: https://github.com/martymcenroe/AgentOS/issues/311
fetched: 2026-02-05T03:25:45.271638Z
---

# Issue #311: Implementation workflow runs wrong test file (scaffold vs unit path mismatch)

## Problem

The TDD implementation workflow fails verification even when the implementation is correct because it runs the **wrong test file**.

## Root Cause

The workflow creates test files in two different locations:
1. **Scaffold phase** creates: `tests/test_issue_N.py` (with `assert False` stubs)
2. **Implementation phase** writes to: `tests/unit/test_<module_name>.py` (with real tests)
3. **Verification phase** runs: `tests/test_issue_N.py` (the stale scaffold!)

## Evidence from #170

```
# Scaffold created (20:18):
tests/test_issue_170.py  # assert False stubs

# Implementation wrote to (20:30):
tests/unit/test_check_type_renames.py  # real tests

# Verification ran (and failed):
tests/test_issue_170.py  # still has assert False!
```

The actual implementation is **complete and all 25 tests pass** when running the correct file:
```
poetry run pytest tests/unit/test_check_type_renames.py -v
# 25 passed
```

## Impact

- Workflow reports failure when implementation is actually complete
- Wastes 5 iteration cycles trying to "fix" passing code
- User sees false failure, loses confidence in workflow

## Proposed Fix

The test file path must be tracked consistently through all phases:
1. Either always use `tests/test_issue_N.py` OR `tests/unit/test_*.py`
2. Store the test file path in state and use it in verification
3. Delete the scaffold file after writing real tests (or don't create it separately)

## Related

- #309 - Green phase retry logic
- #310 - Nested markdown extraction bug

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>