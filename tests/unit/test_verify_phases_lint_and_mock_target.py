"""The three ruff findings in `verify_phases.py`, and what they were hiding (#2671).

They are not three unrelated bits of untidiness. Two of them -- an unused
`coverage_target` local and an f-string with no placeholder -- are halves of one
unfinished edit: somebody began making the mock green phase compare its
measured coverage against the target and interpolate the number into the
report, and stopped. The third, an unused `route_by_exit_code` import, is the
visible end of a larger problem filed separately as #2690.

**What the lint gate actually checks: nothing.** `.github/workflows/ci.yml`
runs `tools/test-gate.py` over `tests/unit/` and `tests/integration/` plus a
coverage upload, and `grep -rn ruff .github/` returns no hits. There is no lint
step in CI at all, so "the gate that should have caught them did not" is
literally true -- the only enforcement is the convention that an agent runs
`ruff check` before finishing. `TestThisFileIsClean` below is a local
substitute for this one file, deliberately not a fleet CI change.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.verify_phases import (
    _mock_verify_green_phase,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "assemblyzero" / "workflows" / "testing" / "nodes" / "verify_phases.py"


class TestThisFileIsClean:
    def test_ruff_reports_nothing(self) -> None:
        """A program, not an inspection (rule 6).

        Scoped to this one file on purpose. A fleet-wide lint gate is a
        separate decision with a separate blast radius, and this issue does
        not license it.
        """
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", str(TARGET),
             "--output-format", "concise"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )

        if result.returncode == 2 and "No module named" in result.stderr:
            pytest.skip("ruff is not installed in this environment")
        assert result.returncode == 0, result.stdout or result.stderr

    def test_the_dead_router_import_is_gone(self) -> None:
        """#2690 owns the duplication; this owns the unused import."""
        source = TARGET.read_text(encoding="utf-8")

        assert "    route_by_exit_code,\n" not in source

    def test_the_constants_it_shared_are_still_imported(self) -> None:
        """The inline branching that DOES run still needs them."""
        source = TARGET.read_text(encoding="utf-8")

        for name in (
            "EXIT_INTERRUPTED", "EXIT_INTERNALERROR",
            "EXIT_USAGEERROR", "EXIT_NOTESTSCOLLECTED",
        ):
            assert name in source, name


class TestTheMockHonoursTheTarget:
    """`coverage_target` was read and ignored; it gates now.

    The second branch hardcoded 92.0% and routed onward unconditionally, so a
    rehearsal could never exercise a coverage shortfall -- which is exactly
    the situation that killed a real stage for 22 minutes on boostgauge #331
    (92.0% against a 95% target, #2644).
    """

    def _green(self, **extra) -> dict:
        state = {"iteration_count": 2, "skip_e2e": True}
        state.update(extra)
        return _mock_verify_green_phase(state)  # type: ignore[arg-type]

    def test_the_default_target_is_unchanged(self) -> None:
        """92.0 clears 90, so every existing caller keeps its old routing."""
        result = self._green()

        assert result["coverage_achieved"] == 92.0
        assert result["next_node"] == "N7_finalize"

    def test_an_explicit_90_behaves_the_same(self) -> None:
        assert self._green(coverage_target=90)["next_node"] == "N7_finalize"

    def test_a_higher_target_routes_to_test_additions(self) -> None:
        """Mirrors the live branch, which never routes a coverage gap to
        implementation (#2327): the cheapest way to raise statement coverage
        is to delete the uncovered code."""
        result = self._green(coverage_target=95)

        assert result["next_node"] == "N4c_augment_tests"

    def test_the_shortfall_route_advances_the_iteration_counter(self) -> None:
        """Load-bearing. `route_after_green` ends the N4c loop on
        `iteration_count >= max_iterations`, and N4c returns unconditionally
        to N5 -- so a shortfall that did not increment would rehearse an
        infinite loop instead of a shortfall."""
        result = self._green(coverage_target=95)

        assert result["iteration_count"] == 3

    def test_a_clearing_run_does_not_advance_it(self) -> None:
        assert self._green()["iteration_count"] == 2

    def test_the_first_iteration_still_fails_to_implementation(self) -> None:
        """Unchanged: a failing suite is an implementation gap, not a
        coverage one."""
        result = _mock_verify_green_phase(  # type: ignore[arg-type]
            {"iteration_count": 0, "skip_e2e": True, "coverage_target": 95}
        )

        assert result["next_node"] == "N4_implement_code"
        assert result["coverage_achieved"] == 75.0

    def test_a_missing_target_falls_back_rather_than_crashing(self) -> None:
        for value in (None, 0, ""):
            result = self._green(coverage_target=value)
            assert result["next_node"] == "N7_finalize", value


class TestTheReportAndTheNumberAgree:
    """The f-string had no placeholder because the number was never
    interpolated. A rehearsal that printed 92% while carrying something else
    in state would be a small lie of exactly the kind #2677 is about."""

    def test_the_printed_total_matches_the_recorded_coverage(self) -> None:
        result = _mock_verify_green_phase(  # type: ignore[arg-type]
            {"iteration_count": 2, "skip_e2e": True}
        )
        achieved = result["coverage_achieved"]

        assert f"{achieved:.0f}%" in result["green_phase_output"]
        assert "TOTAL                        60      5    92%" in (
            result["green_phase_output"]
        )
