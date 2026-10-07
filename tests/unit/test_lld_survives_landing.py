"""The approved LLD outlives its own landing (#3750).

The merge driver lands the LLD and removes the LLD worktree. `final_lld_path`
named the copy inside that worktree, so after a successful landing the lld
stage found no file, failed with an empty reason, and was retried: boostgauge
#2 run-issue2-013743 landed three LLD PRs (#476, #477, #478) that way.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

from assemblyzero.workflows.orchestrator import stages
from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.state import create_initial_state

# The nodes package re-exports the `finalize` function under the module's name.
finalize_mod = importlib.import_module("assemblyzero.workflows.requirements.nodes.finalize")


def test_the_durable_copy_lives_in_the_gitignored_lineage(tmp_path):
    assert finalize_mod.durable_lld_path(tmp_path, 2) == (
        tmp_path / "docs" / "lineage" / "active" / "2-lld-handoff" / "LLD-002.md"
    )


def test_after_a_landing_final_lld_path_is_the_durable_copy(tmp_path):
    worktree = tmp_path / "data" / "worktrees" / "2-lld"
    worktree_lld = worktree / "docs" / "lld" / "active" / "LLD-002.md"
    durable = finalize_mod.durable_lld_path(tmp_path, 2)
    durable.parent.mkdir(parents=True)
    durable.write_text("# LLD\n", encoding="utf-8")

    def landing_removes_the_worktree(**kwargs):
        # What the driver does after merging: the worktree copy is gone.
        assert not worktree_lld.exists()
        return "abc1234", "https://github.com/o/r/pull/476"

    state = {
        "created_files": [str(worktree_lld)], "workflow_type": "lld",
        "issue_number": 2, "target_repo": str(tmp_path), "base_branch": "arc",
        "final_lld_path": str(worktree_lld),
    }
    with patch.object(finalize_mod, "setup_lld_worktree", return_value=(worktree, "2-lld")), \
         patch.object(finalize_mod, "_mirror_to_worktree", return_value=[str(worktree_lld)]), \
         patch.object(finalize_mod, "commit_and_pr", side_effect=landing_removes_the_worktree):
        out = finalize_mod._commit_and_push_files(state)

    assert out["final_lld_path"] == str(durable)
    assert Path(out["final_lld_path"]).is_file()
    assert out["final_lld_pr_url"] == "https://github.com/o/r/pull/476"


def _run_lld_stage(tmp_path, sub_result):
    config = get_default_config()
    config["skip_existing_lld"] = False
    state = create_initial_state(
        2, config, target_repo=str(tmp_path / "target"), assemblyzero_root=str(tmp_path / "az"),
    )

    class _App:
        def invoke(self, payload, *args, **kwargs):
            return sub_result

        def stream(self, payload, *args, **kwargs):
            yield sub_result

    class _Graph:
        def compile(self):
            return _App()

    with patch(
        "assemblyzero.workflows.requirements.graph.create_requirements_graph",
        return_value=_Graph(),
    ):
        return stages.run_lld_stage(state)["stage_results"]["lld"]


def test_a_reported_lld_that_is_gone_is_named_not_blank(tmp_path):
    """The live shape: APPROVED, a path that no longer exists, error_message ''."""
    gone = tmp_path / "data" / "worktrees" / "2-lld" / "docs" / "lld" / "active" / "LLD-002.md"
    result = _run_lld_stage(tmp_path, {
        "final_lld_path": str(gone), "final_verdict": "APPROVED", "error_message": "",
    })

    assert result["status"] == "failed"
    assert result["error_message"], "a failed stage must say why"
    assert str(gone) in result["error_message"]


def test_no_artifact_at_all_keeps_the_old_reason(tmp_path):
    result = _run_lld_stage(tmp_path, {"final_verdict": "APPROVED", "error_message": ""})

    assert result["status"] == "failed"
    assert result["error_message"] == "LLD workflow completed but no artifact produced"
