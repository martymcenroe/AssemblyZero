"""Tests for the terminal cleanup stage (Issues #1531 + #1624 + #1628).

run_cleanup_stage runs after the pr stage and (best-effort): merges the LLD PR
(#1531, landing LLD + spec on target main), deletes the now-redundant LLD/spec
working-tree copies once merged (#1624, scoped — never lld-status.json), and removes
the LLD + impl worktrees (#1628, plain `git worktree remove`, no --force). It always
returns "passed" so cleanup never fails an otherwise-successful run.
"""
from unittest.mock import MagicMock, patch

from assemblyzero.workflows.orchestrator import stages
from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.state import STAGE_ORDER, create_initial_state


def _resp(returncode=0, stdout="", stderr=""):
    out = MagicMock()
    out.returncode = returncode
    out.stdout = stdout
    out.stderr = stderr
    return out


def _state(tmp_path, **overrides):
    config = get_default_config()
    state = create_initial_state(
        42, config,
        target_repo=str(tmp_path / "target"),
        assemblyzero_root=str(tmp_path / "az"),
    )
    state.update(overrides)
    return state


# ---- wiring ----

def test_cleanup_registered_in_order_and_runners():
    assert STAGE_ORDER[-1] == "cleanup", "cleanup must be the terminal stage"
    assert stages.STAGE_RUNNERS.get("cleanup") is stages.run_cleanup_stage


# ---- run_cleanup_stage orchestration ----

def test_cleanup_merges_deletes_removes_when_lld_pr_present(tmp_path):
    state = _state(tmp_path, lld_pr_url="https://github.com/o/r/pull/9")
    with patch.object(stages, "_merge_lld_pr", return_value=True) as m_merge, \
         patch.object(stages, "_delete_landed_working_copies") as m_del, \
         patch.object(stages, "_remove_orchestrator_worktrees") as m_rm:
        new_state = stages.run_cleanup_stage(state)
    m_merge.assert_called_once()
    m_del.assert_called_once()
    m_rm.assert_called_once()
    assert new_state["stage_results"]["cleanup"]["status"] == "passed"
    assert new_state["current_stage"] == "done"


def test_cleanup_no_lld_pr_skips_merge_and_delete(tmp_path):
    state = _state(tmp_path)  # lld_pr_url == "" from create_initial_state
    with patch.object(stages, "_merge_lld_pr") as m_merge, \
         patch.object(stages, "_delete_landed_working_copies") as m_del, \
         patch.object(stages, "_remove_orchestrator_worktrees") as m_rm:
        new_state = stages.run_cleanup_stage(state)
    m_merge.assert_not_called()
    m_del.assert_not_called()
    m_rm.assert_called_once()  # worktrees still removed
    assert new_state["stage_results"]["cleanup"]["status"] == "passed"


def test_cleanup_unmerged_lld_skips_delete_but_passes(tmp_path):
    """Gate: if the LLD PR did not merge, the working-tree copies are NOT deleted
    (they would be lost), but the stage still passes and worktrees are still removed."""
    state = _state(tmp_path, lld_pr_url="https://github.com/o/r/pull/9")
    with patch.object(stages, "_merge_lld_pr", return_value=False), \
         patch.object(stages, "_delete_landed_working_copies") as m_del, \
         patch.object(stages, "_remove_orchestrator_worktrees") as m_rm:
        new_state = stages.run_cleanup_stage(state)
    m_del.assert_not_called()
    m_rm.assert_called_once()
    assert new_state["stage_results"]["cleanup"]["status"] == "passed"


# ---- _merge_lld_pr ----

def test_merge_lld_pr_merges_when_clean():
    notes = []

    def fake_run(cmd, **kw):
        if "view" in cmd:
            return _resp(stdout="OPEN\tCLEAN\n")
        return _resp()  # merge succeeds

    with patch.object(stages, "run_command", side_effect=fake_run):
        ok = stages._merge_lld_pr("https://github.com/o/r/pull/9", 600, notes)
    assert ok is True


def test_merge_lld_pr_already_merged_no_merge_call():
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return _resp(stdout="MERGED\tCLEAN\n")

    with patch.object(stages, "run_command", side_effect=fake_run):
        ok = stages._merge_lld_pr("https://github.com/o/r/pull/9", 600, [])
    assert ok is True
    assert all("merge" not in c for c in calls), "must not attempt merge when already MERGED"


