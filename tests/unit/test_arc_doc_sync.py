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

import os
import subprocess
import sys
from datetime import datetime, timezone
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


# ---------------------------------------------------------------------------
# CLAUDE.md is law too (#2244)
# ---------------------------------------------------------------------------
#
# The tuple carried only docs/design and docs/adrs, so a CLAUDE.md correction
# on the default branch never reached a running arc -- the exact invisibility
# #2205 closed for design docs, left open for the file the drafter reads as
# project context from the arc's own worktree.
#
# Live case, boostgauge #286: CLAUDE.md's Key modules list stated planned files
# as existing, and four runs each paid a revision iteration for drafts that
# marked the phantom files as Modify. Without this the fix lands on main and
# every future draw on that arc keeps paying the iteration it was meant to end.


def claude_md_on_main(repo: Path, text: str, msg: str = "docs: fix Key modules") -> None:
    git(repo, "checkout", "-q", "main")
    (repo / "CLAUDE.md").write_text(text, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", msg)
    git(repo, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")


def arc_claude_md(repo: Path) -> str:
    return git(repo, "show", f"origin/{ARC}:CLAUDE.md").stdout


def test_claude_md_is_a_binding_doc():
    assert "CLAUDE.md" in speedrun_roll.BINDING_DOC_PATHS, (
        "the drafter reads it from the arc's worktree as law, which is the "
        "tuple's own definition"
    )


def test_a_claude_md_fix_reaches_the_arc(repo, log, monkeypatch):
    """Acceptance 1. The boostgauge #286 shape: a Key-modules correction."""
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    claude_md_on_main(repo, "Key modules: gauge.py (planned, not yet built)\n")

    assert "planned" not in arc_claude_md(repo), "precondition: the arc is behind"

    problems = speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log)

    assert problems == []
    assert "planned" in arc_claude_md(repo), (
        "the correction must reach the arc, or every future draw keeps paying "
        "the iteration it was meant to end"
    )


def test_the_sync_names_the_claude_md_commit(repo, log, monkeypatch):
    """Acceptance 1: shown by the launcher's SYNC lines naming it."""
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    claude_md_on_main(repo, "Key modules: corrected\n", "docs: correct Key modules")

    speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log)

    written = log.path.read_text(encoding="utf-8")
    assert "SYNC 1 binding-doc commit(s)" in written
    assert "correct Key modules" in written
    assert "SYNC verified" in written


def test_an_arc_already_carrying_current_claude_md_stays_silent(repo, log, monkeypatch):
    """Acceptance 3: unchanged from today's behaviour for design docs."""
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    claude_md_on_main(repo, "Key modules: corrected\n")
    assert speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log) == []

    # Second launch, nothing new: no worktree, no push, no noise.
    log.path.write_text("", encoding="utf-8")
    assert speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log) == []
    assert "SYNC" not in log.path.read_text(encoding="utf-8")


def _commit_dated(repo: Path, rel: str, text: str, msg: str, when: str) -> None:
    """Commit on the CURRENT branch with an explicit committer date.

    The date is explicit because the fixture's own base commit is made at test
    runtime: a draft timestamp hardcoded in the past is older than everything,
    so the staleness check returns True whatever the path list says. That made
    the first cut of these tests pass with CLAUDE.md absent from the tuple --
    vacuously green, which is worse than red.
    """
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", msg],
        capture_output=True,
        env={**os.environ, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when},
    )


def _drafted_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


#: #2615: staleness is decided by CONTENT, so these fixtures edit the arc's
#: working tree rather than moving commit dates. The arc IS the tree the roll
#: reads -- `repo` is checked out on it below -- so a doc ruling landing on the
#: arc is a doc changing under the draft, which is #2205's whole subject.
BODY = "# Issue seven\n\nProse only.\n"


def _settle_against_the_arc(repo: Path, issue: int = 7) -> None:
    from assemblyzero.core import settlement as s
    from assemblyzero.workflows.requirements.audit import save_settlement

    lld = repo / "docs" / "lld" / "active" / f"LLD-{issue}.md"
    lld.parent.mkdir(parents=True, exist_ok=True)
    lld.write_text("## 1. Context\n\nDerived.\n", encoding="utf-8")
    save_settlement(
        issue, "lld",
        s.build_settlement(
            "lld", lld, s.collect_inputs(repo, issue_body=BODY),
            verdict="APPROVED",
        ),
        repo,
    )


@pytest.fixture
def body_unchanged(monkeypatch):
    monkeypatch.setattr(
        speedrun_roll, "fetch_issue", lambda _r, _i: ("title", BODY)
    )


def test_a_claude_md_edit_makes_a_persisted_draft_stale(
    repo, log, body_unchanged
):
    """Acceptance 2. A draft made before the correction must redraw, not
    resume onto a document the ruling has already invalidated."""
    git(repo, "checkout", "-q", ARC)
    _settle_against_the_arc(repo)

    _commit_dated(
        repo, "CLAUDE.md", "Key modules: corrected\n",
        "docs: correct Key modules", "2099-01-01T00:00:00+0000",
    )

    assert speedrun_roll.draft_is_stale(repo, 7, log), (
        "the draft was derived before the CLAUDE.md correction, so resuming "
        "spends the stage on a document already known to be wrong"
    )


