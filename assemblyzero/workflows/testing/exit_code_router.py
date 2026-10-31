"""Pytest exit codes for the TDD workflow, and what each one means.

Issue #292 introduced these so the workflow could route on pytest's exit
code instead of the pass/fail counts alone. The routing that runs is inline
in `nodes/verify_phases.py`, on these constants; `route_by_exit_code`, a
second copy of that decision that nothing called (see #2690), is deleted
(ADR 0236, ledger 0908): it sent a red phase that passed, an interrupted or
broken pytest, a timeout and an unknown code to a plain end, never to HALT,
so none of them would have alerted anyone had it been wired in.

Pytest exit codes (from pytest documentation):
    0 - All tests passed
    1 - Tests were collected and run but some failed
    2 - Test execution was interrupted by the user
    3 - Internal error happened while executing tests
    4 - pytest command line usage error / test collection error
    5 - No tests were collected
"""

# Pytest exit codes
EXIT_OK = 0
EXIT_TESTSFAILED = 1
EXIT_INTERRUPTED = 2
EXIT_INTERNALERROR = 3
EXIT_USAGEERROR = 4
EXIT_NOTESTSCOLLECTED = 5

# Sentinel for subprocess timeout
EXIT_TIMEOUT = -1


def describe_run_outcome(exit_code: int, failed_count: int | None = None) -> str:
    """describe_exit_code, but never blames tests for the coverage gate.

    #1938: pytest-cov's fail-under forces exit 1 even when every test
    passes. A live run printed '50 passed, 0 failed | Exit: 1 (some tests
    failed)' — the mislabel cost a full log-forensics pass during the
    kill-diagnosis. When the caller knows the failure count is zero, exit 1
    means the coverage gate, and the label says so.
    """
    if exit_code == EXIT_TESTSFAILED and failed_count == 0:
        return "coverage below fail-under; all tests passed"
    return describe_exit_code(exit_code)


def describe_exit_code(exit_code: int) -> str:
    """Return a human-readable description of a pytest exit code.

    Args:
        exit_code: Pytest return code.

    Returns:
        Description string.
    """
    descriptions = {
        EXIT_OK: "all tests passed",
        EXIT_TESTSFAILED: "some tests failed",
        EXIT_INTERRUPTED: "test execution interrupted",
        EXIT_INTERNALERROR: "pytest internal error",
        EXIT_USAGEERROR: "collection/syntax error",
        EXIT_NOTESTSCOLLECTED: "no tests collected",
        EXIT_TIMEOUT: "execution timed out",
    }
    return descriptions.get(exit_code, f"unknown exit code ({exit_code})")
