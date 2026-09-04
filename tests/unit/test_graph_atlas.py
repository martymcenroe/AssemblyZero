"""The graph atlas cannot drift from the compiled graph (#2157).

The atlas is the single source every narration, tutorial, and quiz feature
reads. Its only failure mode is silent rot when someone rewires a graph,
so these tests build the REAL compiled StateGraph and compare: every graph
node is in the atlas, every atlas node is in the graph, and every successor
the atlas claims is an actual edge (and vice versa). A gap fails naming
the missing entry.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.implementation_spec.atlas import (
    ATLAS as SPEC_ATLAS,
    TOTAL_STEPS as SPEC_TOTAL,
)
from assemblyzero.workflows.implementation_spec.graph import (
    create_implementation_spec_graph,
)
from assemblyzero.workflows.requirements.atlas import (
    ATLAS as REQ_ATLAS,
    TOTAL_STEPS as REQ_TOTAL,
)
from assemblyzero.workflows.requirements.graph import create_requirements_graph
from assemblyzero.workflows.testing.atlas import (
    ATLAS as IMPL_ATLAS,
    TOTAL_STEPS as IMPL_TOTAL,
)
from assemblyzero.workflows.testing.graph import build_testing_workflow

_BOUNDARY = {"__start__", "__end__"}


def _graph_shape(builder):
    """(nodes, edges) of the compiled graph, with __end__ rendered as END.

    Accepts either an uncompiled StateGraph (requirements) or an
    already-compiled one (implementation_spec returns CompiledStateGraph).
    """
    compiled = builder.compile() if hasattr(builder, "compile") else builder
    drawable = compiled.get_graph()
    nodes = {n for n in drawable.nodes if n not in _BOUNDARY}
    edges: set[tuple[str, str]] = set()
    for edge in drawable.edges:
        if edge.source in _BOUNDARY:
            continue
        target = "END" if edge.target == "__end__" else edge.target
        edges.add((edge.source, target))
    return nodes, edges


CASES = [
    ("requirements", create_requirements_graph, REQ_ATLAS, REQ_TOTAL),
    ("implementation_spec", create_implementation_spec_graph, SPEC_ATLAS,
     SPEC_TOTAL),
    # #2733: the third graph, and the last to get an atlas. It is the stage
    # where runs get furthest, so its node positions are the ones the report
    # most needs from a record rather than from a log grep.
    ("testing", build_testing_workflow, IMPL_ATLAS, IMPL_TOTAL),
]


@pytest.mark.parametrize("name,factory,atlas,total", CASES,
                         ids=[c[0] for c in CASES])
class TestAtlasMatchesGraph:
    def test_every_graph_node_is_in_the_atlas(self, name, factory, atlas, total):
        nodes, _ = _graph_shape(factory())
        missing = nodes - set(atlas)
        assert not missing, f"{name}: graph nodes absent from atlas: {missing}"

    def test_every_atlas_node_is_in_the_graph(self, name, factory, atlas, total):
        nodes, _ = _graph_shape(factory())
        stale = set(atlas) - nodes
        assert not stale, f"{name}: atlas entries no longer in the graph: {stale}"

    def test_every_atlas_successor_is_a_real_edge(self, name, factory, atlas, total):
        _, edges = _graph_shape(factory())
        for node, entry in atlas.items():
            for successor in entry["successors"]:
                assert (node, successor) in edges, (
                    f"{name}: atlas claims {node} -> {successor}, "
                    "which is not an edge in the compiled graph"
                )

    def test_every_real_edge_is_an_atlas_successor(self, name, factory, atlas, total):
        _, edges = _graph_shape(factory())
        for source, target in edges:
            assert target in atlas[source]["successors"], (
                f"{name}: the graph has {source} -> {target}, "
                "which the atlas does not name"
            )


@pytest.mark.parametrize("name,factory,atlas,total", CASES,
                         ids=[c[0] for c in CASES])
class TestAtlasQuality:
    def test_goals_and_teach_text_are_present_and_plain(self, name, factory,
                                                        atlas, total):
        """Plain-English rule: the operator must never need a code dive to
        understand a narration line built from these strings."""
        for node, entry in atlas.items():
            assert entry["title"].strip(), f"{name}:{node} has no title"
            assert len(entry["goal"].strip()) > 15, f"{name}:{node} goal too thin"
            assert len(entry["teach"].strip()) > 40, f"{name}:{node} teach too thin"

    def test_every_successor_names_its_condition(self, name, factory, atlas, total):
        for node, entry in atlas.items():
            for successor, condition in entry["successors"].items():
                assert condition.strip(), (
                    f"{name}:{node} -> {successor} has no condition text"
                )

    def test_ordinals_walk_the_forward_path(self, name, factory, atlas, total):
        ordinals = sorted(
            e["ordinal"] for e in atlas.values() if e["ordinal"] is not None
        )
        assert ordinals == list(range(1, total + 1)), (
            f"{name}: ordinals must be exactly 1..{total}, got {ordinals}"
        )
        assert atlas["HALT"]["ordinal"] is None, (
            f"{name}: HALT is an exit, never a step"
        )
