# Implementation report: #4490

## The defect, and the part the issue did not know

`run_pytest` inherited the workflow's `VIRTUAL_ENV`, so a run's pytest tested in AssemblyZero's virtualenv, which is what #4490 reported. Building the fix found that stripping it is not enough. `poetry run pytest` looks the command up on `PATH` with the target's environment in front, so an environment with no pytest runs the next one along. Measured on 2026-11-01: a target that declares no pytest ran the pytest in another project's virtualenv and exited 0.

So R1 needed a question put to the target as well as an environment shed.

## `assemblyzero/workflows/target_env.py` (new)

`require_pytest(repo_root, coverage=...)` runs before a run starts and refuses, by name:

- a target with no project of its own, either no `pyproject.toml` or one that only configures tools (R3);
- a project poetry names no environment for, which was never installed. Poetry exits 1 and prints nothing, so the message supplies the words;
- an environment with no pytest;
- an environment with no pytest-cov, when the run measures coverage (R2).

Poetry names the environment, asked with the workflow's virtualenv shed, because asked under it poetry names AssemblyZero's. The target's interpreter then answers `find_spec` for itself. This process is never consulted, so its own `pytest_cov` cannot satisfy the check.

`hook_environment` moved here from `mechanical_hooks.py`, because a runner cannot import from the nodes package. `declares_project` moved too, so provisioning and the gate share one definition of a project.

## The three places a run starts pytest (R1)

- `run_pytest` in `verify_phases.py` calls `require_pytest` first, and `_pytest_env` starts from `hook_environment`. The import of `pytest_cov` in the workflow's process is gone.
- `run_e2e_tests` in `e2e_validation.py` does the same, raising `E2ERunFailed`.
- `BaseTestRunner._run_subprocess` passes `hook_environment()`, and `PytestRunner.require_dependencies` calls `require_pytest`.

A test pins that these are the only three.

## R3's decision

The outcome is the halt. A `pyproject.toml` that only configures tools declares nothing to install, so there is no environment to name. Poetry is not asked: with no project in the directory it walks up and answers for a parent's, which was measured reaching AssemblyZero's own project from a directory inside it.

## What every Python target now needs

Both `pytest` and `pytest-cov` declared. `tools/new_repo.py` already scaffolds both. `docs/runbooks/0933-workflow-readiness-audit.md` now says so, and no longer tells an auditor to trust `poetry run pytest --version`, which succeeds with no pytest installed.

## The rehearsal

`_pytest_in_the_target`, the workaround, is gone. `provision` now goes through `run_pytest` under this process's virtualenv, and the fixture has an optional `coverage` group so one target proves both the refusal and the measurement. `docs/runbooks/0959-two-framework-rehearsal.md` says what a pass now proves.

## Left open

- #4495: the spec's import check in `validate_completeness.py` still asks poetry under the workflow's virtualenv, so it answers from AssemblyZero's.
- #4496: the pytest-cov halt comes at N5, after the implementation is paid for.

## Left behind

The rehearsals' `target` and `origin.git` trees under `data/scratch-2026-11-01-4490-env/` in the primary checkout, in a gitignored folder. They stay because scratch goes file by file and a tree cannot be removed by rule, as with #4438's, and they are listed on #4490.
