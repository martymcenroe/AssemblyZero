# Implementation Report: the LLD workflow lands through the fleet merge driver (#3704)

## What was wrong

`git_operations.commit_and_pr` committed in the `{issue}-lld` worktree, pushed the branch, and opened the PR with a direct `["gh", "pr", "create", ...]`. On the operator's machines `gh` resolves to a wrapper that refuses `gh pr create`, `gh pr new` and `gh pr merge` from any process whose ancestry does not include the fleet merge driver (`tracked_pr_land.py`), on both sides, so every real APPROVED run ended with a pushed remote branch, the worktree, and no PR. Neither the dry run nor the mock run reaches that step.

## Changes made

1. `assemblyzero/core/merge_driver.py`: `check_configured()` (why the driver cannot be used, or None), `driver_path()`, `build_argv()`, `parse_output()` (the driver's fixed `created PR #`, `squash SHA` and `[OK] stage=landed` lines; no pattern matching), and `land()`, which runs the driver found in `AZ_MERGE_DRIVER` and returns a `Landing` (PR number, squash SHA, output) or raises `MergeDriverError` with the driver's own output. Nothing in it calls git or gh; nothing is retried.
2. `commit_and_pr` keeps the stage-and-commit step and hands the worktree, branch, title and a body file (written under the target's gitignored `data/assemblyzero/pr-bodies/`) to `merge_driver.land(..., no_issue=True, base=base_branch)`. The push and the `gh pr create` are gone, so a refused landing leaves no remote branch. The PR URL is built from the target's origin and the PR number the driver reports. The `No-Issue:` / `Ref #N` shape (#238, #1459) is unchanged.
3. `tools/run_requirements_workflow.py`: a real LLD run (not `--dry-run`, not `--mock`) refuses at start with `check_configured()`'s reason, before the pre-generation check and before any model call. The dry run names the driver step.
4. `finalize.py` prints `LLD PR landed by the merge driver: <url>`.

## Design choice, stated

The driver merges as well as opens, so an APPROVED LLD is on the base branch when the run ends and the worktree and branch are gone. That follows the fleet rule that only the driver opens and merges PRs, and the operator's rule that no merge waits on his reading a PR.

## Not changed here

The same direct call sits in the orchestrator (`stages.py:2177`, with `gh pr merge` at `:2253`), the visual gate (`gate.py:283`) and the janitor (`fixers.py:166`). Each is filed to go through `merge_driver`: #3717, #3718, #3719.
