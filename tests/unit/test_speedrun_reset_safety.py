"""The speedrun reset loses nothing it cannot give back (#4215 to #4219, #4221).

Every test drives real git: the defects live in what git does with a branch,
a ref and a worktree, and a mocked `_run` would report success for the code
that shipped them. Only `gh` is faked, because the target repository in a unit
test has no GitHub remote.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_reset as reset  # noqa: E402
import speedrun_roll as roll  # noqa: E402


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _must(result: subprocess.CompletedProcess) -> str:
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class Gh:
    """A stand-in for the `gh` CLI that the reset shells out to.

    `prs` is what `gh pr list` returns; every `gh pr close` and `gh issue
    reopen` is recorded. Anything that is not `gh` runs for real.
    """

    def __init__(self, prs: list[dict] | None = None, *, issue_state: str = "OPEN"):
        self.prs = prs or []
        self.issue_state = issue_state
        self.closed: list[int] = []
        self.commands: list[list[str]] = []

    def __call__(self, cmd, cwd=None, check=False):
        self.commands.append(list(cmd))
        if cmd[0] != "gh":
            return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
        def done(out=""):
            return subprocess.CompletedProcess(cmd, 0, out, "")

        if cmd[1:3] == ["pr", "list"]:
            return done(json.dumps(self.prs))
        if cmd[1:3] == ["pr", "close"]:
            self.closed.append(int(cmd[3]))
            return done()
        if cmd[1:3] == ["issue", "view"]:
            return done(json.dumps({"state": self.issue_state}))
        return done()


@pytest.fixture
def gh(monkeypatch) -> Gh:
    fake = Gh()
    monkeypatch.setattr(reset, "_run", fake)
    return fake


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    path = tmp_path / "origin.git"
    _must(subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(path)], capture_output=True, text=True,
    ))
    return path


@pytest.fixture
def repo(tmp_path: Path, origin: Path) -> Path:
    """A target repo on `main`, with `origin` carrying the same first commit."""
    root = tmp_path / "target"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-m", "seed")
    git(root, "remote", "add", "origin", str(origin))
    _must(git(root, "push", "origin", "main"))
    git(root, "fetch", "origin")
    git(root, "remote", "set-head", "origin", "main")
    return root


def commit_on(repo: Path, branch: str, message: str, filename: str | None = None) -> str:
    """Commit on `branch` (created from main if new), then return to main. Full sha."""
    exists = git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
    _must(git(repo, "switch", branch) if exists else git(repo, "switch", "-c", branch, "main"))
    (repo / (filename or f"{branch.replace('/', '_')}-{message[:6]}.txt")).write_text(
        message + "\n", encoding="utf-8",
    )
    git(repo, "add", "-A")
    _must(git(repo, "commit", "-m", message))
    sha = _must(git(repo, "rev-parse", "HEAD"))
    _must(git(repo, "switch", "main"))
    return sha


def push_branch(repo: Path, branch: str) -> None:
    _must(git(repo, "push", "-u", "origin", branch))


def remote_heads(origin: Path) -> dict[str, str]:
    out = _must(subprocess.run(
        ["git", "-C", str(origin), "for-each-ref", "--format=%(refname:short) %(objectname)",
         "refs/heads"], capture_output=True, text=True,
    ))
    return {line.split()[0]: line.split()[1] for line in out.splitlines() if line}


def local_branches(repo: Path) -> list[str]:
    out = _must(git(repo, "branch", "--list", "--format=%(refname:short)"))
    return [line for line in out.splitlines() if line]


# ---------------------------------------------------------------------------
# #4216: the checkpoint search and the pin both include issue-{N}
# ---------------------------------------------------------------------------


class TestCheckpointSearch:
    def test_the_pin_finds_a_checkpoint_only_on_the_impl_stage_branch(self, repo: Path):
        """T1 (R1): the impl stage checkpoints on `issue-{N}`, nothing creates
        `{N}-impl`, so before #4216 the newest checkpoint was never pinned."""
        sha = commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")

        rescue = reset.pin_checkpoint(repo, 7)

        assert rescue is not None and rescue.startswith("refs/rescue/")
        assert _must(git(repo, "rev-parse", rescue)) == sha

    def test_the_pin_finds_a_checkpoint_that_survives_only_on_origin(
        self, repo: Path
    ):
        sha = commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")
        push_branch(repo, "issue-7")
        _must(git(repo, "branch", "-d", "issue-7"))

        rescue = reset.pin_checkpoint(repo, 7)

        assert rescue is not None
        assert _must(git(repo, "rev-parse", rescue)) == sha

    def test_the_roll_finds_the_same_checkpoint(self, repo: Path):
        sha = commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")
        assert _must(git(repo, "rev-parse", "--short", sha)) == roll.find_checkpoint(repo, 7)

    def test_the_list_names_the_impl_stage_branch_locally_and_on_origin(self):
        refs = reset.checkpoint_search_refs(7)
        assert refs[:2] == ["issue-7", "origin/issue-7"]
        assert "origin/issue-7" in refs and "7-lld" in refs

    def test_the_pin_and_the_roll_read_one_list(self, repo: Path, monkeypatch):
        """T2 (R2): swap the one shared list for a branch no pipeline names. If
        either function kept a list of its own it would not find the checkpoint
        there, or would still find ones on the real branches."""
        monkeypatch.setattr(reset, "CHECKPOINT_BRANCH_FORMATS", ("only-{issue}",))
        commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")
        assert reset.pin_checkpoint(repo, 7) is None
        assert roll.find_checkpoint(repo, 7) is None

        sha = commit_on(repo, "only-7", "[CP:post-impl] issue #7: workflow checkpoint")
        rescue = reset.pin_checkpoint(repo, 7)
        assert rescue is not None and _must(git(repo, "rev-parse", rescue)) == sha
        assert roll.find_checkpoint(repo, 7) == _must(git(repo, "rev-parse", "--short", sha))


