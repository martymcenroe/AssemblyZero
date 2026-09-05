"""Every key the impl stage hands its sub-workflow is a declared channel (#2847).

LangGraph builds a graph's state channels from the schema it is given.
A key in the invoke payload that the schema does not declare is discarded
before the first node runs -- silently, with the payload otherwise intact, so
the sender has every reason to believe it arrived. `TestingWorkflowState`
already carries three comments saying exactly this about fields that were
lost that way (#2018, #2050, #2679).

`run_impl_stage` was sending three such keys:

* `retry_mode` (#1941, and RESUMED from #2845) -- so `is_regeneration` always
  read None, and on run-issue4-113418 the red phase refused a worktree
  carved from run 15's 48-of-52 implementation as green-at-red, because
  `_implementation_already_exists` gates on this field and saw it empty;
* `config_mock_mode` (#2849) -- the SPEC workflow's field name; the testing
  nodes read `mock_mode`, so a --mock rehearsal ran this stage for real;
* `spec_path` (#2848) -- read by nothing; N0 finds the spec its own way.

The first test here is the general guard: it reads the payload the stage
actually sends and the schema the sub-workflow actually declares, and fails
on any difference. That is `test_scaffold_route_carried.py`'s rule -- the
schema IS the merge contract -- applied to the orchestrator's side of the
boundary. The rest prove the value survives into a node, not just that the
name is in a TypedDict.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.core.retry_mode import RESUMED
from assemblyzero.workflows.orchestrator import stages
from assemblyzero.workflows.testing.state import TestingWorkflowState


def _completed(returncode=0, stdout="", stderr=""):
    # mock-ok: subprocess boundary, and a REAL CompletedProcess (standard 0024).
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _quiet_git(cmd, *args, **kwargs):
    """Every git call succeeds with empty output: no graves, no leftovers."""
    cmd = list(cmd) if isinstance(cmd, list) else [cmd]
    if "show-ref" in cmd:
        return _completed(returncode=1)  # no leftover `issue-N` branch
    return _completed()


def _payload_sent_by_run_impl_stage(state: dict) -> dict:
    """The exact dict `run_impl_stage` hands to `app.invoke`."""
    seen: dict = {}

    class _App:
        def invoke(self, payload, config=None):
            seen.update(payload)
            raise RuntimeError("stop here: the payload is what is under test")

    class _Graph:
        def compile(self):
            return _App()

    with patch.object(stages, "run_command", _quiet_git), \
         patch.object(Path, "is_dir", return_value=False), \
         patch(
             "assemblyzero.workflows.testing.graph.build_testing_workflow",
             return_value=_Graph(),
         ):
        try:
            stages.run_impl_stage(state)
        except Exception:
            pass
    assert seen, "run_impl_stage never reached app.invoke"
    return seen


@pytest.fixture
def state(tmp_path):
    target = tmp_path / "targetrepo"
    target.mkdir()
    return {
        "issue_number": 4,
        "target_repo": str(target),
        "assemblyzero_root": str(tmp_path / "az"),
        "base_branch": "hardening-run-20",
        "resumed_from": "",
        "retry_mode": "",
    }


class TestThePayloadMatchesTheSchema:
    def test_every_key_sent_is_a_declared_channel(self, state):
        """The general guard. A key here that the schema lacks is a value the
        orchestrator believes it sent and the sub-workflow never receives."""
        payload = _payload_sent_by_run_impl_stage(state)

        undeclared = set(payload) - set(TestingWorkflowState.__annotations__)
        assert not undeclared, (
            f"run_impl_stage sends key(s) TestingWorkflowState does not "
            f"declare -- LangGraph drops them at invoke, silently: "
            f"{sorted(undeclared)}"
        )

    def test_retry_mode_is_declared(self):
        assert "retry_mode" in TestingWorkflowState.__annotations__, (
            "retry_mode is not a channel of TestingWorkflowState -- #1941's "
            "mode and #2845's RESUMED are dropped before N0 (#2847)"
        )

    def test_the_stage_sends_the_name_the_testing_nodes_read(self, state):
        """#2849: `mock_mode`, not the spec workflow's `config_mock_mode`."""
        payload = _payload_sent_by_run_impl_stage(state)

        assert "mock_mode" in payload
        assert "config_mock_mode" not in payload

    def test_the_stage_does_not_send_the_dead_spec_path_key(self, state):
        """#2848: nothing in the testing workflow reads it."""
        payload = _payload_sent_by_run_impl_stage(state)

        assert "spec_path" not in payload


class TestTheValueSurvivesIntoANode:
    """Declaring the name is the fix; this is the proof it is sufficient.

    A real `StateGraph(TestingWorkflowState)` with one node that records what
    it was handed. Before #2847 this graph drops `retry_mode` on the floor and
    the node sees nothing -- the exact mechanism, not a description of it.
    """

    def _what_one_node_receives(self, payload: dict) -> dict:
        from langgraph.graph import END, StateGraph

        received: dict = {}

        def probe(s):
            received.update(dict(s))
            return {}

        graph = StateGraph(TestingWorkflowState)
        graph.add_node("probe", probe)
        graph.set_entry_point("probe")
        graph.add_edge("probe", END)
        graph.compile().invoke(payload)
        return received

    def test_retry_mode_reaches_the_first_node(self):
        received = self._what_one_node_receives(
            {"issue_number": 4, "retry_mode": RESUMED}
        )

        assert received.get("retry_mode") == RESUMED

    def test_mock_mode_reaches_the_first_node(self):
        received = self._what_one_node_receives(
            {"issue_number": 4, "mock_mode": True}
        )

        assert received.get("mock_mode") is True

    def test_an_undeclared_key_really_is_dropped(self):
        """The premise of this whole module, demonstrated rather than asserted:
        a name the schema lacks does not arrive. If LangGraph ever stops doing
        this, the guard above becomes unnecessary and this test says so."""
        received = self._what_one_node_receives(
            {"issue_number": 4, "no_such_channel_2847": "sent"}
        )

        assert "no_such_channel_2847" not in received


class TestTheRedPhaseNowReadsTheSignal:
    """The consequence that mattered: with `retry_mode` arriving, a worktree
    that already holds the planned files is this run's own progress, not
    green-at-red. This is the predicate the red phase consults (#2337/#2542),
    fed the state a resumed sub-workflow now actually carries."""

    def test_resumed_with_planned_files_present_is_a_later_attempt(self, tmp_path):
        from assemblyzero.workflows.testing.nodes import verify_phases

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "collector.py").write_text("x = 1\n", encoding="utf-8")
        state = {
            "repo_root": str(tmp_path),
            "retry_mode": RESUMED,
            "iteration_count": 0,
            "files_to_modify": [{"path": "src/collector.py", "change_type": "Add"}],
        }

        assert verify_phases._implementation_already_exists(state) is True

    def test_a_first_attempt_is_still_not(self, tmp_path):
        """The guard #2337 was built for must still fire on a genuine first
        entry: same files on disk, no retry_mode, iteration zero."""
        from assemblyzero.workflows.testing.nodes import verify_phases

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "collector.py").write_text("x = 1\n", encoding="utf-8")
        state = {
            "repo_root": str(tmp_path),
            "retry_mode": "",
            "iteration_count": 0,
            "files_to_modify": [{"path": "src/collector.py", "change_type": "Add"}],
        }

        assert verify_phases._implementation_already_exists(state) is False
