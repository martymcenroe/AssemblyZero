# Test Report: one run tests a Python suite and a Vitest suite (#4236, #4237, #3001, #3087, #3085)

Each new test file was written first and run with `-rA` in this worktree against the unchanged source, then against the fix. The fixtures are throwaway targets in `tmp_path`: a pytest suite at the root and a Vitest suite in `web/` with a `package.json` and `vitest.config.ts`. No real npm, npx or model is called. pytest is stood in for at `verify_phases.run_pytest`, Vitest at `base_runner.run_command`, and `npx` on the PATH at `jest_runner.shutil.which`.

Against the unchanged source, the five files together: 48 failed, 10 passed. On the fix: 59 passed.

## #4236: `tests/unit/test_two_frameworks_one_run.py` (17)

- T1, every load site writes both frameworks: the mock load site, the spec load site (`load_lld` with a real spec file) and the issue-only load site (`_load_from_issue`, the `gh` call stood in for) each write `framework_configs` as pytest at the root and Vitest in `web/`, with string values. On `main` all four failed with `KeyError: 'framework_configs'`.
- T2, each phase runs every framework: a failing Vitest test fails the green phase while the pytest test passes, with pytest given the `.py` file alone and Vitest run in `web/` on `tests/engine.test.ts`; both passing goes on to E2E with `full_suite_validated` true; the red phase runs both legs on their own files; a Vitest test passing at red fails red; a run whose only test is Python still runs Vitest's whole suite in `web/` at the gate, with no test paths, and a Vitest regression there routes to N4; a `.test.ts` file outside `web/` halts with "belongs to no framework" before any suite runs. On `main` each failed, because only pytest ran (for example `assert 'N6_e2e_validation' == 'N4_implement_code'`).
- T3, a framework that cannot run halts: with no `web/node_modules`, the green phase and the red phase stop before either suite runs, name `vitest`, `node_modules` and the `web` directory, print an ERROR line, and route to `HALT`; an unreadable `package.json` at a load site routes to `HALT` instead of raising out of the node. On `main` the green and red cases returned no error, and the load site raised `ValueError`.
- A pytest-only target keeps the single-framework path (two cases): on `main` both failed with `KeyError: 'framework_configs'`.
- `test_a_hoisted_node_modules_above_web_is_enough` passed on `main` as well, because `main` ran pytest alone; on the fix it shows a workspace install at the root satisfies `web/`.
- Against `main`: 16 failed, 1 passed. On the fix: 17 passed.

## #4237: `tests/unit/test_ts_path_resolves_to_its_runner.py` (15)

- T1: `web/tests/replay.test.ts` beside `web/vitest.config.ts` resolves to Vitest in `web/` (on `main`, `[JEST]`), and the issue-only load site places it there; a `.spec.ts` beside a Playwright config is Playwright; a `jest` dependency makes a `.test.js` path Jest; a config outranks a dependency; a Python and a Vitest path together give both; two runners at the same strength halt; a glob names no file.
- T2: a `.test.ts` path on a target with no JavaScript runner halts at the load site, naming the path and the directories searched (`tests`, `.`), placing nothing, and routing to `HALT`; the resolver raises `FrameworkResolutionError`; an explicit runner the project has nowhere halts naming it and the directories searched; pytest is never refused.
- T3: an explicit `Test framework: jest` line still resolves to Jest first (passed on `main`, kept behaviour); an explicit Vitest line needs no path.
- `test_a_keyword_in_prose_adds_no_runner_beside_a_resolved_path` was added after the run against `main`, and was not run there. It calls `resolve_framework_dirs`, which `main` does not have.
- Against `main` (14 then): 13 failed, 1 passed. On the fix: 15 passed.

## #3001: `tests/unit/test_pytest_needs_a_declaration.py` (15)

- A Playwright project with a tooling `pyproject.toml` that lists pytest as a dev dependency detects as Playwright alone (on `main`, `[PLAYWRIGHT, PYTEST]`); with Vitest in `web/` and pytest only as a dependency, a silent LLD resolves to `[VITEST]` (on `main`, `[PYTEST, VITEST]`, so pytest was the one framework kept); a `pyproject.toml` mentioning pytest in a comment is nothing.
- Each declaration (`[tool.pytest` in `pyproject.toml`, `pytest.ini`, `[tool:pytest]` in `setup.cfg`, `[pytest]` in `tox.ini`, a root `conftest.py`) detects pytest; on `main` all but the `pyproject.toml` case failed.
- Python test files on disk detect pytest (five layouts), a Python suite beside a web suite is both, and a Python file inside `node_modules` is not a suite. These pin kept behaviour and passed on `main`, where the dependency line alone produced the same answer.
- Against `main`: 7 failed, 8 passed. On the fix: 15 passed.

## #3087: `tests/unit/test_full_suite_gate_every_framework.py` (8)

