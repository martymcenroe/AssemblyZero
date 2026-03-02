# CLAUDE.md - AssemblyZero

Universal rules are in `C:\Users\mcwiz\Projects\CLAUDE.md` (auto-loaded for all projects).

AssemblyZero is the canonical source for core rules, tools, and workflow.

## AssemblyZero Workflows

This repo uses AssemblyZero workflows (LLD, impl spec, TDD).
Babysit protocol: read `C:\Users\mcwiz\Projects\AssemblyZero\docs\babysit-protocol.md` before running.
Worktree isolation: required

## Key Files

- `WORKFLOW.md` — Development workflow gates (worktrees, reviews, reports)
- `tools/` — Shared tooling (merge, batch-workflow, gemini-model-check)
- `docs/standards/` — Engineering standards (0001–0999)

## Merging PRs

NEVER use `gh pr merge` directly. Always follow post-merge cleanup:

```bash
# 1. Merge (squash)
gh pr merge {NUMBER} --squash --repo martymcenroe/AssemblyZero

# 2. Archive lineage (if worktree was used)
poetry run python tools/archive_worktree_lineage.py --worktree ../AssemblyZero-{ID} --issue {ID}

# 3. Remove worktree (if used — clean ephemeral files first, never --force)
git worktree remove ../AssemblyZero-{ID}

# 4. Delete local branch
git branch -d {BRANCH}

# 5. Pull merged changes
git checkout main && git pull
```

Steps 2-3 only apply when a worktree was used. Steps 1, 4-5 always apply.
