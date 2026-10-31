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

### exit_code_router.py (4 ledger rows: 4 fixed)

- **The unused router is deleted (47, 60, 68, 71).** `route_by_exit_code` sent a red phase that passed, an interrupted or broken pytest, a timeout and an unknown code to a plain end, never to HALT. Nothing called it: the routing that runs is inline in `nodes/verify_phases.py` on the same constants (see #2690). The ledger allowed routing to HALT or deletion; deletion leaves no second copy with silent ends to wire in, and changes no route.
- **What verify_phases reads stays.** The constants, `describe_exit_code` and `describe_run_outcome` are unchanged.

### framework_detector.py (3 ledger rows: 3 fixed)

- **Two raises are now loud.** An unreadable package.json (215) and a `test_dirs` declaration naming no framework (252) raised with nothing said where they failed. Each now prints an ERROR line first. The path resolver's read of the same package.json, added by #4237 after the ledger's base, does the same.
- **A missing project is not pytest (273).** `detect_framework_dirs` with a project root that is empty or not a directory raises `FrameworkResolutionError` naming it, after an ERROR line. It returned no frameworks, which the callers read as pytest at the root. A project that exists and declares nothing is still the quiet empty answer.
- **Where the raises go.** N0 catches ValueError on all three paths and halts, and HALT alerts; provisioning turns ValueError into `ProvisioningError` naming the worktree.

### coverage_report.py (2 ledger rows: both compliant, pinned)

- **Unchanged, by design.** No TOTAL row (137) and a table that leaves out the target (143) are each a reading in the state ABSENT, with no percentage and a message naming what was sought and what the report held. That is the module's contract (#2637). N5 stops on it, and N4c returns it as an error that its router sends to HALT. The new tests pin the contract.

### audit.py, the testing workflow's (3 ledger rows: 2 fixed, 1 left for the verify_phases batch)

- **A missing audit directory raises (121).** `next_file_number` raises FileNotFoundError naming it, after an ERROR line. It answered 1, as if the directory were empty. Every caller checks or creates the directory first.
- **A lost audit event raises (280).** `log_workflow_execution` raises `WorkflowAuditError` naming the workflow, the event, the issue, the log and the cause, after an ERROR line, when the log's directory cannot be made or the line cannot be appended. It logged a WARNING and went on. The run ends through its entry point's handler, which alerts.
- **No coverage table still reads 0.0 (320).** `nodes/verify_phases.py`, another batch's file, compares and records the value as a number, so None would raise there. The fix needs that file first; a strict xfail records the open site. N5 already catches the absence with `coverage_report.read_coverage` before it decides a route.

### path_validator.py (3 ledger rows: 2 fixed, 1 compliant and pinned)

- **Every failed context file is said (164, 177).** A rejection, or a read that fails, is an ERROR line naming the file and the cause. The read handler names OSError and UnicodeDecodeError where it caught every exception.
- **No partial context.** When any file fails, no content comes back, only the errors. The one caller, `tools/run_implement_from_lld.py`, already refuses to start on any error, and its handler alerts.
- **Kept (65).** A file that cannot be statted is a rejection with its reason.

### symbol_validator.py (3 ledger rows: 3 fixed)

- **A check that cannot run raises.** A module of the target's own that cannot be read or parsed (71, 152), and a test source that does not parse (137), raise `SymbolCheckError`, a ValueError, naming the file and the cause after an ERROR line. They returned None or an empty list, the same answer as "every import resolves".
- **Not the repository's own is still quiet.** An import from the standard library or a third-party package is not this check's to make.
- **Where the raise goes.** N4c (`nodes/augment_tests.py`) does not catch it, so the run ends through the entry point's handler, which alerts. Catching it at N4c's two calls and returning it as `error_message` would end the run at HALT instead.
