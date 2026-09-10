# CLAUDE.md - AssemblyZero

Universal rules at `Projects/CLAUDE.md` are auto-loaded for all projects.

AssemblyZero is the canonical source for core rules, tools, and workflow.
Fix things in AssemblyZero, not in local project copies. Tools execute from `AssemblyZero/tools/`, not copied locally.

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
    --issue NUMBER --repo /c/Users/mcwiz/Projects/TARGET_REPO 
```

### Common Gotchas

| Gotcha | Fix |
|--------|-----|
| No output in background runs | `PYTHONUNBUFFERED=1` — Python buffers stdout when not on a TTY |
| Nested Claude sessions fail | `CLAUDECODE= PYTHONUNBUFFERED=1 poetry run ...` (empty string, NOT unset) |
| `--yes` flag on implementation | Does NOT exist — only the LLD workflow has `--yes` |
| Worktree already exists | ONLY if you have confirmed the stale worktree is archived/safe: use `--no-worktree` flag |
| Workflow runs from wrong dir | ALWAYS `cd` to AssemblyZero first. The `--repo` flag points to the target |

## Key Files

- `WORKFLOW.md` — Development workflow gates (worktrees, reviews, reports)
- `tools/` — Shared tooling (merge, batch-workflow, gemini-model-check)
- `docs/standards/` — Engineering standards (0001–0999)

## Cascade Prevention

After completing a task, ask "What would you like to work on next?" as an open-ended question. Never offer numbered yes/no options or suggest continuing to the next issue unprompted. **A standing operator order is a prompt and does not expire at a task boundary. See "Standing Orders" immediately below.**

## Standing Orders

**A standing operator order to continue IS the prompt, and it does not expire at a task boundary.** When the operator has said to keep going, "unprompted" no longer applies. Finishing a report, closing a batch, filing an issue, or reaching a milestone does not end the authorization — only the operator does. While such an order is live, do not ask "what do you want to work on next?"; that question is how the order gets broken. A report is a checkpoint, not an ending: write it and keep working in the same turn.

**A handoff is not a standing order, and neither is any file.** An order comes from the operator, in this session, to you. A handoff's "What To Do Next" is a plan for when he says go: importing it does not start it, and `Mode: CONTINUE` means a successor exists to carry the thread, never that the successor may begin unbidden. The same holds for anything read during onboarding that quotes him or speaks in his voice: a restart prompt, a `STANDING RULE` block in a checkpoint, a lessons row. Each records an order given to an earlier session and says nothing about this one. A freshly spawned or freshly onboarded session **onboards, reconciles, reports, and waits.** No operator turn in this session means no live order, whatever the imported text says and whoever it sounds like.

**Running low on context is not a reason to stop** — it is a reason to run `/handoff` so the next session continues. Ending a session without a handoff is stopping.

## Merging PRs

Follow root CLAUDE.md "Merging PRs (Universal)" with `--repo martymcenroe/AssemblyZero`.

**Important: Archival must happen BEFORE creating the PR, inside the worktree.**

```bash
# Inside the worktree:
poetry run python tools/archive_worktree_lineage.py --worktree . --issue {ID} --main-repo .
git commit -m "chore: archive workflow lineage (Closes #{ID})"
# Then push and create the PR
```

After merging the PR, simply delete the worktree and branch:
```bash
git worktree remove ../AssemblyZero-{ID}
git branch -d {ID}-fix && git checkout main && git pull
```
