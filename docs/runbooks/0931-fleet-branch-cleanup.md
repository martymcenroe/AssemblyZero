# 0931 - Fleet Branch Cleanup

**Category:** Runbook / Fleet Hygiene
**Version:** 1.0
**Last Updated:** 2026-05-07
**Tool location:** `unleashed/src/fleet_branch_cleanup.py`
**Related:** ADR-0217 (squash-merge orphan graft cleanup), unleashed#437

---

## Purpose

Periodically sweep local squash-merge orphan branches across every git repo under `~/Projects/`. After GitHub squash-merges a PR and auto-deletes the remote branch, the local branch ref persists indefinitely because git's `branch -d` reachability check refuses to delete branches whose tip SHA isn't an ancestor of main. Without this tool, every squash-merged feature branch becomes immortal local clutter.

The tool applies the ADR-0217 four-step `git replace --graft` recipe to delete safely **without ever using `-D` or `--force`**.

## When to Run

- **After a session that merged multiple PRs** — clean up the orphans before they pile up.
- **Periodically** (weekly/biweekly) as fleet hygiene.
- **Before audit/review tasks** that depend on `git branch --list` accuracy.
- **When you notice clutter** in `git branch --list` after switching to a repo.

## Prerequisites

- `gh auth status` — fine-grained PAT works (only read-only PR queries).
- `core.useReplaceRefs = true` (the git default; the recipe needs it).
- Network access to GitHub (for `gh pr list` lookups).

## Invocation

```bash
cd /c/Users/mcwiz/Projects/unleashed

# Default: dry-run across the whole fleet
poetry run python src/fleet_branch_cleanup.py

# Actually clean up
poetry run python src/fleet_branch_cleanup.py --apply

# Limit to one repo
poetry run python src/fleet_branch_cleanup.py --repo Aletheia
poetry run python src/fleet_branch_cleanup.py --repo Aletheia --apply
```

**Always do `--dry-run` first** (the default) and read the classifications before passing `--apply`.

## What the Tool Does

For every git repo directly under `~/Projects/` (skipping worktrees and the test-rig sextant-2/-4/-6 dirs), the tool walks each non-default-branch local ref and:

1. **Skips** if the branch is checked out in any worktree.
2. **Looks up the merged PR** via `gh pr list --state merged --search head:<branch>` to find the squash commit on main.
3. **Verifies content equivalence via `git cherry origin/main <branch>`** — every commit on the branch must have content already in main (cherry's `-` prefix). This is more permissive than tree-equivalence: it tolerates main absorbing intervening commits during the squash.
4. **Applies the four-step recipe** (ADR-0217):
   ```
   BASE=$(git rev-parse <SQUASH_SHA>^)
   git replace --graft <SQUASH_SHA> $BASE <BRANCH_TIP_SHA>
   git branch -d <BRANCH>      # NEVER -D
   git replace -d <SQUASH_SHA> # cleanup
   ```

## Classifications

Every branch ends up in exactly one of these buckets:

| Status | Meaning | Tool action |
|--------|---------|-------------|
| `cleaned` | All gates passed; graft+delete completed (or `dry_run_would_clean` in dry-run) | branch removed |
| `has_worktree` | Branch is checked out in a worktree | left alone |
| `has_unmerged_commits` | `git cherry` showed commits NOT in `origin/main` (`+` prefix) | left alone — needs human review |
| `no_merged_pr` | `gh pr list` found no merged PR with this branch as head | left alone — likely active feature or abandoned |
| `error` | Unexpected failure (e.g. squash commit missing locally even after fetch) | left alone — surface in summary |

Only `cleaned` branches are actually mutated.

## Safety

- **Defaults to dry-run.** `--apply` required to act.
- **Never uses `git branch -D` or any `--force` flag.** Every step uses safe-mode git commands.
- **Step 4 (`replace -d`) cleanup runs regardless of step 3 outcome** — no stray graft refs linger.
- **Per-branch try/except.** A failure on one repo doesn't stop the rest.
- **Local-only.** No remote refs are touched. No data leaves the machine beyond the read-only `gh pr list` queries.
- **`--apply` is idempotent.** Re-running on a clean fleet is a no-op (every branch is left in `no_merged_pr`, `has_worktree`, or `has_unmerged_commits`).

## Output Interpretation

The tool prints a per-branch line during the scan and a categorized summary at the end. Read the summary first.

### `cleaned` / `dry_run_would_clean`

These are the squash-merge orphans the tool identified and (will / did) remove. No further action needed. Re-run `git branch --list` in any cleaned repo to confirm.

### `has_unmerged_commits`

The branch has commits whose content is NOT in `origin/main`. Possibilities:
- Active feature work that was never merged.
- Local commits made AFTER the merge (your work after PR closed).
- Cherry-picked work that diverged.

**Don't use this tool on these.** Inspect manually:
```bash
cd ~/Projects/<repo>
git log --oneline origin/main..<branch>
```

If the commits matter, finish the work and merge. If they don't, manually delete with `git branch -D` (one-time, with eyes open).

### `no_merged_pr`

No merged PR was found with this branch as head on GitHub. Possibilities:
- Branch was created locally but never pushed.
- PR is still open (check `gh pr list --state open`).
- PR was closed without merging.
- Branch name on GitHub differs from local (rename history).

Inspect manually before deleting.

### `has_worktree`

Branch is in active use somewhere. Don't delete. Resolve by removing the worktree first (`git worktree remove ...`) when you're done with that work.

### `error`

Tool hit something unexpected. Read the detail line. Common cause: the merged PR's squash commit isn't fetched locally even after the tool's auto-fetch. Recovery: `git -C <repo> fetch --all`, then re-run.

## Recovery if Things Go Sideways

The tool's only mutations are local. Worst case is a stranded replace ref:

```bash
# Find lingering replace refs (should be zero after a normal run)
for d in ~/Projects/*/; do
    if [ -d "$d/.git" ]; then
        n=$(git -C "$d" replace --list 2>/dev/null | wc -l)
        [ "$n" -gt 0 ] && echo "$(basename $d): $n"
    fi
done

# Remove any lingering ones
git -C <repo> replace -d <sha>
```

A stranded replace ref is harmless (only changes how `git log` resolves that one commit locally). It's just untidy.

## What This Doesn't Solve

- **Worktree leftovers** — see runbook 0922 (N9 cleanup node).
- **Stale remote branches** — auto-deleted on merge fleet-wide since 2026-04-30 via `delete_branch_on_merge: true` set on every repo.
- **Pre-existing replace refs from manual ADR-0217 runs** — sweep with the recovery loop above.

## Validation

First production run: 2026-05-07 (unleashed#437 / unleashed#470).

- 78 non-default local branches → 34 (45 cleaned, all squash-merge orphans).
- Zero errors.
- Zero lingering replace refs after the run.
- Confirmed `git branch --list` accuracy across the fleet post-run.

## Related

- ADR-0217 — `git replace --graft` decomposition for force-free squash-merge orphan cleanup
- Issue #998 — onboard skill must scrutinize handoff `--force` directives
- Root `CLAUDE.md` — "Git destructive (... `branch -D` ...) require explicit user approval" rule
- Runbook 0922 — N9 cleanup node (worktrees, lineage, learning summary)
- Runbook 0911 — Dependabot PR audit (also creates audit-worktree branches that this tool will sweep when their PRs merge)

## History

| Date | Change |
|------|--------|
| 2026-05-07 | v1.0: Initial runbook. Tool shipped in unleashed#470 closing unleashed#437. |
