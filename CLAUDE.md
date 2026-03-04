# CLAUDE.md - AssemblyZero

Universal rules are in `C:\Users\mcwiz\Projects\CLAUDE.md` (auto-loaded for all projects).

AssemblyZero is the canonical source for core rules, tools, and workflow.

## Running Workflows (CRITICAL)

All workflow scripts live in `tools/` and MUST be run from the AssemblyZero directory with `poetry run python`.
Babysit protocol: read `docs/babysit-protocol.md` before running.

### LLD Workflow (write an LLD for an issue)

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue NUMBER --repo /c/Users/mcwiz/Projects/TARGET_REPO --yes
```

### Implementation Workflow (implement code from an LLD)

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue NUMBER --repo /c/Users/mcwiz/Projects/TARGET_REPO --no-worktree
```

### Common Gotchas

| Gotcha | Fix |
|--------|-----|
| No output in background runs | `PYTHONUNBUFFERED=1` — Python buffers stdout when not on a TTY |
| Nested Claude sessions fail | `CLAUDECODE= PYTHONUNBUFFERED=1 poetry run ...` (empty string, NOT unset) |
| `--yes` flag on implementation | Does NOT exist — only the LLD workflow has `--yes` |
| Worktree already exists | Use `--no-worktree` flag on implementation workflow |
| Workflow runs from wrong dir | ALWAYS `cd` to AssemblyZero first. The `--repo` flag points to the target |

## Key Files

- `WORKFLOW.md` — Development workflow gates (worktrees, reviews, reports)
- `tools/` — Shared tooling (merge, batch-workflow, gemini-model-check)
- `docs/standards/` — Engineering standards (0001–0999)

## Cascade Prevention

After completing a task, ask "What would you like to work on next?" as an open-ended question. Never offer numbered yes/no options or suggest continuing to the next issue unprompted.

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
