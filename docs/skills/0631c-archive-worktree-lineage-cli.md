# archive-worktree-lineage - CLI Usage

**File:** `docs/skills/0631c-archive-worktree-lineage-cli.md`
**Prompt Guide:** [0631p-archive-worktree-lineage-prompt.md](0631p-archive-worktree-lineage-prompt.md)
**Version:** 2026-02-03
**Issue:** #189

---

## Overview

Archives valuable artifacts from a worktree before deletion. Prevents loss of iteration history, coverage data, and execution traces.

---

## Quick Start

```bash
# From main repo directory
python tools/archive_worktree_lineage.py --worktree ../AssemblyZero-42 --issue 42
```

---

## Command Reference

```bash
python tools/archive_worktree_lineage.py [OPTIONS]

Required:
  --worktree PATH    Path to the worktree being removed
  --issue NUMBER     Issue number for this worktree

Optional:
  --main-repo PATH   Path to main repo (default: current directory)
  --no-commit        Skip automatic git commit
```

---

## What It Does

### 1. Archives Lineage

Copies `docs/lineage/active/{issue}-*/` from worktree to main repo's `docs/lineage/archived/`:

```
Worktree:  docs/lineage/active/42-testing/001-issue.md
    ↓
Main:      docs/lineage/archived/42-testing/001-issue.md
```

### 2. Cleans Ephemeral Files

Removes from worktree (NOT archived):
- `.coverage` - pytest coverage data
- `__pycache__/` - Python bytecode
- `.pytest_cache/` - pytest cache
- `.assemblyzero/audit/` - execution traces

### 3. Commits to Main (unless --no-commit)

```bash
git add docs/lineage/archived/
git commit -m "chore: archive workflow lineage for #42"
```

---

## Usage in Post-Merge Cleanup

This tool is step 1 of the post-merge cleanup protocol:

```
Post-Merge Cleanup:
├── Archive lineage: python tools/archive_worktree_lineage.py --worktree ../ProjectName-{ID} --issue {ID}
├── Remove worktree: git worktree remove ../ProjectName-{ID}
├── Delete local branch: git branch -d {ID}-desc
├── Delete remote branch: git push origin --delete {ID}-desc
├── Pull merged changes: git pull
└── Verify: git branch -a (should show only main)
```

---

## Examples

### Standard Usage (after PR merge)

```bash
# Archive lineage, clean ephemeral, commit
python tools/archive_worktree_lineage.py --worktree ../AssemblyZero-155 --issue 155

# Then remove worktree
git worktree remove ../AssemblyZero-155
```

### Review Before Commit

```bash
# Archive without commit
python tools/archive_worktree_lineage.py --worktree ../AssemblyZero-155 --issue 155 --no-commit

# Review what was archived
ls docs/lineage/archived/

# Manually commit if satisfied
git add docs/lineage/archived/
git commit -m "chore: archive workflow lineage for #155"
```

### Non-Standard Main Repo Location

```bash
python tools/archive_worktree_lineage.py \
  --worktree /c/Users/mcwiz/Projects/AssemblyZero-42 \
  --issue 42 \
  --main-repo /c/Users/mcwiz/Projects/AssemblyZero
```

---

## What Gets Archived vs Cleaned

| Item | Action | Why |
|------|--------|-----|
| `docs/lineage/active/{issue}-*/` | Archived | Iteration history valuable for analysis |
| `.coverage` | Cleaned | Binary, regeneratable |
| `__pycache__/` | Cleaned | Bytecode, regeneratable |
| `.pytest_cache/` | Cleaned | Cache, regeneratable |
| `.assemblyzero/audit/` | Cleaned | Execution traces, large |

---

## Troubleshooting

### "No lineage directory found"

The worktree doesn't have `docs/lineage/active/`. This is normal for worktrees that didn't use the lineage workflow.

### Permission denied on Windows

Close any editors or terminals that have files open in the worktree.

### Commit fails

If git commit fails, check:
1. You're in a git repo
2. You have write permissions
3. The main repo isn't locked by another process

---

## Related Files

- Tool: `tools/archive_worktree_lineage.py`
- Tests: `tests/unit/test_worktree_cleanup.py`
- CLAUDE.md: POST-MERGE CLEANUP section
