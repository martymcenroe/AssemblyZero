`tools/test-gate.py` already matches the LLD spec exactly. All 18 tests pass. The fix was replacing the TDD RED stubs in `tests/test_issue_225.py` with real test implementations that exercise the `tools.test_gate` package and the `tools/test-gate.py` CLI entry point.

**Results:**
- **18/18 tests passing**
- **92% coverage** on `tools.test_gate` (174 statements, 14 missed — uncovered lines are error-handling paths like SIGINT forwarding, timeout, and FileNotFoundError in subprocess)
- `tools/test-gate.py` — unchanged, already correct per LLD
