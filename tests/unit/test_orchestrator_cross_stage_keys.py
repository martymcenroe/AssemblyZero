"""Values a stage writes for a later stage must survive the node boundary.

Boostgauge #7, 2026-07-31: the pr stage recorded the implementation PR, the
cleanup stage read back an empty string, PR #159 was never merged, and the run
exited 0 saying "All stages passed". The attempt branch got the design and not
the code.

The graph is `StateGraph(OrchestrationState)`, so LangGraph builds its channels
from that TypedDict's annotations and discards any key it has no channel for.
#2011 wrote `state["impl_pr_url"]` without declaring it. A TypedDict does not
validate at runtime, so nothing raised anywhere along the path.

The existing cleanup tests could not catch it: they assign `impl_pr_url` by hand
and assert the consumer merges it, verifying the reader while assuming the
writer. These cover the boundary instead -- and the declaration guard covers
every future key, not just this one.
"""

import ast
from pathlib import Path

import pytest

from assemblyzero.workflows.orchestrator import stages
from assemblyzero.workflows.orchestrator.state import OrchestrationState

STAGES_PY = Path(stages.__file__)


def _keys_assigned_to_state(source: Path) -> set[str]:
    """Every literal key assigned as `state["..."] = ...` in a module."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "state"
                and isinstance(target.slice, ast.Constant)
                and isinstance(target.slice.value, str)
            ):
                found.add(target.slice.value)
    return found


class TestEveryCrossStageKeyIsDeclared:
    def test_impl_pr_url_is_a_declared_field(self):
        """The specific regression: undeclared, so LangGraph dropped it."""
        assert "impl_pr_url" in OrchestrationState.__annotations__

    def test_no_stage_writes_an_undeclared_key(self):
        """The class of bug, not the instance. A key with no channel is thrown
        away silently, and the run still reports success -- so this must fail a
        test rather than an arc."""
        assigned = _keys_assigned_to_state(STAGES_PY)
        declared = set(OrchestrationState.__annotations__)
        undeclared = assigned - declared

        assert not undeclared, (
            f"stages.py writes state keys that OrchestrationState does not "
            f"declare: {sorted(undeclared)}. LangGraph builds channels from "
            f"those annotations and discards everything else, so these values "
            f"never reach the stage meant to read them."
        )

    def test_the_guard_actually_inspects_something(self):
        """A guard that parsed nothing would pass forever. Pin that it really
        does find the cross-stage writes it is meant to police."""
        assigned = _keys_assigned_to_state(STAGES_PY)
        assert "impl_pr_url" in assigned, (
            "the AST scan found no `state[\"impl_pr_url\"] = ...` write, so the "
            "guard above is not looking at what it claims to"
        )


class TestTheReaderAndWriterAgree:
    def test_the_pr_stage_writes_the_key_cleanup_reads(self):
        """Producer and consumer are in different functions hundreds of lines
        apart; a rename on one side is invisible to the other."""
        source = STAGES_PY.read_text(encoding="utf-8")
        assert 'state["impl_pr_url"] = ' in source
        assert 'state.get("impl_pr_url"' in source


@pytest.mark.parametrize("key", ["pr_url", "lld_pr_url", "impl_pr_url", "base_branch"])
def test_pr_carrying_keys_stay_declared(key):
    """These four are what an arc accumulates on. Losing any one reproduces a
    failure this campaign has already paid for twice."""
    assert key in OrchestrationState.__annotations__
