# Implementation report: #4509

## The defect

`GeminiClient._agy_once` waited in `proc.communicate`, which returns at EOF. On a large prompt agy prints its whole reply and stays alive, so the transport sat out its 300 s, threw a finished answer away and reported a capacity failure, twice, which is the whole call budget. That ended a real implementation run at its first file.

## `assemblyzero/core/gemini_client.py`

- stdout now goes to `agy-reply.out` in the call's temporary directory instead of a pipe. A pipe's contents cannot be seen while `communicate` holds it.
- `_AnswerWatcher` is a daemon thread started beside `communicate`. Every 0.25 s it looks at the file. When the file's size has not changed for 2 s and its text, with ANSI stripped, is `{...}`, it logs a warning naming the pid, sets `answered`, and calls `kill_process_tree`. `communicate` then returns, because agy has gone.
- The watcher decides only when to stop waiting. `_agy_json_reply` still judges what was printed, so a reply that does not parse raises and a bad status fails the call (R2).
- Output that is not `{...}` never ends a call. A warning line, plain text, or a reply still arriving waits for the exit or the timeout as before (R3).
- An agy that exits by itself is seen by `proc.poll()`, the watcher returns, and the existing path runs with agy's real exit status (R4).
- `returncode` is forced to 0 only when `answered` is set. The exit status of a process this call killed says nothing about the call, and the reply's own status decides.
- The 300 s timeout still bounds a call that never answers (R5), and `watcher.stop()` runs in a `finally` on every path.
- `kill_process_tree` signals the session `start_new_session` gave agy, so the process group is gone when the call returns (R6).

## Left open

- #4510: why agy stays alive has not been established. This removes the wait, not the cause.
