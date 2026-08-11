"""Binding-doc rulings reach the arc before the roll reads them (#2205).

The roll's worktree stands on the attempt branch, so the design docs and
ADRs the drafter and reviewer treat as law are the ARC's copies. Issue text
arrives live from GitHub; docs do not.

Earned 2026-08-10: an arc carried a two-day-old aesthetic doc while five
rulings sat on the default branch. Issue #1's spec stage failed twice on an
objection the operator had already answered — the answer existed and was
invisible. Doc rulings had been reaching arcs only when a pipeline PR
happened to smuggle a snapshot along with it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_roll  # noqa: E402

ARC = "hardening-run-9"


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )


@pytest.fixture
def origin(tmp_path) -> Path:
    """A bare remote with main and an arc branch cut from it."""
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--quiet", "--bare", "--initial-branch=main", str(bare)],
        capture_output=True,
    )
    return bare


@pytest.fixture
def repo(tmp_path, origin) -> Path:
    root = tmp_path / "work"
    subprocess.run(
        ["git", "clone", "--quiet", str(origin), str(root)], capture_output=True
    )
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "Test")
    (root / "docs" / "design").mkdir(parents=True)
    (root / "docs" / "design" / "0002-aesthetic.md").write_text(
        "needle: red\n", encoding="utf-8"
    )
    (root / "README.md").write_text("base\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    git(root, "push", "-q", "origin", "main")
    git(root, "branch", ARC)
    git(root, "push", "-q", "origin", ARC)
    git(root, "fetch", "-q", "origin")
    return root


@pytest.fixture
def log(tmp_path) -> "speedrun_roll.EventLog":
    return speedrun_roll.EventLog(tmp_path / "session-events.log")


def rule_on_main(repo: Path, text: str, msg: str = "docs: a ruling") -> None:
    """Land a binding-doc ruling on main, as a merged doc PR would."""
    git(repo, "checkout", "-q", "main")
    (repo / "docs" / "design" / "0002-aesthetic.md").write_text(text, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", msg)
    git(repo, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")


def arc_doc(repo: Path) -> str:
    return git(
        repo, "show", f"origin/{ARC}:docs/design/0002-aesthetic.md"
    ).stdout


# ---------------------------------------------------------------------------
# The case that was live on 2026-08-10
# ---------------------------------------------------------------------------


def test_a_ruling_on_main_reaches_the_arc(repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    rule_on_main(repo, "needle: candy-apple #F73923\n", "docs: the palette ruling")

    assert "F73923" not in arc_doc(repo), "precondition: the arc is behind"

    problems = speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log)

    assert problems == []
    assert "F73923" in arc_doc(repo), "the ruling must now be on the arc"


def test_the_sync_is_announced_with_what_it_carried(repo, log, monkeypatch):
    """Standard 0026: the console says what the machinery did, by name — a
    silent mutation of a shared branch is exactly what an operator must not
    discover later from a diff."""
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    rule_on_main(repo, "needle: candy-apple #F73923\n", "docs: the palette ruling")

    speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log)

    written = log.path.read_text(encoding="utf-8")
    assert "SYNC 1 binding-doc commit(s)" in written
    assert "the palette ruling" in written, "name the ruling being carried"
    assert "SYNC verified" in written


def test_an_arc_already_current_is_silent(repo, log, monkeypatch):
    """No drift, no worktree, no push — the common case must cost nothing."""
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")

    assert speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log) == []


def test_non_doc_commits_do_not_trigger_a_sync(repo, log, monkeypatch):
    """Code on main is the arc's business to merge, not this gate's."""
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    git(repo, "checkout", "-q", "main")
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "chore: readme")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")

    assert speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log) == []


def test_rolling_on_the_default_branch_needs_no_sync(repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    assert speedrun_roll.sync_binding_docs_to_arc(repo, "main", log) == []


# ---------------------------------------------------------------------------
# Refusal beats guessing
# ---------------------------------------------------------------------------


def test_a_conflict_refuses_and_changes_nothing(repo, log, monkeypatch):
    """Both sides edited the same doc lines: the launcher must refuse rather
    than resolve a ruling on the operator's behalf."""
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")

    # The arc edits the doc...
    git(repo, "checkout", "-q", ARC)
    (repo / "docs" / "design" / "0002-aesthetic.md").write_text(
        "needle: arc-side edit\n", encoding="utf-8"
    )
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "docs: arc-side edit")
    git(repo, "push", "-q", "origin", ARC)
    # ...and main edits the same lines.
    rule_on_main(repo, "needle: main-side ruling\n")

    before = arc_doc(repo)
    problems = speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log)

    assert problems, "a conflict must be reported, not silently merged"
    assert "conflict" in problems[0].lower()
    assert "0002-aesthetic.md" in problems[0]
    assert arc_doc(repo) == before, "nothing on the arc may change"


def test_an_unresolvable_default_branch_is_reported(repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "")
    problems = speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log)
    assert problems and "default branch" in problems[0]


def test_no_worktree_is_left_behind(repo, log, monkeypatch):
    """The sync borrows a worktree under data/speedrun/ and returns it —
    stranded worktrees are the failure this campaign already paid for."""
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    rule_on_main(repo, "needle: candy-apple #F73923\n")

    speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log)

    listing = git(repo, "worktree", "list").stdout
    assert ".arc-sync" not in listing
    assert not (repo / "data" / "speedrun" / ".arc-sync").exists()