# ---------------------------------------------------------------------------
# #4217: the live-orchestrator refusal reads the lock where the writer puts it
# ---------------------------------------------------------------------------


class TestLockLayoutIsShared:
    @pytest.fixture
    def az(self, tmp_path: Path, monkeypatch) -> Path:
        """An AssemblyZero root the orchestrator is started in: its cwd."""
        root = tmp_path / "assemblyzero"
        root.mkdir()
        monkeypatch.chdir(root)
        monkeypatch.setattr(reset, "AZ_ROOT", root)
        return root

    def test_a_lock_written_by_the_orchestrators_own_code_stops_the_reset_before_any_write(
        self, repo: Path, az: Path, gh: Gh
    ):
        """T1 (R1, R2): the lock comes from `acquire_orchestration_lock`, run as
        the orchestrator runs it (cwd = the AssemblyZero root), and the target
        repo has no `.assemblyzero` directory at all."""
        from assemblyzero.workflows.orchestrator import resume

        commit_on(repo, "issue-7", "[CP:post-impl] issue #7: workflow checkpoint")
        before_refs = _must(git(repo, "for-each-ref"))
        assert not (repo / ".assemblyzero").exists()
        assert resume.acquire_orchestration_lock(7) is True
        try:
            with pytest.raises(reset.LiveOrchestratorError) as caught:
                reset.reset_one_issue(repo, "owner/repo", 7)
        finally:
            resume.release_orchestration_lock(7)

        assert str(az / ".assemblyzero" / "orchestrator" / "locks" / "7.lock") in str(
            caught.value
        )
        assert _must(git(repo, "for-each-ref")) == before_refs, "no pin, no deletion"
        assert [c for c in gh.commands if c[0] == "gh"] == [], "no PR closed, no issue touched"

    def test_the_reader_and_the_writer_share_one_path(self, az: Path):
        from assemblyzero.workflows.orchestrator import resume

        assert resume.acquire_orchestration_lock(7) is True
        try:
            written = [p.resolve() for p in az.rglob("7.lock")]
            assert written == [resume.orchestration_lock_path(7, az).resolve()]
            assert resume.live_orchestrator_pid(7, az) == os.getpid()
        finally:
            resume.release_orchestration_lock(7)

    def test_a_lock_in_the_target_repo_is_not_where_the_orchestrator_writes(
        self, repo: Path, az: Path, gh: Gh
    ):
        stray = repo / ".assemblyzero" / "orchestrator" / "locks"
        stray.mkdir(parents=True)
        (stray / "7.lock").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        reset.refuse_if_orchestrator_is_live(repo, 7)
