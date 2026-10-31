# Implementation Report: a Python suite and a Vitest suite are scaffolded, written, run and measured (#4244, #4243, #3081, #4245, #3065, #3067, #4246, #3089)

The target is a repository with a pytest suite at its root and a Vitest suite in `web/`. After #4236 one run carried both frameworks and the red and green phases ran both, but N2 scaffolded the first framework alone and in the root's `tests/`, N2.5 judged the TypeScript scaffold as an empty string, N4 registered only Python tests, the JSON runners broke on any `npx` warning, a Jest test asserting nothing validated, Vitest and Jest always measured 0% and sent the shortfall to the coder, and the per-framework coverage targets governed nothing. The rule is ADR 0236 and standard 0034: a failure is loud, stops what depends on it, and alerts the operator. Every new failure path below returns an `error_message` that the testing graph routes to `HALT`, and `HALT` alerts (#3724). One commit per issue, in the order given: `7687211f` #4244, `d0ee4a06` #4243, `992a10ff` #3081, `2f69716c` #4245, `da402b53` #3065, `db2f089e` #3067, `d4b189cd` #4246, and the #3089 commit.

## #4244: N2 scaffolds every framework of the run

`scaffold_tests.py:1322-1332` (at `4ac9c81a`) read `framework_config`, the first framework, alone.

- `scaffold_tests` reads every framework of the run through `framework_ownership.run_frameworks`. With more than one, `_scaffold_every_framework` scaffolds each with its own scaffolder: the pytest scaffold through `_scaffold_python_tests`, the old body of `scaffold_tests` moved unchanged, and each JavaScript framework through `_scaffold_non_python_tests`.
- `generated_tests` stays the Python scaffold when pytest is one of the frameworks, because the pytest validator reads that key (#789).
- A framework whose scaffold cannot be built halts N2 through `_halt_scaffold_framework`, which names the framework and its directory (`vitest (web)`) and the cause, prints an ERROR line on stderr, and routes to HALT.
- A single-framework run takes the path it took before.
- The issue asks N2 to scaffold "the test files the LLD names". Neither scaffolder writes an LLD-named file: pytest's writes `tests/test_issue_<N>.py`, which N4, N4c and #2709 all key on, and the TypeScript one writes `issue_<N>.test.ts`. What changed is which frameworks get one, which is the defect the issue describes; the file names are as they were.

## #4243: a JavaScript scaffold is written in its framework's own directory

`scaffold_tests.py:1207-1214` wrote the Jest, Vitest or Playwright scaffold to `<root>/tests/` whatever the framework's `working_directory`.

- `scaffold_path_for` says where a framework's scaffold goes without touching the disk: pytest's is `tests/test_issue_<N>.py`, as before; a JavaScript framework's is `<its directory>/tests/issue_<N><ext>`, so Vitest in `web/` gets `web/tests/issue_<N>.test.ts`.
- `determine_test_file_path` asks the run's ownership rule who would run that path, among every framework of the run (`run_configs`, the state's `framework_configs`). A path no framework runs, a path another framework would run, or a `working_directory` outside the repository raises `ScaffoldPathError`, naming the path and the frameworks, before any directory is made. N2 halts on it through `_halt_scaffold_framework`, in a single-framework run as in a multi-framework one.
- "The test directory its config names" is not read. A Vitest, Jest or Playwright config is a JavaScript or TypeScript module, and the run does not evaluate one. The scaffold goes in `tests/` under the framework's directory, which each of the three runners' default test patterns collects; a project whose config narrows `include` or `testDir` elsewhere sends the red phase back to N2 with nothing collected, and the scaffold cap halts it.
- The ownership rule moved to `assemblyzero/workflows/testing/framework_ownership.py` (`run_frameworks`, `owner_of`), and `verify_phases._framework_legs` reads it from there, so N2 and the phases cannot disagree about who runs a file. Its messages are word for word what `_owner_of` printed.

## #3081: N2.5 validates the TypeScript scaffold N2 wrote

The issue's premise holds at `4ac9c81a`: `_scaffold_non_python_tests` returned `test_file_content`, which nothing in `assemblyzero/` or `tools/` reads, and `_validate_non_pytest` passed the runner the state's `generated_tests`, absent for every non-pytest scaffold, so each was "Empty test file" and regenerated to the cap.

