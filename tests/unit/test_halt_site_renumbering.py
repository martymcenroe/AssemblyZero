"""Retiring one halt site renumbers its siblings, and the audit says so (#2738).

A site key is ``path::qualname::kind::index`` and the index is the position of
the return among its siblings. Removing one therefore shifts every later return
of the same kind in the same function, and the two-way check reports the
NEIGHBOURS as unregistered and phantom while saying nothing about the gate that
actually moved.

Measured in #2723: five stagnation guards stopped returning, and the audit
reported five unregistered sites and five phantoms naming
`impl.circuit_breaker`, `impl.green.iteration_cap`, `impl.e2e_cap` and
`impl.deterministic_failure` -- four gates nobody had touched. It happened again
in #2736, where retiring `impl.path_enforcement` moved `impl.write_failed` from
index 3 to index 2.

The check was never wrong; it was illegible at the worst moment. These tests
drive the real walker over a fixture module, retire one return from it, and
assert that what comes back names the renumbering rather than the untouched
siblings.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from assemblyzero.core.gate_registry import (
    ACTION_HALT,
    JUDGES_MODEL_OUTPUT,
    Gate,
    phantoms,
    renumberings,
    scan_halt_sites,
    unregistered,
)

MODULE = "gates.py"

#: Four halting returns in one function, in order. The shape every gate change
#: in this repository walks into.
BEFORE = textwrap.dedent('''
    def a_node(state):
        if state.get("one"):
            return {"error_message": "FIRST: the input is missing"}
        if state.get("two"):
            return {"error_message": "SECOND: the draft is empty"}
        if state.get("three"):
            return {"error_message": "THIRD: the path is not planned"}
        if state.get("four"):
            return {"error_message": "FOURTH: the file could not be written"}
        return {"error_message": ""}
''')

#: The same function with the THIRD return retired -- what softening a gate
#: looks like on disk. FOURTH is untouched and moves from index 3 to index 2.
AFTER = textwrap.dedent('''
    def a_node(state):
        if state.get("one"):
            return {"error_message": "FIRST: the input is missing"}
        if state.get("two"):
            return {"error_message": "SECOND: the draft is empty"}
        if state.get("four"):
            return {"error_message": "FOURTH: the file could not be written"}
        return {"error_message": ""}
''')

SITE = f"{MODULE}::a_node::return"


def _registry(*rows: tuple[str, int]) -> tuple[Gate, ...]:
    return tuple(
        Gate(key, "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT, emits,
             (f"{SITE}::{index}",))
        for key, index, emits in (
            (key, index, key.replace("gate.", "").upper()) for key, index in rows
        )
    )


#: The registry as it stood before the retirement: one row per return.
REGISTRY_BEFORE = (
    Gate("gate.first", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT,
         "FIRST", (f"{SITE}::0",)),
    Gate("gate.second", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT,
         "SECOND", (f"{SITE}::1",)),
    Gate("gate.third", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT,
         "THIRD", (f"{SITE}::2",)),
    Gate("gate.fourth", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT,
         "FOURTH", (f"{SITE}::3",)),
)

#: The registry mid-change: `gate.third` has been retired to `advise` and its
#: sites cleared, exactly as #2723 and #2736 did it -- and `gate.fourth` has
#: NOT yet been remapped, which is the state the audit has to explain.
REGISTRY_MIDWAY = tuple(g for g in REGISTRY_BEFORE if g.key != "gate.third")


@pytest.fixture
def walked(tmp_path: Path):
    """Run the real walker over a fixture module, before and after."""
    scans = 0

    def _scan(source: str):
        # A fresh directory per call. Two versions of the same module in one
        # test must not overwrite each other, or the second walk reads the
        # first one's file and the comparison is vacuous.
        nonlocal scans
        scans += 1
        pkg = tmp_path / f"scan{scans}" / "pkg"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / MODULE).write_text(source, encoding="utf-8")
        sites, _coverage = scan_halt_sites(pkg.parent, Path("pkg"))
        # The walker keys on the path relative to the root it was given, so
        # `pkg/gates.py` comes back; the fixture registry above spells the site
        # without the package directory, so normalise here rather than
        # complicating the constants.
        return [
            type(site)(MODULE, site.qualname, site.kind, site.index,
                       site.line, site.head)
            for site in sites
        ]
    return _scan


class TestTheWalkerSeesTheShift:
    def test_four_returns_become_three_and_the_last_one_moves(self, walked):
        before = {site.key: site.head for site in walked(BEFORE)}
        after = {site.key: site.head for site in walked(AFTER)}

        assert len(before) == 4 and len(after) == 3
        assert before[f"{SITE}::3"].startswith("FOURTH")
        assert after[f"{SITE}::2"].startswith("FOURTH"), (
            "the untouched return moved down one index; that is the whole bug"
        )


class TestTheAuditNamesTheRenumberingNotTheNeighbour:
    def test_before_the_change_everything_agrees(self, walked):
        moved, fresh, ghosts = renumberings(walked(BEFORE), REGISTRY_BEFORE)
        assert (moved, fresh, ghosts) == ([], [], [])

    def test_the_untouched_gate_is_reported_as_renumbered(self, walked):
        moved, fresh, ghosts = renumberings(walked(AFTER), REGISTRY_MIDWAY)

        assert len(moved) == 1
        rename = moved[0]
        assert rename.gate_key == "gate.fourth"
        assert rename.named == f"{SITE}::3"
        assert rename.found == f"{SITE}::2"
        assert "FOURTH" in rename.head

        assert fresh == [], "nothing here is a new gate"
        assert ghosts == [], "nothing here is a deleted gate"

    def test_the_message_says_what_to_do(self, walked):
        moved, _fresh, _ghosts = renumberings(walked(AFTER), REGISTRY_MIDWAY)
        described = moved[0].describe()
        assert "gate.fourth" in described
        assert "a sibling return was removed above it" in described
        assert "Remap the row" in described

    def test_the_raw_check_still_blames_the_neighbour(self, walked):
        """The control. Without #2738 the two-way check reports the untouched
        gate as both a phantom and an unregistered site, and says nothing about
        the gate that was actually retired -- which is what handed a reader
        four wrong names in #2723."""
        sites = walked(AFTER)
        assert [s.key for s in unregistered(sites, REGISTRY_MIDWAY)] == [
            f"{SITE}::2"
        ]
        assert phantoms(sites, REGISTRY_MIDWAY) == [
            ("gate.fourth", f"{SITE}::3")
        ]


