"""`pr.commit_message_guard` is retired, and this is why (#2787).

The row claimed two halt sites in
`testing/nodes/validate_commit_message.py::validate_commit_message`, a
twelve-line substring check for `Closes #N`. It was the ONLY row in the `pr`
stage — the `pr: 1` the ratchet carried was this row and nothing else.

**No graph ran it.** #2787 built all four workflows and enumerated their
nodes; none declares a commit-message node. `grep` over `tools/` finds no
caller. The only caller in the package was the answer-key audit, invoking the
function directly to score itself, which is where the row's "ran 6, refused 0"
came from.

**And the repair the issue asked for is already the live behaviour.** The
code that actually opens the PR, `orchestrator/stages.py`, builds
`Closes #{issue_number}` into the title and the body itself. So the gate
could not be repaired into usefulness either: on the only path that exists
the trailer is an f-string, not model output, and cannot go missing.

Retired on #2753's reasoning, which retired two rows along with the unwired
`run_tests.py`: a row whose `action` column describes code that cannot
execute is a promise about nothing.

This file is the audit, not the story. Every claim above that a future change
could falsify is asserted below, so the retirement is re-runnable rather than
a paragraph somebody has to trust.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from assemblyzero.core.gate_registry import (
    ACTION_HALT,
    GATE_REGISTRY,
    registry_by_key,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RETIRED_KEY = "pr.commit_message_guard"
RETIRED_MODULE = (
    "assemblyzero.workflows.testing.nodes.validate_commit_message"
)

#: Every graph in the package, with the builder each module actually exposes.
#: The names differ per workflow, and getting one wrong makes the probe
#: return an AttributeError that reads exactly like "no such node".
BUILDERS = [
    ("testing", "assemblyzero.workflows.testing.graph",
     "build_testing_workflow"),
    ("requirements", "assemblyzero.workflows.requirements.graph",
     "create_requirements_graph"),
    ("implementation_spec", "assemblyzero.workflows.implementation_spec.graph",
     "create_implementation_spec_graph"),
    ("orchestrator", "assemblyzero.workflows.orchestrator.graph",
     "create_orchestration_graph"),
]


def _node_names(builder) -> list[str]:
    graph = builder()
    nodes = getattr(graph, "nodes", None)
    if nodes is None:  # a compiled graph rather than a builder's StateGraph
        nodes = graph.get_graph().nodes
    return sorted(nodes)


class TestNoGraphDeclaresACommitMessageNode:
    """The measurement the retirement rests on, re-run rather than recalled."""

    @pytest.mark.parametrize("name,module,fn", BUILDERS,
                             ids=[b[0] for b in BUILDERS])
    def test_the_graph_builds_and_names_no_commit_node(self, name, module, fn):
        builder = getattr(importlib.import_module(module), fn)
        names = _node_names(builder)
        assert names, f"{name}: built but declared no nodes at all"
        offenders = [n for n in names if "commit" in n.lower()]
        assert not offenders, (
            f"{name} declares {offenders}; if a commit-message node is back, "
            f"{RETIRED_KEY} needs to come back with it"
        )

    def test_the_module_itself_is_gone(self):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(RETIRED_MODULE)

    def test_the_nodes_package_no_longer_exports_it(self):
        nodes = importlib.import_module("assemblyzero.workflows.testing.nodes")
        assert "validate_commit_message" not in getattr(nodes, "__all__", ())
        assert not hasattr(nodes, "validate_commit_message")


class TestTheRowIsGoneAndTheStageIsEmpty:
    def test_the_key_is_not_in_the_registry(self):
        assert RETIRED_KEY not in registry_by_key()

    def test_the_pr_stage_has_no_halt_row_left(self):
        """The whole point of the ratchet's `pr` line, which is now absent.

        `halt_counts()` builds its dict from rows, so a stage with none
        simply has no key — that is what the regenerated baseline records,
        and it is a fall, not a gap.
        """
        halting = [
            g for g in GATE_REGISTRY
            if g.stage == "pr" and g.action == ACTION_HALT
        ]
        assert not halting, [g.key for g in halting]

    def test_no_row_anywhere_still_points_at_the_deleted_file(self):
        """A site key naming a file that no longer exists is how a retirement
        leaves a phantom behind; the walker cannot see it to complain."""
        for gate in GATE_REGISTRY:
            for site in gate.sites:
                assert "validate_commit_message" not in site, (
                    f"{gate.key} still names {site}"
                )


class TestThePipelineComputesTheTrailerItself:
    """Why the gate could not be repaired into usefulness.

    Asserted against the source rather than by rolling the orchestrator,
    because rolling it opens a PR. If this assertion ever fails, the reason
    for the retirement has changed and the row deserves reconsidering — which
    is exactly what a failure here should prompt.
    """

    def test_the_pr_title_and_body_carry_a_computed_closes(self):
        source = (
            REPO_ROOT / "assemblyzero/workflows/orchestrator/stages.py"
        ).read_text(encoding="utf-8", errors="replace")
        assert 'f"Closes #{issue_number}\\n\\n"' in source or (
            "Closes #{issue_number}" in source
        ), "the PR path no longer computes the trailer from issue_number"
