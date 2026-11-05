# Test report: #4686, #4687

## Unit

`tests/unit/test_n5_unmeasured_vitest_project.py`, 7 tests, on a git repository with two Vitest projects: `web/` with a coverage provider and `kit/web/` with `vitest` alone. `base_runner.run_command` stands in for npx, as in `test_vitest_measures_coverage.py`.

- #4686 T1 (R1, R4): `TestT1TheRunnerAsksForWhatTheRunNeeds`, 3 tests: without coverage `vitest` alone is enough; with coverage the provider is still required, naming `@vitest/coverage-v8` and the project; without coverage `vitest` itself is still required.
- #4686 T2 (R2): `TestT2TheFullSuiteGateMeasuresNothing::test_runs_a_project_with_no_provider`: the gate runs the kit's suite and passes.
- #4686 T3 (R3): `TestT3ThePreflightAsksPerLeg`, 2 tests: a gate-only leg with no provider passes the preflight; a leg with test files and no provider raises `FrameworkLegError` naming `vitest (kit/web)` and the provider.
- #4687 T1 (R1): `TestTheLogNamesEveryProject::test_both_vitest_projects_are_named`, and `test_lld_decides_new_test_frameworks.py::TestR3TheLogSaysWhich::test_each_phase_is_named`, whose expected lines change from `{'pytest': '.'}` to `['pytest']` and from `{'pytest': '.', 'vitest': 'web'}` to `['pytest', 'vitest (web)']`.

Run with `main`'s `jest_runner.py`, `verify_phases.py` and `load_lld.py` at `91d7a3b9` written over the branch's, then the branch's restored and checked byte for byte: 5 failed, 2 passed. The 2 that pass hold unchanged behaviour: a provider is still required with coverage, and for a leg with test files. With the change: 7 passed.

Neighbours, with the change: the 74 test files whose names cover the phases, runners, frameworks, N0 and the preflight (`verify_phases`, `vitest`, `jest`, `runner`, `framework`, `green`, `red_`, `full_suite`, `gate_only`, `multi_framework`, `load_lld`, `n0_`, `preflight`, `playwright`, `non_pytest`): 1,055 passed, 1 skipped.

## Real calls

None.

## Full suite

14,917 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed. The same 18 fail on `main` at `91d7a3b9` with no change applied: 16 in `tests/test_auto_reviewer_wait_loop.py`, `tests/test_universal_claude_md.py::test_adr_references_resolve`, and `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success`.

## Lint

`ruff check` on the six changed modules reports the same findings, file by file and rule by rule, as on `main`. The new test file is clean.
