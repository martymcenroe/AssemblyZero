"""Repo-targeting tests for the orchestrator (Issue #1374).

The orchestrator invokes the sub-workflow graphs in-process, and each graph
requires the target repo in its state under its own key name (requirements:
``target_repo``; implementation_spec: ``repo_root``; testing: ``repo_root`` /
``original_repo_root``). Before #1374 the orchestrator passed none of them, so
a missing key silently resolved to ``Path("")`` == cwd == AssemblyZero, and
every "external" build was secretly an AssemblyZero build.

These tests assert the repo is threaded into every stage under the right key,
the worktree is carved FROM the target repo (not merely named after it), and
artifact detection is scoped to the target — i.e. no silent cwd fallback.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from assemblyzero.workflows.orchestrator.artifacts import (
    detect_existing_artifacts,
    get_artifact_path,
    worktree_path_for,
)
from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.stages import (
    run_impl_stage,
    run_lld_stage,
    run_spec_stage,
    run_triage_stage,
)
from assemblyzero.workflows.orchestrator.state import (
    create_initial_state,
    default_assemblyzero_root,
)

EXTERNAL = str(Path("/fake/projects/Chiron"))
AZ_ROOT = str(Path("/fake/projects/AssemblyZero"))


def _capturing_graph(captured: dict, return_value: dict):
    """A mock create_graph() whose compiled app.invoke captures its payload."""
    app = MagicMock()

    def _invoke(payload):
        captured.update(payload)
        return return_value

    app.invoke.side_effect = _invoke
    graph = MagicMock()
    graph.compile.return_value = app
    return graph


def _external_state():
    return create_initial_state(
        5, get_default_config(), target_repo=EXTERNAL, assemblyzero_root=AZ_ROOT
    )


# --- stage threading -------------------------------------------------------


@patch("assemblyzero.workflows.requirements.graph.create_requirements_graph")
@patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
def test_triage_threads_target_repo(mock_detect, mock_create_graph):
    mock_detect.return_value = {k: None for k in ("triage", "lld", "spec", "impl", "pr")}
    captured: dict = {}
    mock_create_graph.return_value = _capturing_graph(captured, {"issue_brief_path": ""})

    run_triage_stage(_external_state())

    assert captured["target_repo"] == EXTERNAL
    assert captured["assemblyzero_root"] == AZ_ROOT


@patch("assemblyzero.workflows.requirements.graph.create_requirements_graph")
@patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
def test_lld_threads_target_repo(mock_detect, mock_create_graph):
    mock_detect.return_value = {k: None for k in ("triage", "lld", "spec", "impl", "pr")}
    captured: dict = {}
    mock_create_graph.return_value = _capturing_graph(captured, {"lld_path": "", "review_verdict": ""})

    run_lld_stage(_external_state())

    assert captured["target_repo"] == EXTERNAL
    assert captured["assemblyzero_root"] == AZ_ROOT


@patch("assemblyzero.workflows.implementation_spec.graph.create_implementation_spec_graph")
@patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
def test_spec_threads_repo_root(mock_detect, mock_create_graph):
    mock_detect.return_value = {k: None for k in ("triage", "lld", "spec", "impl", "pr")}
    captured: dict = {}
    mock_create_graph.return_value = _capturing_graph(captured, {"spec_path": ""})

    run_spec_stage(_external_state())

    # implementation_spec graph names the target `repo_root`, not `target_repo`
    assert captured["repo_root"] == EXTERNAL
    assert captured["assemblyzero_root"] == AZ_ROOT


@patch("assemblyzero.workflows.testing.graph.build_testing_workflow")
@patch("assemblyzero.workflows.orchestrator.stages.run_command")
def test_impl_carves_worktree_from_target(mock_run, mock_create_graph):
    captured: dict = {}
    mock_create_graph.return_value = _capturing_graph(captured, {"error_message": ""})

    run_impl_stage(_external_state())

    # git worktree add must run against the target repo via `-C <target>`
    add_calls = [c for c in mock_run.call_args_list if "worktree" in c.args[0]]
    assert len(add_calls) == 1, "expected exactly one git worktree add"
    argv = add_calls[0].args[0]
    assert argv[:3] == ["git", "-C", EXTERNAL], f"worktree not carved from target: {argv}"

    expected_wt = str(Path(EXTERNAL).parent / "Chiron-5")
    assert expected_wt in argv, f"worktree path is not a sibling of target: {argv}"
    assert "issue-5" in argv  # branch

    # testing graph receives the target as repo_root / original_repo_root
    assert captured["repo_root"] == EXTERNAL
    assert captured["original_repo_root"] == EXTERNAL
    assert captured["worktree_path"] == expected_wt


# --- backward compatibility ------------------------------------------------


def test_create_initial_state_defaults_to_assemblyzero():
    state = create_initial_state(5, get_default_config())
    root = default_assemblyzero_root()
    assert state["assemblyzero_root"] == root
    assert state["target_repo"] == root  # default build target is AssemblyZero
    assert "AssemblyZero" in state["assemblyzero_root"]


def test_worktree_path_for_default_is_assemblyzero_sibling():
    # Backward-compatible fallback when no target is supplied.
    assert worktree_path_for(5, None) == Path("../AssemblyZero-5")


# --- artifact path resolution ----------------------------------------------


def test_worktree_path_for_external_is_target_sibling():
    assert worktree_path_for(5, EXTERNAL) == Path(EXTERNAL).parent / "Chiron-5"


def test_get_artifact_path_resolves_under_target():
    assert get_artifact_path(5, "triage", EXTERNAL) == Path(EXTERNAL) / "docs/lineage/5/issue-brief.md"
    assert get_artifact_path(5, "spec", EXTERNAL) == Path(EXTERNAL) / "docs/lineage/5/impl-spec.md"
    assert get_artifact_path(5, "impl", EXTERNAL) == Path(EXTERNAL).parent / "Chiron-5"


def test_detect_existing_artifacts_scoped_to_target(tmp_path):
    repo = tmp_path / "Chiron"
    brief = repo / "docs" / "lineage" / "5" / "issue-brief.md"
    brief.parent.mkdir(parents=True)
    brief.write_text("## Brief\ncontent", encoding="utf-8")

    artifacts = detect_existing_artifacts(5, str(repo))
    assert artifacts["triage"] == str(repo / "docs/lineage/5/issue-brief.md")


def test_detect_existing_artifacts_no_silent_cwd_fallback(tmp_path):
    # A brief living under one repo must NOT be discovered when detecting
    # against a different target repo. This is the regression guard for the
    # silent-cwd-default bug: detection is scoped to the given target only.
    repo_a = tmp_path / "RepoA"
    (repo_a / "docs" / "lineage" / "5").mkdir(parents=True)
    (repo_a / "docs" / "lineage" / "5" / "issue-brief.md").write_text("## x", encoding="utf-8")

    repo_b = tmp_path / "RepoB"
    repo_b.mkdir()

    artifacts = detect_existing_artifacts(5, str(repo_b))
    assert artifacts["triage"] is None
