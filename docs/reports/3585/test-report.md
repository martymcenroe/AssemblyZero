# Test Report: the testing workflow's runners, templates and top-level modules under standard 0034 (#3585 step 5)

Each fixed site has a test that fails before its fix and passes after, run first against the unchanged module. Filled in module by module on `3585-testing-runners`. Every runner test stands in for `npx` and the subprocess: nothing real is run.

## runners/jest_runner.py

**New: `tests/unit/test_jest_runner_loud_failure.py` (12).** Each site test is named for its ledger line; the rest pin kept behaviour.

**Before the fix, measured** against HEAD's `jest_runner.py`: 9 failed, 3 passed. The nine site tests failed. The three that passed pin a project with no package.json (quiet), a failing typecheck returned as a failing result (72), and a readable report read quietly.

**Changed tests:** `test_jest_runner.py::test_parse_invalid_json` now expects `RunnerError` where it expected a fallback result.

**Neighbouring suites:** 132 passed across the 13 files that import the runner modules.

**Audits:** `audit_loud_failure.py --check` reports 0 new and 1 stale, the deleted tag. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the same issue in each of `jest_runner.py` and `base_runner.py` as at HEAD.

## runners/base_runner.py

**New: `tests/unit/test_base_runner_loud_failure.py` (7).**

**Before the fix, measured:** 5 failed, 2 passed. The five site tests failed. The two that passed pin scenario coverage as passed over total, and a command that ran returning its streams and exit code.

**Changed tests:** none.

**Neighbouring suites:** 194 passed across 18 files: the runner files, the framework integration tests, the full-suite gate, the zero-collected route and the path-to-runner tests.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issue as at HEAD.

## runners/pytest_runner.py

**New: `tests/unit/test_pytest_runner_loud_failure.py` (9).**

**Before the fix, measured:** 6 failed, 3 passed. The six site tests failed: exit codes 2 to 5, a collection error, and the missing coverage table. The three that passed pin exit 0 and exit 1 read from the summary line, and a TOTAL row read.

**Changed tests:** `test_pytest_runner.py::test_parse_no_coverage` now expects None where it expected 0.0.

**Neighbouring suites:** 41 passed across the 5 files that use the pytest runner.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## runners/playwright_runner.py

**New: `tests/unit/test_playwright_runner_loud_failure.py` (9).**

**Before the fix, measured** against HEAD's module: 8 failed, 1 passed. The eight site tests failed; the one that passed pins a readable report.

**Changed tests:** `test_playwright_runner.py::test_parse_invalid_json` now expects `RunnerError` where it expected a fallback result.

**Neighbouring suites:** 52 passed across the 5 files that use the Playwright runner.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issue as at HEAD.

## runner_registry.py

**New: `tests/unit/test_runner_registry_loud_failure.py` (10).**

**Before the fix, measured:** 3 failed, 7 passed. The three site tests failed: an unknown string, a value of another type, and a one-framework run read as pytest. The seven that passed pin three ways of naming no framework and the four frameworks resolving from enum and string.

**Changed tests:**
- `test_scaffold_resolves_framework_string.py`: the "nonsense" case leaves the None test, and a new test expects the raise.
- `test_framework_integration.py`: `test_invalid_string_returns_none` is now `test_invalid_string_raises`.

**Neighbouring suites:** 197 passed across 18 files that resolve a framework, scaffold, or run several frameworks.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## exit_code_router.py

**New: `tests/unit/test_exit_code_router_loud_failure.py` (13).** Four site tests, and nine that pin the descriptions verify_phases prints.

**Before the fix, measured:** 4 failed, 9 passed. The four site tests failed, since the function was there; the nine description tests passed.

**Changed tests:** `test_exit_code_router.py` loses its 16 tests of the deleted function and their import. Its description and constant tests are unchanged.

**Neighbouring suites:** 68 passed and 1 skipped across 5 files: the router's two test files, the verify_phases lint test, the exit-code verify_phases tests and the honest-coverage tests. The skip is the lint test's own: ruff is not importable in the environment.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issue as at HEAD.

## framework_detector.py

**New: `tests/unit/test_framework_detector_loud_failure.py` (8).**

**Before the fix, measured:** 6 failed, 2 passed. The six site tests failed. The two that passed pin an existing empty project, read quietly as pytest at the root, and a detected config.

**Changed tests:** `test_framework_detector.py::test_nonexistent_directory` now expects `FrameworkResolutionError` naming the path, where it expected an empty list.