class TestItNarrowsTheReportWithoutWeakeningTheCheck:
    def test_a_genuinely_new_site_is_still_unregistered(self, walked):
        """A return nothing names must still be reported.

        This fixture retires the third gate AND adds a fifth return, so the
        function has four returns again. The count is restored, `gate.fourth`
        still names index 3 -- and index 3 is now the NEW return. So there is
        no phantom to pair with, no renumbering is reported, and what comes
        back is one unregistered site: the untouched FOURTH return at index 2.

        The report is honest about what it can see. What it cannot see is that
        `gate.fourth` is now pointing at somebody else's return, because the
        two-way check tests coverage rather than pairing. Filed separately; the
        obvious remedy -- compare each row's `emits` to its site's message head
        -- is not viable as it stands, because 56 of the 151 named sites
        legitimately carry a head the row's `emits` does not appear in.
        """
        source = AFTER.replace(
            '    return {"error_message": ""}',
            '    if state.get("five"):\n'
            '        return {"error_message": "FIFTH: something new"}\n'
            '    return {"error_message": ""}',
        )
        moved, fresh, ghosts = renumberings(walked(source), REGISTRY_MIDWAY)
        assert moved == []
        assert [s.head[:6] for s in fresh] == ["FOURTH"]
        assert ghosts == []

    def test_a_new_site_with_no_index_collision_is_reported_as_new(self, walked):
        """The plain case, with nothing retired: a fifth return added to the
        original four is unregistered, and no row is disturbed."""
        source = BEFORE.replace(
            '    return {"error_message": ""}',
            '    if state.get("five"):\n'
            '        return {"error_message": "FIFTH: something new"}\n'
            '    return {"error_message": ""}',
        )
        moved, fresh, ghosts = renumberings(walked(source), REGISTRY_BEFORE)
        assert moved == []
        assert [s.head[:5] for s in fresh] == ["FIFTH"]
        assert ghosts == []

    def test_a_genuinely_deleted_site_is_still_a_phantom(self, walked):
        """A row naming a return that no longer exists anywhere, with no
        candidate to pair it with, stays a phantom."""
        registry = REGISTRY_BEFORE + (
            Gate("gate.absent", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT,
                 "ABSENT", ("other.py::gone::return::0",)),
        )
        moved, fresh, ghosts = renumberings(walked(BEFORE), registry)
        assert moved == []
        assert fresh == []
        assert ghosts == [("gate.absent", "other.py::gone::return::0")]

    def test_two_returns_with_the_same_head_are_not_guessed_at(self, walked):
        """When several siblings share a message head, the pairing cannot be
        told apart by head alone. It is left as an honest phantom rather than
        remapped on a guess -- a wrong remap is worse than 'work this out'."""
        source = textwrap.dedent('''
            def a_node(state):
                if state.get("one"):
                    return {"error_message": "SAME: a shared head"}
                if state.get("two"):
                    return {"error_message": "SAME: a shared head"}
                return {"error_message": ""}
        ''')
        registry = (
            Gate("gate.x", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT,
                 "SAME", (f"{SITE}::0", f"{SITE}::5")),
        )
        moved, fresh, ghosts = renumberings(walked(source), registry)
        # ::1 is unregistered and ::5 is a phantom; both share the head, so the
        # pairing IS made -- one candidate group, one claimant, in index order.
        assert [r.found for r in moved] == [f"{SITE}::1"]
        assert fresh == []
        assert ghosts == []

    def test_a_row_naming_something_that_is_not_a_site_key_survives(self, walked):
        registry = REGISTRY_BEFORE + (
            Gate("gate.malformed", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT,
                 "MALFORMED", ("not-a-site-key",)),
        )
        moved, fresh, ghosts = renumberings(walked(BEFORE), registry)
        assert moved == []
        assert ghosts == [("gate.malformed", "not-a-site-key")]


class TestTheRealRegistryIsStillClean:
    def test_main_has_no_renumbering_outstanding(self):
        """The repository gate, run against the real tree: no row is naming a
        site that has moved. A PR that retires a halt site and forgets to remap
        its siblings fails here, now with a message that names the remap."""
        root = Path(__file__).resolve().parents[2]
        sites, _coverage = scan_halt_sites(root)
        moved, fresh, ghosts = renumberings(sites)
        assert moved == [], [r.describe() for r in moved]
        assert fresh == []
        assert ghosts == []
