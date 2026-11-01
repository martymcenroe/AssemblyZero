# Test report: #4437

## Changed tests

`tests/unit/test_lld_decides_new_test_frameworks.py` (new, 24 tests, on a fixture with pytest at its root and Vitest in `web/`):

- T1: `TestTheTestFilesDecide::test_t1_an_lld_naming_only_python_tests_is_a_pytest_run` and `TestN25AsksForTheRunsFrameworksOnly::test_t1_a_python_only_lld_asks_for_no_vitest_file`.
- T2: `TestTheTestFilesDecide::test_t2_an_lld_naming_only_vitest_paths_is_a_vitest_run`.
- T3: `TestT3TheGateRunsTheFrameworkTheLldDidNotName`, through the real `verify_green_phase`: each direction runs the other side's whole suite, a failure there routes to N4, and a framework that cannot start halts before any suite runs. `TestTheGateListsWhatTheRunDoesNot` holds what N0 lists.
- T4: `TestTheTestFilesDecide::test_t4_an_lld_naming_no_test_file_gets_every_project_framework`.
- R3: `TestR3TheLogSaysWhich`.
- Around them: both kinds named, `*_test.py`, prose naming the other side, a declared runner, a glob, and a checkpoint from before this change.

No existing test changed.

## Runs, 2026-11-01

- With the two old behaviours put back by hand (`_lld_decides` and N5's leg list), restored after: 11 of the 24 failed. A plain stash would have failed on the new imports alone and proved nothing.
- The 29 existing test files that touch framework choice: 967 passed.
- Integration, e2e and adversarial tiers before the last merge from `main`: 64 passed and 7 skipped; 19 passed; 1 skipped.
