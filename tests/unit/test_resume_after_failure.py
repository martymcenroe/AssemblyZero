"""Acceptance tests for resume-after-failure (#2193).

A relaunch that finds a prior non-conflict failure with the lld already
passed resumes from the failed stage; every guard failure falls back to the
fresh redraw, which is always safe. The launcher is the unit under test --
orchestrate.py's --resume-from machinery is exercised by its own suite.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_roll  # noqa: E402

ARC = "hardening-run-17"
CONFLICT = "REQUIREMENTS CONFLICT: the issue's requirements are inconsistent"


@pytest.fixture
def az_root(tmp_path) -> Path:
    root = tmp_path / "az"
    root.mkdir()
    return root


@pytest.fixture
def repo(tmp_path) -> Path:
    """A real git repo: _restore_artifact runs actual git against it."""
    root = tmp_path / "target"
    root.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "Test"],
    ):
        subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    (root / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], capture_output=True)
    return root


@pytest.fixture
def log(tmp_path) -> "speedrun_roll.EventLog":
    return speedrun_roll.EventLog(tmp_path / "session-events.log")


def write_state(
    az_root: Path,
    issue: int,
    *,
    target_repo: Path,
    base_branch: str = ARC,
    lld_status: str = "passed",
    failed_stage: str | None = "spec",
    failed_status: str = "failed",
    error_message: str = "Spec workflow completed but no artifact produced",
    lld_path: str = "",
    spec_path: str = "",
) -> Path:
    state_dir = az_root / ".assemblyzero" / "orchestrator" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    stage_results: dict = {"triage": {"status": "skipped"}}
    stage_results["lld"] = {"status": lld_status}
    if failed_stage:
        stage_results[failed_stage] = {
            "status": failed_status,
            "error_message": error_message,
        }
    data = {
        "issue_number": issue,
        "current_stage": failed_stage or "lld",
        "target_repo": str(target_repo),
        "base_branch": base_branch,
        "lld_path": lld_path,
        "spec_path": spec_path,
        "stage_results": stage_results,
    }
    path = state_dir / f"{issue}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def resumable(monkeypatch, az_root, repo):
    """Everything a spec-resume needs: matching state, arc, open PR, artifact."""
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    monkeypatch.setattr(speedrun_roll, "_open_lld_pr_exists", lambda *_a: True)
    # #2206 staleness has its own suite; here the draft is current.
    monkeypatch.setattr(speedrun_roll, "draft_is_stale", lambda *_a: False)
    lld = repo / "docs" / "lld" / "active" / "LLD-001.md"
    lld.parent.mkdir(parents=True)
    lld.write_text("# LLD\n", encoding="utf-8")
    write_state(az_root, 1, target_repo=repo, lld_path=str(lld))
    return lld


# ---------------------------------------------------------------------------
# resume_plan guards -- each unmet condition falls back to fresh (None)
# ---------------------------------------------------------------------------


def test_no_state_file_means_fresh(az_root, repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) is None


def test_other_repos_state_never_matches(az_root, repo, tmp_path, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    other = tmp_path / "other-campaign-repo"
    other.mkdir()
    write_state(az_root, 1, target_repo=other)
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) is None


def test_rotated_arc_means_fresh(az_root, repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: "hardening-run-18")
    write_state(az_root, 1, target_repo=repo, base_branch=ARC)
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) is None


def test_failed_lld_means_fresh(az_root, repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    write_state(
        az_root, 1, target_repo=repo,
        lld_status="failed", failed_stage="lld",
        error_message="MECHANICAL VALIDATION FAILED",
    )
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) is None


def test_requirements_conflict_means_fresh(az_root, repo, log, monkeypatch):
    """The documented case: a ruling edited the issue, the draft is stale."""
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    monkeypatch.setattr(speedrun_roll, "_open_lld_pr_exists", lambda *_a: True)
    write_state(
        az_root, 1, target_repo=repo,
        failed_status="blocked", error_message=CONFLICT,
    )
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) is None


def test_pr_stage_failure_is_not_resumable(az_root, repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    monkeypatch.setattr(speedrun_roll, "_open_lld_pr_exists", lambda *_a: True)
    write_state(az_root, 1, target_repo=repo, failed_stage="pr")
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) is None


def test_closed_lld_pr_means_fresh(az_root, repo, log, monkeypatch, resumable):
    monkeypatch.setattr(speedrun_roll, "_open_lld_pr_exists", lambda *_a: False)
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) is None


def test_unrestorable_artifact_means_fresh(az_root, repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    monkeypatch.setattr(speedrun_roll, "_open_lld_pr_exists", lambda *_a: True)
    write_state(
        az_root, 1, target_repo=repo,
        lld_path=str(repo / "docs" / "lld" / "active" / "LLD-001.md"),
    )
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) is None


# ---------------------------------------------------------------------------
# resume_plan happy paths
# ---------------------------------------------------------------------------


def test_spec_failure_resumes_from_spec(az_root, repo, log, resumable):
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) == "spec"


def test_impl_failure_resumes_from_impl(az_root, repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    monkeypatch.setattr(speedrun_roll, "_open_lld_pr_exists", lambda *_a: True)
    monkeypatch.setattr(speedrun_roll, "draft_is_stale", lambda *_a: False)
    lld = repo / "docs" / "lld" / "active" / "LLD-001.md"
    spec = repo / "docs" / "lld" / "active" / "SPEC-001.md"
    lld.parent.mkdir(parents=True)
    lld.write_text("# LLD\n", encoding="utf-8")
    spec.write_text("# SPEC\n", encoding="utf-8")
    write_state(
        az_root, 1, target_repo=repo,
        failed_stage="impl", lld_path=str(lld), spec_path=str(spec),
        error_message="impl worktree build failed",
    )
    assert speedrun_roll.resume_plan(az_root, repo, 1, log) == "impl"


# ---------------------------------------------------------------------------
# _restore_artifact -- the janitor-cleared file comes back from the branch
# ---------------------------------------------------------------------------


def test_restore_artifact_from_lld_branch(repo):
    rel = Path("docs") / "lld" / "active" / "LLD-005.md"
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "5-lld"], capture_output=True)
    target = repo / rel
    target.parent.mkdir(parents=True)
    target.write_text("# LLD five\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "lld"], capture_output=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "main"], capture_output=True)
    assert not target.exists()

    assert speedrun_roll._restore_artifact(repo, 5, str(target)) is True
    assert target.read_text(encoding="utf-8") == "# LLD five\n"


def test_restore_artifact_outside_repo_refuses(repo, tmp_path):
    outside = tmp_path / "elsewhere" / "LLD-005.md"
    assert speedrun_roll._restore_artifact(repo, 5, str(outside)) is False


# ---------------------------------------------------------------------------
# ensure_base_for_resume -- verify, never reset
# ---------------------------------------------------------------------------


def test_resume_base_requires_attempt_branch(repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: "")
    assert speedrun_roll.ensure_base_for_resume(repo, 1, log) is None


def test_resume_base_requires_structural_soundness(repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    monkeypatch.setattr(
        speedrun_roll, "base_is_structurally_sound",
        lambda *_a: ["'hardening-run-17' does not exist on origin"],
    )
    assert speedrun_roll.ensure_base_for_resume(repo, 1, log) is None


def test_resume_base_accepts_sound_base_without_reset(repo, log, monkeypatch):
    monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
    monkeypatch.setattr(speedrun_roll, "base_is_structurally_sound", lambda *_a: [])

    def _no_reset(*_a, **_k):  # pragma: no cover - the assertion IS the test
        raise AssertionError("reset must never run on the resume path")

    monkeypatch.setattr(speedrun_roll.reset, "reset_one_issue", _no_reset)
    assert speedrun_roll.ensure_base_for_resume(repo, 1, log) == ARC


# ---------------------------------------------------------------------------
# roll_issue -- the flag reaches the child, the reset stays away
# ---------------------------------------------------------------------------


def _capture_child(monkeypatch):
    captured: list[list[str]] = []

    def fake_run(cmd, **_kw):
        captured.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(speedrun_roll.subprocess, "run", fake_run)
    return captured


def test_roll_issue_resume_passes_flag_and_skips_reset(repo, tmp_path, monkeypatch):
    captured = _capture_child(monkeypatch)
    monkeypatch.setattr(
        speedrun_roll, "ensure_base_for_resume", lambda *_a: ARC
    )

    def _no_fresh_base(*_a, **_k):  # pragma: no cover - the assertion IS the test
        raise AssertionError("ensure_base must not run when resuming")

    monkeypatch.setattr(speedrun_roll, "ensure_base", _no_fresh_base)

    code = speedrun_roll.roll_issue(
        repo, 1, tmp_path, tmp_path, [], resume_from="spec"
    )
    assert code == 0
    assert captured, "the orchestrator child was never launched"
    child = captured[0]
    assert "--resume-from" in child
    assert child[child.index("--resume-from") + 1] == "spec"


def test_roll_issue_falls_back_to_fresh_when_resume_base_fails(
    repo, tmp_path, monkeypatch
):
    captured = _capture_child(monkeypatch)
    monkeypatch.setattr(speedrun_roll, "ensure_base_for_resume", lambda *_a: None)
    monkeypatch.setattr(speedrun_roll, "ensure_base", lambda *_a: ARC)

    code = speedrun_roll.roll_issue(
        repo, 1, tmp_path, tmp_path, [], resume_from="spec"
    )
    assert code == 0
    assert captured
    assert "--resume-from" not in captured[0]


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def test_detached_argv_forwards_fresh(tmp_path):
    args = argparse.Namespace(
        issue=[1, 7], attempts=3, override_prereqs=False, fresh=True
    )
    argv = speedrun_roll.detached_argv(args, [], tmp_path, tmp_path, tmp_path)
    assert "--fresh" in argv


def test_detached_argv_omits_fresh_by_default(tmp_path):
    args = argparse.Namespace(
        issue=[1], attempts=1, override_prereqs=False, fresh=False
    )
    argv = speedrun_roll.detached_argv(args, [], tmp_path, tmp_path, tmp_path)
    assert "--fresh" not in argv
