"""A launch must not destroy an in-flight issue's resume state (#2409).

On 2026-08-15 the launcher's self-heal gate found three things for boostgauge
#1 -- the open LLD PR the requirements workflow keeps open by design, that PR's
branch, and an untracked LLD the halt path left behind -- classified all three
as contamination, and reset the issue. That closed the PR, deleted the remote
branch, deleted the lineage dirs, and removed the worktree holding checkpoint
`d1e9269 [CP:post-impl]`.

What it destroyed was a passed spec stage carrying five review iterations, impl
iteration 0, and the #2383 resume seeds: roughly forty-five to sixty minutes of
machine time, and a fresh spec redraw that then ran without its verdict history.
The checkpoint survived only as an unreferenced object that nothing had
garbage-collected yet.

The same command had resumed the same issue two and a half hours earlier, so
the gate was inconsistent on nearly identical state. The deciding delta was not
the untracked artifact: it was whether `resume_plan` happened to return a stage,
which routes to `ensure_base_for_resume` (verify, never reset) instead of
`ensure_base` (self-heal, which reset).

These tests pin the four rules the issue asks for.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_reset as reset  # noqa: E402
import speedrun_roll as roll  # noqa: E402


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo with one commit, on a branch named like a pipeline branch."""
    r = tmp_path / "target"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "T")
    (r / "README.md").write_text("x\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "initial")
    return r


def _checkpoint_on(repo: Path, branch: str, name: str = "post-impl") -> str:
    """Put a real `[CP:*]` commit on `branch`, the way checkpoints.py does."""
    _git(repo, "checkout", "-b", branch)
    (repo / f"{branch}.py").write_text("work\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"[CP:{name}] issue #1: workflow checkpoint")
    sha = _git(repo, "log", "-1", "--format=%h").stdout.strip()
    _git(repo, "checkout", "main")
    return sha


class TestTheCheckpointIsWhatDecides:
    """Rule 2: resume versus residue is decided by the checkpoint, not cosmetics."""

    def test_a_checkpoint_is_found_on_the_impl_branch(self, repo: Path):
        sha = _checkpoint_on(repo, "1-impl")
        assert roll.find_checkpoint(repo, 1) == sha

    def test_a_checkpoint_is_found_on_any_pipeline_branch(self, repo: Path):
        sha = _checkpoint_on(repo, "1-spec", name="post-scaffold")
        assert roll.find_checkpoint(repo, 1) == sha

    def test_no_checkpoint_when_the_branch_carries_ordinary_commits(
        self, repo: Path
    ):
        _git(repo, "checkout", "-b", "1-impl")
        (repo / "a.py").write_text("x\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "ordinary work, not a checkpoint")
        _git(repo, "checkout", "main")
        assert roll.find_checkpoint(repo, 1) is None

    def test_another_issues_checkpoint_is_not_this_issues(self, repo: Path):
        _checkpoint_on(repo, "41-impl")
        assert roll.find_checkpoint(repo, 1) is None

    def test_an_empty_repo_answers_none_rather_than_raising(self, repo: Path):
        assert roll.find_checkpoint(repo, 1) is None


class TestTheResetIsChosenNeverInferred:
    """Rules 1 and 3, asserted at the decision point in ensure_base."""

    @pytest.fixture
    def gated(self, repo: Path, monkeypatch):
        """A base that is structurally sound but has debris findings.

        Stands in for 2026-08-15's three findings: an open LLD PR, its branch,
        and an untracked LLD.
        """
        monkeypatch.setattr(roll, "resolve_attempt_branch", lambda r: "attempt-1")
        monkeypatch.setattr(roll, "base_is_structurally_sound", lambda r, b: [])
        monkeypatch.setattr(
            roll.gate, "check_repo",
            lambda r, issues, base: [
                "remote branch: origin/1-lld",
                "open PR: #301",
                "untracked artifact: docs/lld/active/LLD-001.md",
            ],
        )
        monkeypatch.setattr(roll, "record_heal", lambda *a, **k: None)
        return repo

    def test_a_checkpoint_preserves_the_work_and_rolls_on(
        self, gated: Path, monkeypatch
    ):
        """The 2026-08-15 fixture: open PR, its branch, and a checkpoint.

        Acceptance leg one, verbatim from the issue: resumes untouched.
        """
        _checkpoint_on(gated, "1-impl")
        called: list[str] = []
        monkeypatch.setattr(
            roll.reset, "reset_one_issue",
            lambda *a, **k: called.append("reset"),
        )
        log = _RecordingLog()

        base = roll.ensure_base(gated, 1, log, fresh=False)

        assert base == "attempt-1", "the roll must proceed on the existing base"
        assert not called, "a checkpoint must never be reset away"
        assert any("preserving, no reset" in line for line in log.lines)

    def test_without_a_checkpoint_a_plain_launch_refuses(
        self, gated: Path, monkeypatch
    ):
        """Acceptance leg two: refuses, with both exits named."""
        called: list[str] = []
        monkeypatch.setattr(
            roll.reset, "reset_one_issue",
            lambda *a, **k: called.append("reset"),
        )
        log = _RecordingLog()

        base = roll.ensure_base(gated, 1, log, fresh=False)

        assert base is None, "refusal must abort the roll, not proceed"
        assert not called, "a plain launch must not reset"
        joined = "\n".join(log.lines)
        assert "REFUSING to reset" in joined
        assert "repair the findings" in joined, "exit 1 must be named"
        assert "--fresh" in joined, "exit 2 must be named"
        for finding in ("origin/1-lld", "#301", "LLD-001.md"):
            assert finding in joined, f"finding {finding} must be listed"

    def test_fresh_performs_the_reset(self, gated: Path, monkeypatch):
        """Acceptance leg three: the destructive path exists, behind the flag."""
        called: list[str] = []
        monkeypatch.setattr(
            roll.reset, "reset_one_issue",
            lambda *a, **k: called.append("reset"),
        )
        monkeypatch.setattr(roll.reset, "_gh_repo", lambda r: "owner/repo")
        monkeypatch.setattr(
            roll.gate, "check_repo", lambda r, issues, base: []
        )
        # check_repo is consulted twice: once for the findings, once after the
        # reset. Return findings first, clean second.
        findings = iter([
            ["remote branch: origin/1-lld", "open PR: #301"],
            [],
        ])
        monkeypatch.setattr(
            roll.gate, "check_repo", lambda r, issues, base: next(findings)
        )
        log = _RecordingLog()

        base = roll.ensure_base(gated, 1, log, fresh=True)

        assert called == ["reset"], "--fresh must actually reset"
        assert base == "attempt-1"

    def test_fresh_resets_even_with_a_checkpoint(self, gated: Path, monkeypatch):
        """The operator's explicit instruction outranks the checkpoint.

        It is not ignored: the reset pins it to a rescue ref first.
        """
        _checkpoint_on(gated, "1-impl")
        called: list[str] = []
        monkeypatch.setattr(
            roll.reset, "reset_one_issue",
            lambda *a, **k: called.append("reset"),
        )
        monkeypatch.setattr(roll.reset, "_gh_repo", lambda r: "owner/repo")
        findings = iter([["open PR: #301"], []])
        monkeypatch.setattr(
            roll.gate, "check_repo", lambda r, issues, base: next(findings)
        )
        log = _RecordingLog()

        roll.ensure_base(gated, 1, log, fresh=True)

        assert called == ["reset"]
        assert any("will be pinned" in line for line in log.lines)


class TestNothingIsDeletedThatCouldBeArchived:
    """Rule 1: the remedy preserves, and it does so consistently."""

    def test_a_checkpoint_is_pinned_before_the_branches_go(self, repo: Path):
        """`d1e9269` survived by luck. This makes it survive by design."""
        sha = _checkpoint_on(repo, "1-impl")

        rescue = reset.pin_checkpoint(repo, 1)

        assert rescue is not None
        resolved = _git(repo, "rev-parse", "--short", rescue).stdout.strip()
        assert resolved == sha

        # The pin must outlive the branch deletion that follows it in
        # reset_one_issue, which is the whole point of the ordering.
        _git(repo, "branch", "-D", "1-impl")
        still = _git(repo, "rev-parse", "--short", rescue).stdout.strip()
        assert still == sha, "the checkpoint was orphaned despite the pin"

    def test_pinning_is_a_no_op_without_a_checkpoint(self, repo: Path):
        assert reset.pin_checkpoint(repo, 1) is None

    def test_the_reset_leaves_no_artifact_behind(self, repo: Path):
        """Acceptance leg four: every pre-reset artifact exists afterwards.

        The 2026-08-15 remedy relocated the LLD while deleting the lineage,
        which is two principles in one function.
        """
        lineage = repo / "docs" / "lineage" / "active" / "1-lld"
        lineage.mkdir(parents=True)
        (lineage / "verdict.md").write_text("five iterations\n", encoding="utf-8")
        (lineage / "draft.md").write_text("spec draft\n", encoding="utf-8")

        before = {p.name: p.read_text(encoding="utf-8")
                  for p in lineage.rglob("*") if p.is_file()}

        reset.archive_lineage_dirs(repo, 1)

        holder = (
            repo / "data" / "speedrun" / "reset-artifacts" / "issue-1"
            / "lineage" / "1-lld"
        )
        after = {p.name: p.read_text(encoding="utf-8")
                 for p in holder.rglob("*") if p.is_file()}
        assert after == before, "the post-reset tree lost content"


class _RecordingLog:
    """Stand-in for EventLog that keeps what was written."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, message: str) -> None:
        self.lines.append(message)
