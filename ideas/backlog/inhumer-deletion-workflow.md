# Brief: The Inhumer — Safe Deletion Workflow

**Status:** Active
**Created:** 2026-02-01
**Updated:** 2026-02-28
**Effort:** Medium
**Priority:** Medium
**Tracking Issue:** #206

---

## Problem

Deleting code is risky. Remove a file and its tests might still import it, its references might litter other modules, and you won't know until CI fails (or worse, until production). The codebase has 184 Python files in `tests/` alone — manual grep-and-delete is error-prone.

Issue #206 (Inhume `workflows/issue/`) is the first concrete target: the old issue workflow directory needs removal, but its imports and references must be cleaned up first.

## What Already Exists

- **`git rm`** — removes files from the repo
- **`git restore`** — rolls back if things go wrong
- **`pytest`** — the verification oracle: if tests pass after deletion, the deletion is safe
- **Issue #206** — first target for deletion (old `workflows/issue/` directory)
- **Issue #94** — Janitor workflow (complementary: Janitor finds dead code, Inhumer removes it)

## The Gap

No automated "delete-then-verify" workflow. Today, deletion is a manual sequence: grep for imports, `git rm`, run tests, fix what breaks, repeat. This is tedious and easy to get wrong, especially when a file is imported transitively.

## Proposed Solution

A Python script (not a LangGraph workflow — no LLM needed, this is deterministic) that safely deletes files:

### Algorithm

1. **Scan** — given a target file or directory, find all imports and references across the codebase (`grep -r`, AST analysis for Python imports)
2. **Plan** — list all files that reference the target, categorized:
   - Direct imports (`from target import ...`)
   - String references (paths in config, docs)
   - Test files that test the target
3. **Dry run** — show the plan, ask for confirmation
4. **Execute** — `git rm` the target and its dedicated test files. Remove import lines from referencing files.
5. **Verify** — run `pytest`. If green, commit. If red, `git restore` everything and report what failed.

### CLI Interface

```
poetry run python tools/run_inhumer.py --target workflows/issue/    # Interactive
poetry run python tools/run_inhumer.py --target workflows/issue/ --dry-run  # Plan only
```

### Safety Rails

- Always dry-run first (unless `--no-dry-run` is explicit)
- `git restore` rollback if tests fail after deletion
- Never delete files outside the target and its direct references
- Commit only on green tests

## Integration Points

- **Janitor** (Issue #94) — Janitor identifies dead code candidates; Inhumer executes the removal
- **Watch** (`city-watch-regression-guardian.md`) — Watch verifies no regressions after deletion
- **pytest** — the verification oracle for safe deletion

## Acceptance Criteria

- [ ] Finds all imports and references for a given target
- [ ] Dry-run mode shows full deletion plan without changing anything
- [ ] Executes deletion and runs tests
- [ ] Rolls back via `git restore` if tests fail
- [ ] Commits only on green test suite
- [ ] Works on single files and directories
- [ ] Successfully handles Issue #206 (inhume `workflows/issue/`)

## Dependencies & Cross-References

- **Issue #206** — first concrete target (inhume `workflows/issue/`)
- **Issue #94** — Janitor workflow (identifies dead code for Inhumer to remove)
- **Brief: `city-watch-regression-guardian.md`** — Watch verifies post-deletion health
