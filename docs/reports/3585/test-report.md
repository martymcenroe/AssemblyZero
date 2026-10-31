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
