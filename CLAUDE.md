# CLAUDE.md - AssemblyZero

Universal rules are in `C:\Users\mcwiz\Projects\CLAUDE.md` (auto-loaded for all projects).

AssemblyZero is the canonical source for core rules, tools, and workflow.

## Key Files

- `WORKFLOW.md` — Development workflow gates (worktrees, reviews, reports)
- `tools/` — Shared tooling (merge, batch-workflow, gemini-model-check)
- `docs/standards/` — Engineering standards (0001–0999)

## Merging PRs

NEVER use `gh pr merge` directly. Always follow the post-merge cleanup in WORKFLOW.md:

```bash
# 1. Merge (squash)
gh pr merge {NUMBER} --squash --repo martymcenroe/AssemblyZero

# 2. Archive lineage
poetry run python tools/archive_worktree_lineage.py --worktree ../AssemblyZero-{ID} --issue {ID}

# 3. Remove worktree (clean ephemeral files first, never --force)
git worktree remove ../AssemblyZero-{ID}

# 4. Delete local branch
git branch -d {BRANCH}

# 5. Pull merged changes
git checkout main && git pull
```

Skipping post-merge cleanup leaves orphaned worktrees and stale branches.
