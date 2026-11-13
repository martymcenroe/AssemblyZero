# Test report: #4737

## Changed tests

- `tests/unit/test_dependabot_outcomes.py` (new):
  - Test 1 (R1, AC1): each way a PR's run ends records one outcome and prints one outcome line. `test_each_run_ending_records_one_outcome`, with the cases `pytest-exit-0`, `pytest-exit-1`, `pytest-exit-5`, `pytest-timeout` and `runtime-error`; also `test_keyboard_interrupt_is_recorded_errored_and_reraised`, `test_an_unknown_status_from_process_pr_is_recorded_errored` and `test_outcome_refuses_a_status_outside_the_three`.
  - Test 2 (R1, AC1): the Summary names every PR the run tested. `test_main_summary_names_every_processed_pr`, `test_main_summary_keeps_the_prs_an_interrupt_cut_short` and `test_main_counts_no_commented_review_for_a_two_strike_deferral`. The last covers `UNREVIEWED_DEFERRED`: a two-strike deferral posts no review, so the Summary's COMMENTED count leaves it out.
  - R2: the timeout kills the whole process tree. `test_run_kill_tree_kills_the_grandchild_on_timeout`.
  - R3: a PR whose last run recorded no outcome is not rerun silently. The five `test_ledger_*` tests, `test_process_repo_stops_loudly_on_a_corrupt_ledger`, `test_one_prior_run_prints_repeat_and_still_runs_the_pr`, `test_two_prior_runs_at_the_same_head_defer_without_running`, `test_two_prior_runs_at_an_older_head_still_run_the_pr`, `test_interrupts_keep_the_entry_until_the_second_strike` and `test_a_recorded_outcome_clears_the_entry`.
- `tests/unit/test_dependabot_review.py`: `TestProcessRepoWithBudget` adds `UNREVIEWED_DEFERRED` to the statuses a run may return.
- Test 3 and AC2, one outcome line in the next nightly's `=== PR #4315` section, is carried by a follow-up issue, filed before the PR.

## `utf8_console`

`tests/unit/test_headless_tools_widen_stdout.py::test_every_no_console_tool_also_widens_stdout` failed once the tool installed `no_console`: #2673 requires every tool that installs `no_console` to install `utf8_console` too, because such a tool runs headless and echoes child output. The tool now installs `utf8_console` beside `no_console` (`tools/dependabot_review.py:99-104`), and the unit tier below, run after that edit, passes the test.

## Runs, 2026-11-13

Every run below finished after the last code edit, at 2:19 PM Central.

- Targeted run, 2:20 PM Central: 273 passed in 35 s.
- Unit tier, 2:42 PM Central: 14510 passed, 66 skipped, 7 deselected, 7 xfailed in 22m 7s.
- Integration tier, 2:44 PM Central: 65 passed, 7 skipped in 1m 31s.
- E2E tier, 2:46 PM Central: 19 passed in 2m 11s.
- Adversarial tier, 2:49 PM Central: 1 skipped in 45 s. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 2:49 PM Central: 559 passed in 13 s.
- No #4735 failures.
- `ruff check`: `tools/dependabot_review.py` reports 16 findings, the same as `main`. The new test files are clean.

No nightly was run.
