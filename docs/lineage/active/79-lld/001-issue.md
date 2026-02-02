# Issue #79: fix: --brief with ideas/active/ file does not trigger cleanup

## Bug Description

When using `--brief` with a file path pointing to `ideas/active/`, the idea file is NOT moved to `ideas/done/` after the issue is filed. The cleanup logic exists but is never triggered.

## Root Cause

In `tools/run_issue_workflow.py`:

- **Line 613** (`--select`): Sets `source_idea=idea_path` → cleanup works
- **Line 615** (`--brief`): Does NOT set `source_idea` → cleanup never triggers

The cleanup logic in `file_issue.py:357-365` only runs when `source_idea` is non-empty.

## Expected Behavior

When `--brief ideas/active/my-idea.md` is used, the workflow should:
1. Detect the file is in `ideas/active/`
2. Set `source_idea` to enable cleanup
3. After successful issue filing, move file to `ideas/done/{issue#}-my-idea.md`

## Actual Behavior

The idea file remains in `ideas/active/` after issue filing.

## Fix

Modify the `--brief` handler to detect and set `source_idea`:

```python
elif args.brief:
    brief_path = Path(args.brief).resolve()
    repo_root = get_repo_root()
    ideas_active = repo_root / "ideas" / "active"
    if brief_path.parent == ideas_active:
        return run_new_workflow(args.brief, source_idea=str(brief_path))
    return run_new_workflow(args.brief)
```

## Test Case

```python
# --brief with ideas/active/ file should set source_idea
brief_path = "ideas/active/test-idea.md"
# After fix: source_idea should be set to brief_path
# Before fix: source_idea is empty string
```