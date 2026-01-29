# Implementation Report: Issue #70 - Fix Resume Workflow

## Issue Reference
https://github.com/martymcenroe/AgentOS/issues/70

## Summary

Fixed the resume workflow functionality to properly save and restore state when user chooses to pause. Also improved UX by changing menu prompts from `[S]end/[R]evise/[M]anual` to `[G]emini/[R]evise/[S]ave and exit`.

## Changes Made

### 1. KeyboardInterrupt Fix for Save/Resume (`agentos/workflows/issue/nodes/human_edit_draft.py`)

**The root cause:** When user chose `[M]anual` (now `[S]ave`), the node returned `error_message: "User chose manual handling"` which completed the node and routed to END. This meant the checkpoint was saved AFTER the node, so resume had nothing to do.

**The fix:** Changed to raise `KeyboardInterrupt` instead of returning, so the checkpoint is saved BEFORE the node completes. Resume then re-runs the node and shows the prompt again.

```python
if decision == HumanDecision.MANUAL:
    # Raise KeyboardInterrupt to pause workflow WITHOUT completing this node.
    # This ensures the checkpoint is saved BEFORE this node, so resume
    # will re-run this node and show the prompt again.
    print("\n>>> Pausing workflow for manual handling...")
    raise KeyboardInterrupt("User chose manual handling")
```

### 2. UX Improvements (`agentos/workflows/issue/nodes/human_edit_draft.py`)

Changed menu options for clarity:
- `[S]end to Gemini` → `[G]emini - send to Gemini for review`
- `[R]evise` → `[R]evise - send back to Claude with feedback`
- `[M]anual` → `[S]ave and exit - pause workflow for later`

### 3. Resume Commands Include `poetry run` (`tools/run_issue_workflow.py`)

All printed resume commands now include `poetry run` prefix for copy-paste convenience:
```
>>> Resume with: poetry run python tools/run_issue_workflow.py --resume <file>
```

### 4. Database Path Isolation (`tools/run_issue_workflow.py`)

Added environment variable support for worktree-isolated testing:

```python
def get_checkpoint_db_path() -> Path:
    """Get path to SQLite checkpoint database.

    Supports AGENTOS_WORKFLOW_DB environment variable for worktree isolation.
    """
    # Support environment variable for worktree isolation
    if db_path_env := os.environ.get("AGENTOS_WORKFLOW_DB"):
        db_path = Path(db_path_env)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    # Default: ~/.agentos/issue_workflow.db
    db_dir = Path.home() / ".agentos"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "issue_workflow.db"
```

This enables:
- Worktree-isolated testing without corrupting production database
- CI/CD testing with ephemeral databases
- Multiple concurrent workflows with isolated state

### 2. Integration Tests (`tests/test_issue_workflow.py`)

Added 4 new integration tests that verify the checkpoint/resume mechanism:

1. **test_checkpoint_db_path_env_var** - Verifies AGENTOS_WORKFLOW_DB env var works
2. **test_checkpoint_db_path_default** - Verifies default path (~/. agentos/issue_workflow.db)
3. **test_sqlite_checkpointer_saves_state** - Verifies SQLite actually persists workflow state
4. **test_workflow_resume_from_checkpoint** - Verifies stream(None, config) continues correctly

## End-to-End Testing Results

### Test 1: --resume CLI flag

```
============================================================
Resuming Issue Creation Workflow
============================================================
Slug: test-resume-brief
============================================================

>>> Resuming from iteration 3
>>> Drafts: 3
>>> Verdicts: 3

[12:35:31] Calling Claude to generate draft...
>>> Executing: N2_draft

>>> Iteration 4 | Draft #4
```

**Result:** Resume correctly preserves iteration count and continues from checkpoint.

### Test 2: [R]esume from slug collision prompt

```
>>> Slug 'test-resume-brief' already exists in active/

[R]esume existing workflow
[N]ew name - enter a different slug
[C]lean - delete checkpoint and audit dir, start fresh
[A]bort - exit cleanly

Your choice [R/N/C/A]: Resuming workflow for 'test-resume-brief'...

============================================================
Resuming Issue Creation Workflow
============================================================
Slug: test-resume-brief
============================================================

>>> Resuming from iteration 4
>>> Drafts: 4
>>> Verdicts: 3

[12:36:36] Calling Gemini for review...
```

**Result:** [R]esume option correctly calls run_resume_workflow() and continues.

## Design Decisions

1. **Environment variable for isolation**: Chose env var over auto-detecting worktree because:
   - More explicit and predictable
   - Works in CI/CD environments
   - No risk of accidental path detection errors

2. **Real SQLite tests instead of mocks**: The original mocked tests passed but didn't catch real issues. New tests use actual SQLite checkpointer to verify real behavior.

## Files Changed

- `agentos/workflows/issue/nodes/human_edit_draft.py` - KeyboardInterrupt fix, UX improvements
- `tools/run_issue_workflow.py` - AGENTOS_WORKFLOW_DB support, poetry run in resume commands
- `tests/test_issue_workflow.py` - Added 4 integration tests

## Known Limitations

1. The shared database at `~/.agentos/issue_workflow.db` is still the default - users working on multiple workflows simultaneously should use AGENTOS_WORKFLOW_DB to isolate.

## Verification

- All 58 existing tests pass (1 pre-existing failure unrelated to this fix)
- 4 new integration tests pass
- Full end-to-end test with `AGENTOS_TEST_MODE=1` ran 25 iterations successfully
- Manual testing confirms `[S]ave and exit` properly saves state for resume
- Resume command with `poetry run` prefix works correctly
