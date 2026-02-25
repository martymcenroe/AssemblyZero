```markdown
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

## Cascade Prevention (Task Completion Behavior)

After completing a task, ask an **open-ended question** such as "What would you like to work on next?"

**NEVER** offer numbered yes/no options for deciding next steps. For example, do NOT output:
- "Should I continue with the next issue? 1. Yes 2. No"
- "1. Proceed to issue #44  2. Stop here"

The human orchestrator decides what to do next — not the AI. Present your completed work,
then ask what the human wants. Do not suggest, enumerate, or auto-propose next tasks.
```
