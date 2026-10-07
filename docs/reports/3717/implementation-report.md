# Implementation report: #3717, #3740, #3741

An orchestrated roll now lands through the fleet merge driver end to end, says so when it does not, and can resume after the driver has landed its LLD. Found on boostgauge #2 under boostgauge #421: run `run-issue2-230238` approved an LLD that never left the machine, with nothing said, and the relaunch `run-issue2-001443` could not resume and stopped in 7 seconds.

## #3717: the pr and cleanup stages use the driver

- `assemblyzero/workflows/orchestrator/stages.py::run_pr_stage`: no `git push`, no `gh pr create`. The PR body (`Closes #N` plus the adversarial summary, as before) is written to `<target>/data/assemblyzero/pr-bodies/impl-<N>.md` beside the LLD's, and the worktree and branch go to `merge_driver.land(..., issue=N, base=<base>)`. The stage records `impl_pr_url` and the reported squash in `impl_squash_sha`. A `MergeDriverError` fails the stage with the driver's output and `transient=False`, because the driver's refusals are decisions. `_reconcile_stale_remote_branch` still runs first.
- `_merge_pr` is deleted with its three tests. `run_cleanup_stage` merges nothing: an LLD PR URL in state is the driver's report that the LLD landed, and the implementation counts as landed only when `_squash_on_base` finds the reported squash with `git merge-base --is-ancestor <sha> origin/<base>` after a fetch. #2011's contract stands: a run whose pr stage produced a PR fails cleanup when that PR is not confirmed on the base.
- `assemblyzero/workflows/orchestrator/state.py`: `impl_squash_sha` is declared, for the #2018 reason (an undeclared key never crosses the LangGraph node boundary).
- `tools/orchestrate.py`: refuses with exit 2 when `merge_driver.check_configured()` gives a reason, before the model profile is resolved and before any stage runs. A `--mock` or `--dry-run` run lands nothing and is not refused.
- Requirement 3, the LLD PR: `run_lld_stage` uses the requirements workflow's `commit_and_pr`, which #3704 already routed through the driver; confirmed, no change.

## #3740: a failed LLD landing is said and fails the stage

- `assemblyzero/workflows/requirements/nodes/finalize.py`: the `GitOperationError` / `GitBranchError` handler prints `    [LLD] NOT LANDED: <reason>` and still stores `commit_error`.
- `run_lld_stage` reads `commit_error` from the sub-workflow result. An approved LLD whose landing failed is a failed stage, `LLD approved but not landed: <reason>`, `transient=False`. Before this nothing read `commit_error`.

## #3741: resume after a driver-landed LLD, and every decline said

- `tools/speedrun_roll.py`: new `_lld_landed_on_base(repo, issue, base)`: fetch, then `git cat-file -e origin/<base>:docs/lld/active/LLD-NNN.md` (or `LLD-N.md`). `resume_plan` accepts either an open LLD PR (the pre-#3704 shape) or the LLD on the attempt branch.
- Every reason `resume_plan` declines now writes `RESUME declined for #N: <reason>` to the events log through a local `declined()`; the artifact and pr-worktree declines already wrote their own `RESUME abandoned` lines and are unchanged.

## Fail-open baseline

Regenerated. The new `except merge_driver.MergeDriverError` in `run_pr_stage` is ruled on in the code (`# fail-open:` -- it records the stage's failed result and halts the run), so the baseline only renumbers the stage's two existing handlers from 0 and 1 to 1 and 2.

## Machine setting

`AZ_MERGE_DRIVER` was unset on both sides. Set in the Windows user environment on 2026-10-07 to `C:\Users\mcwiz\Projects\Secret-Agent-Man\tools\tracked_pr_land.py` (verified with `reg query HKCU\Environment`), which is where detached rolls run. Rollback: `reg delete HKCU\Environment /v AZ_MERGE_DRIVER`. The driver starts under the Windows AssemblyZero interpreter (`--help` checked).
