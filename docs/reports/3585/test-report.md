# Test Report: the testing workflow's implementation subpackage under standard 0034 (#3585 step 5, batch B)

Each module's new test file was run against the unchanged module first; every site test failed there, and every test that pins kept behaviour passed. No test makes a model call: `call_claude_for_file` and the provider gate behind it are replaced.

## orchestrator.py

- New: `tests/unit/test_orchestrator_loud_failure.py`, 32 tests (26 site tests, 6 that pin kept behaviour).
- Before the fix: 26 failed, 6 passed. After: 32 passed.
- Changed existing tests: five files ran `implement_code` in a temporary directory that was not a git repository and relied on `came_from_base` reading that as "untracked". Each now initialises a repository, as N4's worktree always is: `test_implement_code_timeout.py` (1 test), `test_modify_on_missing_is_an_add.py` (fixture), `test_n4_registers_every_framework.py` (helper, 4 tests), `test_planned_imports_resolve.py` (fixture), `test_testing_workflow.py` (3 tests).
- Neighbouring suites: the 56 unit test files that import the implementation package, the `implement_code` shim or the nodes package, plus `test_run_implement_from_lld_loud_failure.py`: 1031 passed and 10 failed, all ten the case above; after the change, the ten pass.
- Audits: `audit_loud_failure.py --check` 0 new, 7 stale (the baseline entries this fix removed); `audit_fail_open.py --check` no new fail-open; `audit_halt_sites.py --check` PASS, 162 sites registered.

## keep_passing_tests.py

- New: `tests/unit/test_keep_passing_tests_loud_failure.py`, 11 tests. Before the fix: 7 failed, 4 passed (the kept-behaviour pins). After: 11 passed.
- Changed existing tests in `test_n4_keeps_passing_tests.py`: five tests that asserted a quiet pass-through now assert the raise; two source-text tests search for the keep and release calls without their closing parenthesis, since the calls now pass the path.
- Neighbouring suites (the module's importers, the orchestrator's, and the green-phase contract tests): 114 passed and 2 failed, the two source-text tests; after the change, 80 passed in the three files they touch.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.
