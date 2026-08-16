"""The memory ceiling is a number the operator can predict (#2296).

Operator report, 2026-08-13, launching the boostgauge #7 roll: "the machine
health thing is still too tight."

    09:57:43  refused: memory 96.1% against the 90.0% ceiling
    09:57:49  six seconds later, after closing some browser windows, it passed

The gate was accurate and the remediation was cheap, but this was at least the
second interruption of the operator's flow on a workstation that routinely runs
many concurrent agent sessions plus browsers.

Operator ruling 2026-08-15: raise it to 94.0. Deliberately NOT tunable and NOT
derived from a measured baseline, both of which were on the table -- the
failure being avoided is an interrupted launch, and a ceiling the operator can
predict is worth more than one that adapts. A moving ceiling makes "will this
launch start" unanswerable in advance, which is the question the number exists
to answer.

The gate itself was never in question, and this narrows the band it refuses in
rather than removing it. These fixtures pin both halves.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from assemblyzero.speedrun.box_health import MEMORY_ABORT_PERCENT

RUNBOOK = (
    Path(__file__).resolve().parents[2]
    / "docs" / "runbooks" / "0952-speedrun-operator-solo.md"
)


class TestTheRuling:
    def test_the_ceiling_is_the_ruled_value(self):
        assert MEMORY_ABORT_PERCENT == 94.0

    def test_the_2026_08_13_refusal_would_still_refuse(self):
        """96.1% was a real reading on a real launch. Raising the ceiling must
        not have raised it past the case that prompted the report."""
        assert 96.1 > MEMORY_ABORT_PERCENT

    def test_the_band_is_narrowed_not_removed(self):
        """Between the old and new ceilings a launch now proceeds; above the
        new one it still refuses. Both halves, so 'narrows' is checkable."""
        assert 90.0 < MEMORY_ABORT_PERCENT < 100.0
        assert 92.0 <= MEMORY_ABORT_PERCENT  # the old ceiling no longer refuses

    def test_it_is_a_constant_not_a_setting(self):
        """'Not tunable' is the ruling, not an oversight. A future flag would
        reintroduce exactly the unpredictability the ruling rejected."""
        import inspect

        from assemblyzero.speedrun import box_health

        source = inspect.getsource(box_health)
        assert "MEMORY_ABORT_PERCENT = 94.0" in source
        assert "--memory-ceiling" not in source
        assert "AZ_MEMORY_CEILING" not in source


class TestTheGateStillRefuses:
    """The gate was accurate both times it fired. It must still fire."""

    @pytest.mark.parametrize("reading", [94.1, 96.1, 99.9])
    def test_a_starved_box_is_refused(self, reading):
        assert reading > MEMORY_ABORT_PERCENT

    @pytest.mark.parametrize("reading", [60.0, 88.0, 90.0, 93.9])
    def test_an_ordinary_box_is_not_refused(self, reading):
        assert reading <= MEMORY_ABORT_PERCENT


class TestTheRunbookCarriesTheNumber:
    """'Record the ruling in runbook 0952 alongside the preflight's other
    refusals' -- so the next operator learns it from the runbook rather than
    from a traceback."""

    def _text(self) -> str:
        return RUNBOOK.read_text(encoding="utf-8")

    def test_the_runbook_states_the_current_ceiling(self):
        assert "94%" in self._text()

    def test_the_runbook_does_not_still_claim_the_old_one(self):
        """The specific rot: a runbook that names a number the code no longer
        uses sends the operator to the wrong conclusion."""
        health_rows = [
            line for line in self._text().splitlines()
            if "This machine is not healthy enough" in line
        ]
        assert health_rows, "the health refusal row is missing from the runbook"
        assert "above 90%" not in health_rows[0]

    def test_the_number_in_the_runbook_matches_the_code(self):
        """Two copies of one fact. Pinned so they cannot drift, which is the
        failure #2384 was filed about one module over."""
        health_rows = [
            line for line in self._text().splitlines()
            if "This machine is not healthy enough" in line
        ]
        found = re.findall(r"(\d+)%", health_rows[0])
        assert str(int(MEMORY_ABORT_PERCENT)) in found, found

    def test_the_runbook_names_the_ruling(self):
        assert "#2296" in self._text()

    def test_the_runbook_says_what_to_do_about_it(self):
        """A refusal row that states a threshold without a remedy is a
        traceback with better formatting."""
        health_rows = [
            line for line in self._text().splitlines()
            if "This machine is not healthy enough" in line
        ]
        assert "browser" in health_rows[0].lower()
