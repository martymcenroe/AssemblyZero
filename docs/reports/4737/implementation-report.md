# Implementation report: #4737

## The cause the issue left open

The nightly ran the full suite on PR #4315 on twelve nights, 2026-11-01 to 2026-11-12, and recorded no outcome for any of them. Every nightly log from 2026-11-01 to 2026-11-13, thirteen of them, carries `Interrupted (SIGINT received) -- shutting down cleanly...`; none of the thirty October logs does. Each run was interrupted inside the pytest call, and nothing in the tool recorded an interrupted PR:

- `run()` caught only `subprocess.TimeoutExpired`, so a `KeyboardInterrupt` raised inside `subprocess.run` printed neither `TIMEOUT after` nor `pytest exit code`.
- `process_pr`'s try/finally removed the worktree and ran `poetry env remove --all`, then re-raised. That is the `env remove` line each log shows straight after pytest.
- `process_repo` never appended the PR to any list, and `main()`'s finally printed a Summary without it.

With no review posted, the zero-review pre-pass picked #4315 first again the next night, and the interrupt ended the whole fleet run, so the other pre-pass PRs were never processed either.

Ten of the twelve runs also went past `PYTEST_TIMEOUT_S` (1800s) with no `TIMEOUT after` line. On Windows, `subprocess.run`'s timeout kills only `poetry`, and the `communicate()` that follows waits on the pipes the pytest grandchild still holds. That is #1966's class.

## Where the interrupt comes from: #4740, not fixed here

The likeliest source is `os.kill(pid, 0)` in `assemblyzero/workflows/orchestrator/resume.py:122`. On Windows, signal 0 is `CTRL_C_EVENT`, so the call is a console Ctrl-C. Tests that reach it arrived in 9df0806e, an ancestor of #4315's tested heads.

## Children get a console of their own

`assemblyzero.core.no_console.install()` runs at module level (`tools/dependabot_review.py:95-97`), as it does in `tools/orchestrate.py` and `tools/speedrun_roll.py`. Every child then starts with a console of its own, so a Ctrl-C broadcast inside one cannot reach the nightly. `utf8_console.install()` follows it (`:99-104`), as #2673 requires of every tool that installs `no_console`.

## The timeout kills the tree (R2)

`run(..., kill_tree=False)` at `:528`. With `kill_tree=True`, `_run_killing_tree` (`:615`) starts the command with `Popen`, in a session of its own off Windows. On timeout it prints `TIMEOUT after {n}s -- killing the process tree of pid N`, calls `kill_process_tree` from `assemblyzero/utils/process.py`, waits up to `KILL_DRAIN_TIMEOUT_S` (60s) for the pipes, and returns exit `TIMEOUT_EXIT` (124). Pipes still open after that raise `ProcessTreeKillError`. Any `BaseException` while it waits, `KeyboardInterrupt` included, kills the tree and re-raises.

Only `run_tests_detailed` (`:958`) passes `kill_tree=True`. A pytest timeout is recorded `deferred` with the reason `pytest TIMEOUT after 1800s; the suite's process tree was killed (#4737)`, and the baseline is not run (`:1945-1953`). A baseline that times out is not exonerable (`:1838-1842`).

## One outcome per PR (R1)

`Outcome` (`:364`) is a `str` that carries `.reason`, so every caller that compares the status with `"merged"` keeps working. Every return in `_process_pr_inside_worktree` and `process_pr` is an `Outcome`. `process_repo` records every PR it reaches, the skipped-unchanged and limit-skipped ones included, through `_record_outcome` (`:2435`), which prints exactly one line:

```
  OUTCOME PR #<n>: <status> -- <reason>
```

- An `Exception` from `process_pr` is printed with its traceback, recorded `errored`, sent to the operator through `alert_operator`, and the loop goes on to the repo's next PR (`:2403-2419`).
- A `KeyboardInterrupt` is recorded `errored` and re-raised (`:2394-2402`).
- A status other than merged, deferred or errored is recorded `errored`, naming the status (`:2422-2425`).
- The loop's `except BaseException` attaches the results so far as `exc.dependabot_partial` (`:2429-2431`). `main()` merges them with `_extend_results` on every path that re-raises, so the Summary names every PR the run touched.

## A PR that never finishes is not rerun every night (R3)

`InFlightLedger` (`:451`) keeps `data/dependabot-runs/in-flight.json`, keyed `"<repo>#<pr>"`, each entry `{"head": sha, "runs": [label, ...]}`, where a run's label is its log file's name. `main()` makes the one ledger and passes it into every `process_repo` call (`:2668-2676`); nothing else creates one.

- An entry is written just before a PR is tested and cleared when its outcome is recorded. An interrupt keeps it.
- The next run that reaches the PR prints `  REPEAT PR #<n>: run <label> began this PR at head <sha9> and recorded no outcome`.
- Once `IN_FLIGHT_STRIKES` (2) runs have begun the PR at its current head with no outcome, it is recorded `deferred` without running, before any harvest budget is spent (`:2362-2381`). That path keeps the entry, so the PR is deferred the same way on each later run until its head changes. A new head starts the count again.
- That path posts no review, so it also lists the PR in `UNREVIEWED_DEFERRED` (`:361`), and `main()` leaves those PRs out of the Summary's COMMENTED count (`:2828-2832`); without it, every two-strike deferral was counted as a posted review.
- A ledger that is not valid JSON, or not a JSON object, raises `InFlightLedgerError`, naming the path, and the file is left as it is: resetting it would forget the runs it records.

To clear a stuck entry by hand, remove that key from the JSON file. Runbook 0911 says so.

## Tests

Tests 1 and 2 of the issue are in `tests/unit/test_dependabot_outcomes.py`, with changes to `tests/unit/test_dependabot_review.py` and `tests/tools/test_dependabot_review.py`. The test report records the run.

## Left open

- #4740: the interrupt's source. This change keeps an interrupt from reaching the nightly and from going unrecorded; it does not remove the call.
- #1966: the other `run()` calls whose timeout kills only the direct child, or that have none.
- Test 3 and AC2, one outcome line in the next nightly's `=== PR #4315` section: a follow-up issue carries the check after the next nightly.
- The scheduled checkout does not update itself today, so this fix reaches the nightly only once that checkout is brought to a `main` that carries it. The follow-up confirms that from the run's provenance SHA.
