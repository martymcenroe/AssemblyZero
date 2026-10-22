# Test Report: a timed-out agy call no longer kills its caller on Linux (#4195)

## T1: `tests/unit/test_gemini_call_bounds.py::TestTimeoutEndsOnlyTheCall`

A real-process test, skipped on Windows. A fake `agy` (`sleep 30`) is called through `_invoke_via_stdin` with a 1-second timeout by a caller script that first starts a sibling `sleep`. The caller runs in a session of its own, so a regression's group kill stops at the caller and cannot end the test run. It asserts the caller exits 0, the result is a failure naming the timeout, and the sibling is still alive.

- With this change: passed.
- Against `main`'s client (the same test file run under the main checkout's environment): failed with the caller's exit code `-9`, the SIGKILL the issue describes, and the test run survived.

## Suites

`tests/unit/test_gemini_call_bounds.py`: 14 passed. `ruff check` on the test file: clean. Full suite: run after the commit; its result is recorded on #4195's closing comment.
