# Issue #156: fix: CLI tools have argparse arguments that are never used

## Severity: LOW-MEDIUM

## Problem

Multiple CLI tools define argparse arguments that are never validated or used in the actual functions.

## Locations

**Files with unused or incomplete argument handling:**
- `tools/run_implement_from_lld.py`
- `tools/run_scout_workflow.py`
- `tools/run_requirements_workflow.py` (--select is the worst example)
- `tools/run_issue_workflow.py`
- `tools/run_lld_workflow.py`

## Pattern

Arguments are defined:
```python
parser.add_argument("--some-flag", help="Does something")
```

But then:
1. Never checked in main()
2. Never passed to functions
3. Never validated for conflicts
4. Never documented what happens when used

## Impact

- Users pass flags expecting behavior that doesn't happen
- Runbooks document features that don't work
- No error when using broken flags - silent failure

## Expected Behavior

Every argparse argument should be:
1. Used in the code path
2. Validated for conflicts with other args
3. Documented with actual behavior
4. Tested

## Suggested Fix

Audit each CLI tool:
1. List all argparse arguments
2. Trace each through the code
3. Either implement or remove

## Related Issues

- #151 (--select specifically)

## Found By

Comprehensive codebase scan for stub implementations.