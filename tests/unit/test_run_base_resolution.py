"""Both entry points tell the testing workflow what the run's base is (#4436).

N5 measures what the run changed from its base, so a state that names none
halts. The orchestrator always knows its base branch. The standalone launcher
knows it on every path but two: a run inside an issue's own work branch, which
asks origin for the default, and a run in place, which freezes HEAD. Git is
real in every test here.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.changed_lines import changed_lines, run_base_commit
from tools.run_implement_from_lld import RunFailed, resolve_run_base


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(root), check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "a.py").write_text("one = 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "base")
    return root


def _edit_and_commit(root: Path) -> None:
    (root / "a.py").write_text("one = 11\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "[CP:post-impl] issue #7: workflow checkpoint")


def test_a_named_base_is_the_answer(repo):
    assert resolve_run_base(repo, 7, "speedrun-attempt-3", resume=False) == (
        "speedrun-attempt-3", "",
    )


def test_a_run_in_place_freezes_head_and_its_own_checkpoints_stay_changes(repo):
    """The whole reason for the freeze: a merge-base with the branch the run
    is on moves with every checkpoint, and reads as nothing changed."""
    branch, frozen = resolve_run_base(repo, 7, "", resume=False)
    _edit_and_commit(repo)

    assert branch == ""
    assert run_base_commit(repo, branch, frozen) == frozen
    assert changed_lines(repo, frozen, lambda _path: True) == {"a.py": {1}}


def test_a_resume_in_place_freezes_nothing_so_the_checkpoints_commit_stands(repo):
    assert resolve_run_base(repo, 7, "", resume=True) == ("", "")


def test_on_an_issue_branch_the_base_is_origins_default(repo, tmp_path):
    bare = tmp_path / "origin.git"
    _git(repo, "clone", "--bare", str(repo), str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "fetch", "origin")
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    _git(repo, "switch", "-c", "7-implementation")
    fork = _git(repo, "rev-parse", "HEAD")
    _edit_and_commit(repo)

    branch, frozen = resolve_run_base(repo, 7, "", resume=False)

    assert (branch, frozen) == ("origin/main", "")
    assert run_base_commit(repo, branch, frozen) == fork, "the issue's commits are the run's"


def test_on_an_issue_branch_with_no_default_the_run_is_refused_before_it_starts(repo):
    _git(repo, "switch", "-c", "7-implementation")

    with pytest.raises(RunFailed) as refused:
        resolve_run_base(repo, 7, "", resume=False)

    assert "--base-branch" in str(refused.value)
    assert "nothing ran" in refused.value.consequence


def test_the_launcher_sends_only_what_it_knows():
    """An empty value in the initial state would overwrite what a resumed
    run's checkpoint holds: `app.stream(initial_state, config)` merges it."""
    source = (
        Path(__file__).resolve().parents[2] / "tools" / "run_implement_from_lld.py"
    ).read_text(encoding="utf-8")

    assert 'if base_commit:\n        initial_state["base_commit"] = base_commit' in source
    assert 'if measured_branch:\n        initial_state["base_branch"] = measured_branch' in source


def test_the_measured_base_never_becomes_the_pr_base():
    """On an issue branch the measured base is `origin/main`, which is no PR
    base: the landing keeps reading `base_branch`, which stays as it was."""
    source = (
        Path(__file__).resolve().parents[2] / "tools" / "run_implement_from_lld.py"
    ).read_text(encoding="utf-8")

    assert "measured_branch, base_commit = resolve_run_base(" in source
    assert "base_branch, base_commit = resolve_run_base(" not in source.replace(
        "measured_branch, base_commit = resolve_run_base(", "",
    )
