# Test Report: the three workflow entry points fail loud (#4100, #4097, #4098)

Every test drives the entry point's `main()` with stand-ins, as `tests/unit/test_impl_lands_through_driver.py` does: a throwaway git repository as the target, a stand-in for the graph, and a stand-in for `gh` or `git` only where a test injects that failure. No model is called and no graph node runs. Alerts are asserted through the `operator_alerts` fixture. Each new test file was run against the unchanged module first, and every site test failed there.

## `tests/unit/test_run_requirements_workflow_loud_failure.py` (53)

One or more tests per ledger line, named `test_<line>_...`, for all 36 sites, plus pins of the behaviour that stays: an empty checkpoint database is "no checkpoint" (118), a brief with no heading is "(no title)" (175), a brief outside any repository falls back to the working directory's repository (560), an empty `ideas/active/` is exit 0 for `--all` (1203), manual handling at a human gate files or saves nothing and succeeds (1551, 1558), declining the regeneration prompt is exit 0 with no alert (1690), and quitting either `--select` menu is a cancel (1662, 1668). The success paths of a saved LLD, a resumed review, a batch and a resume pass with no alert. One test holds the module to no `# fail-open:` tag.

The stand-ins: `invoke_with_budget` and `create_requirements_graph` are replaced on the module, so the run's own code (the run record, the result block, the outcome check) runs for real. A checkpoint database is a file of garbage bytes, which sqlite refuses for real. An unreadable brief is a directory named `broken.md`. A working directory in no repository is a real directory outside any repository.

- Against the unchanged module: `39 failed, 14 passed`. The 39 are the site tests, failing for the intended reasons: exit 0 where a failure happened, the failure on stdout and not stderr, no alert, or the `GitBranchError` escaping `main`. The 14 that passed are the pins and the success paths.
- On this branch: 53 passed.

### Changed existing tests (11)

- `tests/unit/test_requirements_cli.py`: the missing-brief title test now expects `RunFailed` naming the file; the two `select_brief_file` and four `select_github_issue` tests that expected None for a failure (including an empty issue list) now expect `RunFailed` with the cause; the `--all` and `--resume` refusals and the merge-driver refusal now read stderr and assert one alert.
- `tests/unit/test_run_record.py`: `test_lld_runner_records_a_crash_in_the_graph` expects the RuntimeError raised after the record is written, which it still checks.

### Neighbouring suites

Every test file that imports the module: `test_requirements_cli.py` and `test_run_record.py`, 87 passed; `test_agy_both_seats.py`, `test_alert_channel_at_start.py`, `test_best_of_n.py`, `test_issue_161.py`, `test_lld_dry_run_is_dry.py`, `test_lld_mock_completes.py`, `test_lld_mock_is_offline.py`, `test_lld_writes_only_worktree.py`, `test_profile_bench.py`, `test_seats.py`, `test_standalone_runner_heartbeat.py`, `test_step_budget.py` and `test_the_law_gemini_in_both_seats.py`, 164 passed; `test_requirements_nodes.py`, 98 passed.

`tools/audit_loud_failure.py --check`: 0 new; 3 stale, the module's three handlers this fix removed, which leave the baseline in the parent session. `tools/audit_fail_open.py --check`: no new fail-open. `ruff check`: the new test file is clean; the module has 13 findings against 16 at HEAD, none new.

The full unit tier runs in the parent session.
