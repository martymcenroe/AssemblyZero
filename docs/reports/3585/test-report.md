# Test Report: the testing graph and three of its nodes under standard 0034 (#3585 step 5, batch C)

Each fixed site has a test that fails before its fix and passes after, run first against the unchanged module. Filled in module by module on `3585-testing-graph`. No test makes a model call, and no workflow is run against a repository; routers and nodes are called directly with built state, the one graph roll stubs every node it passes through, and alerts are asserted through the `operator_alerts` fixture.

## graph.py

**New: `tests/unit/test_testing_graph_loud_failure.py` (37).** Each site test is named for its ledger line; the rest pin kept behaviour and the stop wrapper's identity.

**Before the fix, measured** against HEAD's `graph.py`: 32 failed, 5 passed. The five that passed pin a working checkpoint, an N1 error without auto_mode, a BLOCKED plan under the revision cap, the augment path under budget, and N7.5's halt (557).

**Changed tests:** in `test_testing_workflow.py`, eight router tests that asserted `end` (or N2 under auto) now assert HALT or a revision; in `test_revise_test_plan.py`, the cap and strict tests assert HALT and the two auto tests assert a revision; `test_test_plan_revision_budget.py::test_what_the_defect_actually_was` now finds a halt with the budget reason and a bundle; `test_impl_verdict_integrity.py::test_the_cap_still_stops_the_loop`, two tests in `test_coverage_routes_to_tests.py`, `test_red_phase_retry_semantics.py::test_existing_routes_are_unchanged[END-HALT]` and `test_spec_stage_pair.py::test_an_exhausted_scaffold_no_longer_reaches_implementation` assert HALT.

**Neighbouring suites:** 28 files that import the graph, its routers, the atlas, the gate registry or the halt node: 434 passed, 1 skipped, and the two stale-baseline tests failed as expected. 18 impl, mock-roll, CLI and orchestrator files that build or invoke the graph: 306 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new and 1 stale, the checkpoint wrapper's handler. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes with every site registered. Ruff finds no issue in the module that is not at HEAD; the new test file is clean.

## nodes/load_lld.py

**New: `tests/unit/test_load_lld_loud_failure.py` (27).** Each site test is named for its ledger line; the eight compliant rows are pinned, and a control spec carries everything the halting tests remove.

**Before the fix, measured** against HEAD's `load_lld.py` with the first 26 tests: 15 failed, 11 passed. The eleven that passed are the control, the quiet "no functions" answer, a clean rebuild miss, and the eight compliant pins. The 27th test, added with the fix, checks that `validate_spec_structure` raises exactly the reason `spec_structure_error` gives.

**Changed tests:** each a fixture that relied on a missing files table or test plan being accepted, or an assertion of the old empty list: `test_extract_files_fencing.py::test_table_inside_code_fence_is_skipped` and `test_testing_workflow.py::test_extract_files_to_modify_no_table` expect the raise; the specs in `test_testing_workflow.py` (two tests), `test_implement_from_lld_cli.py`, `test_per_framework_coverage_target.py` and `test_two_frameworks_one_run.py` gain a files table; `test_ts_path_resolves_to_its_runner.py`'s helpers write a three-column table and a Section 10 test plan, and `test_two_frameworks_one_run.py`'s issue-only body carries both.

**Neighbouring suites:** 27 files that import the module or its functions, the spec workflow's three checks that call the extractor, the answer key and `tests/integration/test_lld_parsing_chain.py`: 670 passed after the fixture updates. The first pass, before them, failed 11, each one of those fixtures.

**Audits:** `audit_loud_failure.py --check` reports 0 new and 2 more stale, the rebuild handler and its tag. `audit_fail_open.py --check` reports no new fail-open, and none is left in the module. `audit_halt_sites.py --check` passes. Ruff finds the module's same three issues as at HEAD; the new test file is clean.

## nodes/augment_tests.py

**New: `tests/unit/test_augment_tests_loud_failure.py` (32).** Each site test is named for its ledger line. The node runs with the model call and the vetting pytest run patched, in a temporary worktree with a small package, a test file and an audit dir; no model is called.

