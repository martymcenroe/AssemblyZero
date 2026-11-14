# Test report: #4264

## Changed tests

- `tests/unit/test_requirements_status_retired.py` (new, 4 tests), T1: `test_no_module_names_requirements_status`, `test_the_module_file_is_gone`, `test_the_check_finds_each_kind_of_reference` and `test_the_check_passes_names_that_only_resemble_it`.
- `tests/unit/test_requirements_status_loud_failure.py`: deleted, with its seven tests, which exercised only the deleted module's writer and reader.
- `tests/unit/test_n0c_unarticulated_conflict.py` (34 tests): the `node` fixture no longer patches `record_unverified`. `test_an_all_unarticulated_verdict_writes_no_proceeded_record` and `test_a_clean_verdict_is_not_recorded_as_unverified` are removed. `test_a_mixed_verdict_halts_on_the_real_one_and_files_only_that` and `test_a_well_formed_verdict_is_unchanged` lose the writer assertion and keep the rest. `test_an_all_unarticulated_verdict_files_nothing_and_halts_unverified` shows the all-unarticulated verdict halting.
- `tests/unit/test_requirements_gate_timeout.py` (23 tests): the ledger and banner tests are removed. `test_an_exhausted_retry_halts`, `test_an_unparseable_response_halts` and `test_the_last_fail_open_path_now_halts` keep their halt assertions. `TestTheVerdictBlock` holds `test_a_clean_roll_says_nothing_extra` and `test_a_failed_roll_reads_as_failed`.
- `tests/unit/test_speedrun_roll_kill.py` (21 tests): `TestKilledVerdictRendering::test_a_kill_is_not_rendered_as_a_failure`, `test_the_verdict_promises_the_resume` and `test_an_ordinary_failure_still_reads_as_a_failure` no longer patch `_requirements_unverified_lines`. Their assertions are unchanged.
- `tests/unit/test_loud_failure_check.py` (18 tests) and `tests/fixtures/loud_failure_baseline.json`: the two banner handlers leave the baseline, and `count` and `BASELINE_CEILING` are both 113. `test_no_fixed_site_left_in_the_baseline` holds it.

## Implementation runs, 2026-11-14

- `tests/unit/test_loud_failure_check.py`: `18 passed`.
- The same file with `test_failopen_tags_3767.py` and `test_fail_open_audit.py`: `88 passed`.
- Every `tests/**/test_*.py` that loads `tools/orchestrate.py` or `tools/speedrun_roll.py`: `1042 passed, 20 skipped, 1 warning in 717.94s (0:11:57)`.

## Full suite, 2026-11-14

Every tier ran in the worktree after the last edit, at 3:30 AM Central, with the two deletions staged. Each exited 0.

- Unit tier, 3:59 AM Central: `= 14562 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1119.35s (0:18:39) =`
- Integration tier, 3:42 AM Central: `=== 65 passed, 7 skipped, 15262 deselected, 34 warnings in 76.48s (0:01:16) ====`
- E2E tier, 3:42 AM Central: `========= 19 passed, 15315 deselected, 34 warnings in 80.49s (0:01:20) =========`
- Adversarial tier, 3:42 AM Central: `========= 1 skipped, 15333 deselected, 34 warnings in 63.97s (0:01:03) =========`. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 3:41 AM Central: `559 passed, 1 warning in 15.81s`

No nightly was run.
