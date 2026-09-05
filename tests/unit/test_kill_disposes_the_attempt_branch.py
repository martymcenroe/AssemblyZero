"""An ordered stop disposes the attempt branch, so the resume it promises can
happen (#2859).

`--kill` tree-kills the roll, which skips RESTORE's `finally`. On 2026-09-05
that left `issue-4` standing at the run's last checkpoint. The launcher's entry
sweep removes worktrees and not branches; the next launch's impl stage then
refuses a leftover `issue-N` that carries commits (#2310), and #2845's
recovery looks only under `graveyard/`. The stop had printed "the next launch
resumes from where this one stopped", and the launch that followed halted in
three seconds. The branch was renamed by hand that day.

The first class runs against a REAL git repository: a base branch, an attempt
branch with a checkpoint on it, a registered worktree. The kill itself is
stubbed at the process boundary, as the sibling kill tests do; everything git
does is real, because the claim is about what git is left holding.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """main with one commit; issue-1 with one checkpoint; a worktree on issue-1."""
    r = tmp_path / "campaign"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "T")
    (r / "base.txt").write_text("base\n", encoding="utf-8")
    _git(r, "add", "base.txt")
    _git(r, "commit", "-m", "base")
    (r / "data" / "speedrun" / "runs").mkdir(parents=True)
    _git(r, "worktree", "add", str(r / "data" / "worktrees" / "1"), "-b", "issue-1", "main")
    wt = r / "data" / "worktrees" / "1"
    (wt / "impl.py").write_text("x = 1\n", encoding="utf-8")
    _git(wt, "add", "impl.py")
    _git(wt, "commit", "-m", "[CP:post-impl] issue #1: workflow checkpoint")
    return r


@pytest.fixture
def log_dir(repo):
    return repo / "data" / "speedrun" / "runs"


def _kill(repo, log_dir, issue=1):
    sr.pid_file(log_dir).write_text("48324", encoding="utf-8")
    patches = [
        patch.object(sr, "is_live_python", return_value=True),
        patch.object(sr, "tree_kill", return_value=(True, "")),
        patch.object(sr, "_active_run_event_logs", return_value=[]),
    ]
    if sys.platform == "win32":
        patches.append(patch.object(sr, "_end_task_for", return_value=(False, "no task")))
    for p in patches:
        p.start()
    try:
        return sr.kill_roll(repo, log_dir, issue)
    finally:
        for p in patches:
            p.stop()


class TestTheAttemptBranchIsDisposed:
    def test_issue_branch_is_gone_and_its_checkpoint_is_under_graveyard(self, repo, log_dir, capsys):
        tip = _git(repo, "rev-parse", "issue-1")

        code = _kill(repo, log_dir)

        assert code == 0
        branches = _git(repo, "branch", "--list", "--format=%(refname:short)").splitlines()
        assert "issue-1" not in branches, branches
        graves = [b for b in branches if b.startswith("graveyard/issue-1-")]
        assert len(graves) == 1, branches
        assert _git(repo, "rev-parse", graves[0]) == tip, "the checkpoint must survive at the same SHA"
        assert "the next launch recovers it" in capsys.readouterr().out

    def test_the_worktree_is_removed(self, repo, log_dir):
        _kill(repo, log_dir)

        listed = _git(repo, "worktree", "list", "--porcelain")
        assert "data/worktrees/1" not in listed.replace("\\", "/"), listed

    def test_a_branch_with_nothing_unique_is_freed_not_preserved(self, repo, log_dir):
        """#2310's other disposition: pointer-identical to the base means the
        name is simply freed, and no grave is made for nothing."""
        # Rewind issue-1 to main by recreating it empty.
        _git(repo, "worktree", "remove", str(repo / "data" / "worktrees" / "1"))
        _git(repo, "branch", "-m", "issue-1", "graveyard/issue-1-earlier")
        _git(repo, "branch", "issue-1", "main")

        _kill(repo, log_dir)

        branches = _git(repo, "branch", "--list", "--format=%(refname:short)").splitlines()
        assert "issue-1" not in branches
        assert [b for b in branches if b.startswith("graveyard/issue-1-")] == [
            "graveyard/issue-1-earlier"
        ]


class TestNothingIsDisposedUnlessATreeWasKilled:
    def test_a_stale_pid_leaves_the_branch_alone(self, repo, log_dir):
        sr.pid_file(log_dir).write_text("48324", encoding="utf-8")
        with patch.object(sr, "is_live_python", return_value=False), \
             patch.object(sr, "tree_kill", return_value=(True, "")), \
             patch.object(sr, "_active_run_event_logs", return_value=[]):
            sr.kill_roll(repo, log_dir, 1)

        branches = _git(repo, "branch", "--list", "--format=%(refname:short)").splitlines()
        assert "issue-1" in branches

    def test_no_issue_named_means_no_disposal(self, repo, log_dir, capsys):
        _kill(repo, log_dir, issue=None)

        branches = _git(repo, "branch", "--list", "--format=%(refname:short)").splitlines()
        assert "issue-1" in branches
        assert "no issue named" in capsys.readouterr().out


class TestACleanupFailureDoesNotFailTheStop:
    def test_a_repo_git_cannot_read_still_reports_a_successful_stop(self, tmp_path, capsys):
        """The sibling kill tests use a bare `.git` directory and patch
        `sr._run`; disposal runs real git through `speedrun_reset`, which
        must report rather than raise on such a tree."""
        fake = tmp_path / "boostgauge"
        (fake / ".git").mkdir(parents=True)
        log_dir = fake / "data" / "speedrun" / "runs"
        log_dir.mkdir(parents=True)

        code = _kill(fake, log_dir)

        assert code == 0
        out = capsys.readouterr().out
        assert "This was an ordered stop" in out
