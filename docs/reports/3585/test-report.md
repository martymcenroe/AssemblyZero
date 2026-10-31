# Test Report: the testing workflow's remaining nodes under standard 0034 (#3585 step 5, batch D)

Each fixed site has a test that fails before its fix and passes after, run first against the unchanged module. Filled in module by module on `3585-testing-nodes`. No test makes a model call, and no workflow is run; nodes are called directly with built state in temporary directories, and alerts are asserted through the `operator_alerts` fixture.

## nodes/validate_tests_mechanical.py

**New: `tests/unit/test_validate_tests_mechanical_loud_failure.py` (18).** Each site test is named for its ledger line; the rest pin kept behaviour.

**Before the fix, measured** against HEAD's `validate_tests_mechanical.py`: 10 failed, 8 passed. The ten site tests failed (500, 523, three for 522, two for 676, three for 1043). The eight that passed pin the parse answers (101, 418, 499, 557), the two budget halts (963, 975), an absent neighbour, and a carried escalate with its reason.

**Changed tests:** `test_assertion_reading.py::test_an_unparseable_neighbour_costs_a_helper_not_the_run` is now `test_an_unparseable_neighbour_is_named_not_dropped` and expects `HelperSourceUnreadable`; `test_scaffold_gates_see_stubs.py::test_validator_reports_but_allows_a_hollow_suite_with_no_spec_bodies` reads the hollow line from stderr; `test_spec_stage_pair.py::test_an_exhausted_scaffold_no_longer_reaches_implementation` and `test_validate_tests_mechanical.py::test_escalate_after_max_attempts` expect the raise without a reason and "escalate" with one; `test_wave1_token_savings.py::test_identical_output_triggers_escalation` and `test_max_attempts_still_escalates` carry the node's `error_message` in state.

**Neighbouring suites:** 338 passed, 1 skipped, across the 20 files that import the module or `route_after_validate`, with `test_gate_registry.py`, `test_answer_key.py` and the new file.

**Audits:** `audit_loud_failure.py --check` reports 0 new and 2 stale, the two deleted tags. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the same two issues in the module as at HEAD; the new test file is clean.

## nodes/scaffold_tests.py

**New: `tests/unit/test_scaffold_tests_loud_failure.py` (18).** Generated test code is compiled and its test function called, so "fails until replaced" is measured rather than read off the text. The finder error is a stand-in `find_spec` that raises for one name.

**Before the fix, measured** against HEAD's `scaffold_tests.py`: 11 failed, 7 passed. The eleven site tests failed (105, 325, 342, two for 787, 788, 833, 834, 1069, two for 1199). The seven that passed pin a Section 10 that still parses, a derivable assertion, an unsupported framework raising (435), an unknown name read as a symbol, both scaffolds' audit copies when the directory exists, and the no-scenarios halt (1153).

**Changed tests:** `test_scaffold_tests.py::TestParseLLDTestSection::test_parse_missing_section_10` expects the ValueError; `test_spec_test_missing_imports.py::test_unparseable_source_reports_nothing` is now `test_unparseable_source_raises` and expects `ScaffoldImportError`.

**Neighbouring suites:** the 31 files that import the module or its changed functions, `tests/integration/test_lld_parsing_chain.py` among them: 720 passed and 2 failed before the two changes above, which were those two tests; both files pass after (37).

**Audits:** `audit_loud_failure.py --check` reports 0 new and 2 more stale, the two deleted tags. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes: no new halt site, since the halts go through the registered `_halt_scaffold_framework` and the existing returns. Ruff finds the module's same 8 issues as at HEAD; the new test file is clean.

## nodes/review_test_plan.py

**New: `tests/unit/test_review_test_plan_loud_failure.py` (11).** The provider and `with_retry` are stand-ins: no model is called. The router half of five rows is `graph.py`'s, so these tests pin the node half: an `error_message` and an ERROR line on stderr.

**Before the fix, measured** against HEAD's `review_test_plan.py`: 10 failed, 1 passed. Every site test failed (two for 156, 428, 489, 553, 579, 609, three for 710). The one that passed pins blocking issues as the feedback.

**Changed tests:** in `test_testing_workflow.py`, `test_load_review_prompt_file_missing` expects FileNotFoundError; `test_default_review_prompt` loads AssemblyZero's own prompt with no root; `test_extract_feedback_numbered_list`, `test_extract_feedback_fallback` and `test_extract_feedback_default_message` expect "" where they accepted the placeholder.

**Neighbouring suites:** the 23 files that import the module or `route_after_review`: 798 passed, 1 skipped and 5 failed before the changes above, which were those five tests; their classes pass after (14).

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the module's same 2 issues as at HEAD; the new test file is clean.
