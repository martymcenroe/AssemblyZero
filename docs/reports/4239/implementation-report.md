# Implementation Report: a run must be able to start (#4239, #4241, #4158)

Three defects that each stop a real run from starting cleanly, or from finishing honestly once it has. The rule is ADR 0236: a failure is loud, stops what depends on it, and alerts.

## #4239: the implementation run checks its transport before it starts

`preflight_for_specs` ran only inside the LLD and spec drafters. `tools/run_implement_from_lld.py` checked only the merge driver at start, so with agy missing or logged out an implementation run cut its worktree and branch and learned at its first model call that it could not run.

- `transport_preflight(args, repo_root)` resolves the run's profile as the run will (`profile_from_args` with the same legacy `--reviewer` mapping, now the constant `LEGACY_SEAT_FLAGS`) and sends every seat's spec through `preflight_for_specs`. Any Gemini seat means one real call through agy; a profile with none is not probed.
- `main()` calls it after the merge-driver check and before the resume contract is consumed. A failure prints an ERROR line, alerts the operator, and exits 1, with no worktree, branch or lineage made.
- A mock run and a dry run call no model and are not asked.
- `claude.toml` keeps four seats on Gemini (among them `impl.adversarial`), so a run on it is rightly probed.

## #4241: every workflow worktree is recorded with relative paths

The issue named seven sites. Requirement 1 covers every `git worktree add` in `assemblyzero/` and `tools/`, and there were nine. All nine now pass `--relative-paths`:

- `tools/run_implement_from_lld.py`: the detached mock cut, the new-branch cut and the existing-branch retry;
- `assemblyzero/workflows/requirements/git_operations.py`: the LLD worktree's new-branch cut and its retry;
- `assemblyzero/workflows/orchestrator/stages.py`: the new-branch cut and the recovered-branch cut;
- `tools/dependabot_review.py`: the audit worktree;
- `tools/speedrun_roll.py`: the sync tree.

## #4158: a real run started on its own issue branch refuses

The finish lands a worktree the run cut, or found from the integration branch. A real run started from a checkout already on `<issue>-implementation` had neither, so it reported SUCCESS, exited 0 and landed nothing. The issue allowed either landing or refusing; refusing was chosen, because landing from inside the worktree being landed would have the driver remove the directory the run's own records are in.

- `issue_branch_refusal(args, repo_root)` returns the reason when a real run's checkout is on the issue's own work branch. `main()` checks it before the transport preflight, so the refusal comes before any model call, the probe included. It alerts and exits 1.
- The reason says where to start: the integration branch's checkout, which finds the issue's worktree and reuses it.
- A run that lands nothing (dry, mock, scaffold-only, `--no-worktree`) is not refused, so working in place stays the operator's choice.

## Not changed

- The worktree block's "Already on issue branch" case still serves mock and scaffold-only runs.
