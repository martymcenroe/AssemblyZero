# Implementation Report: the rule files stop teaching hand merging (#3803)

## What changed

- **`CLAUDE.md`, "Merging PRs".** The section now says to land with the merge driver and, when it fails, to follow the route the root `CLAUDE.md` gives for the stage it printed. It keeps the one override this repository has: archive the lineage in the worktree after the last test run, before the driver. The hand push, PR creation, worktree removal, `git branch -d` and fetch of `main` are gone. It names no private repository and no driver path.
- **`[skip ci]`.** It is now forbidden on any commit of a branch the driver lands, and the archival example no longer carries it. Before, the rule said the final commit must omit it, while its own example made the final commit carry it. Measured on GitHub: PR #3683, whose only commit carried `[skip ci]`, ran only the two pr-sentinel checks and merged with no `test` run. PR #3769 ran `test`.
- **Runbook 0935, version 1.2:**
  - Step 5 applies the body with `--body-file`; the guard refuses the inline `--body` it used before.
  - Step 7 reruns the merge driver, which reuses the open PR. It used to merge, check out `main`, fast-forward and delete the branch by hand.
  - `behind` and `dirty` merge `origin/main` into the branch in the worktree, run the tests, commit and rerun the driver. The `update-branch` loop is gone: the merge commit it adds on GitHub makes the driver's next push non-fast-forward, so the run stops at `push_failed`.
  - The loop also called `echo` and ended in `gh pr merge`.
  - Never rebase a pushed branch: only a force push can publish it.
  - Five rows added to the banned table: hand merging and cleanup, `git checkout`, rebasing a pushed branch, `--theirs`, and rerunning the driver after its PR merged.
  - Step 4's quotation of the Auto Review workflow is fenced as `text`, because it is quoted for reading, not to be run.

- **`tools/archive_worktree_lineage.py`.** Its closing message told the agent to run `git worktree remove` by hand. It now says to commit what was staged and land the branch with the merge driver, which removes the worktree after the merge. Its docstring says the same.

## Not changed here

`ruff` reports five findings in `tools/archive_worktree_lineage.py` on lines this change did not touch, and 2779 across the repository, and CI does not run `ruff`. Tracked as #3804.

## Why

The operator directed on 2026-10-07 that when an agent has made a mess and is told to reread the rules, the rules must get it out through the driver and never send it into a blocked command. These two files did the opposite. The universal law's side is filed in the private tracking repository.
