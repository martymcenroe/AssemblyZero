# Test Report — A standalone implementation run reaches a defined end state (#3509)

Backfilled 2026-09-25 after the merge, from PR #3538 (merge `444849ae`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

New file `tests/unit/test_impl_standalone_end_state.py`, against throwaway repos with a bare origin, reading the worktree list, the branch list, the checkout's status and the origin's refs:

- `test_worktrees_branches_status_and_origin_are_unchanged`: a full `--mock` run leaves all four identical to before.
- `test_the_report_leaves_nothing_in_place`: `[run] left in place (0):`.
- `test_the_status_file_is_beside_the_run_log`
- `test_only_the_remote_branch_remains`: `finish_standalone_run` on a worktree with work leaves no worktree and no local branch, only `origin/42-implementation`, and leaves the checkout status unchanged.
- `test_the_late_work_is_on_the_pushed_branch`
- `test_ignored_lineage_is_kept_and_caches_are_not`
- `test_a_failed_push_keeps_the_worktree_and_the_branch`
- `test_help_carries_the_end_state`

## Results the PR reported

All 8 fail on the old code. The full local unit tier was run before the push; the PR's first comment carries the result.

## Not verified for this backfill

- Nothing was re-run.
