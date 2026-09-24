"""The LLD workflow writes into its worktree and nowhere in the checkout (#3510).

N5 wrote `docs/lld/active/LLD-{NNN}.md` and `docs/lld/lld-status.json` into
the operator's checkout and copied them to the LLD worktree, so every run left
both behind as uncommitted changes; regeneration deleted the checkout's tracked
LLD and rewrote its status; a mock run wrote its lineage beside the real one.
Nothing said who removed the worktree and the branch.

These run against throwaway repos and read `git status --porcelain` of the
checkout afterwards.
"""
from __future__ import annotations

import importlib
import io
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    """Keep halt snapshots and the workflow audit log out of the operator's
    real home directory (#3531)."""
    from assemblyzero.core import resume_contract, state_persistence
    from assemblyzero.workflows.testing import audit as testing_audit

    state = tmp_path / "workflow_state"
    monkeypatch.setattr(state_persistence, "STATE_DIR", state)
    monkeypatch.setattr(resume_contract, "STATE_DIR", state)
    monkeypatch.setattr(
        testing_audit, "WORKFLOW_AUDIT_FILE", tmp_path / "workflow-audit.jsonl"
    )


@pytest.fixture(autouse=True)
def _disarm_call_recording():
    """`main()` leaves call recording armed (see test_lld_mock_completes.py)."""
    from assemblyzero.core import call_recording

    yield
    call_recording.reset_context()


def _repo(root: Path, with_origin: bool) -> Path:
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    # The target-repo prerequisite this relies on: data/ and docs/lineage/
    # are ignored (#2077 puts worktrees under data/; #1458 says lineage is
    # ignored audit data).
    (root / ".gitignore").write_text("data/\ndocs/lineage/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    if with_origin:
        origin = root.parent / "origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
            capture_output=True, text=True, check=True,
        )
        _git(root, "remote", "add", "origin", str(origin))
        _git(root, "push", "-qu", "origin", "main")
    return root


def _porcelain(repo: Path) -> str:
    return _git(repo, "status", "--porcelain", "--untracked-files=all").stdout


def _run_mock(target: Path) -> tuple[int, str]:
    from tools.run_requirements_workflow import main

    argv = [
        "prog", "--type", "lld", "--issue", "42", "--mock", "--yes",
        "--review", "none", "--repo", str(target), "--base-branch", "main",
    ]
    out = io.StringIO()
    with patch("sys.argv", argv), patch(
        "tools.run_requirements_workflow.resolve_roots",
        return_value=(ROOT, target),
    ), redirect_stdout(out):
        rc = main()
    return rc, out.getvalue()


class TestAMockRunLeavesTheCheckoutClean:
    def test_porcelain_is_empty_after_a_full_mock_run(self, tmp_path):
        target = _repo(tmp_path / "target", with_origin=False)
        assert _porcelain(target) == ""

        rc, out = _run_mock(target)

        assert rc == 0, out
        assert "Saved LLD to:" in out, out
        assert _porcelain(target) == "", out

    def test_the_mock_outputs_are_under_data_mock_runs(self, tmp_path):
        target = _repo(tmp_path / "target", with_origin=False)

        rc, out = _run_mock(target)

        root = target / "data" / "mock-runs" / "42-lld"
        assert rc == 0, out
        assert (root / "docs" / "lld" / "active" / "LLD-042.md").exists(), out
        assert list((root / "docs" / "lineage").rglob("001-issue.md")), out
        # ...and nothing under the checkout's own docs/.
        assert not (target / "docs").exists(), out

    def test_a_mock_run_records_no_approval_in_the_real_cache(self, tmp_path):
        """The approval cache resolves to the target's main worktree whatever
        path it is given (#1970); a mock APPROVED verdict must not land there."""
        from assemblyzero.workflows.requirements.audit import lld_status_path

        target = _repo(tmp_path / "target", with_origin=False)

        rc, out = _run_mock(target)

        assert rc == 0, out
        assert not lld_status_path(target).exists(), out

    def test_the_final_report_leaves_nothing_in_place(self, tmp_path):
        target = _repo(tmp_path / "target", with_origin=False)

        rc, out = _run_mock(target)

        assert rc == 0, out
        assert "[run] left in place (0):" in out, out

    def test_a_mock_run_does_not_shift_a_real_runs_lineage(self, tmp_path):
        target = _repo(tmp_path / "target", with_origin=False)
        real = target / "docs" / "lineage" / "active" / "42-lld"
        real.mkdir(parents=True)
        (real / "001-issue.md").write_text("real run\n", encoding="utf-8")

        rc, out = _run_mock(target)

        assert rc == 0, out
        assert (real / "001-issue.md").read_text(encoding="utf-8") == "real run\n"
        assert not (target / "docs" / "lineage" / "active" / "42-lld-n1").exists()


