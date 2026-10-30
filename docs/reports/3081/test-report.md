# Test Report: a Python suite and a Vitest suite are scaffolded, written, run and measured (#4244, #4243, #3081, #4245, #3065, #3067, #4246, #3089)

In progress. Each issue's section is written when its commit lands.

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
