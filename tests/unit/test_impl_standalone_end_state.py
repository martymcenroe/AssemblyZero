"""The standalone implementation run has a defined end state (#3509).

N9 cleans up only when `pr_url` is set and nothing standalone sets it, so
every standalone run ended with its worktree, branch, checkpoint commits,
status file and lineage in place, and a "Next steps" asking the operator to
commit by hand. `END_STATE` in `tools/run_implement_from_lld.py` now says what
a run leaves; these hold it to that, against throwaway repos with a bare
origin, by reading the worktree list, the branch list, the origin's refs and
the checkout's status.
"""
from __future__ import annotations

import io
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest


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
    from assemblyzero.core import call_recording

    yield
    call_recording.reset_context()


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
        capture_output=True, text=True, check=True,
    )
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\ndocs/lineage/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-qu", "origin", "main")
    return root


def _snapshot(target: Path) -> dict[str, str]:
    origin = target.parent / "origin.git"
    return {
        "worktrees": _git(target, "worktree", "list", "--porcelain").stdout,
        "branches": _git(target, "branch", "--list", "--all").stdout,
        "status": _git(target, "status", "--porcelain", "--untracked-files=all").stdout,
        "origin_refs": _git(origin, "for-each-ref", "--format=%(refname) %(objectname)").stdout,
    }


def _run_mock(target: Path, tmp_path: Path) -> tuple[int, str]:
    from tools import run_implement_from_lld as tool

    argv = [
        "prog", "--issue", "42", "--repo", str(target), "--mock", "--auto",
        "--db-path", str(tmp_path / "ckpt.db"),
    ]
    out = io.StringIO()
    rc = None
    with patch("sys.argv", argv), redirect_stdout(out):
        try:
            rc = tool.main()
        except SystemExit as exc:
            rc = exc.code
    return rc, out.getvalue()


class TestAMockRunLeavesNothing:
    def test_worktrees_branches_status_and_origin_are_unchanged(self, target_repo, tmp_path):
        before = _snapshot(target_repo)

        rc, out = _run_mock(target_repo, tmp_path)

        assert rc == 0, out
        assert _snapshot(target_repo) == before, out
        assert not (target_repo.parent / "target-42").exists(), out

    def test_the_report_leaves_nothing_in_place(self, target_repo, tmp_path):
        rc, out = _run_mock(target_repo, tmp_path)

        assert rc == 0, out
        assert "[run] left in place (0):" in out, out
        assert "removed worktree:" in out, out

    def test_the_status_file_is_beside_the_run_log(self, target_repo, tmp_path):
        rc, out = _run_mock(target_repo, tmp_path)

        assert rc == 0, out
        runs = target_repo / "data" / "speedrun" / "runs"
        assert (runs / ".implement-status-42.json").exists(), out
        assert not list(target_repo.glob(".implement-status-*.json"))

    def test_the_checkpoint_db_stays_in_the_target_not_home(
        self, target_repo, tmp_path, monkeypatch,
    ):
        """#3547: with no --db-path a mock run wrote ~/.assemblyzero/
        testing_42.db, where a later real --resume for issue 42 would read
        the mock's checkpoints."""
        from tools import run_implement_from_lld as tool

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        argv = ["prog", "--issue", "42", "--repo", str(target_repo), "--mock", "--auto"]
        out = io.StringIO()
        with patch("sys.argv", argv), redirect_stdout(out):
            try:
                tool.main()
            except SystemExit:
                pass

        assert not (home / ".assemblyzero" / "testing_42.db").exists(), out.getvalue()
        db = target_repo / "data" / "mock-runs" / "impl-42" / "checkpoints.db"
        assert db.exists(), out.getvalue()
        assert f"Checkpoint database (resume state): {db}" in out.getvalue()


# A real run's finish (push, remove, delete) is gone: #4150 hands the worktree
# and the branch to the merge driver. Its tests are in
# test_impl_lands_through_driver.py, one for each that stood here.


class TestTheEndStateIsWrittenDown:
    def test_help_carries_the_end_state(self):
        from tools.run_implement_from_lld import create_argument_parser

        text = create_argument_parser().format_help()

        assert "End state (#3509, #4150)" in text
        assert "Left: the implementation merged on the base branch" in text
        assert "AZ_MERGE_DRIVER" in text
        assert "--mock run cuts a detached worktree" in text
        assert "gh pr create" not in text
