"""Graph-position narration (#2158): NODE and NEXT lines, atlas-sourced.

The wrapper narrates on node entry. Since #3585 a node with no atlas entry
fails the graph build, and a narration failure alerts and stops the node.
"""
from __future__ import annotations

import pytest

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


def test_an_unknown_node_fails_the_graph_build():
    """#3585: it used to warn once and run; a graph cannot be built with a
    node its atlas does not describe."""
    with pytest.raises(ValueError, match="Z_mystery"):
        narrated("Z_mystery", lambda state: state, ATLAS, 2)


def test_a_broken_atlas_entry_stops_the_node(capsys, operator_alerts):
    """#3585: a narration failure alerts and raises; the node does not run."""
    broken = {"A_first": {"title": "t", "ordinal": 1}}  # no goal: KeyError

    fn = narrated("A_first", lambda state: "ran", broken, 1)

    with pytest.raises(KeyError):
        fn({})
    assert len(operator_alerts) == 1
