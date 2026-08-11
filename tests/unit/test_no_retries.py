"""Automatic retries are deauthorized; drafts go stale (#2206).

Two halves of one operator ruling, both earned on 2026-08-10/11:

1. The redraw loop is retired. A failed roll halts so its cause can be found;
   the relaunch resumes from the failed stage (#2193) rather than re-paying
   for the passed ones. The day that forced it: six spec halts on one issue,
   every one systematic, every redraw a re-run of a known result.

2. A resumed draft must still be derived from current law. The live case —
   an LLD drafted at 01:27Z, invalidated by design-doc rulings merged at
   05:13Z and 06:18Z, while the issue's own text last changed at 01:10Z,
   BEFORE the draft — proves an issue-only staleness check is insufficient.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_roll  # noqa: E402

ARC = "hardening-run-17"
DRAFTED = "2026-08-11T01:27:12Z"
BEFORE_DRAFT = "2026-08-11T01:10:43Z"   # the real issue-edit time that night
AFTER_DRAFT = "2026-08-11T06:18:28Z"    # the real doc-ruling merge time


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    for args in (["init", "-q", "-b", "main"],
                 ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "Test"]):
        subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    (root / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], capture_output=True)
    return root


@pytest.fixture
def log(tmp_path) -> "speedrun_roll.EventLog":
    return speedrun_roll.EventLog(tmp_path / "session-events.log")


def fake_runner(issue_ts: str, doc_ts: str, *, issue_rc: int = 0, doc_rc: int = 0):
    """Stub _run: answers the issue-time probe and the doc-history probe."""
    def _run(cmd, cwd=None):
        if cmd and cmd[0] == "gh":
            return subprocess.CompletedProcess(cmd, issue_rc, issue_ts, "")
        if cmd and cmd[0] == "git" and "log" in cmd:
            return subprocess.CompletedProcess(cmd, doc_rc, doc_ts, "")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return _run


# ---------------------------------------------------------------------------
# Half 1 — the redraw loop is retired
# ---------------------------------------------------------------------------


def test_attempts_above_one_refuses_before_spending(monkeypatch, repo, capsys):
    """The refusal lands before any gate, so nothing is spent."""
    spent: list[str] = []
    monkeypatch.setattr(
        speedrun_roll, "check_assemblyzero_tree",
        lambda *_a: spent.append("tree-gate") or [],
    )
    monkeypatch.setattr(
        speedrun_roll, "check_box_health",
        lambda *_a: spent.append("health-gate"),
    )
    monkeypatch.setattr(speedrun_roll, "roll_issue", lambda *a: spent.append("roll") or 0)

    code = speedrun_roll.main([
        "--repo", str(repo), "--issue", "1", "--attempts", "3",
    ])

    assert code == 91
    assert spent == [], f"a refused launch must spend nothing, ran: {spent}"
    out = capsys.readouterr().out
    assert "#2206" in out
    assert "--attempts 1" in out


def test_attempts_one_is_accepted(monkeypatch, repo):
    """The sanctioned value passes the gate."""
    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda *_a: [])
    monkeypatch.setattr(
        speedrun_roll, "check_box_health",
        lambda *_a: type("H", (), {"ok": True, "message": ""})(),
    )
    monkeypatch.setattr(speedrun_roll, "check_prereqs", lambda *_a: None)
    monkeypatch.setattr(
        speedrun_roll, "sweep_pipeline_worktrees",
        lambda *_a, **_k: type("S", (), {"problems": [], "entries": []})(),
    )
    monkeypatch.setattr(speedrun_roll, "classify_dirt", lambda *_a: ([], []))
    monkeypatch.setattr(speedrun_roll, "untracked_files", lambda *_a: [])
    monkeypatch.setattr(speedrun_roll, "restore_repo", lambda *a: [])
    monkeypatch.setattr(speedrun_roll, "print_verdict", lambda *a, **k: None)
    monkeypatch.setattr(speedrun_roll, "resume_plan", lambda *a: None)
    rolls: list[int] = []
    monkeypatch.setattr(
        speedrun_roll, "roll_issue", lambda *a: rolls.append(a[1]) or 0,
    )

    code = speedrun_roll.main([
        "--repo", str(repo), "--issue", "1", "--attempts", "1",
    ])

    assert code == 0
    assert rolls == [1]


def test_a_failure_rolls_the_issue_exactly_once(monkeypatch, repo):
    """The heart of the ruling: failure does not redraw."""
    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda *_a: [])
    monkeypatch.setattr(
        speedrun_roll, "check_box_health",
        lambda *_a: type("H", (), {"ok": True, "message": ""})(),
    )
    monkeypatch.setattr(speedrun_roll, "check_prereqs", lambda *_a: None)
    monkeypatch.setattr(
        speedrun_roll, "sweep_pipeline_worktrees",
        lambda *_a, **_k: type("S", (), {"problems": [], "entries": []})(),
    )
    monkeypatch.setattr(speedrun_roll, "classify_dirt", lambda *_a: ([], []))
    monkeypatch.setattr(speedrun_roll, "untracked_files", lambda *_a: [])
    monkeypatch.setattr(speedrun_roll, "restore_repo", lambda *a: [])
    monkeypatch.setattr(speedrun_roll, "print_verdict", lambda *a, **k: None)
    monkeypatch.setattr(speedrun_roll, "resume_plan", lambda *a: None)
    calls: list[int] = []
    monkeypatch.setattr(
        speedrun_roll, "roll_issue", lambda *a: calls.append(a[1]) or 1,
    )

    code = speedrun_roll.main([
        "--repo", str(repo), "--issue", "1", "--issue", "7", "--attempts", "1",
    ])

    assert code == 1
    assert calls == [1], "the failed issue must roll once and stop the batch"


def test_a_storm_does_not_wait_or_redraw(monkeypatch, repo):
    """With one roll per issue there is nothing to back off for."""
    monkeypatch.setattr(speedrun_roll, "check_assemblyzero_tree", lambda *_a: [])
    monkeypatch.setattr(
        speedrun_roll, "check_box_health",
        lambda *_a: type("H", (), {"ok": True, "message": ""})(),
    )
    monkeypatch.setattr(speedrun_roll, "check_prereqs", lambda *_a: None)
    monkeypatch.setattr(
        speedrun_roll, "sweep_pipeline_worktrees",
        lambda *_a, **_k: type("S", (), {"problems": [], "entries": []})(),
    )
    monkeypatch.setattr(speedrun_roll, "classify_dirt", lambda *_a: ([], []))
    monkeypatch.setattr(speedrun_roll, "untracked_files", lambda *_a: [])
    monkeypatch.setattr(speedrun_roll, "restore_repo", lambda *a: [])
    monkeypatch.setattr(speedrun_roll, "print_verdict", lambda *a, **k: None)
    monkeypatch.setattr(speedrun_roll, "resume_plan", lambda *a: None)

    def _no_sleep(*_a, **_k):  # pragma: no cover - the assertion IS the test
        raise AssertionError("a storm must not wait when nothing will be redrawn")

    monkeypatch.setattr(speedrun_roll, "_interruptible_sleep", _no_sleep)
    calls: list[int] = []
    monkeypatch.setattr(
        speedrun_roll, "roll_issue",
        lambda *a: calls.append(a[1]) or speedrun_roll.STORM_EXIT_CODE,
    )

    speedrun_roll.main(["--repo", str(repo), "--issue", "1", "--attempts", "1"])

    assert calls == [1]


# ---------------------------------------------------------------------------
# Half 2 — a draft goes stale when binding inputs move
# ---------------------------------------------------------------------------


def test_doc_ruling_after_the_draft_is_stale(monkeypatch, repo, log):
    """The live case: docs moved after the draft, issue text did not."""
    monkeypatch.setattr(
        speedrun_roll, "_run", fake_runner(BEFORE_DRAFT, AFTER_DRAFT),
    )
    assert speedrun_roll.draft_is_stale(repo, 1, DRAFTED, ARC, log) is True


def test_issue_edit_after_the_draft_is_stale(monkeypatch, repo, log):
    monkeypatch.setattr(
        speedrun_roll, "_run", fake_runner(AFTER_DRAFT, BEFORE_DRAFT),
    )
    assert speedrun_roll.draft_is_stale(repo, 1, DRAFTED, ARC, log) is True


def test_current_draft_is_not_stale(monkeypatch, repo, log):
    monkeypatch.setattr(
        speedrun_roll, "_run", fake_runner(BEFORE_DRAFT, BEFORE_DRAFT),
    )
    assert speedrun_roll.draft_is_stale(repo, 1, DRAFTED, ARC, log) is False


def test_repo_with_no_doc_history_is_not_stale(monkeypatch, repo, log):
    """An empty probe result means no binding doc has ever changed."""
    monkeypatch.setattr(speedrun_roll, "_run", fake_runner(BEFORE_DRAFT, ""))
    assert speedrun_roll.draft_is_stale(repo, 1, DRAFTED, ARC, log) is False


def test_unknowable_answers_are_stale(monkeypatch, repo, log):
    """Every probe failure draws fresh, which is always safe."""
    monkeypatch.setattr(
        speedrun_roll, "_run", fake_runner(BEFORE_DRAFT, BEFORE_DRAFT, issue_rc=1),
    )
    assert speedrun_roll.draft_is_stale(repo, 1, DRAFTED, ARC, log) is True

    monkeypatch.setattr(
        speedrun_roll, "_run", fake_runner(BEFORE_DRAFT, BEFORE_DRAFT, doc_rc=1),
    )
    assert speedrun_roll.draft_is_stale(repo, 1, DRAFTED, ARC, log) is True

    monkeypatch.setattr(
        speedrun_roll, "_run", fake_runner("not-a-time", BEFORE_DRAFT),
    )
    assert speedrun_roll.draft_is_stale(repo, 1, DRAFTED, ARC, log) is True


def test_missing_draft_time_is_stale(repo, log):
    assert speedrun_roll.draft_is_stale(repo, 1, "", ARC, log) is True


def test_resume_plan_refuses_a_stale_draft(monkeypatch, repo, log, tmp_path):
    """End to end: every other guard passes, staleness alone draws fresh."""
    az_root = tmp_path / "az"
    state_dir = az_root / ".assemblyzero" / "orchestrator" / "state"
    state_dir.mkdir(parents=True)
    lld = repo / "docs" / "lld" / "active" / "LLD-001.md"
    lld.parent.mkdir(parents=True)
    lld.write_text("# LLD\n", encoding="utf-8")
    (state_dir / "1.json").write_text(json.dumps({
        "issue_number": 1,
        "target_repo": str(repo),
        "base_branch": ARC,
        "started_at": DRAFTED,
        "lld_path": str(lld),
        "stage_results": {
            "lld": {"status": "passed"},
            "spec": {"status": "failed", "error_message": "cap reached"},
        },
    }), encoding="utf-8")
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    monkeypatch.setattr(speedrun_roll, "_open_lld_pr_exists", lambda *_a: True)

    monkeypatch.setattr(speedrun_roll, "draft_is_stale", lambda *_a: False)
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) == "spec"

    monkeypatch.setattr(speedrun_roll, "draft_is_stale", lambda *_a: True)
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) is None
