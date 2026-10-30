# Implementation Report: a run installs its worktree's environment before any node runs (#4238)

A run worked in a worktree that had none of the target's dependencies. Poetry keys its environments to the checkout path, so a new worktree has no environment of its own, and `node_modules` is never committed. On a target with a Python package at its root and a Vitest suite in `web/`, the tests ran against whatever environment happened to resolve. The rule is ADR 0236: a failed install is loud, stops the run before its graph is built, and alerts.

## The premise, checked against the code

The issue is right on both entry points:

- `tools/run_implement_from_lld.py` cut its worktree in `create_worktree` and installed nothing on any path.
- `run_impl_stage` in `assemblyzero/workflows/orchestrator/stages.py` ran `poetry install` and never `npm ci`. Nothing in AssemblyZero ran `npm ci` for a run.

Reading the orchestrator's install found three more defects in the same block:

- It inherited the workflow's environment. The workflow runs under `poetry run`, and with `VIRTUAL_ENV` set, `poetry install` in the target's worktree installs the target's dependencies into AssemblyZero's own virtualenv. #3705 fixed the same leak for `post_implement_command`.
- It ran only when the stage cut the worktree. A failed install was not marked non-transient, so the stage was retried unless the run was `--fail-fast`. The retry found the worktree on disk, skipped the install, and ran the sub-workflow on the unprovisioned tree. A resume did the same.
- It ran a real `poetry install` in a `--mock` rehearsal.

## The step: `assemblyzero/workflows/provisioning.py`

Both entry points now call one function, `provision_worktree(worktree, mock=..., run=...)`.

- `poetry install` runs in the worktree's root, and in every directory `detect_framework_dirs` places a suite in, where a `pyproject.toml` declares a project (a `[project]` or `[tool.poetry]` table). The #1994 retry with `--no-root` moved here unchanged. A `pyproject.toml` that only configures tools declares nothing to install, so `poetry install` is not run on it; `poetry install` refuses such a file, and refusing would halt a JavaScript target that keeps one for its tooling.
- `npm ci` runs in every directory that holds a `package-lock.json` or `npm-shrinkwrap.json` and is, or is under, the directory of a detected JavaScript suite. `npm_install_dirs(worktree, suite_dirs)` reads this from the files on disk, to the detector's own depth and skipping its skipped directories. It takes the suites' directories as an argument, so a detector that finds more suites can hand them over.
- A JavaScript suite's directory with no lock file, or a `package.json` in or under one with no lock beside it, stops the run. `npm ci` needs the lock, and without one the suite's tests would run against whatever `node_modules` resolves.
- Every install runs with `hook_environment()`: `VIRTUAL_ENV`, `POETRY_ACTIVE` and the workflow's virtualenv `bin` directory are removed, so poetry resolves the worktree's own environment.
- On Windows the executable is resolved through `shutil.which`, since `npm` is `npm.cmd` there and `CreateProcess` does not apply `PATHEXT`.
- Each install has 30 minutes (`INSTALL_TIMEOUT_SECONDS`), since a first install builds the environment from nothing; the orchestrator's install had `run_command`'s default of 300 seconds. An install that runs past it is a failure that carries its output so far.
- Nothing to install is an answer, in one line: `[ENV] nothing to install in <worktree>: ...`.

## What a mock run does

A `--mock` run makes the same plan and runs none of it. It prints one line per planned install, saying it was planned and not run, so it stays offline and fast. A plan that cannot be made (an unreadable `pyproject.toml`, a JavaScript suite with no lock file) stops the mock run as it would stop a real one. That is what the step 6 rehearsal of #3585 exercises.

## The standalone runner

`main()` provisions the tree the run works in once the worktree is cut or found and the run record is open, before the context files, the profile and the graph. That tree is the worktree it cut, the one it found for the issue, or, for a mock or scaffold-only run started inside the issue's worktree, that worktree. A `--no-worktree` run works in place in the operator's own checkout and environment; it installs nothing and says so in one line.

## The orchestrator

`run_impl_stage` calls `_provision_impl_worktree` after the creation block, so a worktree found on disk is installed as well as one just cut, and before the testing graph is built. A failure returns a failed stage through `_provisioning_failed`, wrapped in `update_stage_result` as #1993 requires, and marked `transient=False`: the same install against the same lock fails the same way, so the run halts the first time.

## Compliance with standard 0034

The change adds two failure paths and touches one.

| Failure path | Loud | Logged with details | Stops | Alerts |
|---|---|---|---|---|
| Standalone: `ProvisioningError` in `main()` | `[implement] ERROR:` on stderr | `alert_operator` with what, where (`main, worktree provisioning`), repo, issue, the error as cause (command, directory, exit code, output) and the consequence | exits 1 before the graph is built; the run record finishes `fail` | `alert_operator` |
| Orchestrator: `ProvisioningError` in `run_impl_stage` | `[ENV] ERROR:` on stderr | the stage's `error_message` carries the command, directory, exit code and output; the HALT node records it | stage `failed`, non-transient, routed to `terminal`; the sub-workflow is never invoked | the orchestrator's HALT node |
| Inside the step: a command that exits non-zero, cannot start, or does not finish; an unreadable `pyproject.toml` or project file; a test directory outside the worktree; a JavaScript suite with no lock | carried by the two callers above | `ProvisioningError` names the directory, the command and the output tail | raises; no later install runs | through the callers |

No `# fail-open:` tag is added. `tools/audit_loud_failure.py --check` and `tools/audit_fail_open.py --check` pass with no new site, and the two baselines and `BASELINE_CEILING` are unchanged.

## Not changed

- `assemblyzero/workflows/testing/` is untouched. The step imports `detect_framework_dirs`, `MAX_DETECT_DEPTH` and `SKIPPED_DIRS` from `framework_detector`, and `hook_environment` from `nodes/mechanical_hooks.py`. `hook_environment` would belong in a shared module; moving it means editing the testing package.
- A directory under a suite that is a member of an npm workspace has no lock of its own; the workspace root's lock covers it. The step stops on it, as the rule says. If workspace targets appear, coverage by a root lock whose `package.json` declares `workspaces` is the change to make.
