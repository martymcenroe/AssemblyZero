"""Tests for the N8 doc-step handling (Issues #1627 + #1631).

#1631: the document node generates wiki/runbook/README into the impl worktree but
historically committed nothing, leaving them untracked. N8_document is now wrapped
with a `post-document` checkpoint so they are committed (and land via the impl PR).

#1627: the 907/908 c/p docs are AZ-internal boilerplate (they assume an AssemblyZero
context and target docs/skills/). The orchestrator sets `skip_cp_docs=True` for
external-repo builds so only those c/p docs are suppressed — wiki/runbook/README are
kept. `skip_docs`/`doc_scope` are deliberately NOT used (too broad).
"""
from unittest.mock import MagicMock, patch

from assemblyzero.workflows.testing import graph
from assemblyzero.workflows.testing.nodes.document import document, is_cli_tool
from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.state import create_initial_state


def _invoke_node(spec, state):
    """Pull the invokable callable out of a langgraph node spec, robust to the
    StateGraph node representation, and run it."""
    runnable = getattr(spec, "runnable", spec)
    if hasattr(runnable, "func"):
        return runnable.func(state)
    if hasattr(runnable, "invoke"):
        return runnable.invoke(state)
    return runnable(state)


def _doc_state(tmp_path, **overrides):
    audit_dir = tmp_path / "docs" / "lineage" / "active" / "42-testing"
    audit_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "issue_number": 42,
        "repo_root": str(tmp_path),
        "lld_content": "# Tool\n\nImplement a CLI tool.",
        "audit_dir": str(audit_dir),
        "implementation_files": ["tools/new_tool.py"],  # is_cli_tool -> True
        "test_files": [],
        "iteration_count": 1,
        "coverage_achieved": 95.0,
        "coverage_target": 90,
        "doc_scope": "minimal",  # past the doc_scope=="none" early-return; no wiki
    }
    state.update(overrides)
    return state


# ---- #1627: c/p-docs suppression gate ----

def test_document_suppresses_cp_docs_when_skip_flag_set(tmp_path):
    """skip_cp_docs suppresses the 907/908 c/p docs even for a CLI tool."""
    state = _doc_state(tmp_path, skip_cp_docs=True)
    assert is_cli_tool(state) is True  # precondition: would normally emit
    result = document(state)
    assert result.get("doc_cp_paths") == [], "skip_cp_docs must suppress the c/p docs"


def test_document_emits_cp_docs_when_not_skipped(tmp_path):
    """Default (skip_cp_docs unset) still emits c/p docs for a CLI tool — AZ
    self-builds keep them."""
    state = _doc_state(tmp_path)  # no skip_cp_docs
    result = document(state)
    assert len(result.get("doc_cp_paths", [])) == 2, (
        "a CLI tool must still get its c/p docs when not skipped"
    )


# ---- #1631: post-document checkpoint wiring ----

def test_build_workflow_wraps_document_with_post_document_checkpoint(tmp_path):
    """N8_document must be wrapped with a post-document checkpoint so the
    wiki/runbook/README it generates are committed, not left untracked."""
    seen = []

    def fake_commit(worktree, issue, name):
        seen.append(name)
        return True

    def stub_document(state):
        return {}

    with patch.object(graph, "commit_checkpoint", side_effect=fake_commit), \
         patch.object(graph, "document", stub_document):
        wf = graph.build_testing_workflow()
        _invoke_node(wf.nodes["N8_document"], {"worktree_path": str(tmp_path), "issue_number": 1631})

    assert "post-document" in seen, (
        "build_testing_workflow must wrap N8_document with a post-document checkpoint (#1631)"
    )


def test_document_node_is_not_bare_document():
    """Regression guard: N8_document must not be the bare document function. #1631."""
    wf = graph.build_testing_workflow()
    runnable = getattr(wf.nodes["N8_document"], "runnable", wf.nodes["N8_document"])
    func = getattr(runnable, "func", runnable)
    assert func is not graph.document, (
        "N8_document is the bare document node — the post-document checkpoint (#1631) was removed"
    )


# ---- #1627: orchestrator sets the flag ----

def _capture_impl_payload(state):
    from assemblyzero.workflows.orchestrator.stages import run_impl_stage

    captured: dict = {}

    class _StubApp:
        def invoke(self, payload):
            captured["payload"] = payload
            return {"error_message": ""}

    class _StubGraph:
        def compile(self):
            return _StubApp()

    with patch("assemblyzero.workflows.orchestrator.stages.run_command") as mock_run:
        out = MagicMock()
        out.stdout = ""
        out.stderr = ""
        out.returncode = 0
        mock_run.return_value = out
        with patch(
            "assemblyzero.workflows.testing.graph.build_testing_workflow",
            return_value=_StubGraph(),
        ):
            run_impl_stage(state)
    return captured.get("payload", {})


def test_impl_stage_sets_skip_cp_docs_for_external_repo(tmp_path):
    """Building an external repo (target_repo != assemblyzero_root) sets
    skip_cp_docs=True so the 907/908 docs are suppressed there."""
    config = get_default_config()
    state = create_initial_state(
        42, config,
        target_repo=str(tmp_path / "external"),
        assemblyzero_root=str(tmp_path / "az"),
    )
    state["spec_path"] = str(tmp_path / "spec.md")
    (tmp_path / "spec.md").write_text("# spec")
    payload = _capture_impl_payload(state)
    assert payload.get("skip_cp_docs") is True


def test_impl_stage_keeps_cp_docs_for_az_self_build(tmp_path):
    """AZ self-build (target_repo == assemblyzero_root) leaves skip_cp_docs False
    so the c/p docs are still emitted on AZ."""
    config = get_default_config()
    az = str(tmp_path / "az")
    state = create_initial_state(42, config, target_repo=az, assemblyzero_root=az)
    state["spec_path"] = str(tmp_path / "spec.md")
    (tmp_path / "spec.md").write_text("# spec")
    payload = _capture_impl_payload(state)
    assert payload.get("skip_cp_docs") is False
