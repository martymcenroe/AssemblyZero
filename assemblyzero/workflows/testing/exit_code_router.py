"""Pytest exit code routing for TDD workflow.

Issue #292: Route workflow based on pytest exit codes instead of
just pass/fail counts. This correctly handles syntax errors (exit 4)
and no-tests-collected (exit 5) by routing back to scaffold instead
of looping endlessly through implementation.

Pytest exit codes (from pytest documentation):
    0 - All tests passed
    1 - Tests were collected and run but some failed
    2 - Test execution was interrupted by the user
    3 - Internal error happened while executing tests
    4 - pytest command line usage error / test collection error
    5 - No tests were collected
"""

from typing import Literal

# Pytest exit codes
EXIT_OK = 0
EXIT_TESTSFAILED = 1
EXIT_INTERRUPTED = 2
EXIT_INTERNALERROR = 3
EXIT_USAGEERROR = 4
EXIT_NOTESTSCOLLECTED = 5

# Sentinel for subprocess timeout
EXIT_TIMEOUT = -1


def route_by_exit_code(
    exit_code: int,
    phase: Literal["red", "green"],
) -> str:
    """Determine next workflow node based on pytest exit code.

    Args:
        exit_code: Pytest return code (0-5, or -1 for timeout).
        phase: Which TDD phase we're in ("red" or "green").

    Returns:
        Next node name string for workflow routing.
    """
    if exit_code == EXIT_OK:
        if phase == "red":
            # All tests passed in red phase = unexpected (feature already exists?)
            return "END"
        # Green phase: all tests pass = success, handled by caller
        return "PASS"

    if exit_code == EXIT_TESTSFAILED:
        if phase == "red":
            # Tests failed = valid RED state, proceed to implementation
            return "N4_implement_code"
        # Green phase: tests still failing, need more implementation
        return "N4_implement_code"

    if exit_code in (EXIT_INTERRUPTED, EXIT_INTERNALERROR):
        # Human review needed — not a code problem, not safe to auto-retry
        return "end"

    if exit_code in (EXIT_USAGEERROR, EXIT_NOTESTSCOLLECTED):
        # Syntax/collection error or no tests found = scaffold problem
        return "N2_scaffold_tests"

    if exit_code == EXIT_TIMEOUT:
        # Subprocess timed out — stop workflow
        return "end"

    # Unknown exit code — stop safely
    return "end"


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
