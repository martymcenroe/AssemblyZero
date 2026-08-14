"""#2346: the pr stage must survive a same-name branch left on origin.

`run-issue7-231606` reached the pr stage for the first time in campaign
history and died on `! [rejected] issue-7 -> issue-7 (non-fast-forward)`.
`origin/issue-7` was a leftover from an earlier run; the new local branch was
cut fresh from the arc, so the two had diverged.

#2310/#2324/#2325 taught RESTORE this discipline for the LOCAL branch --
preserve under graveyard/, never force. The remote never learned it, so
leftovers outlive every run and collide with the next.

These tests drive real git against a real bare remote, because the defect is
entirely about what git does with two diverged refs of the same name.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.orchestrator.graph import RESUMED
from assemblyzero.workflows.orchestrator.stages import (
    NON_FAST_FORWARD,
    _reconcile_stale_remote_branch,
)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True,
    )


@pytest.fixture()
def remote_and_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A bare origin plus a clone sitting on `issue-7`."""
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)],
        capture_output=True, text=True,
    )
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "T")
    (work / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(work, "add", "seed.txt")
    _git(work, "commit", "-m", "seed")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-u", "origin", "main")
    _git(work, "checkout", "-b", "issue-7")
    return origin, work


def _remote_branches(origin: Path) -> list[str]:
    out = _git(origin, "branch", "--list", "--format=%(refname:short)").stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def test_no_remote_branch_needs_no_reconcile(remote_and_worktree) -> None:
    _origin, work = remote_and_worktree
    assert _reconcile_stale_remote_branch(work, "issue-7") == ""


def test_an_ancestor_remote_is_left_alone(remote_and_worktree) -> None:
    """A fast-forwardable remote is not debris — the ordinary push handles it."""
    origin, work = remote_and_worktree
    _git(work, "push", "origin", "issue-7")
    (work / "more.txt").write_text("more\n", encoding="utf-8")
    _git(work, "add", "more.txt")
    _git(work, "commit", "-m", "ahead of origin")

    assert _reconcile_stale_remote_branch(work, "issue-7") == ""
    assert _remote_branches(origin) == sorted(["issue-7", "main"])


def test_a_diverged_remote_is_preserved_and_cleared(remote_and_worktree) -> None:
    """The live case, and the push must succeed afterwards."""
    origin, work = remote_and_worktree
    (work / "old.txt").write_text("earlier run\n", encoding="utf-8")
    _git(work, "add", "old.txt")
    _git(work, "commit", "-m", "an earlier run's work")
    stale_sha = _git(work, "rev-parse", "HEAD").stdout.strip()
    _git(work, "push", "origin", "issue-7")

    # A fresh branch of the same name, cut from main — diverged.
    _git(work, "checkout", "main")
    _git(work, "checkout", "-B", "issue-7", "main")
    (work / "new.txt").write_text("this run\n", encoding="utf-8")
    _git(work, "add", "new.txt")
    _git(work, "commit", "-m", "this run's work")

    # Precondition: without reconciliation the push is rejected.
    rejected = _git(work, "push", "origin", "issue-7")
    assert rejected.returncode != 0
    assert NON_FAST_FORWARD in rejected.stderr.lower()

    note = _reconcile_stale_remote_branch(work, "issue-7")

    assert "preserved as graveyard/issue-7-" in note
    assert "nothing was force-pushed" in note

    branches = _remote_branches(origin)
    assert "issue-7" not in branches, "the colliding name must be cleared"
    parked = [b for b in branches if b.startswith("graveyard/issue-7-")]
    assert len(parked) == 1
    assert _git(origin, "rev-parse", parked[0]).stdout.strip() == stale_sha, (
        "the earlier run's commit must survive"
    )

    # And the push now works.
    assert _git(work, "push", "-u", "origin", "issue-7").returncode == 0


def test_reconcile_never_force_pushes() -> None:
    """Asserted against the source, per the banned-commands discipline."""
    source = (
        Path(__file__).resolve().parents[2]
        / "assemblyzero" / "workflows" / "orchestrator" / "stages.py"
    ).read_text(encoding="utf-8")
    body = source.split("def _reconcile_stale_remote_branch", 1)[1]
    body = body.split("\ndef run_pr_stage", 1)[0]

    for banned in ('"--force"', "'--force'", '"-f"', "'-f'",
                   '"--force-with-lease"'):
        assert banned not in body, banned


def test_an_unreachable_remote_invents_nothing(tmp_path: Path) -> None:
    """A reconcile that cannot read the remote must not act destructively."""
    work = tmp_path / "solo"
    work.mkdir()
    _git(work, "init", "-b", "main")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "T")
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    _git(work, "add", "a.txt")
    _git(work, "commit", "-m", "a")

    assert _reconcile_stale_remote_branch(work, "issue-7") == ""


# --------------------------------------------------- honest retry messaging


def test_the_retry_message_is_stage_appropriate() -> None:
    """A pr retry rewrites no generated files; the message used to say it did."""
    import inspect

    from assemblyzero.workflows.orchestrator import graph

    source = inspect.getsource(graph)
    assert 'current_stage in ("impl", "lld", "spec")' in source
    assert 're-running the {current_stage} stage' in source
    assert RESUMED  # the mode names still drive the wording
