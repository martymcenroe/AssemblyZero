# Test Report: the green phase judges the lines a run changed (#4436, #4266)

The Python gate is tested with real pytest, real pytest-cov and real git repositories under `tmp_path`; only `poetry run` is replaced, because a throwaway target has no virtualenv. The Vitest tests use real git and a stand-in for `npx` that writes both reports in the shape of a real `coverage-final.json`.

## Requirements and the tests that prove them

| Req | Proved by |
|---|---|
| R1 | `test_t1_ten_covered_lines_in_a_large_module_pass_at_95`, `test_t2_two_of_the_ten_uncovered_are_refused_and_named`, `test_t3_ten_covered_lines_on_a_vitest_module_pass_at_95`, `test_t3_two_of_ten_uncovered_on_a_vitest_module_are_refused_and_named`, `test_t4_a_new_file_is_judged_whole`, `test_t4_a_new_file_no_test_imports_is_a_measured_zero_not_a_failure`, `test_a_committed_change_is_judged_too` |
| R2 | `test_t5_a_python_only_run_is_not_judged_on_vitest_and_the_log_says_so`, `test_r2_the_log_records_the_framework_it_did_not_judge`, `test_r2_a_run_that_changes_only_test_files_passes_on_any_figure`, `test_r2_a_run_that_only_deletes_lines_passes`, `test_r2_a_changed_comment_is_no_changed_line`, `test_r2_a_framework_with_changed_source_and_no_test_file_is_still_judged` |
| R3 | `test_r3_a_targets_own_fail_under_cannot_fail_the_run`, `test_r3_the_gate_passes_no_whole_module_threshold`, `test_r3_whole_file_coverage_is_reported`, `test_vitest_asks_for_the_per_line_report_and_switches_thresholds_off`, `test_jest_asks_for_the_per_line_report_and_switches_its_threshold_off` |
| R4 | `test_t2_two_of_the_ten_uncovered_are_refused_and_named`, `test_r4_n4c_is_asked_for_those_two_lines_and_no_others`, `test_t3_two_of_ten_uncovered_on_a_vitest_module_are_refused_and_named` |
| R5 | `test_t6_a_missing_report_halts_and_names_the_path`, `test_t6_an_unreadable_report_halts` (4 shapes), `test_t6_a_missing_report_is_never_zero_changed_lines_on_a_test_only_run`, `test_t6_a_report_with_no_data_quotes_coverages_reason`, `test_t6_a_stale_report_from_an_earlier_iteration_is_never_read`, `test_t6_a_changed_file_the_report_does_not_name_halts`, `test_t6_vitest_halts_on_either_report_missing`, `test_t6_vitest_with_nothing_changed_still_needs_its_report`, `test_t6_a_run_with_no_base_halts_before_the_suite_runs`, `test_t6_a_base_that_shares_no_history_halts` |
| R6, and #4266 | `test_t1_the_flag_wins_over_the_llds_target_on_the_spec_path`, `test_t2_with_no_flag_the_llds_target_is_used_and_named_as_its_source`, `test_the_flag_wins_on_the_issue_only_path`, `test_the_flag_wins_on_the_mock_path`, `test_a_flag_of_zero_is_still_the_flag` |
| R7 | ADR 0207 and the 0102 template read against the gate. No test: this is prose agreement. |

The tests are in `tests/unit/test_changed_line_coverage.py`, `test_changed_lines.py`, `test_run_base_resolution.py` and `test_coverage_target_source.py`.

## Each new test fails before the fix

`test_changed_line_coverage.py` uses only what `main` has, so it was copied into a detached worktree of `769a6136` and run there, with #4266's two tests beside it: 31 failed, 4 passed. The issue's named tests failed for the reason the issue gives:

| Test | On `769a6136` |
|---|---|
| T1 | `'N4c_augment_tests' == 'N7_finalize'`: the whole module is judged |
| T2 | `50.0 == 80.0`: the whole-file figure |
| R4 | N4c is asked for lines `2, 6, 10, 14, ...`, not `1210, 1211`: the defect, in one line |
| T3 | `54.28 == 80.0`, and `'N4c_augment_tests' == 'N7_finalize'` |
| T5 | `'N4c_augment_tests' == 'N7_finalize'`: judged on Vitest's whole-file 54.28% |
| #4266 T1 | `80 == 95` |

The 4 that pass there hold on both: `test_t6_a_failing_run_needs_no_report` is a control, and `test_t6_a_missing_report_is_never_zero_changed_lines_on_a_test_only_run`, `test_t6_a_report_with_no_data_quotes_coverages_reason` and `test_t6_vitest_halts_on_either_report_missing[no-summary]` are halts `main` already made, kept so they cannot be lost.

Tests added after that run were proved the same way:

- `test_the_runs_own_snapshots_are_never_judged_on_the_next_iteration` and its committed twin were run with `_RUN_RECORDS` disabled. Both fail, and the second iteration reads `Coverage: 1.3% (was 80.0%)`.
- `test_the_reports_leave_nothing_for_a_checkpoint_to_commit` runs on a target that does not ignore `coverage/`, as the real one does not, and fails if a report is left, by reading `git status`.
- `test_changed_lines.py` and `test_run_base_resolution.py` test new functions, so they cannot run on `main`. Each named failure is read from the code: `test_a_merge_base_with_the_branch_the_run_is_on_would_read_as_nothing` shows the failure the freeze prevents.

## Existing tests changed, and why

- 22 modules that fake N5's test run take the `coverage_as_reported` fixture, because a fake run has no report or base. It is applied per module, so a new test that forgets it halts loudly. It stands in for the measurement, and the routing under test is unchanged.
- N4c's tests supply `uncovered_changed_lines`, because N4c reads that and no report.
- `test_n5_halts_on_the_run_201554_shape` now runs in a real git repository, so it halts on the missing report and not on a missing base.
- Removed, with their reasons: `test_a_target_missing_from_the_report_is_named` (the law now holds per changed file, in `test_t6_a_changed_file_the_report_does_not_name_halts`), `test_fallback_infers_tools_from_impl_files`, `test_2387_a_candidate_outside_the_repository_halts` and `test_2393_no_derivable_coverage_target_halts` (the derivation is gone), `test_101_the_node_halts_on_a_report_it_cannot_read` (rewritten: N4c reads no report).

## Tiers on this branch

| Tier | Result |
|---|---|
| unit | 13,347 passed, 0 failed, 66 skipped, 7 deselected, 7 xfailed |
| integration, `ASSEMBLYZERO_MOCK_MODE=1` | 64 passed, 7 skipped |
| e2e, `ASSEMBLYZERO_MOCK_MODE=1` | 19 passed |
| adversarial | 1 skipped: its one test needs live model access |
| `tests/unit/test_mock_roll.py`, within the unit tier | 22 passed |
| `tests/unit/test_loud_failure_check.py`, `test_fail_open_audit.py`, `test_gate_registry.py`, within the unit tier | pass; no new baseline site |
| ruff on the 49 changed Python files, by rule against `769a6136` | 184 findings, 185 at the base; none new |

## N7's labels: `tests/unit/test_n7_labels_its_coverage.py` (3)

With a run's changed lines judged, and with nothing to judge, the console, the test report and the summary each name the figure they show. All three assert the labelled text, which does not exist without this change.

## Not tested

No real Vitest or Jest ran. The shell guard refuses `node_modules/.bin/vitest` because the npm shim contains an `echo`. The stand-in's report is built to the shape read from the installed provider and a real Jest report; see the implementation report's limits.
