# Test Report: a Python suite and a Vitest suite are scaffolded, written, run and measured (#4244, #4243, #3081, #4245, #3065, #3067, #4246, #3089)

Each new test file was written first and run with `-rA` in this worktree against the unchanged source, commit `4ac9c81a`, then against the fix. The fixtures are throwaway targets in `tmp_path`: a pytest suite at the root and a Vitest suite in `web/` with a `package.json` and `vitest.config.ts`. No real npm, npx, node or model is called: `base_runner.run_command` stands in for the subprocess layer (and, for a coverage run, writes the json-summary a real one would), `shutil.which` answers for `npx`, `run_pytest` stands in for pytest, and `generate_file_with_retry` for N4's model call.

Against the unchanged source, the eight files together: 56 failed, 13 passed. On the fix: 71 passed (two tests were added after the run against `4ac9c81a`, and one was renamed; each is named below).

## #4244: `tests/unit/test_scaffold_every_framework.py` (5)

- T1: a target with pytest at the root and Vitest in `web/` gets two scaffolds, `tests/test_issue_7.py` and a `.test.ts` importing from `vitest` (on `4ac9c81a`: one file, `assert 0 == 1`); `generated_tests` is the Python scaffold the pytest validator reads (passed there too: it was the only scaffold).
- T2: a pytest-only target writes the one scaffold as before (kept behaviour, passed there).
- T3: a TypeScript template that raises for the second framework, and a Vitest runner with no `npx`, each halt N2 naming `vitest (web)` and the cause, print an ERROR line on stderr, and route to HALT (on `4ac9c81a`: `assert 'vitest (web)' in ''`, nothing scaffolded for Vitest).
- Against the unchanged source: 3 failed, 2 passed. On the fix: 5 passed.

## #4243: `tests/unit/test_ts_scaffold_in_its_directory.py` (6)

