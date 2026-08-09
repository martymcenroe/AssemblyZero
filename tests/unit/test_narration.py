"""Graph-position narration (#2158): NODE and NEXT lines, atlas-sourced.

The wrapper narrates on node entry and must never cost a run: printing
failures degrade to silence, and an unknown node warns once by name.
"""
from __future__ import annotations

from assemblyzero.workflows import narration
from assemblyzero.workflows.narration import narrated

ATLAS = {
    "A_first": {
        "title": "first step",
        "ordinal": 1,
        "goal": "Do the first thing.",
        "teach": "x" * 50,
        "successors": {"B_second": "always"},
    },
    "B_second": {
        "title": "second step",
        "ordinal": 2,
        "goal": "Do the second thing.",
        "teach": "x" * 50,
        "successors": {"END": "always"},
    },
}


def test_node_and_next_lines_render_from_the_atlas(capsys):
    fn = narrated("A_first", lambda state: {"ok": True}, ATLAS, 2)

    result = fn({"anything": 1})

    out = capsys.readouterr().out
    assert result == {"ok": True}
    assert "NODE [1/2] first step -- Do the first thing." in out
    assert "NEXT second step (always)" in out


def test_successor_titles_come_from_the_atlas_end_stays_literal(capsys):
    fn = narrated("B_second", lambda state: state, ATLAS, 2)
    fn({})
    assert "NEXT END (always)" in capsys.readouterr().out


def test_an_unknown_node_warns_once_then_stays_silent(capsys):
    narration._warned.discard("Z_mystery")
    fn = narrated("Z_mystery", lambda state: state, ATLAS, 2)

    fn({})
    fn({})

    out = capsys.readouterr().out
    assert out.count("no atlas entry") == 1


def test_a_broken_atlas_entry_never_costs_the_node(capsys):
    """Narration failure degrades to silence; the node still runs."""
    broken = {"A_first": {"title": "t", "ordinal": 1}}  # no goal: KeyError

    fn = narrated("A_first", lambda state: "ran", broken, 1)

    assert fn({}) == "ran"
