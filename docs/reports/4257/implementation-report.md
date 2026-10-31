# Implementation Report: #4257 (with #4215, #4216, #4217, #4218, #4219, #4221)

One batch for the speedrun launcher and reset. Each item below is read from the code at HEAD, not from the issue's old line numbers.

## #4257 (the fidelity preflight's refuse flag)

- **R1.** `tools/speedrun_roll.py::main` unpacked `check_contract_fidelity_at_preflight` as `fidelity_text, _`. What the preflight returns is `(text, refuse)`, and `refuse` is True only when the audit did not run (it has already alerted the operator); findings stay report-only. The launcher now keeps the flag, and on True prints the preflight's own text and a `BLOCKED` line and returns 91 before any detach or roll.

## #4216 (checkpoint branch list)

- **R1, R2.** `tools/speedrun_reset.py` defines `CHECKPOINT_BRANCH_FORMATS` and `checkpoint_search_refs(issue)` once: `issue-{N}` first, then `{N}-impl`, `{N}-lld`, `{N}-spec`, `{N}-fix`, each as a local ref and as `origin/<ref>`. `pin_checkpoint` and `speedrun_roll.find_checkpoint` both read it.

## #4217 (the lock the reset reads)

- **R1, R2.** `assemblyzero/workflows/orchestrator/resume.py` gains `orchestration_lock_path(issue, root=None)`. The writer (`acquire_orchestration_lock`), the releaser and `live_orchestrator_pid` all build the path through it. `refuse_if_orchestrator_is_live` passes the AssemblyZero root (`speedrun_reset.AZ_ROOT`, the directory `speedrun_roll.py` starts the orchestrator in) instead of changing into the target repository.

## #4218 (which PRs are closed)

- **R1, R2.** `close_open_prs` asks `gh` for `headRefName`, shuts only a PR whose head is `issue-{N}` or `{N}-*` (`is_pipeline_branch`), and prints every other PR as `Left open PR #n`.

## #4215 (branch tips before deletion)

- **R1, R2.** `reset_one_issue` no longer uses `git branch -d` as the proof. Local branches go through `dispose_pipeline_branches`, the proof the end-of-roll restore uses (no commits beyond the base is deleted; anything else, or a count that cannot be made, is renamed under `graveyard/`). `delete_remote_branches` now lists origin's heads that are `issue-{N}` or `{N}-*`, and for each: proves the tip is on the base, or pushes it to `graveyard/<branch>-<stamp>` and reads the ref back from origin, and only then runs `git push origin --delete`. A tip that is not in the local object store is fetched first. If any step fails the operator is alerted (`alert_operator`), `ResetPreservationError` is raised, the branch is not deleted, and the reset stops. `delete_local_branches` is removed. The reset takes a `base` argument, which the launcher passes as the attempt branch and the standalone tool as the checked-out branch.

## #4219 (ignored worktree files)

- **R1, R2.** `_remove_worktree_at` now checks for uncommitted work first (unchanged behaviour: a dirty worktree is left in place), then `preserve_ignored_files` copies the clean worktree's ignored files to `data/speedrun/reset-artifacts/issue-{N}/worktree-ignored/<worktree name>/` and compares each copy byte for byte (a symbolic link is compared by target). Any listing, copy or comparison failure alerts the operator, keeps the worktree, and raises `ResetPreservationError`. `remove_worktree` is shared with the end-of-roll restore, so the restore is covered too; `restore_repo` catches the error, keeps going and names the kept worktree among its failures.

## #4221 (`--execute` and the typed phrase)

- **R1.** `--fresh --execute` asks for `approve forbidden reset-issues for <owner/repo> #N #M` (`require_confirmation`, `tools/_gate.py`), on the launching console, after every preflight and before any detach. The detached child gets `--fresh --execute --fresh-confirmed` from `detached_argv`; it honours `--fresh-confirmed` only when `--detached-stdout` is set, and refuses (exit 91) instead of prompting when it is not confirmed. A wrong phrase or no console exits 91 with nothing changed. `tools/speedrun_reset.py` takes the same `--execute` and phrase.
- **R2.** `--fresh` without `--execute` prints a read-only plan (PRs it would shut and the ones it would leave, worktrees, local and origin branches with their disposition, lineage, issue reopening) and the phrase, then returns 0 before any preflight, write or spend.
- The help text, the refusal messages that told the operator to relaunch with `--fresh`, `docs/runbooks/0952-speedrun-operator-solo.md` and `docs/runbooks/0956-compare-model-profiles-on-boostgauge.md` say so. The runbook's two "until repaired" warnings for #4215 and #4217 are gone.

## Behaviour the operator will notice

- `--fresh` alone no longer resets anything.
- A reset leaves `graveyard/issue-N-<stamp>` branches (local, and on origin for pushed branches whose work had not landed). The old reset left a branch holding unmerged work in place; it now parks it.
- The remote sweep covers every `issue-{N}` and `{N}-*` head on origin, which is what the clean-check already counted as debris; before it covered `issue-{N}`, `{N}-lld` and the `{N}-*` names that existed locally.
- The checkpoint search now finds a checkpoint on `issue-{N}`, so a launch without `--fresh` that sees debris and such a checkpoint preserves rather than refuses (the intended #2409 behaviour that the missing branch had disabled).
- Ignored worktree files other than those under `node_modules`, `__pycache__`, `.venv`, `.pytest_cache`, `.mypy_cache` and `.ruff_cache` are copied; those directories are counted and named, not copied.

## Not changed

- `assemblyzero/speedrun/worktrees.py` (the launch-time sweep) removes worktrees with its own `git worktree remove`; the issue names the reset and the end-of-roll restore, which share `speedrun_reset.remove_worktree`, so the sweep was left alone.
- Loud-failure baseline: no site added, none removed (`BASELINE_CEILING` unchanged).