**Before the fix, measured** against HEAD's `augment_tests.py`: 29 failed, 3 passed. The three that passed pin the compliant fallback to bare lines (142), the quiet "nothing to remove" answers of `_without_named_tests`, and the clean success path.

**Changed tests:** in `test_n4c_keeps_the_suite_and_bounds_output.py`, the no-audit-dir test is now `test_no_audit_dir_halts_before_any_call`; the timed-out generation, the vetting run that collects nothing, and no addition passing expect the halt with the file as it was; the dropped-tests tests read the drops at ERROR on stderr, and the one whose repair call fails expects that halt. In `test_coverage_routes_to_tests.py`, the two node tests that returned to N5 are now `test_node_halts_when_nothing_to_target` and `test_node_halts_with_no_test_file`.

**Neighbouring suites:** 12 files that import the module, with the gate registry, the graph halts and the new file: 250 passed and 8 failed on the first pass, each one of the tests above; the three changed files then passed (78).

**Audits:** `audit_loud_failure.py --check` reports 0 new and 3 more stale, the three deleted tags. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the module's same nine issues as at HEAD; the new test file is clean.

## nodes/e2e_validation.py

**New: `tests/unit/test_e2e_validation_loud_failure.py` (23).** Each site test is named for its ledger line; the three compliant rows and the no-E2E-test finalize are pinned. pytest is patched at `run_command`, so no test runs a suite.

**Before the fix, measured** against HEAD's `e2e_validation.py` with the first 22 tests: 16 failed, 6 passed. The six that passed pin the advisory count (45), the finalize for a run with no E2E test (313, 337), the circuit breaker (394), the cap (417) and the exit-1 loop to N4. The 23rd, added with the fix, checks that a file is judged by its path inside the repository.

**Changed tests:** in `test_testing_workflow.py`, `test_run_e2e_tests_timeout` and `test_run_e2e_tests_not_found` expect `E2ERunFailed`, `test_cleanup_sandbox` and `test_verify_safety_limits` expect `NotImplementedError`, and `test_e2e_validation_with_sandbox` expects the halt before any test runs.

**Neighbouring suites:** 15 files that name the node or N6, with the mock rolls and the gate registry: 532 passed after the updates. The first pass failed 5, the tests above.

**Audits:** `audit_loud_failure.py --check` reports 0 new; the module had no baseline entry. `audit_fail_open.py --check` reports no new fail-open, and the module's two baseline entries are stale. `audit_halt_sites.py --check` passes. Ruff finds the module's one issue at HEAD; the new test file is clean.


---

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

## routing.py

- New: `tests/unit/test_routing_loud_failure.py`, 2 tests that pin the compliant site; both pass before and after.
- Neighbouring suite `test_implement_code_routing.py` with the new file: 31 passed.

## prompts.py

