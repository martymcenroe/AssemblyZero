"""Tests for the spec riding the LLD PR (Issue #1625).

finalize_spec writes the implementation spec to the target working tree but does
no git op, so the spec was orphaned. Per ADR 0221 the spec is a permanent artifact
that rides the LLD PR: run_spec_stage mirrors it into the existing {N}-lld worktree
and commits + pushes (the open LLD PR auto-updates). The terminal cleanup later
removes the working-tree copy after the LLD PR merges.
"""
from unittest.mock import MagicMock, patch

from assemblyzero.workflows.orchestrator import stages
from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.state import create_initial_state


def _ok_run(cmd, **kw):
    out = MagicMock()
    out.returncode = 0
    out.stdout = ""
    out.stderr = ""
    return out


def test_ride_spec_commits_to_lld_worktree(tmp_path):
    """When the {N}-lld worktree exists, the spec is mirrored in and add/commit/push run."""
    target = tmp_path / "target"
    drafts = target / "docs" / "lld" / "drafts"
    drafts.mkdir(parents=True)
    spec = drafts / "spec-0042-implementation-readiness.md"
    spec.write_text("# spec")
    worktree = tmp_path / "target-42-lld"  # == lld_worktree_path_for(target, 42)
    worktree.mkdir()

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return _ok_run(cmd, **kw)

    with patch.object(stages, "run_command", side_effect=fake_run):
        ok = stages._ride_spec_on_lld_pr(str(spec), str(target), 42)

    assert ok is True
    # spec mirrored into the worktree at the same relative path
    assert (worktree / "docs" / "lld" / "drafts" / "spec-0042-implementation-readiness.md").exists()
    joined = [" ".join(c) for c in calls]
    assert any(c.startswith("git add") for c in joined), joined
    assert any(c.startswith("git commit") for c in joined), joined
    assert any(c.startswith("git push") for c in joined), joined


def test_ride_spec_no_worktree_returns_false(tmp_path):
    """No {N}-lld worktree (e.g. LLD stage skipped) → no-op, returns False, no raise."""
    target = tmp_path / "target"
    drafts = target / "docs" / "lld" / "drafts"
    drafts.mkdir(parents=True)
    spec = drafts / "spec-0042-implementation-readiness.md"
    spec.write_text("# spec")
    # deliberately do NOT create the worktree
    ok = stages._ride_spec_on_lld_pr(str(spec), str(target), 42)
    assert ok is False


def test_ride_spec_commit_noop_returns_false(tmp_path):
    """If git commit is a no-op (nothing staged), best-effort returns False."""
    target = tmp_path / "target"
    drafts = target / "docs" / "lld" / "drafts"
    drafts.mkdir(parents=True)
    spec = drafts / "spec-0042-implementation-readiness.md"
    spec.write_text("# spec")
    worktree = tmp_path / "target-42-lld"
    worktree.mkdir()

    def fake_run(cmd, **kw):
        out = MagicMock()
        out.stdout = ""
        out.stderr = "nothing to commit"
        out.returncode = 1 if "commit" in cmd else 0
        return out

    with patch.object(stages, "run_command", side_effect=fake_run):
        ok = stages._ride_spec_on_lld_pr(str(spec), str(target), 42)
    assert ok is False


def test_spec_stage_rides_spec_on_lld_pr(tmp_path):
    """run_spec_stage invokes _ride_spec_on_lld_pr on a successful spec."""
    config = get_default_config()
    config["skip_existing_spec"] = False  # force the workflow to run (don't skip)
    state = create_initial_state(
        42, config,
        target_repo=str(tmp_path / "target"),
        assemblyzero_root=str(tmp_path / "az"),
    )
    spec_file = tmp_path / "target" / "docs" / "lld" / "drafts" / "spec-0042-implementation-readiness.md"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text("# spec")

    class _StubApp:
        def invoke(self, payload):
            return {"spec_path": str(spec_file), "error_message": ""}

    rode: dict = {}

    def fake_ride(spec_path, target_repo, issue_number):
        rode["called"] = (spec_path, target_repo, issue_number)
        return True

    with patch(
        "assemblyzero.workflows.implementation_spec.graph.create_implementation_spec_graph",
        return_value=_StubApp(),
    ), patch.object(stages, "_ride_spec_on_lld_pr", side_effect=fake_ride):
        stages.run_spec_stage(state)

    assert rode.get("called") == (str(spec_file), str(tmp_path / "target"), 42), (
        "run_spec_stage must ride the spec on the LLD PR for a successful spec"
    )
