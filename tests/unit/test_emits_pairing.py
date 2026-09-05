"""A row must name the return it actually describes (#2776).

The registry's two-way check proves every walked site is named by a row and
every site a row names exists. Both hold while a row points at the **wrong
return**, and the issue's six-line reproduction is why:

Take a function with four halting returns, registered `::0` through `::3`.
Retire the third gate and add a new return at the end. The function has four
returns again, index 3 now holds the NEW one, and the row that owned the old
fourth return still names index 3. No phantom — index 3 exists. One
unregistered site — index 2, which shifted down. `--check` reports one
finding and it is the wrong one, while a row sits attached to a return it has
nothing to do with.

`mismatched_emits` compares the row's message to THAT SITE's head, which is
the only comparison that catches it.

**Two wider rules were measured first and rejected, and the numbers are here
so nobody re-proposes them.**

*`emits`-in-head over every named site* fails **42 of 128** readable sites. A
row covering five returns can only name one of their messages, so most of the
42 are correct rows. The issue measured 56 of 151 on an older tree.

*A source-text rule* — is `emits` written in the function the site sits in, or
in what `decided_in` names — reads **0 of 81** rows, and is worthless for this
purpose. Both the right and the wrong return live in the SAME function, so it
passes the exact scenario above. It was built, measured, and deleted. A check
that cannot fail on its own case is the defect, not the guard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.core.gate_registry import (
    ACTION_HALT,
    EMITS_HEAD_EXEMPTIONS,
    GATE_REGISTRY,
    JUDGES_MODEL_OUTPUT,
    Gate,
    mismatched_emits,
    registry_by_key,
    scan_halt_sites,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def walked():
    sites, coverage = scan_halt_sites(REPO_ROOT)
    assert coverage.files_scanned > 0
    return sites


class TestTheTreeIsPaired:
    def test_no_single_site_row_names_someone_elses_return(self, walked):
        bad = mismatched_emits(walked)
        assert not bad, "\n".join(
            f"{key}: emits {emits!r} but its only site's head is {head[:70]!r}"
            for key, emits, head in bad
        )

    def test_the_check_covers_most_of_the_registry(self, walked):
        """A guard is only worth what it looks at, so the denominator is
        asserted rather than left to be discovered as near-zero later."""
        checked = [
            g for g in GATE_REGISTRY
            if len(g.sites) == 1 and g.key not in EMITS_HEAD_EXEMPTIONS
        ]
        with_sites = [g for g in GATE_REGISTRY if g.sites]
        assert len(checked) >= 45, (
            f"only {len(checked)} of {len(with_sites)} rows with sites are "
            f"under the pairing check; it has stopped being worth running"
        )


class TestItCatchesTheIssuesOwnScenario:
    """Discrimination, on the reproduction #2776 wrote out.

    Every check retired this week was one that could not fail. This one is
    watched failing on the case it exists for, with a synthetic registry so
    the real one is untouched.
    """

    def _tree(self, tmp_path: Path) -> Path:
        module = tmp_path / "assemblyzero" / "workflows" / "fake" / "node.py"
        module.parent.mkdir(parents=True)
        module.write_text(
            "\n".join(
                [
                    "def n(state):",
                    "    if state.get('a'):",
                    "        return {'error_message': 'ALPHA: first'}",
                    "    if state.get('b'):",
                    "        return {'error_message': 'BETA: second'}",
                    "    return {'error_message': ''}",
                ]
            ),
            encoding="utf-8",
        )
        return tmp_path

    def _row(self, emits: str, index: int) -> Gate:
        return Gate(
            "fake.row", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT, emits,
            (f"assemblyzero/workflows/fake/node.py::n::return::{index}",),
        )

    def test_a_row_naming_the_wrong_return_is_caught(self, tmp_path):
        sites, _ = scan_halt_sites(self._tree(tmp_path))
        bad = mismatched_emits(sites, (self._row("ALPHA", 1),))
        assert [k for k, _, _ in bad] == ["fake.row"]
        assert bad[0][2] == "BETA: second", bad

    def test_the_same_row_naming_its_own_return_passes(self, tmp_path):
        sites, _ = scan_halt_sites(self._tree(tmp_path))
        assert mismatched_emits(sites, (self._row("ALPHA", 0),)) == []

    def test_the_two_way_check_would_not_have_noticed(self, tmp_path):
        """Why this check had to exist: the wrong name is not a phantom.

        The site the row points at is real, so `phantoms` is empty and
        nothing in the existing pair of checks fires.
        """
        from assemblyzero.core.gate_registry import phantoms

        sites, _ = scan_halt_sites(self._tree(tmp_path))
        assert phantoms(sites, (self._row("ALPHA", 1),)) == []


class TestTheExemptionsAreHonest:
    def test_each_names_a_real_row(self):
        keys = registry_by_key()
        for key in EMITS_HEAD_EXEMPTIONS:
            assert key in keys, f"{key} is exempted but not in the registry"

    def test_each_says_why(self):
        for key, reason in EMITS_HEAD_EXEMPTIONS.items():
            assert len(reason.strip()) > 40, f"{key}: {reason!r}"

    def test_each_is_a_walker_defect_and_not_a_row_defect(self, walked):
        """An exemption is only legitimate while the HEAD is what is wrong.

        Every entry is a row whose site head fails to carry the message the
        code really emits -- an interpolation that leaves no words, or a call
        whose argument the walker reads instead of its callee. #2814 fixes
        those readings; when one lands, its row stops needing an exemption
        and this asserts the entry is gone.
        """
        by_key = {s.key: s for s in walked}
        for key in EMITS_HEAD_EXEMPTIONS:
            gate = registry_by_key()[key]
            site = by_key.get(gate.sites[0])
            assert site is not None, f"{key} exempted but its site is gone"
            assert gate.emits not in site.head, (
                f"{key} no longer needs its exemption -- its head now carries "
                f"{gate.emits!r}. Remove the entry (#2814)."
            )