- The scaffold returns `generated_tests`, and `test_file_content` is gone.
- The issue's stronger repair is taken too: `_non_pytest_errors` reads each test file from disk and hands the runner's validator what is there, so the content judged and the file the red phase runs are one thing. Only a single-framework state that lists no test file at all is judged on `generated_tests`, as `<generated>`, as it was.
- With several frameworks (#4244), N2.5 validates every scaffold: pytest's on `generated_tests` as before, and each other framework's files, assigned by `owner_of`, by that framework's validator. A non-pytest framework with no file is a validation error. The stagnation hash (#502) and the exhaustion check cover all of them, and the non-pytest path now stores the hash as the pytest path does.
- A validator that cannot be built (no `npx`), a test file that cannot be read, or a test file no framework owns halts through `_halt_validation_cannot_run`: an ERROR line on stderr, `is_valid` False, `error_message` routed to HALT by `route_after_validate`. The runner-unavailable branch used to return `is_valid: True` with a warning (ledger 0908, `validate_tests_mechanical.py:811`).

## #4245: N4 registers every test file it writes, by the ownership rule

`orchestrator.py:1166-1171` counted a written file as a test only when it was a Python `test_*` file under `tests/`, so `web/tests/replay.test.ts` never joined `test_files`.

- `framework_ownership.is_test_file` says which written files are tests: N4's Python rule unchanged, or a name ending in one of the four JavaScript test suffixes N0 resolves (`.test.ts`, `.test.js`, `.spec.ts`, `.spec.js`).
- `registered_test_files` gives each written test, and each file already in `test_files`, to the framework `owner_of` names, then merges each framework's files with `merge_test_files` and that framework's own scaffold: pytest's spec suite stays (#2709), and a stub scaffold, pytest's or a JavaScript framework's, is replaced by N4's tests for that framework as #460 intended. A framework N4 wrote no test for keeps its files. With one framework this is the one `merge_test_files` call it was.
- A written test file no framework owns, or that two own, halts N4 through `_halt_test_file_unowned`, naming the file, routed to HALT by `route_after_implement`.
- The red phase's resume registration (#2897, `_register_prior_attempt_files`) used the pytest merge for every leg, so a Vitest leg with the spec suite on disk had `tests/test_issue_<N>.py` added to its files and lost its own scaffold. It now calls `registered_test_files` too; a planned test file no framework owns halts the red phase through `_halt_legs_cannot_run`.

## #3065: the JSON runners parse stdout alone

The premise holds: `_run_subprocess` appended stderr to stdout, and both JSON runners decoded from the first `{` to the end of that string, so any `npx` warning after the report, or a brace in a log line before it, sent the run to `_fallback_result`.

- `_run_subprocess` returns `(stdout, stderr, exit_code)`. `PytestRunner`, which reads human output, joins them as before (`combined_output`); the Jest/Vitest and Playwright runners parse stdout alone and keep both streams in the result's `raw_output` for the reader. The Vitest typecheck step joins them for its own failure output.
- `first_json_object` finds the report: each `{` is matched to the `}` that closes it, reading JSON strings as strings, and an object is decoded only when it opens as JSON does and names the report's key (`numPassedTests` for Jest/Vitest, `suites` for Playwright). Text after the report, a brace in a log line, and a JSON log line that is not the report are all passed over.
- The issue proposed `raw_decode` at each `{`. That needs a handler that steps past each failed attempt, and the fail-open audit flags it: it is the fall-through shape ADR 0236 retires. The brace-matched search has no such handler. An object that carries the key and does not parse raises `ValueError`, which `parse_results` treats as it treated a `JSONDecodeError` before.
- What `_fallback_result` does with a run that has no report, an invented failing test, is the separately filed defect the issue points to; it is unchanged here.

## #3067: a Jest or Vitest test file must call `expect`

The premise holds: `JestRunner.validate_test_file`'s docstring lists an `expect()` check that the code never made.

- It now refuses a file with no `expect(` call: "No expect() assertions found in <file>". `expect` named in the import line is not a call. The check is per file, the repair the issue asks for; counting per test needs a TypeScript parse.
- The TypeScript scaffold's own placeholders were the same hole from the other side (ledger 0908, `scaffold_tests.py:457` and `:489`): `expect(true).toBe(true)` and `await expect(page).toBeTruthy()` pass with no implementation, so a fresh TypeScript scaffold could never fail its red phase. Each placeholder is now `expect(false).toBe(true);` under a `TDD RED` comment, failing until a real test replaces it, as the Python scaffold's `assert False, 'TDD RED: ...'` does. N2 says so in one line per scaffold. The ledger's "and ERROR" is not taken: a placeholder that fails is the red phase working, and an ERROR line on every TypeScript scaffold would be a false alarm.
- Scenario names are written as JSON string literals, which TypeScript reads: a description holding an apostrophe (`Replays a user's session`) or a newline used to end the literal and break the file.

## #4246: Vitest and Jest measure coverage, and a shortfall goes to N4c

Both halves of the premise hold, and the first is wider than the issue says: Jest ran without `--coverage` too, so every Jest run also read 0%.

- `JestRunner.run_tests(..., measure_coverage=True)`, which only the green phase passes, adds `--coverage.enabled=true --coverage.reporter=json-summary --coverage.reportsDirectory=coverage` for Vitest and `--coverage --coverageReporters=json-summary --coverageDirectory=coverage` for Jest, after removing any `coverage/coverage-summary.json` an earlier run left. The red phase and the full-suite gate pass nothing, and their argv is as it was.
- When every test of the run passed, `coverage_percent` is the report's `total.lines.pct`. No report, a report that does not parse, or one with no number there (istanbul writes `"Unknown"` when nothing was instrumented) raises `CoverageReportError` naming the report's path, and the green phase halts through `_halt_coverage_unreadable` ("COVERAGE MEASUREMENT FAILED", joining `impl.coverage_unreadable`). While tests fail, or when none ran, coverage decides nothing, `coverage_percent` is None, and the phase prints "not measured" rather than 0%. The JSON report's `coverageMap` is no longer read; the json-summary is the one source.
- `require_dependencies` for Vitest also requires `@vitest/coverage-v8` or `@vitest/coverage-istanbul` in `node_modules` in its directory or above (or a `.pnp.cjs`), so a run that cannot measure coverage halts at its first phase, naming the packages and the directories searched, instead of failing at green in a way the fallback would read as a failing test.
- A Jest, Vitest or Playwright coverage shortfall routes to `N4c_augment_tests` with `coverage_gap_framework` naming the framework; pytest's sets `"pytest"`. The key is declared in the state (#2018).
- The issue's premise that N4c can fill the gap does not hold: `augment_tests_for_coverage` reads pytest-cov's term-missing report and writes and vets pytest functions. So N4c halts on a gap in any other framework (`_halt_gap_not_augmentable`), naming the framework and saying it adds pytest tests only. That is the route #2327 set for pytest, applied to every framework: a test gap never goes to the coder. Filling a JavaScript gap is new work, not this issue's.
- N4c's edge back to N5 was unconditional, so its own "coverage not measured" halt was overwritten by the next measurement (ledger 0908, `graph.py:732` and `augment_tests.py:551`). It now goes through `route_after_augment`, which sends a recorded reason to HALT; the atlas lists HALT as N4c's successor.
- In a two-framework run N4c extends a Python test file: `coverage_target_file` chooses among `.py` files, because the first plan-owned test file may be a `.test.ts`.

## #3089: each framework is judged by its own coverage target

The premise holds: the registry declared `coverage_target` on all four configs as fractions, and nothing read it. The issue left two repairs open; this one governs, and resolves the unit deliberately.

- The field is `coverage_target_percent`, an integer percentage like every other target in the run: 95 for pytest, Jest and Vitest (ADR 0207), 100 for Playwright's scenario coverage. The fractional `coverage_target` key is gone from the registry and from `FrameworkConfig`, and the new name means a fraction left in a checkpoint from before can never be read as 0.95% and make a gate nothing fails.
- N0 writes the target on every framework config: the LLD's declared target (`declared_coverage_target`, new, which is `extract_coverage_target` with None for "not declared") on every framework when it declares one, the operator's `coverage_target` on the issue-only path, 90 on the mock path, and otherwise each framework's registry default.
- The green phase judges each framework by `_coverage_target(state, framework_config)`: its config's percentage, or the run's `coverage_target` for a config from a checkpoint written before this change, which is what judged every framework then. The pytest branch reads it for `--cov-fail-under`, for the shortfall branch and for the unreadable-coverage check; `_leg_state` gives each leg its own `framework_config`, so the pytest leg of a two-framework run reads pytest's.
- With nothing declared, every target is what it was, except Playwright's, which is 100 where the run's default was 95.

## Compliance with standard 0034

| Failure path | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| N2: a framework of the run cannot be scaffolded, or its scaffold would land where no framework runs it (`_halt_scaffold_framework`) | ERROR line on stderr | names the framework, its directory and the cause (`ScaffoldPathError` names the path and the frameworks) | `error_message`; `route_after_scaffold` to `HALT` | through `HALT` |
| N2.5: a scaffold's validator cannot be built, a test file cannot be read, or no framework owns one (`_halt_validation_cannot_run`) | ERROR line on stderr | names the framework and the cause, or the path | `is_valid` False, `error_message`; `route_after_validate` to `HALT` | through `HALT` |
| N4: a written test file no framework of the run owns (`_halt_test_file_unowned`) | ERROR line on stderr | names the file and the frameworks | `error_message`; `route_after_implement` to `HALT` | through `HALT` |
| N3: a prior attempt's planned test file no framework owns | ERROR line printed | names the file | `_halt_legs_cannot_run`; `HALT` | through `HALT` |
| N5: a Jest or Vitest run whose tests all pass has no readable coverage report (`_halt_coverage_unreadable`) | ERROR line on stderr | names the framework, the report path and the cause | `error_message`; `route_after_green` to `HALT` | through `HALT` |
| N3/N5: Vitest has no coverage provider installed | ERROR line printed | names the packages and the directories searched | the existing runner-unavailable and `_halt_legs_cannot_run` halts | through `HALT` |
| N4c: a coverage gap in a framework it cannot write tests for (`_halt_gap_not_augmentable`) | ERROR line on stderr | names the framework, its coverage and the target | `error_message`; `route_after_augment` to `HALT` | through `HALT` |
| N4c: coverage not measured (existing) | printed | `failure_message()` | now reaches `HALT` through `route_after_augment`; it was overwritten by N5 | through `HALT` |

No handler added by this branch falls through: the fail-open audit passes, and the loud-failure check reports 0 new sites.

## Ledger 0908 rows settled

- `validate_tests_mechanical.py:811`: the non-pytest runner cannot be built: halts (#3081).
- `scaffold_tests.py:457` and `:489`: the always-passing TypeScript placeholders fail until replaced (#3067). The rows' "and ERROR" is not taken: a failing placeholder is the red phase working, and an ERROR line on every TypeScript scaffold would be a false alarm.
- `graph.py:732` and `augment_tests.py:551`: N4c's error reaches `HALT` through a conditional edge (#4246). The loud-failure check now prints `FIXED but still in the baseline: assemblyzero.workflows.testing.graph::N4c_augment_tests::unrouted_error::1`; the baseline was left for the parent session to shrink.

## The gate registry

Every halt site names a row in `assemblyzero/core/gate_registry.py`. The GUARD and import-resolution halts moved with the pytest scaffold into `_scaffold_python_tests` (#4244), so `impl.no_test_files` and `impl.scaffold_import_unresolved` name that function. `_halt_coverage_unreadable` joins `impl.coverage_unreadable`, whose head it shares. Four halt rows are new, each citing the operator's ADR 0236 ruling in `created_by`, as the earlier ADR 0236 rows do: `impl.scaffold_framework_failed` (#4244, infrastructure), `impl.scaffold_validation_cannot_run` (#3081, infrastructure), `impl.test_file_unowned` (#4245, upstream) and `impl.coverage_gap_not_augmentable` (#4246, infrastructure). The impl halt-row ratchet in `tests/fixtures/gate_registry_baseline.json` rises from 40 to 44, one per commit that added a row, each written with `--write-baseline`; model-output halt rows stay at 1. The parent session should confirm that citing that ruling is acceptable for this rise, as for #4236's.

## New defects found, not changed here

- `assemblyzero/workflows/testing/nodes/scaffold_tests.py`, `_scaffold_python_tests` and `_scaffold_non_python_tests`: `Path(state.get("audit_dir", ""))` is `Path(".")` when the key is empty, and `.` exists, so audit copies (`NNN-test-scaffold.py`) are written into the process's working directory. A test run here wrote twelve into the worktree root before the tests were changed to use the audit directory N0 makes. Ledger rows `:1069` and `:1199` name the silent skip when the directory is missing; this is its other half.
- `assemblyzero/workflows/testing/nodes/load_lld.py`, the spec load site: `"coverage_target": coverage_target` writes the LLD's target over an operator `--coverage-target` the initial state already holds (`tools/run_implement_from_lld.py:1377-1378`), so the flag has no effect on the spec path; the issue-only path keeps it.
- `assemblyzero/workflows/testing/nodes/verify_phases.py`, the Playwright green branch: scenario coverage is `passed / total_scenarios`, and `total_scenarios` counts every scenario of the run, so in a run with Playwright and another framework its coverage can never reach its target.
- `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` fails with `GraphRecursionError` in this worktree. It fails identically with the base commit `4ac9c81a`'s version of every source file this branch changed, so it is not this branch's; it drives the orchestrator workflow with every stage stood in.

## A consequence to know before a real run

A green Vitest run now needs `@vitest/coverage-v8` or `@vitest/coverage-istanbul` installed in its directory or above, and the preflight halts at the red phase without one. A JavaScript coverage gap halts at N4c with its framework named, where it used to send the coder to close a gap that 0% made permanent; a target whose Vitest suite is under its coverage target therefore stops there until the tests are written, or the LLD declares a target the suite meets.
