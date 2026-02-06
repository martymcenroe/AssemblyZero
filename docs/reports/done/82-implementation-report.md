# Implementation Report: Issue #82

## Issue Reference
https://github.com/martymcenroe/AssemblyZero/issues/82

## Summary
Fixed the `--brief` flag to properly clean up idea files from `ideas/active/` after issue creation.

## Files Changed

| File | Change |
|------|--------|
| `tools/run_issue_workflow.py` | Added auto-detection for `ideas/active/` paths in `--brief` handler |
| `tests/test_issue_workflow.py` | Added `TestBriefIdeaDetection` test class with 5 tests |

## Design Decisions

### Root Cause
- The `--select` flag sets the `source_idea` parameter, which triggers cleanup
- The `--brief` flag did NOT set `source_idea`, so cleanup never happened

### Solution
Auto-detect if the `--brief` path is inside `ideas/active/` and set `source_idea` accordingly:

```python
elif args.brief:
    # Auto-detect if brief is from ideas/active/ and set source_idea
    brief_path = Path(args.brief).resolve()
    repo_root = get_repo_root()
    ideas_active = repo_root / "ideas" / "active"
    if brief_path.parent == ideas_active:
        return run_new_workflow(args.brief, source_idea=str(brief_path))
    return run_new_workflow(args.brief)
```

## Known Limitations

1. Only works for direct children of `ideas/active/`, not nested subdirectories
   - e.g., `ideas/active/foo.md` triggers cleanup
   - e.g., `ideas/active/subdir/bar.md` does NOT trigger cleanup
   - This matches the existing behavior of `--select`

## Verification

- All 5 new tests pass
- 63/64 existing tests pass (1 pre-existing failure unrelated to this change)
