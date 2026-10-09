# Implementation Report: a real implementation run lands through the merge driver (#4150)

The rule is ADR 0236 and standard 0034. #3704 did the same for the LLD workflow.

## The landing

- **`finish_standalone_run`** (`tools/run_implement_from_lld.py`). A successful real run commits `[CP:final]`, keeps ignored and excluded files under `<repo>/data/runs-kept/`, and hands the worktree and `<issue>-implementation` to `merge_driver.land`. The title is `feat: implement #N from its approved LLD (Closes #N)`. The body is written to `<target>/data/assemblyzero/pr-bodies/impl-N.md`, the path the orchestrator's PR stage uses (#3717). It opens with `Closes #N` on its own line and carries the adversarial review's summary. Nothing is pushed, removed or deleted by the run; the driver does all three. The `gh pr create` line is gone.
- **The start-up refusal.** `landing_preflight(args)` returns `merge_driver.check_configured()` for a real run that will finish a worktree. `main` prints it on stderr, alerts, and exits 1 before the resume contract is consumed, a worktree is cut or a graph is built. A dry run, a mock run, a scaffold-only run and a `--no-worktree` run land nothing and are not asked.
- **`--scaffold-only`** lands nothing, since its tests are red by design. It keeps the worktree and the branch for the full run; it used to push the branch.
- **`--mock`** is unchanged: detached worktree, no branch, no push, no driver, worktree removed.
- **`END_STATE`**, `--help` and the dry-run plan say the new end state.
- **`merge_driver.check_configured`** says the LLD, implementation and orchestrated runs all land through the driver.

## A success is what N7 says it is

The testing graph has routes to END with no `error_message`: an iteration cap, a spent budget, exhausted augment attempts, an exhausted scaffold, a BLOCKED plan under the strict policy. They are sweep rows in #3815. The runner read every one of them as SUCCESS. Under the old finish that pushed a branch nothing could land. Under the new finish it would have merged failing code, so the runner now requires proof:

- `workflow_status == "completed"`, which only N7 finalize sets (#2677); or, for `--scaffold-only`, a scaffold in `test_files`.
- Any other end is sent through the testing HALT node with a reason naming `workflow_status`, `next_node` and the iteration. HALT saves the state and a recovery plan and alerts. The run exits 1 and lands nothing.

## An end state not reached is a failure

`finish_standalone_run` keeps its contract (`(finished, lines)`, never raises for a refusal). Every refusal is now a stop:

| Stop | Was |
|---|---|
| The driver refuses (`MergeDriverError`, its output in the line) | not possible: the run pushed and printed `gh pr create` |
| `git status` fails (ledger 296, 345) | read as clean, then moved nothing and removed the worktree |
| `git branch --show-current` fails or is empty (ledger 353) | the push was skipped, the worktree removed, `finished=True` |
| The final checkpoint left work uncommitted | the work was moved into `runs-kept`, the tree read clean, and the branch went out without it |

`commit_checkpoint` reports a failed commit only on stdout (#3810). So the finish checks the invariant the checkpoint promises: after `[CP:final]`, nothing is uncommitted except `checkpoints.EXCLUDED_PATHS`, now named once there for both readers.

When the finish stops, `main` sends the run through HALT with the stop line as the cause, so the driver's output reaches the alert. It writes the FAILED status file and exits 1. The worktree and the branch are kept; after a driver refusal the next step is the driver's route for the stage it printed.

## The rest of the run's outcome (ledger 0908, sweep issue #4097)

| Site | Was | Now |
|---|---|---|
| `:1344` a node's `error_message` | stdout | `[ERROR]` on stderr |
| `:1377` an error at END | stdout, return 1, no alert unless HALT ran | sent through HALT when `workflow_status` is not `halted`; never alerted twice |
| `:1442` end state not reached | a note, return 0 | HALT, exit 1 |
| `:1458` unexpected exception, `ImplementationError` | stdout, return 1, no alert | stderr, `alert_operator`, return 1 |
| `:1484` no final state | recorded a halt, exit 0 | ERROR, `alert_operator`, exit 1 |

With 296, 345 and 353 above, eight of #4097's 23 rows are fixed and marked in ledger 0908. The other fifteen are entry-point and helper sites; they stay on #4097.

## Loud-failure compliance (standard 0034)

| Failure path | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| driver not configured | `[implement] ERROR` on stderr | `alert_operator` record | exit 1 before any work | `alert_operator` |
| run ended short of N7 | ERROR on stderr | HALT state snapshot, plan, alert record | exit 1, nothing landed | HALT |
| finish stopped (driver, git, checkpoint) | ERROR on stderr | HALT, with the stop line as the cause | exit 1, worktree and branch kept | HALT |
| error that bypassed HALT | `[ERROR]` on stderr | HALT | exit 1 | HALT |
| no final state, crash, `ImplementationError` | stderr | `alert_operator` record | exit 1 | `alert_operator` |

## Baselines

- **Loud-failure baseline:** 318 to 317. Main's broad handler (`main::swallowed_handler::1`) now calls `alert_operator`. `BASELINE_CEILING` is lowered with it.
- **Fail-open baseline:** unchanged; the audit passes in strict mode.
- **Halt sites:** unchanged (152); the audit passes.

## Not done here, filed

- #4158: a real run started on its own issue branch never sets `worktree_path`, so it succeeds without landing.
- #3815 still owns the testing graph's silent END routes; the runner's proof of success only keeps them from being landed.
