# Test Report: #4257 (with #4215, #4216, #4217, #4218, #4219, #4221)

New tests are in `tests/unit/test_speedrun_reset_safety.py` (real git, a bare origin, `gh` faked at `speedrun_reset._run`) and `tests/unit/test_speedrun_launch_gates.py` (drives `speedrun_roll.main`). Each fails on `main`: the fidelity, `issue-N`, lock, PR and ignored-file tests assert behaviour the old code lacked, and the branch tests need `speedrun_reset.ResetPreservationError`, `checkpoint_search_refs` or `reset_phrase`, which did not exist.

| Issue | Requirement | Test |
|---|---|---|
| #4257 | R1, T1, T2 | `test_speedrun_launch_gates.py::TestFidelityRefusalStopsTheLaunch` (refusal returns 91, starts nothing, also when detached; a passing preflight launches) |
| #4216 | R1, T1 | `TestCheckpointSearch::test_the_pin_finds_a_checkpoint_only_on_the_impl_stage_branch`, `..._survives_only_on_origin`, `TestNoBranchIsDeletedBeforeItsTipIsRecoverable::test_the_checkpoint_is_pinned_before_any_branch_leaves_origin` |
| #4216 | R2, T2 | `TestCheckpointSearch::test_the_pin_and_the_roll_read_one_list` |
| #4217 | R1, R2, T1 | `TestLockLayoutIsShared::test_a_lock_written_by_the_orchestrators_own_code_stops_the_reset_before_any_write`, `test_the_reader_and_the_writer_share_one_path`, `test_a_lock_in_the_target_repo_is_not_where_the_orchestrator_writes` |
| #4218 | R1, R2, T1 | `TestOnlyPipelinePrsAreClosed` |
| #4215 | R1, T1 | `test_a_pushed_branch_with_unlanded_commits_survives_on_origin_after_the_reset`, `test_the_graveyard_ref_is_on_origin_before_the_delete_goes_out`, `test_a_per_stage_branch_is_secured_the_same_way`, `test_a_tip_that_exists_only_on_origin_is_fetched_and_preserved`, `test_origin_refusing_the_graveyard_push_keeps_the_branch_and_stops_the_reset`, `test_an_unlistable_origin_stops_the_reset_instead_of_skipping_the_sweep` |
| #4215 | R2, T2 | `test_a_branch_whose_commits_are_all_on_the_base_is_removed_with_no_graveyard_ref`, `test_a_local_only_branch_is_parked_locally_and_pushes_nothing`, `test_the_reset_never_hands_git_a_force_delete` |
| #4219 | R1, T1 | `TestIgnoredFilesAreCopiedOutBeforeTheWorktreeGoes::test_a_clean_worktrees_ignored_lineage_is_in_reset_artifacts_with_the_same_bytes` (and the regenerable, second-reset and no-ignored-files cases) |
| #4219 | R2, T2 | `test_a_failed_copy_keeps_the_worktree_and_says_why`, `test_a_copy_that_differs_from_its_source_keeps_the_worktree`, `test_the_end_of_roll_restore_keeps_a_worktree_it_could_not_preserve` |
| #4221 | R1, T1 | `TestFreshNeedsExecuteAndTheTypedPhrase::test_fresh_execute_without_the_phrase_changes_nothing` (wrong phrase, empty answer, no console), `test_the_phrase_is_asked_on_the_console_before_the_detach`, the three detached-child tests, `TestStandaloneResetNeedsExecute` |
| #4221 | R2, T2 | `test_fresh_alone_prints_the_plan_and_writes_nothing`, `TestStandaloneResetNeedsExecute::test_without_execute_it_prints_the_plan_and_changes_nothing`, `test_the_plan_names_what_the_reset_would_do_to_each_branch`, `test_the_runbooks_teach_the_two_step_reset` |

Existing tests changed because the code they drove moved: `test_orphaned_roll_guards.py` (the lock fixture now sits under an AssemblyZero root, and the target repo has none), `test_speedrun_roll.py` (three `reset_one_issue` stubs accept `base`), `test_speedrun_reset.py` (the two mock classes for the retired deleters removed; the source-text guard stays), `test_branch_decoration_parsing.py` (the decoration tests point at `dispose_pipeline_branches`), `test_speedrun_reset_verify.py` (drives `main()` with `--execute` and the phrase), `test_rmtree_sites_are_gated.py` (`_remove_worktree_at` takes the issue).

`tests/unit/test_loud_failure_check.py` passes with no new baseline site and none removed.

Every CI tier in the worktree (`ASSEMBLYZERO_MOCK_MODE=1` for the last two):

- unit: 13235 passed, 66 skipped, 7 deselected, 7 xfailed, in 18 min 15 s. An earlier full run had one failure, `test_windows_paths_marker.py::test_at_least_one_test_carries_the_marker`: the home-state guard (#3531) reported five files added to `~/.assemblyzero/workflow_state` for issue 462 by a process outside this run, and that test's nested collection run inherited the failure. The test passes on its own and the rerun above is clean.
- integration: 64 passed, 7 skipped
- e2e: 19 passed

`ruff check` reports nothing in the two new test files. `tools/speedrun_roll.py` and `tools/speedrun_reset.py` report the same findings as `origin/main` (37 and a count that fell from 3 to 2), so none is in the added lines.
