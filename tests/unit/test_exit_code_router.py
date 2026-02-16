"""Tests for pytest exit code routing.

Issue #292: Verify exit code routing logic for TDD workflow.

Tests cover:
- route_by_exit_code() for all exit codes in both red/green phases
- describe_exit_code() for human-readable descriptions
- Graph routing functions handle N2_scaffold_tests target
"""

import pytest

from assemblyzero.workflows.testing.exit_code_router import (
    EXIT_OK,
    EXIT_TESTSFAILED,
    EXIT_INTERRUPTED,
    EXIT_INTERNALERROR,
    EXIT_USAGEERROR,
    EXIT_NOTESTSCOLLECTED,
    EXIT_TIMEOUT,
    describe_exit_code,
    route_by_exit_code,
)


class TestRouteByExitCodeRedPhase:
    """Test exit code routing during RED phase (N3)."""

    def test_exit_0_red_ends_workflow(self):
        """Exit 0 in red = all tests passed unexpectedly."""
        assert route_by_exit_code(EXIT_OK, "red") == "END"

    def test_exit_1_red_routes_to_implement(self):
        """Exit 1 in red = valid RED state, proceed to N4."""
        assert route_by_exit_code(EXIT_TESTSFAILED, "red") == "N4_implement_code"

    def test_exit_2_red_stops_workflow(self):
        """Exit 2 in red = interrupted, stop."""
        assert route_by_exit_code(EXIT_INTERRUPTED, "red") == "end"

    def test_exit_3_red_stops_workflow(self):
        """Exit 3 in red = internal error, stop."""
        assert route_by_exit_code(EXIT_INTERNALERROR, "red") == "end"

    def test_exit_4_red_routes_to_scaffold(self):
        """Exit 4 in red = syntax/collection error, re-scaffold."""
        assert route_by_exit_code(EXIT_USAGEERROR, "red") == "N2_scaffold_tests"

    def test_exit_5_red_routes_to_scaffold(self):
        """Exit 5 in red = no tests collected, re-scaffold."""
        assert route_by_exit_code(EXIT_NOTESTSCOLLECTED, "red") == "N2_scaffold_tests"

    def test_timeout_red_stops_workflow(self):
        """Timeout (-1) in red = stop."""
        assert route_by_exit_code(EXIT_TIMEOUT, "red") == "end"

    def test_unknown_exit_code_red_stops(self):
        """Unknown exit code in red = stop safely."""
        assert route_by_exit_code(99, "red") == "end"


class TestRouteByExitCodeGreenPhase:
    """Test exit code routing during GREEN phase (N5)."""

    def test_exit_0_green_passes(self):
        """Exit 0 in green = all tests passed."""
        assert route_by_exit_code(EXIT_OK, "green") == "PASS"

    def test_exit_1_green_routes_to_implement(self):
        """Exit 1 in green = tests failing, need more implementation."""
        assert route_by_exit_code(EXIT_TESTSFAILED, "green") == "N4_implement_code"

    def test_exit_2_green_stops_workflow(self):
        """Exit 2 in green = interrupted, stop."""
        assert route_by_exit_code(EXIT_INTERRUPTED, "green") == "end"

    def test_exit_3_green_stops_workflow(self):
        """Exit 3 in green = internal error, stop."""
        assert route_by_exit_code(EXIT_INTERNALERROR, "green") == "end"

    def test_exit_4_green_routes_to_scaffold(self):
        """Exit 4 in green = syntax/collection error, re-scaffold."""
        assert route_by_exit_code(EXIT_USAGEERROR, "green") == "N2_scaffold_tests"

    def test_exit_5_green_routes_to_scaffold(self):
        """Exit 5 in green = no tests collected, re-scaffold."""
        assert route_by_exit_code(EXIT_NOTESTSCOLLECTED, "green") == "N2_scaffold_tests"

    def test_timeout_green_stops_workflow(self):
        """Timeout (-1) in green = stop."""
        assert route_by_exit_code(EXIT_TIMEOUT, "green") == "end"

    def test_unknown_exit_code_green_stops(self):
        """Unknown exit code in green = stop safely."""
        assert route_by_exit_code(42, "green") == "end"


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
