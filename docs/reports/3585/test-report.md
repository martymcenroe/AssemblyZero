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

## parsers.py

- New: `tests/unit/test_parsers_loud_failure.py`, 7 tests. Before the fix: 4 failed, 3 passed. After: 7 passed.
- Changed existing test: `test_zero_needs_denominator.py::TestConftestOptionValidation::test_unparseable_new_code_abstains_here` becomes `test_unparseable_new_code_stops_here` and asserts the SyntaxError.
- Neighbouring suites (the ten unit files that import the parsers): 150 passed and 1 failed, the test above; after the change, 20 passed in the two files it touches.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## edit_script_fix.py

- New: `tests/unit/test_edit_script_fix_loud_failure.py`, 9 tests. Before the fix: 5 failed, 4 passed. After: 9 passed. Rows 497, 503 and 507 are tested in `test_orchestrator_loud_failure.py`.
- Changed existing test: `test_failure_attribution_by_test_body.py::test_an_unparseable_planned_file_attributes_nothing` becomes `test_an_unparseable_planned_file_stops_attribution` and asserts the SyntaxError.
- Neighbouring suites (the 13 unit files that import the module or its functions): 192 passed.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## deprecated.py

- New: `tests/unit/test_deprecated_loud_failure.py`, 8 tests. Before the fix: 5 failed, 3 passed. After: 8 passed.
- Changed existing tests in `test_testing_workflow.py`: two `parse_implementation_response` tests that relied on an invented `implementation_N.py` now assert the ValueError.
- Neighbouring suites (`test_testing_workflow.py`, `test_implement_code_shim_exports.py` and the new file): 294 passed and 2 failed, the two tests above; after the change they pass.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## claude_client.py

- New: `tests/unit/test_claude_client_loud_failure.py`, 5 tests. Before the fix: 3 failed, 2 passed. After: 5 passed.
- Changed existing test: `test_llm_idle_timeout.py::test_a_bad_override_falls_back_rather_than_failing_the_call` becomes `test_a_bad_override_raises_naming_the_variable`, and an empty value is pinned as the default in `test_an_empty_override_is_the_default`.
- Neighbouring suites (the 21 unit files that import the module or its functions): 578 passed and 3 failed, the three parametrised cases above; after the change, 27 passed in the two files.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## import_validator.py

- New: `tests/unit/test_import_validator_loud_failure.py`, 7 tests. Before the fix: 4 failed, 3 passed. After: 7 passed.
- Changed existing tests: none.
- Neighbouring suites (the unit files that import the module, and `test_validate_code_short.py`): 60 passed.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.