def test_merge_lld_pr_timeout_returns_false():
    notes = []

    def fake_run(cmd, **kw):
        return _resp(stdout="OPEN\tBLOCKED\n")  # never CLEAN

    # timeout_s=0 → exits after the first check without sleeping
    with patch.object(stages, "run_command", side_effect=fake_run):
        ok = stages._merge_lld_pr("https://github.com/o/r/pull/9", 0, notes)
    assert ok is False
    assert any("not merged within" in n for n in notes)


# ---- _delete_landed_working_copies ----

def test_delete_landed_working_copies_is_scoped(tmp_path):
    """Deletes the LLD + spec copies but NOT lld-status.json (or anything else)."""
    target = tmp_path
    active = target / "docs" / "lld" / "active"
    active.mkdir(parents=True)
    drafts = target / "docs" / "lld" / "drafts"
    drafts.mkdir(parents=True)
    lld = active / "LLD-042.md"
    lld.write_text("lld")
    spec = drafts / "spec-0042-implementation-readiness.md"
    spec.write_text("spec")
    status = target / "docs" / "lld" / "lld-status.json"
    status.write_text("{}")

    notes = []
    stages._delete_landed_working_copies(str(target), 42, notes)

    assert not lld.exists(), "LLD copy must be deleted"
    assert not spec.exists(), "spec copy must be deleted"
    assert status.exists(), "lld-status.json must NOT be deleted (mutable tracking file)"


# ---- _remove_orchestrator_worktrees ----

def test_remove_worktrees_removes_both_and_deletes_merged_lld_branch(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    lld_wt = tmp_path / "target-42-lld"
    lld_wt.mkdir()
    impl_wt = tmp_path / "target-42"
    impl_wt.mkdir()

    removed = []

    with patch("assemblyzero.workflows.requirements.git_operations.lld_worktree_path_for", return_value=lld_wt), \
         patch.object(stages, "worktree_path_for", return_value=impl_wt), \
         patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.remove_worktree",
               side_effect=lambda p: removed.append(str(p)) or True), \
         patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.get_worktree_branch", return_value="42-lld"), \
         patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.delete_local_branch") as m_del:
        stages._remove_orchestrator_worktrees(str(target), 42, lld_merged=True, notes=[])

    assert str(lld_wt) in removed and str(impl_wt) in removed, "both worktrees must be removed"
    m_del.assert_called_once_with("42-lld"), "merged LLD branch -d attempted"


def test_remove_worktrees_skips_lld_branch_delete_when_unmerged(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    lld_wt = tmp_path / "target-42-lld"
    lld_wt.mkdir()
    impl_wt = tmp_path / "target-42"
    impl_wt.mkdir()

    with patch("assemblyzero.workflows.requirements.git_operations.lld_worktree_path_for", return_value=lld_wt), \
         patch.object(stages, "worktree_path_for", return_value=impl_wt), \
         patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.remove_worktree", return_value=True), \
         patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.get_worktree_branch", return_value="42-lld"), \
         patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.delete_local_branch") as m_del:
        stages._remove_orchestrator_worktrees(str(target), 42, lld_merged=False, notes=[])

    m_del.assert_not_called(), "must not delete LLD branch when its PR did not merge"


# ---- run_lld_stage captures the LLD PR url ----

def test_lld_stage_captures_lld_pr_url(tmp_path):
    config = get_default_config()
    config["skip_existing_lld"] = False  # force the workflow to run
    state = create_initial_state(
        42, config,
        target_repo=str(tmp_path / "target"),
        assemblyzero_root=str(tmp_path / "az"),
    )
    lld_file = tmp_path / "target" / "docs" / "lld" / "active" / "LLD-042.md"
    lld_file.parent.mkdir(parents=True)
    lld_file.write_text("# LLD\n\nAPPROVED")

    class _App:
        def invoke(self, payload):
            return {
                "final_lld_path": str(lld_file),
                "final_verdict": "APPROVED",
                "final_lld_pr_url": "https://github.com/o/r/pull/9",
            }

    class _Graph:
        def compile(self):
            return _App()

    with patch(
        "assemblyzero.workflows.requirements.graph.create_requirements_graph",
        return_value=_Graph(),
    ):
        new_state = stages.run_lld_stage(state)

    assert new_state.get("lld_pr_url") == "https://github.com/o/r/pull/9", (
        "run_lld_stage must capture final_lld_pr_url into orchestration state for the "
        "terminal cleanup stage to merge"
    )
