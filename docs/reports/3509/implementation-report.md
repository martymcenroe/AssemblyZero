# Implementation Report — A standalone implementation run reaches a defined end state (#3509)

Backfilled 2026-09-25 after the merge, from PR #3538 (merge `444849ae`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502.

## What was wrong

N9 removes the worktree and branch only when `pr_url` is set and the PR has merged. Nothing in the standalone tool sets `pr_url`, so every standalone run ended with the sibling worktree, the branch and its checkpoint commits, `.implement-status-{issue}.json` at the root of whichever tree the run was in, and the lineage directory all in place, then printed a "Next steps" block telling the operator to `git add . && git commit` by hand.

## The end state chosen

Written in `--help` as `END_STATE`; the final report restates each step as it happens.

- Success, real run: commit what was written after the last checkpoint (`[CP:final]`); move every untracked or ignored, non-cache file out of the worktree into `<repo>/data/runs-kept/impl-<issue>-<HHMMSS>/`; push `<issue>-implementation`; remove the worktree with plain `git worktree remove`; `git branch -d` the local branch. What is left is the remote branch, and the report prints `gh pr create --head <branch> --base <base>` and the delete command for after the PR merges or closes.
- Mock run: a detached worktree with no branch and no push, removed at the end; it leaves nothing.
- Failure or halt: the worktree and branch are kept for `--resume`, and the report lists both with the commands that remove them (#3510's `[run] to finish:`).
- A step that cannot complete stops the finish there, keeps everything, and says which step failed and why.
- The status file moves to `<repo>/data/speedrun/runs/`, beside the run's log.

The #3519 ruling may revise this.

## Files

`tests/unit/test_impl_standalone_end_state.py`, `tools/run_implement_from_lld.py`.