- A green Vitest run runs its whole suite (a runner call with no test paths) and returns `full_suite_validated: True`; so does a run with `skip_e2e`; a regression outside the targeted files routes to N4 with the failing output in the summary and one repair pass spent; a whole suite that collects nothing halts naming `vitest (web)`; an already validated suite is not run again.
- A pytest whole suite that collects nothing halts; on `main` it validated (`assert True is False`).
- A gate whose runner cannot start halts, for an `OSError` and a `ValueError`.
- Against `main`: 8 failed (most with `KeyError: 'full_suite_validated'`). On the fix: 8 passed.

## #3085: `tests/unit/test_non_pytest_zero_collected.py` (4)

- The first zero collected is a named repair task carrying the collection error, not a coverage gap; the second halts naming the error; at the iteration cap it is still a collection failure, where `main` reported `coverage 0.0% < target 90%`.
- `test_both_branches_call_the_one_guard` checks that both green branches call `_zero_collected_route` and neither counts strikes itself.
- Against `main`: 4 failed. On the fix: 4 passed.

## Existing tests changed

The first neighbour run on the fix gave 17 failed, 1885 passed, 1 skipped. Each failure and what it took:

- `tests/unit/test_js_project_in_subdirectory.py::TestDetection::test_the_root_keeps_its_old_order` wrote a `pyproject.toml` holding only the word `pytest`, the dependency-line evidence #3001 retires. Its fixture now writes `[tool.pytest.ini_options]`; what it pins, the order (Jest at the root, then pytest), is unchanged.
- `tests/unit/test_js_project_in_subdirectory.py::TestDetection::test_n0_puts_each_directory_on_its_config` asserted the retired behaviour: Jest, named and found nowhere, placed at the root. It now asserts Vitest in `web/` and pytest at the root, and that Jest raises `FrameworkResolutionError` naming the directories searched (#4237).
- `tests/unit/test_iteration_isolation.py::TestTheStagnantHaltNamesTheTests::test_the_message_carries_the_names` read the stagnation message from `_verify_green_pytest_single`'s source. The message moved, unchanged, into `_full_suite_gate`, and the test reads that function.
- `tests/unit/test_non_pytest_red_distinguishes.py` (5 failures) and `tests/unit/test_non_pytest_red_is_deterministic.py` (6 failures): their `_Runner` stand-in did not have the runner interface's new `require_dependencies`. Each stand-in gains an empty one; no assertion changed.
- `tests/unit/test_gate_registry.py` (4 failures): the registry did not know the new and moved halt sites. No test changed; the registry did (below).

## Neighbouring suites

Every test file that imports a changed module (`framework_detector`, `load_lld`, `verify_phases`, the runners), every file that imports the testing graph or the runner registry, every file that reads the gate registry, and `tests/unit/test_loud_failure_check.py` and `tests/unit/test_fail_open_audit.py`: 103 files plus the two, run in this worktree on the finished change.

```
poetry run pytest <the 105 files> -q -p no:cacheprovider
2047 passed, 1 skipped, 15 warnings in 1072.73s (0:17:52)
```

The one skip was not identified: the quiet run does not name it, and it is not `test_js_project_in_subdirectory.py`'s `npx` skip, which ran. The full unit tier was not run here; the parent session runs it.

## Audits, registry and lint

- `tools/audit_loud_failure.py --check`: PASS, 317 sites, all in the baseline. The change adds and removes none, so the baseline and `BASELINE_CEILING` are unchanged.
- `tools/audit_fail_open.py --check`: PASS, no new fail-open. Its first run flagged the two new halt helpers as substituting a value, because a returned call counts as halting only when its name says so; they were renamed `_halt_legs_cannot_run` and `_halt_full_suite_gate`. The denominator moved from 9754 to 9868 sites examined, so `tests/fixtures/fail_open_baseline.json` was rewritten with `--write-baseline` after `--check` passed: only `sites_examined` changed, and the 538 findings are the same. `--check --strict` then passes.
- `tools/audit_halt_sites.py --check --strict`: PASS, 157 halt sites, every one registered. `assemblyzero/core/gate_registry.py` changed as follows. The zero-collected halt moved into `_zero_collected_route`, so `impl.green.collection_broken` names that site, and the sites after it in `_verify_green_pytest_single` shifted down by one (`impl.green.iteration_cap` 2 and 5, `impl.deterministic_failure` 3, `impl.circuit_breaker` 4 and 6). The multi-framework guards joined `impl.no_test_files`. Three halt rows are new, each citing the ADR 0236 ruling in `created_by` as the earlier ADR 0236 rows do: `impl.framework_unresolved` (N0), `impl.framework_cannot_run` (the phases) and `impl.full_suite_cannot_run` (the gate). The impl halt-row ratchet in `tests/fixtures/gate_registry_baseline.json` rises from 37 to 40, written with `--write-baseline`; model-output halt rows stay at 1.
- `ruff check` on every changed and new file, compared rule by rule with the unchanged file: no new findings.