def test_a_non_binding_edit_leaves_the_draft_current(repo, log, body_unchanged):
    """The control that makes the test above mean something: the SAME shape
    with a file outside the tuple must NOT invalidate the draft. Without this,
    a staleness assertion proves only that some file changed."""
    git(repo, "checkout", "-q", ARC)
    _settle_against_the_arc(repo)

    _commit_dated(
        repo, "README.md", "changed\n", "chore: readme",
        "2099-01-01T00:00:00+0000",
    )

    assert not speedrun_roll.draft_is_stale(repo, 7, log), (
        "code on the arc is not law; only the binding-doc paths invalidate a "
        "draft"
    )


def test_the_staleness_message_names_the_document_that_moved(
    repo, log, body_unchanged
):
    """The old message joined the whole BINDING_DOC_PATHS tuple with '/',
    rendering `docs/design/docs/adrs/CLAUDE.md` -- one nonexistent path. The
    content check names the single input that actually moved, which is both
    unambiguous and more useful, and the run-together hazard is structurally
    gone because no tuple is joined into prose any more."""
    git(repo, "checkout", "-q", ARC)
    _settle_against_the_arc(repo)

    _commit_dated(
        repo, "CLAUDE.md", "changed\n", "docs: change",
        "2099-01-01T00:00:00+0000",
    )

    speedrun_roll.draft_is_stale(repo, 7, log)

    written = log.path.read_text(encoding="utf-8")
    assert "binding:CLAUDE.md" in written
    assert "docs/adrs/CLAUDE.md" not in written


def _issue_updated_at(stamp: str, real):
    """Stub only the gh issue-view probe; every git call runs for real."""
    def _run(cmd, cwd=None, env=None):
        if cmd[:2] == ["gh", "issue"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=stamp, stderr="")
        return real(cmd, cwd=cwd) if env is None else real(cmd, cwd=cwd)
    return _run


# ---------------------------------------------------------------------------
# The arc moved on origin while the local ref slept (#2473)
#
# Earned 2026-08-16: boostgauge PR #321 moved origin/hardening-run-17; the
# next launch built its doc merge on the stale local ref, the push was
# rejected non-fast-forward, the launch died at SYNC BLOCKED in fifteen
# seconds, and a diverged local branch was left stranded. The operator,
# launched detached, believed it was rolling for ninety minutes.
# ---------------------------------------------------------------------------


def move_arc_on_origin(tmp_path: Path, origin: Path, text: str) -> None:
    """Move origin/<ARC> from a second clone, as a pipeline PR merge would.

    The primary clone's local arc ref goes stale -- it learns nothing until
    something fetches, which is exactly the state the launch dies in.
    """
    other = tmp_path / "other-clone"
    subprocess.run(
        ["git", "clone", "--quiet", str(origin), str(other)], capture_output=True
    )
    git(other, "config", "user.email", "t@example.com")
    git(other, "config", "user.name", "Test")
    git(other, "checkout", "-q", ARC)
    (other / "README.md").write_text(text, encoding="utf-8")
    git(other, "add", ".")
    git(other, "commit", "-qm", "arc: a pipeline PR moved the arc")
    git(other, "push", "-q", "origin", ARC)


def test_an_arc_moved_on_origin_is_absorbed_not_fatal(
    repo, origin, log, monkeypatch, tmp_path
):
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    move_arc_on_origin(tmp_path, origin, "arc moved remotely\n")
    rule_on_main(repo, "needle: candy-apple #F73923\n", "docs: the palette ruling")

    problems = speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log)

    assert problems == []
    assert "F73923" in arc_doc(repo), "the ruling reached the moved arc"
    assert "arc moved remotely" in git(
        repo, "show", f"origin/{ARC}:README.md"
    ).stdout, "the remote movement was kept, not clobbered"
    written = log.path.read_text(encoding="utf-8")
    assert "absorbing before the doc merge" in written


def test_a_previously_stranded_diverged_arc_reconciles(
    repo, origin, log, monkeypatch, tmp_path
):
    """The leftover of the 2026-08-16 incident: local-only commits on the
    arc AND independent remote movement. The next launch reconciles by
    ordinary merge -- all three sides land on origin, nothing discarded."""
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    git(repo, "checkout", "-q", ARC)
    (repo / "docs" / "design" / "notes.md").write_text(
        "stranded sync-merge leftovers\n", encoding="utf-8"
    )
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Merge main into arc - the stranded sync merge")
    git(repo, "checkout", "-q", "main")
    move_arc_on_origin(tmp_path, origin, "arc moved remotely\n")
    rule_on_main(repo, "needle: candy-apple #F73923\n", "docs: the palette ruling")

    problems = speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log)

    assert problems == []
    assert "F73923" in arc_doc(repo), "the ruling landed"
    assert "arc moved remotely" in git(
        repo, "show", f"origin/{ARC}:README.md"
    ).stdout, "the remote side survived"
    assert "stranded sync-merge leftovers" in git(
        repo, "show", f"origin/{ARC}:docs/design/notes.md"
    ).stdout, "the stranded local side survived"


def test_a_blocked_push_names_the_leftover_state(repo, origin, log, monkeypatch):
    """A push refusal must say what state it left behind and who repairs it,
    not just relay git's rejection line."""
    monkeypatch.setattr(speedrun_roll.attempt, "default_branch", lambda _r: "main")
    rule_on_main(repo, "needle: candy-apple #F73923\n", "docs: the palette ruling")
    hook = origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho rejected by test hook >&2\nexit 1\n")
    hook.chmod(0o755)

    problems = speedrun_roll.sync_binding_docs_to_arc(repo, ARC, log)

    assert len(problems) == 1
    assert "could not push" in problems[0]
    assert f"local '{ARC}' now carries the sync merge" in problems[0]
    assert "the next launch absorbs" in problems[0]
