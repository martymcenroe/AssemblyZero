# Test Report: run-path modules outside the workflow packages under standard 0034 (#3585 step 5)

Each fixed site has a test that fails before its fix and passes after, measured by running the new test file against the unchanged module first. Filled in module by module.

## speedrun/requirements_status.py

**New: `tests/unit/test_requirements_status_loud_failure.py` (7).** Each site test is named for its ledger line, plus tests that pin the kept behaviour: a written record reads back, an absent ledger is `[]`, blank lines are not corruption.

**Before the fix, measured** against the unchanged module: 4 failed, 3 passed. The three are the kept-behaviour tests.

**Changed test:** `test_requirements_gate_timeout.py::test_recording_never_raises` is now `test_a_record_that_cannot_be_written_alerts_and_raises`.

**Neighbouring suites:** 67 passed across `test_requirements_gate_timeout.py` and `test_n0c_unarticulated_conflict.py`.

## utils/ast_sentinel.py

**New: `tests/unit/test_ast_sentinel_loud_failure.py` (6).** Four site tests, plus an undefined name that is still a finding and a clean file that is ok.

**Before the fix, measured** against the unchanged module: 4 failed, 2 passed (the two kept-behaviour tests).

**Changed tests:** `test_ast_sentinel.py::test_analyze_file_io_error` and `::test_syntax_error` expect `SentinelCannotRun`; they read an `<io>` and a `<syntax>` finding.

**Neighbouring suites:** 24 passed across `test_ast_sentinel.py` and the new file; `test_validate_mechanical.py` 79 passed; `test_mechanical_gates.py` 18 passed.
