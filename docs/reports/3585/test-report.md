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
