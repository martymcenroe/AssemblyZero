"""The implementation graph knows where it is, and says so (#2733).

`tests/unit/test_graph_atlas.py` already pins this atlas to the compiled graph
in both directions, for all three workflows. What it cannot check is the thing
#2733 was actually filed for: that entering a node in THIS stage writes a
`node.enter` record, so the report reads a machine-written position instead of
grepping node markers out of a prose log.

That matters more here than in the other two stages. Counted over boostgauge's
180 runs, 45 of the 135 failures were in the implementation stage, and the
furthest run in the whole record -- `run-issue4-172600`, three tests passing at
72% coverage -- stopped at N5.
"""

from __future__ import annotations

import ast
from pathlib import Path

from assemblyzero.speedrun.convergence import (
    EVENT_NODE_ENTER,
    furthest_by_run,
    read_records,
)
from assemblyzero.workflows.narration import narrated
from assemblyzero.workflows.testing.atlas import ATLAS, TOTAL_STEPS

GRAPH_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "assemblyzero" / "workflows" / "testing" / "graph.py"
)

#: Nodes that exist only to loop back, plus the exit. None is on the forward
#: path, so none consumes an ordinal.
OFF_PATH = {"N1_5_revise_test_plan", "N4c_augment_tests", "HALT"}


class TestTheAtlasIsWellFormed:
    def test_the_forward_path_is_numbered_without_gaps(self):
        ordinals = sorted(
            entry["ordinal"] for name, entry in ATLAS.items()
            if name not in OFF_PATH
        )
        assert ordinals == list(range(1, TOTAL_STEPS + 1))

    def test_total_steps_counts_the_forward_path_and_nothing_else(self):
        assert TOTAL_STEPS == len(ATLAS) - len(OFF_PATH)

    def test_a_loop_or_an_exit_consumes_no_ordinal(self):
        """A run that dies inside a loop node reports the forward node it came
        from as its furthest position, which is the truth about how far it
        got."""
        for name in OFF_PATH:
            assert ATLAS[name]["ordinal"] is None, name

    def test_every_entry_says_what_the_node_is_for(self):
        for name, entry in ATLAS.items():
            assert entry["title"].strip(), name
            assert entry["goal"].strip(), name
            assert entry["teach"].strip(), name


class TestEveryNodeIsWrapped:
    def test_the_graph_adds_no_node_that_skips_narration(self):
        """A node added with a bare `workflow.add_node(...)` narrates nothing
        and records nothing, and would be invisible to the report while
        looking perfectly healthy in the graph. Read off the source, because
        the wrapper deliberately borrows the wrapped function's `__name__` and
        so leaves no marker to inspect at runtime."""
        tree = ast.parse(GRAPH_SOURCE.read_text(encoding="utf-8"))

        # The one legitimate `add_node` is inside `_add` itself, which is the
        # helper that does the wrapping. Everything outside it is a node that
        # would go in unwrapped.
        helpers = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_add"
        ]
        assert len(helpers) == 1, "expected exactly one _add helper"
        inside_helper = {
            node.lineno for node in ast.walk(helpers[0])
            if isinstance(node, ast.Call)
        }

        bare = sorted(
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_node"
            and node.lineno not in inside_helper
        )
        assert bare == [], (
            f"add_node called directly at line(s) {bare}; use the local _add "
            "helper so the node narrates and records (#2733)"
        )

    def test_the_helper_adds_one_node_per_atlas_entry(self):
        tree = ast.parse(GRAPH_SOURCE.read_text(encoding="utf-8"))
        added = {
            node.args[0].value for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == "_add"
            and node.args and isinstance(node.args[0], ast.Constant)
        }
        assert added == set(ATLAS)


class TestEnteringANodeWritesTheRecord:
    def test_it_records_the_node_the_stage_and_the_ordinal(self, tmp_path):
        wrapped = narrated(
            "N5_verify_green", lambda state: {"ok": True},
            ATLAS, TOTAL_STEPS, stage="impl",
        )
        assert wrapped({"repo_root": str(tmp_path)}) == {"ok": True}

        records, unreadable = read_records(tmp_path)
        assert unreadable == 0
        entries = [r for r in records if r["event"] == EVENT_NODE_ENTER]
        assert len(entries) == 1
        assert entries[0]["stage"] == "impl"
        assert entries[0]["node"] == "N5_verify_green"
        assert entries[0]["ordinal"] == ATLAS["N5_verify_green"]["ordinal"]
        assert entries[0]["total"] == TOTAL_STEPS

    def test_the_furthest_node_is_readable_from_the_record(self, tmp_path, monkeypatch):
        """The whole point: how far into the implementation stage a run got,
        without parsing a log. `run-issue4-172600` is the shape -- scaffolded,
        implemented, and stopped in the green loop."""
        monkeypatch.setenv("SPEEDRUN_RUN_TAG", "run-issue4-172600")
        from assemblyzero.speedrun.convergence import record_stage_enter

        record_stage_enter(tmp_path, "impl", 3, 5)
        for node in ("N2_scaffold_tests", "N4_implement_code", "N5_verify_green"):
            narrated(node, lambda state: {}, ATLAS, TOTAL_STEPS, stage="impl")(
                {"repo_root": str(tmp_path)}
            )

        records, _ = read_records(tmp_path)
        assert furthest_by_run(records) == {
            "run-issue4-172600": ("impl", "N5_verify_green")
        }

    def test_a_run_with_no_repo_root_records_nothing_and_still_runs(self):
        """Narration and recording never cost a run. A node invoked with no
        repository to write to returns its result and files nothing."""
        wrapped = narrated(
            "N0_load_lld", lambda state: {"ok": True},
            ATLAS, TOTAL_STEPS, stage="impl",
        )
        assert wrapped({}) == {"ok": True}
