# Test Report: a run installs its worktree's environment before any node runs (#4238)

No test runs a real `poetry install` or `npm ci`. The tests stand in the subprocess layer for those two tools only and record each call's argv, working directory and environment; every git command runs for real against a throwaway repository with a bare origin. Each new test was run against HEAD's unchanged `stages.py` and `run_implement_from_lld.py`, with the new module absent (copied aside, run, copied back, confirmed with `cmp`), and then against this branch.

## `tests/unit/test_impl_worktree_provisioned.py` (21)

- T1 (R1), through `main()` on a target with a `pyproject.toml` at the root and `web/package.json` with its lock: the installs are `poetry install` in the worktree's root and `npm ci` in its `web/`, in that order, after the worktree is cut and before the graph is built. A second T1 test sets `VIRTUAL_ENV`, `POETRY_ACTIVE` and a virtualenv `bin` on `PATH`, and every install runs without them.
- T2 (R2), parametrized on a failing `poetry install` and a failing `npm ci`: exit 1, the graph never built, nothing landed, one alert whose cause names the command, the directory and the output, an ERROR line on stderr, and no install after the failed one. A JavaScript suite with no lock file stops the run the same way, mock or real.
- R4: a mock run names each planned install and runs none; a target with nothing to install says so in one line.
- T3 (R3), through `run_impl_stage` with a real `git worktree add`: both installs, before the testing graph is built; a reused worktree (a resume) is installed too; a failed `npm ci` fails the stage non-transient, never invokes the sub-workflow, routes to `terminal`, and the orchestrator's HALT node alerts with the command, the directory and the output; a mock rehearsal installs nothing; the installs run outside the workflow's virtualenv.
- `npm_install_dirs` (the parent session's rule): `npm ci` in every locked directory in or under a suite (`sentinel/`, `web/`, `web/admin/`), never in `node_modules/` or a `dashboard/` with no suite; a `package.json` with no lock under a suite stops the run; the plan for a Vitest suite in `sentinel/` beside a suite-less `dashboard/` installs `sentinel/` only; a lock with no JavaScript suite is not installed.
- The step: a tooling-only `pyproject.toml` is nothing to install; one that is not TOML stops the run; a command that cannot start and one that runs past its timeout are failures naming themselves; on Windows `npm` resolves through `shutil.which`.
- Against HEAD: 21 failed. The 12 tests through `main()` and `run_impl_stage` failed on their assertions: nothing installed (T1; T2 exited 0 and landed; the mock lines absent), only `poetry install` and no `npm ci` (T3), nothing installed on the reused worktree, the failed `npm ci` stage reported `passed`, the mock rehearsal ran `poetry install`, and the orchestrator's install inherited the environment (`env=None`). The 9 step and `npm_install_dirs` tests failed on the missing `assemblyzero.workflows.provisioning`. On this branch: 21 passed.

## Changed existing tests: `tests/unit/test_impl_stage_provisioning.py` (10)

- `TestNoRootFallback` (5): the #1994 rule moved from `stages._provision_worktree_env`, which is gone, to `provisioning.provision_worktree`. Each test keeps its case and now drives the shared step with a stand-in runner; a failed install is now a raised `ProvisioningError` naming the command, rather than a returned exit code.
- `TestFailureKeepsTheState` (4): the failing install comes from the `run_command` stand-in instead of a replaced `_provision_worktree_env`. Its comment no longer says a worktree found on disk skips the install.
- On this branch: 10 passed.

## AssemblyZero's own plan

`plan_provisioning` on this worktree, planning only: `poetry install` at the root and `npm ci` in `sentinel/`. `dashboard/` has a package and its lock but no test runner, so it is not installed.

## Neighbouring suites

Every test file under `tests/` that imports `orchestrator.stages`, `orchestrator.graph`, `tools/run_implement_from_lld.py` or the new module (65 files: 64 unit, 1 integration): 908 passed, 5 skipped, 1 failed. The failure, `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success`, replaces every stage runner with a stand-in and ends in `GraphRecursionError`; it fails identically with HEAD's sources.

`tools/audit_loud_failure.py --check`: PASS, 317 sites, all in the baseline. `tools/audit_fail_open.py --check`: PASS, no new fail-open. `ruff check` finds nothing in the new module or the two test files, and the same findings in `stages.py` and `run_implement_from_lld.py` as at HEAD.

The full unit tier runs in the parent session.
