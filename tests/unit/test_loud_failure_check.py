"""The loud-failure check (ADR 0236, standard 0034, #3580).

T1: the check fails on each non-compliant example in standard 0034 and passes
on each compliant one. T2: it runs in the unit tier, against the whole tree,
with a baseline that may only shrink.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from assemblyzero.core.halt_node import create_halt_node
from assemblyzero.core.loud_failure_check import (
    GRAPH_BUILDERS,
    KIND_HANDLER,
    KIND_TAG,
    KIND_UNROUTED,
    returns_error,
    routes_error_to_halt,
    scan,
    scan_graphs,
    scan_source,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "tests" / "fixtures" / "loud_failure_baseline.json"

#: The baseline's size the day it was written (#3580). Each #3581 batch lowers
#: this by the entries it removes; it is never raised.
BASELINE_CEILING = 324  # #3584 removed two; #3581 core batch 1 (#3724) four; testing batch 1 (#3811) three; spec N6 (#3887) one; requirements N0b (#3864) one


# ---------------------------------------------------------------------------
# T2: the tree against the baseline
# ---------------------------------------------------------------------------


def _tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--", "assemblyzero/*.py", "tools/*.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


@pytest.fixture(scope="module")
def tree_keys() -> set[str]:
    files = _tracked()
    assert len(files) > 100, "git ls-files found too few modules; the check would pass vacuously"
    return {f.key for f in scan(REPO_ROOT, files)}


@pytest.fixture(scope="module")
def baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def test_no_new_site(tree_keys, baseline):
    new = sorted(tree_keys - set(baseline["entries"]))
    assert new == [], (
        "a new site breaks the loud-failure standard (ADR 0236, standard 0034); "
        "fix it, do not baseline it:\n  " + "\n  ".join(new)
    )


def test_no_fixed_site_left_in_the_baseline(tree_keys, baseline):
    gone = sorted(set(baseline["entries"]) - tree_keys)
    assert gone == [], (
        "fixed sites still in the baseline; run tools/audit_loud_failure.py "
        "--write-baseline and lower BASELINE_CEILING:\n  " + "\n  ".join(gone)
    )


def test_the_baseline_only_shrinks(baseline):
    assert baseline["count"] == len(baseline["entries"])
    assert len(baseline["entries"]) <= BASELINE_CEILING


def test_every_baseline_entry_names_the_sweep(baseline):
    assert {e["issue"] for e in baseline["entries"].values()} == {3581}


def test_every_graph_module_is_listed():
    out = subprocess.run(
        ["git", "grep", "-l", "StateGraph(", "--", "assemblyzero/*.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    building = set()
    for rel in out:
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8-sig"))
        if any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "StateGraph" for n in ast.walk(tree)):
            building.add(rel[:-3].replace("/", "."))
    assert building == {module for module, _ in GRAPH_BUILDERS}


# ---------------------------------------------------------------------------
# T1: standard 0034's examples
# ---------------------------------------------------------------------------


def _kinds(source: str) -> list[str]:
    return [f.kind for f in scan_source("fixture.py", source)]


@pytest.mark.parametrize(
    "source",
    [
        "try:\n    run()\nexcept:\n    pass\n",
        "try:\n    run()\nexcept Exception:\n    log.warning('skipped')\n",
        "try:\n    run()\nexcept (ValueError, Exception) as e:\n    return None\n".replace("return None", "x = None"),
        "try:\n    run()\nexcept BaseException:\n    def later():\n        raise\n",
    ],
)
def test_a_swallowed_handler_is_found(source):
    assert _kinds(source) == [KIND_HANDLER]


@pytest.mark.parametrize(
    "source",
    [
        "try:\n    run()\nexcept Exception:\n    raise\n",
        "try:\n    run()\nexcept Exception as e:\n    raise RunFailed('step') from e\n",
        "try:\n    run()\nexcept Exception as e:\n    alert_operator(what='x', where='y', cause=str(e), consequence='z')\n    raise\n",
        "try:\n    run()\nexcept ValueError:\n    x = None\n",
    ],
)
def test_a_loud_or_narrow_handler_passes(source):
    assert _kinds(source) == []


def test_a_fail_open_tag_is_found_but_a_string_naming_it_is_not():
    assert _kinds("x = 1  # fail-open: continuing is fine\n") == [KIND_TAG]
    assert _kinds("MARKER = '# fail-open:'\n") == []


def test_keys_survive_an_unrelated_line_move():
    a = scan_source("m.py", "def f():\n    try:\n        g()\n    except Exception:\n        pass\n")
    b = scan_source("m.py", "\n\n\ndef f():\n    try:\n        g()\n    except Exception:\n        pass\n")
    assert [f.key for f in a] == [f.key for f in b] == ["m.py::f::swallowed_handler::1"]


def test_returns_error_and_routes_error_to_halt():
    node = ast.parse("def n(s):\n    return {'error_message': 'boom'}\n")
    quiet = ast.parse("def n(s):\n    return {'error_message': ''}\n")
    router = ast.parse("def r(s):\n    if s.get('error_message'):\n        return 'HALT'\n    return 'next'\n")
    blind = ast.parse("def r(s):\n    return 'next'\n")
    assert returns_error(node) and not returns_error(quiet)
    assert routes_error_to_halt(router, {"HALT"}) and not routes_error_to_halt(blind, {"HALT"})


# A fixture graph for scan_graphs: one node routed to HALT, one not.


class _S(TypedDict, total=False):
    error_message: str


def _failing_node(state: _S) -> dict:
    return {"error_message": "boom"}


def _route(state: _S) -> str:
    if state.get("error_message"):
        return "HALT"
    return "unrouted"


def build_fixture_graph() -> StateGraph:
    graph = StateGraph(_S)
    graph.add_node("routed", _failing_node)
    graph.add_node("unrouted", _failing_node)
    graph.add_node("HALT", create_halt_node("fixture"))
    graph.set_entry_point("routed")
    graph.add_conditional_edges("routed", _route, {"HALT": "HALT", "unrouted": "unrouted"})
    graph.add_edge("unrouted", END)
    graph.add_edge("HALT", END)
    return graph


def test_a_node_whose_source_cannot_be_read_stops_the_check():
    """ADR 0236: skipping it would pass a node the check never looked at."""
    from assemblyzero.core.loud_failure_check import (
        UnreadableGraphFunction,
        _function_tree,
    )

    with pytest.raises(UnreadableGraphFunction):
        _function_tree(len)  # a builtin has no Python source


def test_scan_graphs_finds_only_the_unrouted_node():
    findings = scan_graphs(REPO_ROOT, builders=((__name__, "build_fixture_graph"),))
    assert [(f.kind, f.key.split("::")[1]) for f in findings] == [(KIND_UNROUTED, "unrouted")]
