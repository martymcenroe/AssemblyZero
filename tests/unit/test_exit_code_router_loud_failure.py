"""exit_code_router.py under standard 0034, one test per sweep site (#3585).

`route_by_exit_code` sent a red phase whose every test passed to END with no
error (47), and an interrupted or broken pytest (60), a timeout (68) or an
exit code it did not know (71) to "end", never to HALT, so none of them would
have alerted anyone. It was never called: the routing that runs is inline in
`nodes/verify_phases.py` on the same constants (see #2690), and nothing but
its own tests read it. The ledger's prescription was to route those to HALT
or delete the function; it is deleted, so no copy of the decision is left to
be wired in with its silent ends. The constants and the descriptions, which
verify_phases does use, stay.

Line numbers in the names are ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.testing import exit_code_router as ecr


class TestTheUnusedRouterIsGone:
    def test_47_a_red_phase_that_passes_is_not_routed_to_a_silent_end(self):
        assert not hasattr(ecr, "route_by_exit_code")

    def test_60_an_interrupted_or_broken_pytest_has_no_silent_end(self):
        assert not hasattr(ecr, "route_by_exit_code")

    def test_68_a_timeout_has_no_silent_end(self):
        assert not hasattr(ecr, "route_by_exit_code")

    def test_71_an_unknown_exit_code_has_no_silent_end(self):
        assert not hasattr(ecr, "route_by_exit_code")


class TestWhatVerifyPhasesReadsStays:
    @pytest.mark.parametrize(("code", "described"), [
        (ecr.EXIT_OK, "all tests passed"),
        (ecr.EXIT_TESTSFAILED, "some tests failed"),
        (ecr.EXIT_INTERRUPTED, "test execution interrupted"),
        (ecr.EXIT_INTERNALERROR, "pytest internal error"),
        (ecr.EXIT_USAGEERROR, "collection/syntax error"),
        (ecr.EXIT_NOTESTSCOLLECTED, "no tests collected"),
        (ecr.EXIT_TIMEOUT, "execution timed out"),
        (9, "unknown exit code (9)"),
    ])
    def test_every_code_is_described(self, code, described):
        """Kept: the descriptions verify_phases prints and halts with."""
        assert ecr.describe_exit_code(code) == described

    def test_exit_one_with_no_failures_is_the_coverage_gate(self):
        """Kept (#1938)."""
        assert ecr.describe_run_outcome(1, failed_count=0) == (
            "coverage below fail-under; all tests passed"
        )
        assert ecr.describe_run_outcome(1, failed_count=2) == "some tests failed"
