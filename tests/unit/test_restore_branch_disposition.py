"""#2310: RESTORE must not strand the branch its worktree carried.

The incident: a failed roll's RESTORE removed the impl worktree but left
`issue-7` standing on the exact SHA the relaunch wanted to branch from. The
relaunch's `git worktree add -b issue-7` died with

    fatal: a branch named 'issue-7' already exists

killing a roll whose spec stage had just passed for the first time in
campaign history.

These tests drive real git repositories rather than mocks, because the
defect lives entirely in what git does with a branch name -- a mocked
`_run` would have happily reported success for the code that shipped the bug.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_reset as reset  # noqa: E402

from assemblyzero.workflows.orchestrator.stages import (  # noqa: E402
    _classify_leftover_branch,
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A git repo with one commit on `main`, origin/HEAD resolvable."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "seed.txt")
    _git(root, "commit", "-m", "seed")
    return root


def _branches(repo: Path) -> list[str]:
    out = _git(repo, "branch", "--list", "--format=%(refname:short)").stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def test_pointer_identical_branch_name_is_freed(repo: Path) -> None:
    """The measured #2310 case: zero unique commits, so the name is freed.

    This is the state that killed the roll -- `issue-7` pointing at the very
    SHA the relaunch wanted as its base.
    """
    _git(repo, "branch", "issue-7")
    assert "issue-7" in _branches(repo)

    failures = reset.dispose_pipeline_branches(repo, 7)

    assert failures == []
    assert "issue-7" not in _branches(repo)


def test_branch_with_unique_commits_is_preserved_not_deleted(
    repo: Path,
) -> None:
    """Unique work is renamed under graveyard/, never deleted.

    The name is still freed -- that is what unblocks the relaunch -- but
    every commit survives under the new name.
    """
    _git(repo, "checkout", "-b", "issue-7")
    (repo / "work.txt").write_text("unique work\n", encoding="utf-8")
    _git(repo, "add", "work.txt")
    _git(repo, "commit", "-m", "work only on issue-7")
    tip = _git(repo, "rev-parse", "issue-7").stdout.strip()
    _git(repo, "checkout", "main")

    failures = reset.dispose_pipeline_branches(repo, 7)

    assert failures == []
    names = _branches(repo)
    assert "issue-7" not in names, "the colliding name must be freed"

    parked = [n for n in names if n.startswith("graveyard/issue-7")]
    assert len(parked) == 1, f"expected one preserved branch, got {names}"
    preserved_tip = _git(repo, "rev-parse", parked[0]).stdout.strip()
    assert preserved_tip == tip, "the commit must survive the rename"


def test_checked_out_branch_is_never_disposed(repo: Path) -> None:
    """#1762: never dispose of the branch the checkout is standing on."""
    _git(repo, "checkout", "-b", "issue-7")

    failures = reset.dispose_pipeline_branches(repo, 7)

    assert failures == []
    assert "issue-7" in _branches(repo)


def test_branch_with_upstream_and_unique_work_is_preserved(
    tmp_path: Path,
) -> None:
    """#2325: an upstream must not make unique work deletable.

    `git branch -d` accepts any branch merged into its UPSTREAM, and every
    pipeline branch gets one at creation (`push -u`, #1780). Delegating the
    decision to `-d` therefore deleted exactly the branches worth keeping --
    observed against the boostgauge #7 branches, which held 3 and 2 commits
    and were both reported as "no unique commits".

    The upstream is the whole point of this test: without a real remote the
    bug is invisible, which is why the earlier tests did not catch it.
    """
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)],
        capture_output=True, text=True,
    )
    root = tmp_path / "clone"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "seed.txt")
    _git(root, "commit", "-m", "seed")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-u", "origin", "main")

    # A pipeline branch with real work, pushed with an upstream.
    _git(root, "checkout", "-b", "issue-7")
    (root / "work.txt").write_text("unique work\n", encoding="utf-8")
    _git(root, "add", "work.txt")
    _git(root, "commit", "-m", "work only on issue-7")
    tip = _git(root, "rev-parse", "issue-7").stdout.strip()
    _git(root, "push", "-u", "origin", "issue-7")
    _git(root, "checkout", "main")

    # Precondition: bare `-d` WOULD accept it. If this ever stops being
    # true the test below is no longer proving anything.
    probe = _git(root, "branch", "-d", "issue-7")
    assert probe.returncode == 0, (
        "expected `branch -d` to accept an upstream-merged branch; "
        f"got: {probe.stderr}"
    )
    _git(root, "branch", "issue-7", tip)

    failures = reset.dispose_pipeline_branches(root, 7, "main")

    assert failures == []
    names = _branches(root)
    assert "issue-7" not in names, "the name must still be freed"
    parked = [n for n in names if n.startswith("graveyard/issue-7")]
    assert len(parked) == 1, f"work must be preserved, got {names}"
    assert _git(root, "rev-parse", parked[0]).stdout.strip() == tip