- T1: in a two-framework run the Vitest scaffold is `web/tests/issue_7.test.ts`, and `verify_phases._framework_legs` gives it to the Vitest leg and `tests/test_issue_7.py` to pytest; a single-framework Vitest config with `working_directory: web` gets `web/tests/`; a JavaScript framework at the root and pytest keep the root's `tests/` (two kept behaviours).
- T2: a scaffold for Vitest in `web/` in a run whose frameworks are pytest at the root and Vitest in `app/` raises `ScaffoldPathError` naming `issue_7.test.ts`, `pytest` and `vitest (app)`; a `working_directory` of `../elsewhere` raises naming "outside the repository".
- Against the unchanged source: 4 failed (`assert [] == [...web/tests/issue_7.test.ts]`, the root's `tests/` path, and `ImportError: cannot import name 'ScaffoldPathError'` twice), 2 passed. On the fix: 6 passed.

## #3081: `tests/unit/test_ts_scaffold_is_validated.py` (7)

- The Vitest scaffold returns `generated_tests`, equal to the file it wrote, and no `test_file_content` (on `4ac9c81a`: `KeyError: 'generated_tests'`).
- End to end, N2 then N2.5 on a Vitest target: no errors, `is_valid` True, route `continue`, `route_after_validate` gives `N3_verify_red` (on `4ac9c81a`: `Empty test file: .../tests/issue_7.test.ts`).
- A good file on disk with an empty state key validates; a bad file on disk with a good state key is refused with "No test structure" (on `4ac9c81a` each was judged on the state key, so both came out the other way).
- A test file that cannot be read halts naming the path and "cannot be read", routed to HALT; a runner that cannot be built (no `npx`) halts naming `vitest` and `npx`, prints an ERROR line on stderr, and routes to HALT (on `4ac9c81a`: `is_valid` True for both).
- With two frameworks, a TypeScript scaffold with no test in it is refused beside a good Python one (on `4ac9c81a`: valid, since the Python scaffold alone was checked).
- `test_a_test_file_that_cannot_be_read_halts_naming_it` was written as "...is a validation error naming it" and run that way against `4ac9c81a`, where it failed; the fail-open audit then refused the handler that recorded an error and stepped past the file, so an unreadable file halts instead, and the test asserts the halt.
- Against the unchanged source: 7 failed. On the fix: 7 passed.

## #4245: `tests/unit/test_n4_registers_every_framework.py` (5)

These drive `implement_code` itself, with `generate_file_with_retry` stood in for.

- T1: N4 writing `web/src/replay.ts` and `web/tests/replay.test.ts` on the two-framework target registers `web/tests/replay.test.ts`; the Vitest stub scaffold is removed from the list and from disk, and `tests/test_issue_7.py` stays (on `4ac9c81a`: the TypeScript test was not in `test_files`).
- T2: a Python test is registered as before, the stub scaffold replaced by it (kept behaviour, passed there).
- T3: `tests/stray.test.ts`, outside every framework's directory, halts N4 naming it with "belongs to no framework", prints an ERROR line on stderr, and routes to HALT (on `4ac9c81a`: no error).
- The red phase's prior-attempt registration for the Vitest leg gives `[web/tests/replay.test.ts]` alone (on `4ac9c81a`: `tests/test_issue_7.py` came first).
- Against the unchanged source: 4 failed, 1 passed. On the fix: 5 passed.

## #3065: `tests/unit/test_json_runner_reads_stdout.py` (9)

`base_runner.run_command` is stood in for with a `CompletedProcess` carrying separate stdout and stderr.

- `_run_subprocess` returns the streams apart (on `4ac9c81a`: one joined string and the code).
- A Jest report and a Vitest report with an `npm WARN` line on stderr parse to 3 passed, 1 failed, 4 total, and the warning is still in `raw_output`; a Playwright report likewise parses to 2 passed, 1 failed (on `4ac9c81a`: the fallback's `(0, 1, 1)` and `(0, 1)`).
- A `{rootDir: web}` log line ahead of the report, and a JSON log line that is not the report, are passed over (on `4ac9c81a`: the fallback).
- pytest still reads both streams (kept behaviour, passed there).
- Two tests were added after the run against `4ac9c81a`, with the brace-matched search: an object that carries the key and does not parse raises naming the key, and a brace inside a JSON string does not end the object.
- Against the unchanged source (7 then): 6 failed, 1 passed. On the fix: 9 passed.

## #3067: `tests/unit/test_jest_validator_needs_expect.py` (14)

Each runner test runs for Jest and for Vitest.

- A test that asserts nothing is refused with exactly "No expect() assertions found in tests/collector.test.ts", and so is one that imports `expect` and never calls it (on `4ac9c81a`: `[]`); a test that asserts is accepted (kept behaviour).
- The Jest/Vitest placeholder and the Playwright placeholder contain `expect(false).toBe(true)` and `TDD RED`, and neither of the old always-passing lines (on `4ac9c81a`: `expect(true).toBe(true)` and `toBeTruthy()`).
- A scenario description with an apostrophe and a newline is written as one valid string literal, for all three frameworks (on `4ac9c81a`: `it('Replays a user's session` and a raw newline).
- The scaffold passes its own framework's validator (kept behaviour; on `4ac9c81a` the old placeholder passed it too).
- Against the unchanged source: 10 failed, 4 passed. On the fix: 14 passed.

## #4246: `tests/unit/test_vitest_measures_coverage.py` (15)

`base_runner.run_command` stands in for `npx` and, for a coverage run, writes the json-summary a real one would, in the directory the run was started in.

- T1: the Vitest argv starts `npx vitest run --reporter=json` and carries `--coverage.enabled=true` and `--coverage.reporter=json-summary`, and a stand-in report of 85% is read as 85.0; Jest carries `--coverage` and `--coverageReporters=json-summary` and reads 72.5; a run not asked to measure has the old argv exactly and `coverage_percent` None (on `4ac9c81a` all three failed: `run_tests` took no `measure_coverage`).
- T2: no report, and a report whose percentage is `"Unknown"`, each raise `CoverageReportError` naming `web/coverage/coverage-summary.json`; a stale report from an earlier run is removed and never read; the green phase halts with "COVERAGE MEASUREMENT FAILED" and the path, prints an ERROR line on stderr, and routes to HALT; a failing run needs no report and still routes to N4 (kept behaviour, passed there).
- The Vitest preflight requires a coverage provider, naming `@vitest/coverage-v8` and `web/` (on `4ac9c81a`: no error); either provider is enough (passed there: nothing was required).
- T3: a Vitest shortfall (50% against 90%) routes to `N4c_augment_tests` with `coverage_gap_framework` `vitest` and the iteration counted (on `4ac9c81a`: `N4_implement_code`); N4c given a Vitest gap halts naming `vitest` and `pytest`, prints an ERROR line, and `route_after_augment` gives HALT; the built graph has no plain N4c to N5 edge and routes N4c through its router; in a two-framework run N4c extends the `.py` file, not the `.test.ts` (on `4ac9c81a`: the `.test.ts`).
- Against the unchanged source: 12 failed, 3 passed. On the fix: 15 passed.

## #3089: `tests/unit/test_per_framework_coverage_target.py` (10)

- The registry declares `coverage_target_percent` as an integer, 95, 95, 95 and 100, and no `coverage_target` key (on `4ac9c81a`: `KeyError: 'coverage_target_percent'`).
- The spec load site with "Coverage target: 85%" writes 85 on pytest and Vitest; with no declaration, 95 and 95; the mock load site writes 90 on both (on `4ac9c81a`: None on each).
- A Vitest leg whose config says 80, in a run whose `coverage_target` is 95, passes at 85% and goes to E2E (on `4ac9c81a`: judged against 95, a shortfall).
- `_coverage_target` reads the config, falls back to the run's target for a config without one, and never reads the old fraction; each leg's state carries its own `framework_config`.
- Against the unchanged source: 10 failed. On the fix: 10 passed.

## A test change after the runs against `4ac9c81a`

Four tests that drive N2 first passed `"audit_dir": ""`. N2 reads that as `Path("")`, the working directory, which exists, so the runs against `4ac9c81a` wrote twelve audit copies (`001-test-scaffold.py` to `012-test-scaffold.test.ts`) into the worktree root. They were deleted, each by name, and the tests now use the audit directory N0's mock load site makes under the target. Their results were the same. The defect is listed in the implementation report.

## Existing tests changed

- `tests/unit/test_framework_integration.py` (#3081): `test_runner_unavailable_skips_validation`, which asserted the retired pass-with-a-warning, is `test_runner_unavailable_halts_validation` and asserts the halt; `test_playwright_uses_runner_validation` and `test_jest_validation_errors_propagated` write their test file under `tmp_path`, because the validator reads the file, and assert what it was given.
- `tests/unit/test_green_loop_contract.py::TestTheScaffoldIsTheContract::test_implement_code_routes_through_the_helper` (#4245): reads `merge_test_files(` through `registered_test_files`, which `implement_code` now calls.
- `tests/unit/test_jest_runner.py`, `test_playwright_runner.py`, `test_pytest_runner.py`, `test_vitest_typecheck.py` and `test_target_env_tests.py` (#3065): their `_run_subprocess` stand-ins return `(stdout, stderr, exit_code)`; no assertion changed.
- `tests/unit/test_jest_runner.py::TestJestRunnerParse::test_parse_with_coverage_map` (#4246): the report's `coverageMap` is no longer a coverage source, so it asserts `coverage_percent` is None.
- `tests/unit/test_full_suite_gate_every_framework.py` (#4246): its runner stand-in accepts the green run's `measure_coverage` keyword.
- `tests/unit/test_two_frameworks_one_run.py` (#4246): the fixture installs `@vitest/coverage-v8` beside the Vitest binary (and at the root in the hoisted case), the stand-in writes a 100% json-summary for a coverage run, and the JSON report no longer carries a `coverageMap`.
- `tests/unit/test_testing_graph_halts_through_halt.py::TestTheGraphReachesHalt::test_halt_has_inbound_edges_now` (#4246): `N4c_augment_tests` joins the nodes with an edge to `HALT`.
- `tests/unit/test_runner_registry.py` (#3089): asserts `coverage_target_percent` 100 and 95, and the copy test uses it.

## Neighbouring suites

Each commit was tested on its own tree: edits that belonged to later commits were copied to `data/` and HEAD's versions put back while it ran, then copied back and confirmed with `cmp`. Per commit, the issue's new file and every test file that imports the modules it changed: #4244, 23 files, 613 passed; #3081, 35 files, 771 passed; #4245, 27 files, 583 passed; #3065, 23 files, 191 passed with the 32 failures all in the three new files whose fixes had not landed; #3067, its file and 6 neighbours, 81 passed, then 25 more, 629 passed; #4246, 96 files, 1568 passed, with the 10 not-yet-fixed #3089 tests and the pre-existing failure below. #4243's run was stopped at the first failure by `-x`, which was `test_gate_registry` reading halt helpers of later issues that were on disk at the time; the remaining 64 files were run, and every failure there was in a new test file or traced to those later edits.

On the finished branch: every test file that imports a module the branch changed (`verify_phases`, `scaffold_tests`, `validate_tests_mechanical`, the implementation orchestrator, `framework_detector`, `framework_ownership`, the runners and their registry, `augment_tests`, `load_lld`, the testing graph, atlas and state, the gate registry), plus `tests/unit/test_loud_failure_check.py` and `tests/unit/test_fail_open_audit.py`: 152 files.

```
poetry run pytest <the 152 files> -q -p no:cacheprovider -rs
2 failed, 2844 passed, 1 skipped, 20 warnings in 603.68s (0:10:03)
```

- The two failures are the stale-baseline reports for sites this branch fixed: `test_loud_failure_check.py::test_no_fixed_site_left_in_the_baseline` names `assemblyzero.workflows.testing.graph::N4c_augment_tests::unrouted_error::1`, and `test_fail_open_audit.py::TestTheRepoGate::test_the_baseline_is_not_stale` names `validate_tests_mechanical.py::_validate_non_pytest::except_handler::0`. Both baselines were left for the parent session.
- The skip is `test_verify_phases_lint_and_mock_target.py:54`: "ruff is not installed in this environment".
- `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` is not in the 152: it imports the orchestrator workflow, not these modules, and reaches them only through the testing package's import of its graph; the #4246 list caught it by the word "runners". It fails with `GraphRecursionError` here, and fails identically with `4ac9c81a`'s version of every source file the branch changed: pre-existing.

The full unit tier was not run here; the parent session runs it.

## Audits, registry and lint

- `tools/audit_loud_failure.py --check`: 0 new; 1 stale, the N4c edge above (`FAIL -- 0 new, 1 stale`). The baseline and `BASELINE_CEILING` are unchanged.
- `tools/audit_fail_open.py --check`: PASS, no new fail-open, before every commit. `--check --strict` reports the denominator moved: `files_scanned` 313 to 314, `sites_examined` 9868 to 9966, `findings_total` 538 to 537. `tests/fixtures/fail_open_baseline.json` was left for the parent session to regenerate with `--write-baseline`. Twice the audit refused a shape before it was committed: the validator's handlers that recorded an error and stepped past a file, and the JSON search's `raw_decode` retry; both were reshaped so no handler falls through.
- `tools/audit_halt_sites.py --check --strict`: PASS, 180 files, 162 halt sites, every one registered, 107 gates, halt rows impl 44. The registry rows and the ratchet are in the implementation report.
- `ruff check` on every changed file, compared rule by rule with HEAD's version before each commit: no new findings, and four fewer, all in code this branch rewrote or removed: a `SIM114` in `scaffold_tests.py`, a `UP024` in `validate_tests_mechanical.py`, and a `PERF102` and a `RUF019` in `jest_runner.py`'s removed `coverageMap` reader. Every new test file passes.