- New: `tests/unit/test_prompts_loud_failure.py`, 3 tests. Before the fix: 1 failed, 2 passed. After: 3 passed.
- Changed existing tests: none.
- Neighbouring suites (the nine unit files that import the prompt builders, and the orchestrator's new tests): 480 passed.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## context.py

- New: `tests/unit/test_context_loud_failure.py`, 3 tests. Before the fix: 2 failed (both on the new `filepath` keyword), 1 passed. After: 3 passed.
- Changed existing tests: none.
- Neighbouring suites (the module's importers and the prompt and context tests): 78 passed.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.


---

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

## nodes/document.py

**New: `tests/unit/test_document_loud_failure.py` (11).** The lessons template and the execution log are stand-ins; the wiki page, README and sidebar are real files, and each failure is injected at the step it names.

**Before the fix, measured** against HEAD's `document.py`: 9 failed, 2 passed. Every site test failed (two for 182, 215, two for 289, 292, 308, 338, 350); the first tests for 215 and 289 failed on the new wording only, since the kept behaviour, no raise and no change, held. The two that passed pin a README entry added under Features and a README that already names the feature.

**Changed tests:** `test_testing_workflow.py::TestDocumentModule::test_update_readme_no_readme` expects FileNotFoundError.

**Neighbouring suites:** `test_adversarial_review_halts.py`, `test_cleanup.py`, `test_doc_step_handling.py`, `test_document_assembler.py`, `test_testing_workflow.py` and `test_gate_registry.py`: 392 passed and 1 failed before the change above, which was that test; its class passes after (10).

**Audits:** `audit_loud_failure.py --check` reports 0 new and 4 more stale, the module's four broad handlers, which now re-raise. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff's four findings on the module at HEAD are gone; the new test file is clean.

## nodes/mechanical_hooks.py

**New: `tests/unit/test_mechanical_hooks_loud_failure.py` (9).** The hooks are real shell commands in a temporary directory, and `git` is the real one: the failed staging is git's own exit 128 outside a repository.

**Before the fix, measured** against HEAD's `mechanical_hooks.py`: 5 failed, 4 passed. The two 108 tests failed on the unread return code; 74, 91 and 98 failed only on the new stderr line, since their halts held. The four that passed pin no config, a config naming no command (two cases) and a successful hook's output staged.

**Changed tests:** none.

**Neighbouring suites:** the six files that import the module, with `test_gate_registry.py`: 158 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the module's one issue as at HEAD; the new test file is clean.

## nodes/revise_test_plan.py

**New: `tests/unit/test_revise_test_plan_loud_failure.py` (6).** The provider and `with_retry` are stand-ins: no model is called. Each site test drives the node into its failure and routes the result through `route_after_revision`.

**Before the fix, measured** against HEAD's `revise_test_plan.py`: 4 failed, 2 passed. The four site tests failed only on the new stderr line; their halts held. The two that passed pin a short plan under the cap asking again with no reason, and a complete revision going back to N1.

**Changed tests:** none.

**Neighbouring suites:** the six files that import the module or `route_after_revision`, with `test_gate_registry.py`: 381 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff is clean on the module and the new test file.

## nodes/finalize.py

**New: `tests/unit/test_finalize_loud_failure.py` (10).** Files are real, in a temporary repository; the failed move is a stand-in `rename`. The test report generator is a stand-in where N7 runs whole.

**Before the fix, measured** against HEAD's `finalize.py`: 8 failed, 2 passed. Every site test failed (46, the done/ lookup, 74, two cases of 152, two of 216, and the skipped-list print on its new wording). The two that passed pin a file outside active/ left alone and a green output with counts completing.

**Changed tests:** in `test_issue_141.py`, `test_100` expects `FinalizeError`, and `test_030` and `test_080` expect FileNotFoundError; `test_testing_workflow.py::TestFinalizeFullCoverage::test_finalize_archives_lld` carries a green output with counts.

**Neighbouring suites:** the 21 files that import the module or `route_after_finalize`, with `test_gate_registry.py`: 608 passed, 1 skipped and 4 failed before the changes above, which were those four tests; after, 25 passed in `test_issue_141.py` with the new file, and 18 in the Finalize classes of `test_testing_workflow.py`.

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the module's same 2 issues as at HEAD; the new test file is clean.

## nodes/adversarial_validator.py

**New: `tests/unit/test_adversarial_validator_loud_failure.py` (4).** All four pin kept behaviour: a file that does not compile is an error, reported once, and the scans still find a mock and a test without assertions in code that compiles.

**Before the change, measured** against HEAD's `adversarial_validator.py`: 4 passed, as pins should.

**Changed tests:** none.

**Neighbouring suites:** `test_adversarial_validator.py`, `test_adversarial_review_halts.py`, `test_adversarial_node.py` and the new file: 115 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff is clean, as at HEAD.

## nodes/completeness_gate.py

**New: `tests/unit/test_completeness_gate_loud_failure.py` (2).** Both drive N4b with an empty requirement set and route the result through `route_after_completeness_gate`.

**Before the change, measured** against HEAD's `completeness_gate.py`: 1 failed, 1 passed. The first test failed only on the new stderr line, since the halt held; the second, with no recorded reason, passed.

**Changed tests:** none.

**Neighbouring suites:** the seven files that import the module, with `test_gate_registry.py`: 169 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff is clean, as at HEAD.