def test_unmeasurable_comparison_preserves(repo: Path) -> None:
    """#2325: an unknown count preserves rather than deletes.

    A base that cannot be resolved makes the count unknowable. Preserving
    costs a less tidy graveyard; deleting could cost the work.
    """
    _git(repo, "branch", "issue-7")

    failures = reset.dispose_pipeline_branches(
        repo, 7, "no-such-base-ref-exists",
    )

    assert failures == []
    names = _branches(repo)
    assert "issue-7" not in names
    assert any(n.startswith("graveyard/issue-7") for n in names)


def test_disposal_never_force_deletes() -> None:
    """The banned-commands rule, asserted against the source.

    A future edit that reaches for `-D` to make a stubborn branch go away
    fails here rather than in a post-mortem.
    """
    source = (
        Path(__file__).resolve().parents[2] / "tools" / "speedrun_reset.py"
    ).read_text(encoding="utf-8")
    body = source.split("def dispose_pipeline_branches", 1)[1]
    body = body.split("\ndef delete_remote_branches", 1)[0]

    assert '"-D"' not in body
    assert "'-D'" not in body
    assert '"-M"' not in body, "-M would clobber an existing graveyard name"


def test_absent_branch_falls_through_to_normal_creation(repo: Path) -> None:
    """No leftover: neither reusable nor divergent, so `-b` runs as before."""
    verdict = _classify_leftover_branch(str(repo), "issue-7", "main")

    assert verdict.absent is True
    assert verdict.reusable is False
    assert verdict.divergent is False


def test_pointer_identical_leftover_is_reusable(repo: Path) -> None:
    """The measured #2310 case must not kill the roll."""
    _git(repo, "branch", "issue-7")

    verdict = _classify_leftover_branch(str(repo), "issue-7", "main")

    assert verdict.absent is False
    assert verdict.reusable is True
    assert verdict.divergent is False
    assert verdict.unique_commits == 0


def test_divergent_leftover_is_named_not_silently_reused(repo: Path) -> None:
    """A branch holding work is not this roll's to adopt or destroy."""
    _git(repo, "checkout", "-b", "issue-7")
    (repo / "work.txt").write_text("unique\n", encoding="utf-8")
    _git(repo, "add", "work.txt")
    _git(repo, "commit", "-m", "someone else's work")
    _git(repo, "checkout", "main")

    verdict = _classify_leftover_branch(str(repo), "issue-7", "main")

    assert verdict.divergent is True
    assert verdict.reusable is False
    assert verdict.unique_commits == 1
    assert "1 commit(s)" in verdict.describe_unique()


def test_unresolvable_base_keeps_previous_behaviour(repo: Path) -> None:
    """Cannot prove safe or divergent -> let git speak, as before."""
    _git(repo, "branch", "issue-7")

    verdict = _classify_leftover_branch(str(repo), "issue-7", "")

    assert verdict.reusable is False
    assert verdict.divergent is False


def test_relaunch_sequence_survives_the_incident(repo: Path) -> None:
    """End to end: run dies leaving a branch, RESTORE sweeps, relaunch works.

    This is the #2310 acceptance case -- the sequence that failed on
    2026-08-13, driven against real git.
    """
    # A roll creates its impl worktree on issue-7, then dies.
    worktree = repo / "data" / "worktrees" / "7"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    added = _git(
        repo, "worktree", "add", str(worktree), "-b", "issue-7", "main",
    )
    assert added.returncode == 0, added.stderr

    # RESTORE sweeps: worktree removed, then the branch disposed of.
    assert reset.remove_worktree(repo, 7) is True
    assert reset.dispose_pipeline_branches(repo, 7) == []

    # The relaunch carves its worktree from the same base. Before the fix
    # this failed with "a branch named 'issue-7' already exists".
    relaunch = _git(
        repo, "worktree", "add", str(worktree), "-b", "issue-7", "main",
    )
    assert relaunch.returncode == 0, (
        f"relaunch worktree add failed: {relaunch.stderr}"
    )
