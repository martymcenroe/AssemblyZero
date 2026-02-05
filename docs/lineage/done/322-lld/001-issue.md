---
repo: martymcenroe/AgentOS
issue: 322
url: https://github.com/martymcenroe/AgentOS/issues/322
fetched: 2026-02-05T04:58:53.957566Z
---

# Issue #322: bug: Mechanical validation silently skips path checks when target_repo invalid

## Problem

In `validate_mechanical.py`, path validation is **silently skipped** if `target_repo` is empty or doesn't exist:

```python
# Line 887
if repo_root and repo_root.exists():
    path_errors = validate_file_paths(files, repo_root)
    # ...
```

If this condition is False, **no error or warning is raised**. The LLD passes mechanical validation with potentially hallucinated paths like `src/thing.py`.

## Impact

- Hallucinated paths (e.g., `src/`, `lib/`, `app/`) could slip through to implementation
- User has no indication that path validation was skipped
- Defeats the purpose of #277 mechanical validation

## Root Cause

1. `target_repo` is validated as non-empty in `create_initial_state()` (line 247-248)
2. But existence is NOT validated
3. `validate_mechanical.py` silently skips validation instead of failing

## Proposed Fix

Option A (strict - recommended):
```python
if not repo_root or not repo_root.exists():
    return {
        "validation_errors": ["Cannot validate file paths: target_repo is invalid or missing"],
        "lld_status": "BLOCKED",
        ...
    }
```

Option B (warning):
```python
if not repo_root or not repo_root.exists():
    all_warnings.append(ValidationError(
        severity=ValidationSeverity.WARNING,
        message="Path validation skipped: target_repo does not exist",
    ))
else:
    path_errors = validate_file_paths(files, repo_root)
    # ...
```

## Files to Modify

| File | Change |
|------|--------|
| `agentos/workflows/requirements/nodes/validate_mechanical.py` | Add explicit check for invalid repo_root |
| `tests/unit/test_validate_mechanical.py` | Add test for missing/invalid target_repo |

## Related

- #277 - Mechanical validation framework
- #188 - Enforce file paths from LLD (depends on validation working)

## Labels

`bug`, `workflow`
