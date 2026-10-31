"""Tests for pytest exit codes and their descriptions.

Issue #292 added the exit codes the TDD workflow routes on. Its router,
`route_by_exit_code`, was never called and is deleted (ADR 0236, ledger 0908;
see #2690): its route tests went with it, and
`test_exit_code_router_loud_failure.py` pins that it is gone. The routing
that runs is in `nodes/verify_phases.py`.

Tests cover:
- describe_exit_code() for human-readable descriptions
- the exit code constants
"""


from assemblyzero.workflows.testing.exit_code_router import (
    EXIT_OK,
    EXIT_TESTSFAILED,
    EXIT_INTERRUPTED,
    EXIT_INTERNALERROR,
    EXIT_USAGEERROR,
    EXIT_NOTESTSCOLLECTED,
    EXIT_TIMEOUT,
    describe_exit_code,
)


class TestDescribeExitCode:
    """Test human-readable exit code descriptions."""

    def test_all_known_codes_have_descriptions(self):
        """Every known exit code returns a non-empty description."""
        known_codes = [EXIT_OK, EXIT_TESTSFAILED, EXIT_INTERRUPTED,
                       EXIT_INTERNALERROR, EXIT_USAGEERROR,
                       EXIT_NOTESTSCOLLECTED, EXIT_TIMEOUT]
        for code in known_codes:
            desc = describe_exit_code(code)
            assert desc, f"No description for exit code {code}"
            assert "unknown" not in desc.lower()

    def test_unknown_code_includes_number(self):
        """Unknown exit codes include the code number."""
        desc = describe_exit_code(99)
        assert "99" in desc

    def test_exit_0_description(self):
        assert "passed" in describe_exit_code(EXIT_OK)

    def test_exit_4_description(self):
        desc = describe_exit_code(EXIT_USAGEERROR)
        assert "collection" in desc or "syntax" in desc


class TestExitCodeConstants:
    """Verify exit code constants match pytest documentation."""

    def test_exit_ok(self):
        assert EXIT_OK == 0

    def test_exit_testsfailed(self):
        assert EXIT_TESTSFAILED == 1

    def test_exit_interrupted(self):
        assert EXIT_INTERRUPTED == 2

    def test_exit_internalerror(self):
        assert EXIT_INTERNALERROR == 3

    def test_exit_usageerror(self):
        assert EXIT_USAGEERROR == 4

    def test_exit_notestscollected(self):
        assert EXIT_NOTESTSCOLLECTED == 5

    def test_exit_timeout(self):
        assert EXIT_TIMEOUT == -1
