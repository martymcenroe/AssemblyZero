# Implementation Report: a timed-out agy call no longer kills its caller on Linux (#4195)

## What was wrong

`GeminiClient._invoke_via_stdin` started agy with `subprocess.Popen(...)` and no `start_new_session`, so agy shared the caller's process group. On a timeout it calls `kill_process_tree(proc.pid)`, which off Windows runs `os.killpg(os.getpgid(pid), 9)`. The group was the caller's, so the caller, the script that started it and every sibling died with SIGKILL, and the client never returned its timeout result. Seen on 2026-10-16: a script's third call timed out at exactly `AGY_CALL_TIMEOUT_SECONDS` (300 s) and the whole script exited 137.

## R1: agy in a session of its own

The `Popen` call passes `start_new_session=os.name != "nt"`, so off Windows agy leads its own session and process group, and `kill_process_tree` ends agy and its descendants only. `llm_provider.py`'s subprocesses already start this way (`start_new_session=sys.platform != "win32"`), and `tools/prove_idle_timeout.py` records why. `os.name` is used because the module imports `os` and not `sys`. Windows is unchanged: `kill_process_tree` uses `taskkill /T` there.

## R2: the timeout result

With the caller alive, the existing `except subprocess.TimeoutExpired` path runs to its `return False, "", "agy CLI timeout (...)"`, as it already did on Windows.

No other line changed. `ruff check` reports the same 19 findings in `gemini_client.py` before and after; none is in the changed lines.
