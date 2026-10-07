"""Tests for the terminal cleanup stage (Issues #1531 + #1624 + #1628 + #3717).

run_cleanup_stage runs after the pr stage. Since #3717 it merges nothing: the
merge driver landed the LLD in the lld stage and the implementation in the pr
stage. It confirms the implementation's squash is on the attempt branch (#2011),
deletes the now-redundant LLD/spec working-tree copies once the LLD landed
(#1624, scoped — never lld-status.json), and removes any LLD + impl worktree left
(#1628, plain `git worktree remove`, no --force).
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

def test_cleanup_deletes_and_removes_when_the_lld_landed(tmp_path):
    """#3717: an LLD PR URL in state is the driver's report that it landed."""
    state = _state(tmp_path, lld_pr_url="https://github.com/o/r/pull/9")
    with patch.object(stages, "_delete_landed_working_copies") as m_del, \
         patch.object(stages, "_remove_orchestrator_worktrees") as m_rm:
        new_state = stages.run_cleanup_stage(state)
    m_del.assert_called_once()
    m_rm.assert_called_once()
    assert new_state["stage_results"]["cleanup"]["status"] == "passed"
    assert new_state["current_stage"] == "done"


def test_cleanup_without_a_landed_lld_keeps_the_copies(tmp_path):
    """No landed LLD: the working-tree copies are the only copies and are NOT
    deleted; the stage still passes and the worktrees are still removed."""
    state = _state(tmp_path)  # lld_pr_url == "" from create_initial_state
    with patch.object(stages, "_delete_landed_working_copies") as m_del, \
         patch.object(stages, "_remove_orchestrator_worktrees") as m_rm:
        new_state = stages.run_cleanup_stage(state)
    m_del.assert_not_called()
    m_rm.assert_called_once()
    assert new_state["stage_results"]["cleanup"]["status"] == "passed"


def test_cleanup_merges_nothing(tmp_path):
    """#3717: the driver merged both PRs; cleanup calls no gh at all."""
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return _resp()

    state = _state(
        tmp_path, lld_pr_url="https://github.com/o/r/pull/9",
        impl_pr_url="https://github.com/o/r/pull/10", impl_squash_sha="abc1234",
        base_branch="arc",
    )
    with patch.object(stages, "run_command", side_effect=fake_run), \
         patch.object(stages, "_delete_landed_working_copies"), \
         patch.object(stages, "_remove_orchestrator_worktrees"):
        new_state = stages.run_cleanup_stage(state)

    assert not [c for c in calls if c[:1] == ["gh"]], calls
    assert ["git", "merge-base", "--is-ancestor", "abc1234", "origin/arc"] in calls
    assert new_state["stage_results"]["cleanup"]["status"] == "passed"


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

    result = {
        "final_lld_path": str(lld_file),
        "final_verdict": "APPROVED",
        "final_lld_pr_url": "https://github.com/o/r/pull/9",
    }

    class _App:
        # #2245: the lld stage streams through invoke_with_budget under a
        # derived step budget, so a spent budget can name the loop.
        def invoke(self, payload, *args, **kwargs):
            return result

        def stream(self, payload, *args, **kwargs):
            yield result

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


# ---- #2011: the implementation PR must actually land ----


def test_cleanup_confirms_the_impl_squash_on_the_base(tmp_path):
    """#2011's contract, on the driver's report (#3717): the implementation has
    landed only when its squash is on the attempt branch."""
    seen = []

    def fake_check(target, sha, base, notes):
        seen.append((sha, base))
        return True

    state = _state(tmp_path, impl_squash_sha="abc1234", base_branch="arc")
    state["impl_pr_url"] = "https://github.com/o/r/pull/155"
    with patch.object(stages, "_squash_on_base", side_effect=fake_check), \
         patch.object(stages, "_delete_landed_working_copies"), \
         patch.object(stages, "_remove_orchestrator_worktrees"):
        new_state = stages.run_cleanup_stage(state)

    assert seen == [("abc1234", "arc")]
    assert new_state["stage_results"]["cleanup"]["status"] == "passed"


def test_an_unconfirmed_impl_squash_fails_the_stage(tmp_path):
    """Reporting an unlanded implementation as green is exactly how the gap
    stayed invisible (#2011)."""
    state = _state(tmp_path)
    state["impl_pr_url"] = "https://github.com/o/r/pull/155"
    with patch.object(stages, "_squash_on_base", return_value=False), \
         patch.object(stages, "_delete_landed_working_copies"), \
         patch.object(stages, "_remove_orchestrator_worktrees"):
        new_state = stages.run_cleanup_stage(state)

    result = new_state["stage_results"]["cleanup"]
    assert result["status"] == "failed", result
    assert "cannot accumulate" in result.get("error_message", "")


def test_a_cleanup_hiccup_without_an_impl_pr_still_passes(tmp_path):
    """Best-effort housekeeping keeps its old contract; only the landing is
    load-bearing."""
    state = _state(tmp_path)
    with patch.object(stages, "_squash_on_base", return_value=False), \
         patch.object(stages, "_delete_landed_working_copies"), \
         patch.object(stages, "_remove_orchestrator_worktrees"):
        new_state = stages.run_cleanup_stage(state)

    assert new_state["stage_results"]["cleanup"]["status"] == "passed"


def test_squash_on_base_without_a_sha_is_not_confirmed(tmp_path):
    """A state written before #3717 carries no squash: nothing to confirm, so
    the landing is not assumed."""
    notes = []
    assert stages._squash_on_base(str(tmp_path), "", "arc", notes) is False
    assert any("cannot verify" in n for n in notes)
