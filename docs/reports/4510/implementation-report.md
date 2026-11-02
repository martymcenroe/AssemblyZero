# Implementation report: #4510

#4510 asked why agy stays alive after printing its whole answer. The measurements and the log reading are in `agy-exit-probe.md` beside this file.

## What changed

- `tools/agy_exit_probe.py` is new. It makes bounded real calls with the transport's own argv, never ends agy before `--grace` after the answer, and records the answer time, whether agy exited by itself, agy's log for the process, and the state of every process in agy's group while it is alive. `--through-transport` calls through `GeminiClient._invoke_via_stdin` and records whether the watcher ended agy. `--logs PREFIX` reads agy's logs without a call. It refuses any model but `gemini-3.8-flash-*`, takes the model from the fleet switch's `workflow` role, and writes each call to the model-call ledger.
- `AGY_ANSWER_SETTLE_SECONDS` in `assemblyzero/core/gemini_client.py` is 10 s, from 2 s. On 30 real calls agy exited by itself 0.5 to 2.8 s after its answer, and 7 of those exits took 2.0 s or more, so a 2 s settle ended normal exits mid-shutdown and warned about each as a hang.

## What did not change

The watcher stays. The hang measured on 2026-11-01 did not reproduce, and its logs end at `sending completion signal` with no shutdown begun. Nothing on the calling side was found that starts that shutdown, so the cause lies inside agy and the watcher is its backstop.

## Filed

#4531: a 2,141-character prompt was billed 16,687 input tokens.
