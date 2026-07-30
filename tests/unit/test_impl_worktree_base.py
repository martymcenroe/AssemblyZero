"""The impl stage's worktree is carved from a NAMED base (#1960).

`git worktree add -b issue-N <path>` with no commit-ish branches from whatever
the target repo is checked out on, so the content a roll started from was
decided by ambient state. `--base-branch` did not help: it resolves to the PR
target (`stages.py`: `gh pr create --base`), so a roll could target `main`
while its worktree carried a different branch's tree entirely.

That is the same trap #1852/#1903 closed for hand-driven branching — never cut
a branch from ambient HEAD without checking where HEAD is. The pipeline did it
on every roll.

These tests assert on the argv handed to git. That is deliberately white-box:
the base ref is a positional argument whose ABSENCE was the defect, and no
observable output distinguishes "carved from the right base" from "carved from
whatever was checked out" until a whole roll has run and silently built nothing.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.utils.git import GitBranchError
from assemblyzero.workflows.orchestrator import stages


def _completed(returncode=0, stdout="", stderr=""):
    # mock-ok: subprocess boundary, and a REAL CompletedProcess (standard 0024).
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


class _Recorder:
    """Captures every run_command argv, succeeding for all of them."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *args, **kwargs):
        self.calls.append(list(cmd) if isinstance(cmd, list) else [cmd])
        return _completed()

    def worktree_add(self) -> list[str] | None:
        for cmd in self.calls:
            if "worktree" in cmd and "add" in cmd:
                return cmd
        return None


@pytest.fixture
def state(tmp_path):
    target = tmp_path / "targetrepo"
    target.mkdir()
    return {
        "issue_number": 4,
        "target_repo": str(target),
        "assemblyzero_root": str(tmp_path / "az"),
    }


def _run_impl(state, recorder, worktree_missing=True):
    """Drive run_impl_stage far enough to issue the worktree add."""
    with patch.object(stages, "run_command", recorder), \
         patch.object(Path, "is_dir", return_value=not worktree_missing):
        try:
            stages.run_impl_stage(state)
        except Exception:
            # Downstream stage work (provisioning, workflow invocation) is not
            # under test; the worktree add has already been recorded.
            pass
    return recorder.worktree_add()


class TestBaseIsNamedExplicitly:
    def test_base_branch_from_state_is_passed_as_the_base_ref(self, state):
        state["base_branch"] = "hardening-run-12"
        cmd = _run_impl(state, _Recorder())

        assert cmd is not None, "no worktree add was issued"
        assert cmd[-1] == "hardening-run-12", cmd
        # And it must come AFTER -b <branch>, i.e. be the base, not the name.
        assert cmd[cmd.index("-b") + 1] == "issue-4", cmd

    def test_the_new_branch_name_is_still_the_issue_branch(self, state):
        state["base_branch"] = "main"
        cmd = _run_impl(state, _Recorder())

        assert "-b" in cmd and cmd[cmd.index("-b") + 1] == "issue-4", cmd

    def test_resolved_base_is_printed(self, state, capsys):
        state["base_branch"] = "speedrun-attempt-3"
        _run_impl(state, _Recorder())

        assert "Worktree base: speedrun-attempt-3" in capsys.readouterr().out

    def test_worktree_belongs_to_the_target_repo(self, state):
        """#1374: `git -C <target>` must still precede the subcommand."""
        state["base_branch"] = "main"
        cmd = _run_impl(state, _Recorder())

        assert cmd[:3] == ["git", "-C", state["target_repo"]], cmd


class TestFallbackWhenStateCarriesNoBase:
    def test_falls_back_to_the_target_repos_current_branch(self, state):
        with patch.object(stages, "current_branch", return_value="main"):
            cmd = _run_impl(state, _Recorder())

        assert cmd[-1] == "main", cmd

    def test_detached_head_keeps_the_previous_ambient_behaviour(
        self, state, capsys
    ):
        """Resolving the base is an improvement, not a new failure mode: a repo
        git cannot answer for must not start failing rolls."""
        with patch.object(
            stages, "current_branch", side_effect=GitBranchError("detached")
        ):
            cmd = _run_impl(state, _Recorder())

        assert cmd is not None
        assert cmd[-1] == "issue-4", cmd  # -b <name>, no trailing base ref
        out = capsys.readouterr().out
        assert "base branch unresolved" in out

    @pytest.mark.parametrize(
        "error", [FileNotFoundError("no such dir"), NotADirectoryError("nope")]
    )
    def test_unrunnable_target_path_does_not_fail_the_stage(self, state, error):
        """A target_repo git cannot chdir into raises OSError, not
        GitBranchError. Letting that escape aborted the stage before it issued
        a single command -- caught by the existing orchestrator suite when the
        first version of this change only handled GitBranchError."""
        with patch.object(stages, "current_branch", side_effect=error):
            cmd = _run_impl(state, _Recorder())

        assert cmd is not None, "the worktree add must still be attempted"
        assert cmd[-1] == "issue-4", cmd


class TestExistingWorktreeUntouched:
    def test_no_add_when_the_worktree_already_exists(self, state):
        state["base_branch"] = "main"
        recorder = _Recorder()
        cmd = _run_impl(state, recorder, worktree_missing=False)

        assert cmd is None, f"worktree add issued for an existing worktree: {cmd}"
