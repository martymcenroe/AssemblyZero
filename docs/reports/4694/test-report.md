# Test report: #4694

## Unit

`tests/unit/test_n4_routes_test_only_failures.py`, 11 tests. The orchestrator tests drive `implement_code` on a tmp TypeScript tree with the model calls stubbed, as `test_failed_patch_on_a_test_file_leaves_it.py` does, and `registered_test_files` stubbed because the fixture has no Vitest config to own its test file. With that stubbed the node runs to its end, so nothing is swallowed. The failure corpus is a Vitest assertion whose frame names only `web/tests/settle.test.ts`.

- T1 (R1): `TestATestOnlyFailureReachesTheCodeUnderTest::test_the_imported_source_is_offered_the_edit`: the planned `web/shared/settlement.ts`, which the failing test imports, is offered the edit, and no skip line names it.
- T4 (R4): `test_a_file_neither_named_nor_imported_stays_unchanged` (a planned file the test does not import keeps its skip line) and `test_without_the_import_the_skip_still_holds` (with no import, only the test file is offered).
- T2 (R2): `TestADeclineRoutesTheFailureToTheFileItNames`, 3 tests: a NO-EDIT on the test file naming a later planned file sends it the corpus led by the decline's reason this iteration; naming an earlier one returns `declined_routes`; and a `declined_routes` carried in state is offered first next iteration, with the reason, while an unnamed file stays skipped.
- T3 (R3): `TestADeclineOutsideThePlanIsReported`, 2 tests: a NO-EDIT naming `web/worker/fold.ts`, which is not planned, is printed at once, returned in `declines_outside_plan`, and carried in the stall text; and `verify_phases._with_the_stall` reports it in the cap's halt when the last pass changed something.
- Helpers, 3 tests: `files_named` reads paths and tails and refuses dotted words such as `e.g.` and `next.last_shown_price_usd_per_mwh`; `exercised_sources` reaches a `src/`-layout Python module from `from pkg import compiler`; `is_test_path` reads repo-relative plan paths.

Run with `main`'s `orchestrator.py`, `verify_phases.py` and `state.py` set aside by a named-path stash (the new module and test file kept, so the test imports), then reapplied and the stash dropped: 6 failed, 5 passed. The 6 are every test of R1, R2 and R3. The 5 that pass are the three helper tests and the two that hold #2851's skip, which did not change. With the change: 11 passed.

`tests/unit/test_node_modules_supply_nodes.py` names `decline_routing` in `SUPPLIES_NO_NODE_EXEMPTIONS`, as a helper imported by `implementation/orchestrator` and `verify_phases`. Without that entry its two tests fail, which the first full run showed.

Neighbours, with the change: `test_failed_patch_on_a_test_file_leaves_it.py`, `test_failure_attribution_by_frame.py`, `test_failure_attribution_by_test_body.py` and `test_green_collection_failure_on_planned_module.py` pass with the new file, 58 in all.

## Real calls

None.

## Full suite

14,937 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed, in 12m 46s. The 18 are the set that already fails on `main` at `b3b1acbd`: 16 in `tests/test_auto_reviewer_wait_loop.py`, `tests/test_universal_claude_md.py::test_adr_references_resolve`, and `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success`.

## Lint

`ruff check` on the changed source files reports only what `main` already reports in them: `orchestrator.py` I001, SIM102, RUF059 and BLE001; `verify_phases.py` its thirteen; `state.py` PIE794. `decline_routing.py` and the new test file are clean.
