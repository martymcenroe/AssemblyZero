# Test Report: a timed-out agy call no longer kills its caller on Linux (#4195)

## T1: `tests/unit/test_gemini_call_bounds.py::TestTimeoutEndsOnlyTheCall`

A real-process test, skipped on Windows. A fake `agy` (`sleep 30`) is called through `_invoke_via_stdin` with a 1-second timeout by a caller script that first starts a sibling `sleep`. The caller runs in a session of its own, so a regression's group kill stops at the caller and cannot end the test run. It asserts the caller exits 0, the result is a failure naming the timeout, and the sibling is still alive.

- With this change: passed.
- Against `main`'s client (the same test file run under the main checkout's environment): failed with the caller's exit code `-9`, the SIGKILL the issue describes, and the test run survived.

## Suites

`tests/unit/test_gemini_call_bounds.py`: 14 passed. `ruff check` on the test file: clean.

Full suite, 2026-10-22, with `origin/main` merged in: 21 failed, 11713 passed, 66 skipped. The same full suite on an untouched `origin/main` worktree: 26 failed. Every one of the branch's 21 failures is among main's 26 (compared by test id), so this change adds none. One of them, `tests/unit/test_checkpoint_carries_no_enums.py::test_the_unit_tier_runs_the_serializer_strict`, passes alone on both and fails only inside the full run: it depends on whether another test imported langgraph first.