**Found later, fixed in a test-only commit:** the commit left 22 tests failing in 6 orchestrator files it had not run. Each drives the implementation stage with git stubbed, so the worktree is never cut, and the stage's provisioning now refuses a worktree that is not there. None of them is about provisioning, so each helper stands `provision_worktree` in, with a comment saying why. The 13 files that reach the stage or provisioning: 215 passed.

**Neighbouring suites:** 576 passed across 21 files: the detector's tests, N0's, provisioning's, the multi-framework and mock runs, and the LLD parsing chain.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## coverage_report.py

**New: `tests/unit/test_coverage_report_loud_failure.py` (6).** Every test pins the kept contract.

**Against HEAD's module:** 6 passed. There is no fix.

**Changed tests:** none.

**Neighbouring suites:** 51 passed across the 3 files that read the coverage report.

## audit.py, the testing workflow's

**New: `tests/unit/test_testing_audit_loud_failure.py` (8).** One is a strict xfail recording the open site 320.

**Before the fix, measured:** 3 failed, 4 passed, 1 xfailed. The three site tests failed. The four that passed pin an empty directory as file 1, numbering after the highest file, a working append, and a TOTAL row read.

**Changed tests:** none.

**Neighbouring suites:** 616 passed and 1 xfailed across 17 files: the module's importers, and the node tests that number and log audit records.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## path_validator.py

**New: `tests/unit/test_path_validator_loud_failure.py` (7).**

**Before the fix, measured:** 4 failed, 3 passed. The four site tests failed. The three that passed pin the stat rejection (65), files that all load, and no files.

**Changed tests:** `test_path_validator.py::test_skips_invalid_files` is now `test_one_invalid_file_leaves_no_partial_context` and expects empty content.

**Neighbouring suites:** 75 passed across 4 files, among them the entry point's loud-failure tests and the context-injection tests.

**Audits:** 0 new loud-failure sites, and this module's swallowed handler is now stale in the baseline; no new fail-open; halt sites pass. Ruff finds one fewer issue than at HEAD.

## symbol_validator.py

**New: `tests/unit/test_symbol_validator_loud_failure.py` (7).**

**Before the fix, measured:** 4 failed, 3 passed. The four site tests failed. The three that passed pin a module that is not the repository's own, a good name, and a missing name with its near match.

**Changed tests:**
- `test_generated_test_symbols.py`: the unparseable source and the unreadable module now expect `SymbolCheckError`.
- `test_symbol_validator_sees_conditional_bindings.py`: `test_an_unparseable_module_is_still_none` is now `test_an_unparseable_module_raises`.

**Neighbouring suites:** 129 passed across 8 files: the validator's tests and N4c's.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## knowledge/patterns.py

**New: `tests/unit/test_knowledge_patterns_loud_failure.py` (10).**

**Before the fix, measured:** 8 failed, 2 passed. The eight site tests failed. The two that passed pin the shipped file, loaded quietly, and detection reading it.

**Changed tests:** `test_testing_workflow.py::test_load_test_types_yaml_missing` now expects FileNotFoundError, where it called the deleted inline copy.

**Neighbouring suites:** 325 passed across 5 files: the workflow tests, N0's and N1's.

**Audits:** 0 new loud-failure sites, and this module's swallowed handler is now stale in the baseline; no new fail-open; halt sites pass. Ruff finds one fewer issue than at HEAD in the module and in the workflow tests.

## templates/runbook.py

**New: `tests/unit/test_runbook_template_loud_failure.py` (5).**

**Before the fix, measured:** 4 failed, 1 passed. The four site tests failed. The one that passed pins a runbook written from the LLD alone, with none of the invented strings.

**Changed tests,** all in `test_testing_workflow.py`:
- two runbook tests gain a verification section in their LLDs;
- the prerequisites test gains a procedure and a verification section, and now asserts the LLD's own row;
- the minimal-LLD test now expects the ValueError naming all three sections.

**Neighbouring suites:** 288 passed across the runbook and workflow tests.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## templates/wiki_page.py

**New: `tests/unit/test_wiki_page_template_loud_failure.py` (5).**

**Before the fix, measured:** 2 failed, 3 passed. The two site tests failed. The three that passed pin a page written from the LLD's own overview, an already-linked page as False, and a new page linked.

**Changed tests:** `test_testing_workflow.py::test_generate_wiki_page_with_long_feature_name` gains an overview in its LLD and asserts the page, where it accepted None or the placeholder.

**Neighbouring suites:** 301 passed across 4 files: the wiki tests, the workflow tests and N8's.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds nothing in the module or the new test file.
