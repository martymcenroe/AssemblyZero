# Test Reports: the testing workflow under standard 0034 (#3585 step 5)

The package was swept in five batches from `fc1b2b0f` and merged on one branch. Each batch's report follows whole, under its own title, in merge order: C, B, D, E, A.

---

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


---

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

## templates/cp_docs.py

**New: `tests/unit/test_cp_docs_template_loud_failure.py` (3).**

**Before the fix, measured:** 2 failed, 1 passed. The two site tests failed. The one that passed pins the LLD's own commands as the reference, with none of the invented ones.

**Changed tests:** `test_doc_step_handling.py::test_document_emits_cp_docs_when_not_skipped` gives its LLD a command, so the c/p docs it expects are written from the LLD.

**Neighbouring suites:** 299 passed across 4 files: the c/p doc tests, the workflow tests and N8's.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds nothing in the module or the new test file.


---

# 3585 - Test Report: loud failure in the testing workflow, batch A

## 1. Metadata

| Field | Value |
|-------|-------|
| **Issue** | #3585 (step 5); module issue #3810 for `checkpoints.py` |
| **Implementation Report** | `docs/reports/3585/implementation-report.md` |
| **Date** | 2026-10-31 |

## 2. Method

For each module the new test file was written first and run against the unchanged module with `-rA`: every site test had to fail, and every test pinning kept behaviour had to pass. The module was then fixed until all passed, and every test file that imports the module or a changed function was run.

## 3. `assemblyzero/workflows/testing/checkpoints.py`

| Run | Result |
|---|---|
| `tests/unit/test_checkpoints_loud_failure.py` against the unchanged module (26 tests) | 20 failed, 6 passed: every site test failed; the 6 kept-behaviour tests passed |
| The same file after the fix (30 tests, with N5's halt) | 30 passed |
| `test_tdd_checkpoints`, `test_impl_resume_prefers_best_measured`, `test_impl_lands_through_driver`, `test_doc_step_handling`, `test_post_finalize_checkpoint`, `test_gate_registry` with the new file | 140 passed |
| The 23 files that reach N5 and failed before the conftest stand-in and the registry row | 631 passed |
| The 17 files reaching `run_impl_stage`, `_best_measured_attempt` or `finish_standalone_run` | 302 passed |
| `tools/audit_loud_failure.py --check` | 0 new, 3 stale (the fixed `fail_open_tag` entries) |
| `tools/audit_fail_open.py --check` | no new fail-open |
| `tools/audit_halt_sites.py --check` | PASS, 163 halt sites, every one registered |

## 4. `verify_phases.py`, `cleanup_helpers.py`, `cleanup.py`

| Run | Result |
|---|---|
| `test_verify_phases_loud_failure.py` against the unchanged module (69 tests) | 42 failed, 27 passed (9 kept-behaviour pins, 18 compliant-row pins) |
| The same file after the fix | 69 passed |
| Every file naming verify_phases, its entry points, the testing graph, augment_tests or run_pytest | first 80 failures from the change (minimal states with no coverage target, full-suite gates outside a git repository, retired behaviour); after updating those tests, 593 and then 55 passed in the affected files |
| `test_cleanup_helpers_loud_failure.py` against HEAD's module (10 tests) | 5 failed, 5 passed |
| It and `test_cleanup_helpers.py` after the fix | 35 passed |
| `test_cleanup_loud_failure.py` against HEAD's module (12 tests) | 10 failed, 2 passed |
| It, `test_cleanup.py`, `test_cleanup_stage.py`, `test_node_modules_supply_nodes.py` | 45 passed |
| `test_adversarial_review_halts`, `test_doc_step_handling`, `test_testing_workflow`, `test_orchestrator_stages`, `test_post_finalize_checkpoint` | 377 passed |
| The three audits after the last commit | loud-failure 0 new (13 stale); fail-open no new; halt sites PASS, 164 sites |

For `checkpoints.py` (section 3): before the conftest stand-in, 92 unit tests in 23 files halted at N5: they stub the test run and point `repo_root` at a plain directory, so the measurement note git cannot write became their halt.

---

# Joining the batches

- **The full unit tier on the merged branch** (`64c051bc`, after the three baselines were regenerated): 14 failed, 5 errors, 12323 passed. Each batch had passed alone; every failure was where two met.
- **Fixed, each with its test:** `test_framework_ownership_unknown.py` (4 tests; 3 fail without the wrap); `test_checkpoint_ignored_exclusions.py` (2 tests; the first fails before the fix); `test_wiki_page_template_loud_failure.py::test_169` now pins None for a wiki with no sidebar. The N8 tests (25), the checkpoint and mock-run tests (40) and the loop-cap rolls (27) pass.
- **The full unit tier again** (`9899db9f`): 1 failed, 12347 passed. The one, `test_tdd_checkpoints.py::test_excludes_workflow_internal_dirs_from_staging`, had a fake git that answered `check-ignore` as "ignored"; corrected in `8e800226`, and the three checkpoint test files pass (44). The full tier runs once more when the package lands, after `origin/main` is merged.
- **Audits after the last code change:** loud-failure PASS (208 sites); fail-open PASS --strict (10116 sites); halt sites PASS --strict (182 sites, 113 gates, impl rows 50).
