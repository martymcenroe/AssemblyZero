# Test report: #4756

## Changed tests

- `tests/unit/test_every_test_file_runs_in_a_tier.py` (new), shared with #4278:
  - R2, the guard on the repository: `test_every_test_file_runs_in_a_tier`.
  - Its named list: `test_every_named_exception_still_exists` and `test_every_named_exception_has_a_reason`.
  - The failure names the file and its test: `test_an_unmarked_file_outside_the_unit_tier_fails_and_is_named`.
  - Each place a tier marker can sit: `test_a_tier_marker_in_any_position_passes`, six cases.
  - A test no tier marker reaches: `test_a_test_no_tier_marker_reaches_is_named`, three cases.
  - `test_a_named_exception_passes`, `test_files_pytest_does_not_collect_are_skipped` and `test_a_conftest_this_check_cannot_read_stops_it`.
- R1, moved by `git mv` from `tests/integration/` to `tests/unit/`, with no change beyond the path: `test_cascade_hook_integration.py`, `test_janitor_workflow.py`, `test_lld_parsing_chain.py` and `test_orchestrator_graph.py`.
- `tests/test_universal_claude_md.py`: its module `pytestmark` now carries `pytest.mark.integration` beside its `skipif`, so the local integration tier runs its 6 tests, `test_issue_references_exist` among them.
- `tests/unit/test_orchestrator_stage_runners.py`: its docstring now says `test_orchestrator_graph.py` carried no marker and has since moved into the unit tier. No test changed.

## Collection, before and after

Every test outside `tests/unit/` that no tier selects, collected with `tools/test-gate.py tests/ --ignore=tests/unit -m "not (integration or e2e or adversarial)" --collect-only -q`:

- At HEAD, before the change: `608/692 tests collected (84 deselected)`
- On this tree: `5/95 tests collected (90 deselected)`. They are the benchmark's 2 tests and the canary's 3, the two files on the guard's named list, left out on purpose.

## Implementation runs, 2026-11-14

On Ubuntu, through `tools/test-gate.py`:

- The four moved files: `38 passed, 1 warning in 100.86s (0:01:40)`
- `tests/unit/test_every_test_file_runs_in_a_tier.py`: `16 passed, 1 warning in 48.97s`
- `tests/unit/test_dependabot_network_guard.py`, `tests/unit/test_cerberus_after_auto_review.py` and `tests/unit/test_orchestrator_stage_runners.py`, which this batch edited: `35 passed, 1 warning in 476.87s (0:07:56)`

## Full suite, 2026-11-14

The last code edit was at 11:14 AM Central. The integration, e2e and adversarial tiers finished after it, and the unit tier after them. Each exited 0.

- Unit tier, 12:46 PM Central: `= 15175 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1381.95s (0:23:01) =`
- Integration tier, 11:23 AM Central: `=== 71 passed, 7 skipped, 15272 deselected, 34 warnings in 177.76s (0:02:57) ===`. This includes `tests/test_universal_claude_md.py`, 6 passed.
- E2E tier, 11:22 AM Central: `======== 19 passed, 15331 deselected, 34 warnings in 131.93s (0:02:11) =========`
- Adversarial tier, 11:21 AM Central: `========= 1 skipped, 15349 deselected, 34 warnings in 99.66s (0:01:39) =========`

The unit tier ran through pytest directly, as `poetry run pytest tests/unit/ -q --tb=short -v`. The `-v` is the one argument `tools/test-gate.py` adds to the command it builds. Run through `tools/test-gate.py`, the tier ended twice with `pytest timed out after 1800 seconds`: `tools/test_gate/parser.py` kills pytest at a fixed 1800 seconds, and other sessions' suites had the machine at a load average of 19.6, 27.1 and 30.8 on 24 cores. On main the same morning the tier took 1119 seconds, and this batch adds 613 tests to it: the 559 of `tests/unit/tools/`, the 38 of the four moved files and the guard's 16. The unit tier's 15175 passed is that morning's 14562 plus those 613.

CI's `test` job has been off since 2026-11-11 by the operator's order (#4711), so these local tiers are the only test gate before this batch lands.
