# Why agy stays alive after its answer: what was measured, 2026-11-02

Issue #4510. Measured between 1:21 and 2:03 AM Central on 2026-11-02, from Ubuntu, with agy 1.4.12, the build installed on 2026-10-16. That is the same build #4509 measured on 2026-11-01. Every call was real, one agy process at a time, on `gemini-3.8-flash-high` chosen by the fleet switch's `workflow` role, and each wrote a line to the model-call ledger.

The program is `tools/agy_exit_probe.py`. It sends a call with the transport's own argv, never ends agy before a grace period, and records when the answer arrived, whether agy exited by itself, and agy's own log for the process. `--through-transport` makes the call through `GeminiClient._invoke_via_stdin`, watcher and all. `--logs PREFIX` makes no call and reads agy's logs.

## R1: where it starts

It did not start anywhere. Every call exited by itself.

| Run | Calls | Prompt | Reply | Exited by itself | After the answer |
|---|---|---|---|---|---|
| Prompt size | 10 | 2,000 to 110,000 chars | one sentence | 10 | 1.3 to 2.5 s |
| Long thinking | 8 | 110,000 chars | one sentence, 6,918 to 20,193 thinking tokens | 8 | 0.5 to 1.3 s |
| Exact argv | 8 | 2,000 and 110,000 chars | one sentence | 8 | 0.8 to 2.8 s |
| Code replies | 4 | 110,000 chars | a Python module, 3,280 and 9,280 text tokens | 4 | 0.5 to 0.8 s |

The first two runs passed `--log-file`, which the transport does not; the third ran the transport's exact argv and agreed with them. The "long thinking" run asked the model to copy lines back, and it declined and answered in a sentence, so it measured long thinking, not long replies. The code-reply run asked for a module of numbered functions, which the model wrote.

## R2: what agy does after its reply

In every exit measured, agy's log goes on from `Stream goroutine exited ..., sending completion signal` to `Language server shutting down`, then `Waiting for migrations to complete to prevent partial migration state...`, then `summary store: reconciliation complete, synced N records` (about 52,000 records on this machine), and the process exits.

The calls #4509 measured hanging on 2026-11-01, between 4:02 and 4:21 PM Central, have logs that end at `sending completion signal`, with nothing after. Their shutdown never began. Their summary-store reconciliation had finished seconds after start, long before the answer, so it was not what held them. Nothing in agy's log says why the shutdown did not start, and the hang did not reproduce in any call above. That puts the cause inside agy.

Read from agy's logs for 2026-11-01 between 10 AM and 8 PM (`--logs 20261101_1`, 617 processes, 610 with an answer): of the processes that ran beside another agy process, 307 of 574 logged no `reconciliation complete`, and 26 logged `database is locked` against the shared summary store. Of those that ran alone, 0 of 36 did. A process that was ended before it reconciled leaves the same log, so this counts both, and it does not show that concurrency delays an exit. It does not explain the 4 PM calls, which ran alone.

## R3: what the calling side could change

The watcher's settle. It ended agy 2.0 s after a finished-looking reply. In all 30 calls above, agy's own exit came 0.5 to 2.8 s after the answer, and 7 took 2.0 s or more. A 2 s settle ends those mid-shutdown, during the step agy's log says is waiting to prevent partial migration state, and warns about each as a hang.

The settle is now 10 s. A normal exit happens first, and a real hang still ends about 290 s sooner than the 300 s timeout would end it.

T3, through the transport with the new settle: six calls of 110,000 characters, two of which returned a 20,487-character module. The watcher ended agy on none of them, and none logged the warning.

## R4: why the watcher stays

The hang #4509 measured is real and lies inside agy: its shutdown did not begin, and nothing on the calling side was found that starts it. The watcher is the backstop for that, with a settle that no longer catches a normal exit.

## Also seen

A 2,141-character prompt was billed 16,687 input tokens. The transport's own comment records 2,766 for the call it measured on 2026-09-25, after the agent definition took the tool schemas out of the prompt. Filed as #4531.