class TestARealRunWritesIntoTheWorktree:
    """N5's save, run for real (not mock) against a repo with a bare origin.
    The commit and PR half is not exercised: that needs `gh`."""

    def _state(self, target: Path) -> dict:
        from assemblyzero.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld", assemblyzero_root=str(ROOT),
            target_repo=str(target), issue_number=42, base_branch="main",
        )
        mock_lld = importlib.import_module(
            "assemblyzero.core.llm_provider"
        ).MockProvider.DEFAULT_RESPONSES["lld"][0]
        state["current_draft"] = mock_lld
        state["lld_status"] = "APPROVED"
        state["verdict_count"] = 1
        state["open_questions_status"] = "NONE"
        return state

    def test_the_lld_and_status_land_in_the_worktree_not_the_checkout(
        self, tmp_path, monkeypatch
    ):
        fz = importlib.import_module(
            "assemblyzero.workflows.requirements.nodes.finalize"
        )
        target = _repo(tmp_path / "target", with_origin=True)
        monkeypatch.chdir(tmp_path)

        state = fz._save_lld_file(self._state(target))

        from assemblyzero.workflows.requirements.audit import lld_status_path

        assert not state.get("error_message"), state.get("error_message")
        worktree = target / "data" / "worktrees" / "42-lld"
        assert (worktree / "docs" / "lld" / "active" / "LLD-042.md").exists()
        # The approval cache is the repo's gitignored data/ (#1970), as before.
        assert lld_status_path(target).exists()
        assert not (target / "docs" / "lld").exists()
        assert _porcelain(target) == ""
        # created_files names the worktree copies, which the commit uses.
        assert all(str(worktree) in f for f in state["created_files"])

    def test_no_audit_dir_writes_nothing_into_the_working_directory(
        self, tmp_path, monkeypatch
    ):
        """`Path("")` is the cwd and always exists: with no audit_dir in
        state, finalize wrote NNN-final.md wherever the process ran. Found
        when four of them appeared at a worktree root during this change."""
        fz = importlib.import_module(
            "assemblyzero.workflows.requirements.nodes.finalize"
        )
        target = _repo(tmp_path / "target", with_origin=True)
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        state = self._state(target)
        assert not state.get("audit_dir")

        fz._save_lld_file(state)

        assert list(cwd.iterdir()) == []

    def test_mirror_passes_through_a_file_already_in_the_worktree(self, tmp_path):
        fz = importlib.import_module(
            "assemblyzero.workflows.requirements.nodes.finalize"
        )
        target = tmp_path / "target"
        worktree = target / "data" / "worktrees" / "42-lld"
        f = worktree / "docs" / "lld" / "active" / "LLD-042.md"
        f.parent.mkdir(parents=True)
        f.write_text("x", encoding="utf-8")

        out = fz._mirror_to_worktree([str(f)], target, worktree)

        assert out == [str(f)]
        assert not (worktree / "data").exists()


class TestTheWorktreeAndBranchHaveAnOwner:
    def test_finishing_commands_for_a_worktree_and_its_branch(self, tmp_path):
        from assemblyzero.core.run_record import finishing_commands

        items = [
            f"worktree: {tmp_path}/t/data/worktrees/42-lld [42-lld]",
            "branch: 42-lld",
            "remote branch: origin/42-lld",
            "checkout: ?? notes.txt",
        ]

        cmds = finishing_commands(tmp_path / "t", items)

        text = "\n".join(cmds)
        assert cmds[0].startswith(f"git -C {tmp_path / 't'} worktree remove ")
        assert "fetch --prune origin" in cmds[1]
        assert "branch -d 42-lld" in cmds[2] and "0217" in cmds[2]
        assert "push origin --delete 42-lld" in cmds[3]
        assert len(cmds) == 4, "checkout lines get no command"
        for banned in (" -D ", "--force", " -f "):
            assert banned not in text.replace("never -D", "").replace("never --force", "")

    def test_nothing_left_means_nothing_to_finish(self, tmp_path):
        from assemblyzero.core.run_record import finishing_commands

        assert finishing_commands(tmp_path, []) == []
