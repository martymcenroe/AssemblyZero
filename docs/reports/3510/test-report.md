# Test Report — The LLD workflow writes only into its worktree and names how it ends (#3510)

Backfilled 2026-09-25 after the merge, from PR #3537 (merge `bf5b060c`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

New file `tests/unit/test_lld_writes_only_worktree.py`, ten tests against throwaway repos:

- `test_porcelain_is_empty_after_a_full_mock_run`: the acceptance test. `git status --porcelain --untracked-files=all` is empty before and after a full mock run.
- `test_the_mock_outputs_are_under_data_mock_runs`, `test_the_final_report_leaves_nothing_in_place` (`[run] left in place (0):`), `test_a_mock_run_does_not_shift_a_real_runs_lineage`, `test_a_mock_run_records_no_approval_in_the_real_cache`.
- `test_the_lld_and_status_land_in_the_worktree_not_the_checkout`: a real (non-mock) N5 save against a repo with a bare origin.
- `test_no_audit_dir_writes_nothing_into_the_working_directory`, `test_mirror_passes_through_a_file_already_in_the_worktree`.
- `test_finishing_commands_for_a_worktree_and_its_branch`, `test_nothing_left_means_nothing_to_finish`.

Changed expectations: three `TestShiftLineageVersions` tests assert the LLD and status survive; the #3507 dry-run test asserts the new wording; the finalize tests in `test_requirements_nodes.py` and `test_finalize_repair_routing.py` point the write root at their own temp directory. The mock-run tests from #3533 and #3512 also redirect `WORKFLOW_AUDIT_FILE` (the wider leak is #3531).

## Results the PR reported

The nine tests that existed before the cwd fix all fail on the old code. 907 passed across the 28 affected files. `tools/audit_fail_open.py --check` passed with no baseline change.

## Not verified for this backfill

- Nothing was re-run.
