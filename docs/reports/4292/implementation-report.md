# Implementation Report: a halt's files belong to one repository and one run (#4292)

A halt wrote its resume contract, state snapshot and recovery plan under names built from the workflow and the issue number alone, in one directory for the whole machine. Issue numbers are per repository, so issue #42 of one repository and issue #42 of another shared every file. A contract left by a halt on one was read by the next spec run on the other, a `--mock` run's halt was read by a real run on the same number, and every issue-type (brief) run shared issue 0. The rule is ADR 0236: a failure is loud, stops what depends on it, and alerts.

## The three keys, in one module

`assemblyzero/core/halt_paths.py` decides where a halt's files live, so the writers and the readers cannot disagree.

- The repository is named as the LLD approval cache already names it (`requirements.audit._repo_key`): the primary checkout's resolved path, found through git's common directory. A run in a worktree and a run in its primary checkout are one repository. The directory is `<name>-<12 hex of a hash of that path>`, the name cut to characters safe on Windows and Linux and 40 long, so two repositories called `app` do not collide.
- A mock run halts into a `mock` subdirectory of its repository's directory. The states spell mock three ways (`mock_mode`, `config_mock_mode`, `config.mock_mode`); `state_is_mock` reads all three.
- The run key is the issue number, or for a brief run `brief-<slug>-<10 hex of a hash of the brief file's resolved path>`.

A halt that names no repository, or neither an issue nor a brief, raises `UnkeyableRun`. The HALT node alerts first ("could not name its files") and re-raises, and writes nothing. It never falls back to the working directory, which is the AssemblyZero checkout when a workflow is launched with `--repo`, or to issue 0.

## What changed

- `state_persistence.save_state_snapshot` writes `<state dir>/<repository dir>[/mock]/<workflow>-<run key>.json`, all taken from the state. `load_state_snapshot` takes `repo_root` and `mock`.
- `RecoveryPlan` carries a `run_key`; its file is `recovery-<run key>-<workflow>.json` in the same directory as the snapshot.
- `halt_node` files the contract and the evidence bundle beside the snapshot, and names the bundle directory with the run key. The audit-directory copies are unchanged.
- `resume_contract`: the contract records `repository`, `mock` and `run_key` (contract version 2). `contract_path`, `save_resume_contract` and `load_resume_contract` take the directory, and `contract_directory(repo_root, mock)` gives a run's own. `check_and_consume` takes `repo_root` (required) and `mock`.
- `tools/run_implementation_spec_workflow.py` and `tools/run_implement_from_lld.py` pass `repo_root` and `mock` to `check_and_consume`. Those are the two callers.

## What happens to a contract written before this change

It has no repository field and sits in the shared directory under the old name. It is never rewritten or moved. `check_and_consume` looks for it only when the run's own directory has none, and attributes it from its `audit_dir`, which lies inside the repository's `docs/lineage`: the directory above that is the repository or one of its worktrees, and the repository key of either is the primary checkout.

- Attributed to this repository: verified and consumed as before. The resume of a real halt is not lost.
- Attributed to another repository: left where it is, one line names the other repository, and this run goes ahead as a fresh run.
- Not attributable (empty `audit_dir`, one outside `docs/lineage`, a repository git cannot read, or a root that is gone and is not this run's own path): the run is refused by name, with an alert naming the file and why. The operator moves the file aside to proceed.

A legacy contract carries no mock flag, so one a mock left before this change and whose repository is this one is still read as a halt of this repository. The operator's current files under `~/.assemblyzero/workflow_state` were read for their shape only.

## Readers and writers found

Writers: `halt_node.halt_with_plan` (snapshot, plan, contract, evidence bundle; also the contract and bundle copies in the audit directory), reached from the four graphs and from `tools/run_implement_from_lld.py` `halt_unfinished_run`, and from the resumed requirements graph in `tools/run_requirements_workflow.py`.

Readers: `resume_contract.check_and_consume` (two callers, above), `state_persistence.load_state_snapshot` (no caller), `assemblyzero/speedrun/factory_report.py` `read_halt_bundles` (finds `halt-evidence.json` with `rglob` under the state directory and attributes by the bundle's `audit_dir`, so the per-repository layout needs no change), and the orchestrator, which reads only the `recovery_plan_path` the HALT node returns. `tools/speedrun_reset.py`, `tools/speedrun_roll.py` and `assemblyzero/workflows/orchestrator/resume.py` do not name these files.

## Not changed, and why

- `RecoveryPlan.resume_command` for a brief run still reads `--issue 0`. It is a printed hint, not a file name, and is outside the three requirements.
- `factory_report` still counts a mock's halt bundle, as it always has: the bundle's `audit_dir` is inside the repository. Skipping the `mock` directory there is a separate change.
