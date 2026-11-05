# Test report: #4680

## Unit

`tests/unit/test_n0_typescript_contract.py`, 7 tests. Each drives `load_lld` on a target with a Python suite at the root and a Vitest suite in `web/`, in an invented domain. Section 10 carries a Python fence with 2 functions and a TypeScript fence with 2 running `it` calls (one inside a `describe`), an `it.skip` and an `it.todo`; Section 6 plans `web/tests/replay.test.ts` with the same calls.

- T1 (R1, R2, R4): `TestT1TheContractIsBothSuites::test_the_contract_holds_both_suites` (4 scenarios, each once) and `test_the_pytest_scaffold_still_gets_only_the_python_functions`.
- T2 (R3): `TestT2EachTypeScriptScenarioCitesItsRequirement::test_each_typescript_scenario_carries_its_tag`, and `TestT2bARowTitledTestJoinsOnItsRequirement::test_each_row_titled_scenario_carries_the_requirement`, whose titles cite `REQ-030` and `REQ-040` and bodies `REQ-3` and `REQ-4`: the scenarios carry `REQ-3` and `REQ-4`, and `check_requirement_coverage` passes.
- T3 (R1): `TestT3N1CountsTheWholeSuite::test_the_mechanical_gates_pass`.
- T4 (R6): `TestT4NoPythonFunctionsKeepsTheTablePath::test_a_typescript_only_section_10_uses_the_tables`.
- T5 (R5): `TestT5N0SaysBothCounts::test_the_line_names_both`.

Run against `main`'s code at `7876e4ff` (the two source files stashed by name): 5 failed, 2 passed. T3 failed with "Only 2 scenario(s) for 4 requirement(s), coverage ratio 50% is below 100%". The 2 that pass hold unchanged behaviour: the pytest scaffold's functions and the table path. With the change: 7 passed.

Neighbours, with the change: `test_scaffold_emits_spec_bodies.py`, `test_diff_header_paths.py`, `test_scaffold_every_framework.py` and every test file that reads `typescript_bodies` or `spec_typescript_tests`: 181 passed.

## Real spec

The halted run's spec and LLD, read only: 13 scenarios for 10 requirements, no mechanical gate error, requirement coverage 10 of 10. On `main`, 5 scenarios and the ratio refusal.

## Real calls

None.

## Full suite

14,894 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed. The same 18 fail on `main` at `7876e4ff` with no change applied: 16 in `tests/test_auto_reviewer_wait_loop.py` ("the 'Wait for required checks' step is gone"), `tests/test_universal_claude_md.py::test_adr_references_resolve`, and `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success`.
