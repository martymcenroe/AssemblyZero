# Test report: #4278

## Changed tests

- `tests/tools/` moved by `git mv` to `tests/unit/tools/`, its `__init__.py` with it: 15 test files and 559 tests, which the unit tier now collects. No test changed beyond its parent-folder count, listed in the implementation report.
- `tests/unit/test_every_test_file_runs_in_a_tier.py` (new), shared with #4756: `test_every_test_file_runs_in_a_tier` fails when a test file outside `tests/unit/` carries no tier marker and is not on its named list. Run against a copy of HEAD's `tests/` tree, it names all 15 files of the old `tests/tools/`. Its other tests are listed in the test report for #4756.
- References that followed the move:
  - `tests/unit/test_dependabot_network_guard.py`: `KNOWN_LOADERS` names `tests/unit/tools/test_dependabot_review.py` and `tests/unit/tools/test_dependabot_worktree_guard.py`, which `test_every_test_file_that_loads_the_tool_runs_under_the_guard` checks.
  - `tests/unit/test_cerberus_after_auto_review.py`: `test_the_cerberus_health_audit_and_its_tests_are_gone` asserts the retired audit's test file is absent from `tests/unit/tools/`.
  - Comments only, no test changed: `tests/unit/test_pat_session_terminal.py`, `tests/unit/test_scraper_import_safety.py` and `tests/unit/test_verify_encrypted_secret_no_disclosure.py`.

## Collection, before and after

Every test outside `tests/unit/` that no tier selects, collected with `tools/test-gate.py tests/ --ignore=tests/unit -m "not (integration or e2e or adversarial)" --collect-only -q`:

- At HEAD, before the change: `608/692 tests collected (84 deselected)`. The 559 tests of `tests/tools/` are among them.
- On this tree: `5/95 tests collected (90 deselected)`. They are the benchmark's 2 tests and the canary's 3, the two files on the guard's named list, left out on purpose.

## Implementation runs, 2026-11-14

On Ubuntu, through `tools/test-gate.py`, so the unit tier's conftest applies:

- `tests/unit/tools/`: `559 passed, 1 warning in 50.22s`
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
