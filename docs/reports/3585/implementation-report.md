# Implementation Report: the testing workflow's runners, templates and top-level modules under standard 0034 (#3585 step 5)

The rule is ADR 0236 and standard 0034. This branch, `3585-testing-runners`, is batch E of the testing workflow's sweep: the runners, the runner registry, the exit-code router, the framework detector, the coverage report, the audit helpers, the path and symbol validators, the knowledge patterns and the three documentation templates under `assemblyzero/workflows/testing/`. One commit per module, each site fixed and tested against ledger 0908. The other batches of the testing workflow are on their own branches. When the branches meet, each keeps its own sections of this file and its sibling.

## Modules

### runners/jest_runner.py (7 ledger rows: 6 fixed, 1 compliant and pinned)

- **A run nobody can read raises.** A run whose stdout carries no JSON report (110), or whose report does not parse (124), raises `RunnerError` after an ERROR line on stderr and in the log. The message names the framework, the project directory, the exit code and the head of both streams.
- **The fallback is gone (169).** It read zero failures and zero errors at exit 0, so a run nobody could read was judged as one where nothing failed. The only result the runner builds without a report is a failed typecheck's, now `_typecheck_failed_result`, which always carries one failure and one error.
- **package.json is read or refused (57, 58).** `_has_typecheck_script` decides whether a Vitest project declares a typecheck. No package.json declares none, quietly. One that cannot be read, does not parse, or is not an object with an object of scripts raises `RunnerError` naming the file, and no suite runs. The fail-open tag and its handler are deleted.
- **npx missing is loud (33).** The constructor prints an ERROR line naming the framework and the project directory, then raises the EnvironmentError every caller already turns into a halt.
- **Kept (72).** A typecheck that exits non-zero is the run's answer and comes back as a failing result.
- **New in `base_runner.py`** for every runner: `RunnerError`, `loud()` and `output_head()`.
- **Where the raise goes.** `nodes/verify_phases.py` calls `run_tests` in N3, N5 and the full-suite gate. None of them catches `RunnerError`, so it ends the run through `tools/run_implement_from_lld.py main`, which prints it at ERROR, alerts the operator and exits 1. Catching it beside `CoverageReportError` and returning it as `error_message` would end the run at HALT instead, with its saved state; that file belongs to another batch.

### runners/base_runner.py (4 ledger rows: 4 fixed)

- **A test command that did not run raises.** A timeout (129), a missing command (132) or another OS error (135) raises `RunnerError` naming the framework, the command, the working directory and the cause, after an ERROR line. They came back as exit code -1 with the cause where stderr would be, and the runners parsed that as a run, so a suite that never started read as one that failed.
- **No scenarios is not 0% (96).** `compute_scenario_coverage` with no scenarios raises ValueError after an ERROR line. It returned 0.0 with a WARNING, which the green phase read as a measured 0%.
- **Where the raises go.** Both reach `nodes/verify_phases.py`, which catches neither, so each ends the run through the entry point's handler, which alerts. Catching them in N5 and returning them as `error_message` would end the run at HALT instead.

### runners/pytest_runner.py (2 ledger rows: 2 fixed)

- **The exit code is read (45).** 0 and 1 are finished runs, read from the summary line. Any other code raises `RunnerError` after an ERROR line, naming the code, what pytest means by it (interrupted or stopped at collection, internal error, usage error, no tests collected) and the head of the output. Those runs used to come back as counts read off their output, mostly zero.
- **No coverage table is not 0% (57).** `coverage_percent` is None, not measured, when the output carries no TOTAL row, as the Jest runner reports it since #4246.
- **No caller swallows it.** Nothing in `assemblyzero/` or `tools/` calls `PytestRunner.run_tests`; the phases run pytest through `run_pytest`.

### runners/playwright_runner.py (2 ledger rows: 2 fixed)

- **A run nobody can read raises.** No JSON report (91), a report that does not parse (104), or a report whose suites are not the shape Playwright writes raises `RunnerError` after an ERROR line, naming the project, the exit code and the head of both streams.
- **The fallback is gone.** It read zero failures and zero errors at exit 0.
- **Where the raise goes.** As for the Jest runner: N3, N5 and the full-suite gate do not catch it, so the run ends through the entry point's handler, which alerts.

### runner_registry.py (1 ledger row: fixed)

- **An unknown framework raises (117).** `resolve_framework` raises `UnknownFrameworkError`, a ValueError, after an ERROR line, naming the value and the four frameworks. It returned None, the same answer as no framework, and `framework_ownership.run_frameworks` reads None on a one-framework run as pytest.
- **No framework named is still None, quietly.** No config, no `framework` key, or a key holding None is the pytest default every caller documents.
- **Where the raise goes.** `run_frameworks` does not catch it, and its four callers catch only `TestFileOwnershipError`, so the run ends through the entry point's handler, which alerts. Wrapping it in `TestFileOwnershipError` in `run_frameworks` would end it at HALT instead; that file belongs to another batch.
