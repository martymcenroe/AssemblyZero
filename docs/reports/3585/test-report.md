# Test Report: the testing workflow's remaining nodes under standard 0034 (#3585 step 5, batch D)

Each fixed site has a test that fails before its fix and passes after, run first against the unchanged module. Filled in module by module on `3585-testing-nodes`. No test makes a model call, and no workflow is run; nodes are called directly with built state in temporary directories, and alerts are asserted through the `operator_alerts` fixture.

## nodes/validate_tests_mechanical.py

**New: `tests/unit/test_validate_tests_mechanical_loud_failure.py` (18).** Each site test is named for its ledger line; the rest pin kept behaviour.

**Before the fix, measured** against HEAD's `validate_tests_mechanical.py`: 10 failed, 8 passed. The ten site tests failed (500, 523, three for 522, two for 676, three for 1043). The eight that passed pin the parse answers (101, 418, 499, 557), the two budget halts (963, 975), an absent neighbour, and a carried escalate with its reason.

**Changed tests:** `test_assertion_reading.py::test_an_unparseable_neighbour_costs_a_helper_not_the_run` is now `test_an_unparseable_neighbour_is_named_not_dropped` and expects `HelperSourceUnreadable`; `test_scaffold_gates_see_stubs.py::test_validator_reports_but_allows_a_hollow_suite_with_no_spec_bodies` reads the hollow line from stderr; `test_spec_stage_pair.py::test_an_exhausted_scaffold_no_longer_reaches_implementation` and `test_validate_tests_mechanical.py::test_escalate_after_max_attempts` expect the raise without a reason and "escalate" with one; `test_wave1_token_savings.py::test_identical_output_triggers_escalation` and `test_max_attempts_still_escalates` carry the node's `error_message` in state.

**Neighbouring suites:** 338 passed, 1 skipped, across the 20 files that import the module or `route_after_validate`, with `test_gate_registry.py`, `test_answer_key.py` and the new file.

**Audits:** `audit_loud_failure.py --check` reports 0 new and 2 stale, the two deleted tags. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the same two issues in the module as at HEAD; the new test file is clean.
