"""Tests for the post-finalize checkpoint (Issue #1626).

N7 finalize() generates the test/implementation reports and archives them
active/ -> done/, but historically committed nothing — so the reports were left
untracked in the impl worktree and lost on worktree removal. The fix wraps
N7_finalize with a post-finalize checkpoint so the reports are committed to the
impl worktree (and land on target main when the impl PR squash-merges).
"""
from unittest.mock import patch

from assemblyzero.workflows.testing import graph


def _node_callable(spec):
    """Pull the invokable callable out of a langgraph node spec, robust to the
    StateGraph node representation."""
    runnable = getattr(spec, "runnable", spec)
    return runnable


def _invoke_node(spec, state):
    runnable = _node_callable(spec)
    if hasattr(runnable, "func"):
        return runnable.func(state)
    if hasattr(runnable, "invoke"):
        return runnable.invoke(state)
    return runnable(state)


def test_wrap_with_checkpoint_commits_with_given_name(tmp_path):
    """_wrap_with_checkpoint runs the node, then commits with the given name,
    passing worktree_path + issue_number from state, and returns the node result."""
    seen = []

    def fake_commit(worktree, issue, name):
        seen.append((worktree, issue, name))
        return True

    node_result = {"test_report_path": "x", "error_message": ""}

    with patch.object(graph, "commit_checkpoint", side_effect=fake_commit):
        wrapped = graph._wrap_with_checkpoint(lambda state: node_result, "post-finalize")
        result = wrapped({"worktree_path": str(tmp_path), "issue_number": 1626})

    assert result is node_result, "wrapper must return the node's result unchanged"
    assert seen == [(str(tmp_path), 1626, "post-finalize")]


def test_build_workflow_wraps_finalize_with_post_finalize_checkpoint(tmp_path):
    """Building the testing workflow must wire N7_finalize through a post-finalize
    checkpoint (#1626). finalize is stubbed so the node is cheap; we then drive the
    registered node and assert the checkpoint fired with the right name."""
    seen = []

    def fake_commit(worktree, issue, name):
        seen.append(name)
        return True

    def stub_finalize(state):
        return {"error_message": ""}

    with patch.object(graph, "commit_checkpoint", side_effect=fake_commit), \
         patch.object(graph, "finalize", stub_finalize):
        wf = graph.build_testing_workflow()
        _invoke_node(wf.nodes["N7_finalize"], {"worktree_path": str(tmp_path), "issue_number": 1626})

    assert "post-finalize" in seen, (
        "build_testing_workflow must wrap N7_finalize with a post-finalize "
        "checkpoint (#1626); the bare finalize node commits nothing"
    )


def test_finalize_node_is_not_bare_finalize():
    """Regression guard: the registered N7_finalize node must not be the bare
    finalize function (which commits nothing). #1626."""
    wf = graph.build_testing_workflow()
    runnable = _node_callable(wf.nodes["N7_finalize"])
    func = getattr(runnable, "func", runnable)
    assert func is not graph.finalize, (
        "N7_finalize is the bare finalize node — the post-finalize checkpoint "
        "wrapper (#1626) was removed"
    )
