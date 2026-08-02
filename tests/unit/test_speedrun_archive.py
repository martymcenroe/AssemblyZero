"""Acceptance tests for the run archiver (#2076).

The six tests named in the issue body are the acceptance criteria; each is
marked with the bullet it implements. They run against a synthetic run built
from a real git repository in a temp dir -- never against live campaign state.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from assemblyzero.speedrun.archive import (
    RestoreRefused,
    archive_run,
    find_orphan_worktrees,
    parse_events_log,
    restore_archive,
    verify_manifest,
)

RUN = "hardening-run-test"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result


def _events(log_dir: Path, tag: str, issue: int, base: str, rc: int | None = 0) -> None:
    """Write a roll's events log in the launcher's exact format."""
    lines = [
        f"2026-08-02 01:00:00 START issue=#{issue} repo=C:\\repo pid=1234",
        f"2026-08-02 01:00:02 BASE '{base}' verified clean for #{issue}",
        f"2026-08-02 01:00:02 LAUNCH base={base} -> {tag}.log",
    ]
    if rc is not None:
        lines.append(f"2026-08-02 01:07:36 CHILD EXITED rc={rc}")
        lines.append(f"2026-08-02 01:07:36 EXIT rc={rc}")
    (log_dir / f"{tag}-events.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (log_dir / f"{tag}.log").write_text(f"stdout for {tag}\n", encoding="utf-8")
    (log_dir / f"{tag}-heartbeat.log").write_text(
        "2026-08-02 01:00:15 alive\n", encoding="utf-8"
    )


@pytest.fixture
def synthetic_run(tmp_path: Path) -> dict:
    """A repo with an integration branch, a graveyard attempt, and two rolls."""
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")

    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")

    _git(repo, "checkout", "-q", "-b", RUN)
    (repo / "feature.py").write_text("value = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "arc work")
    integration_sha = _git(repo, "rev-parse", RUN).stdout.strip()

    _git(repo, "checkout", "-q", "-b", f"graveyard/{RUN}-attempt1")
    (repo / "abandoned.py").write_text("nope = True\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "abandoned attempt")
    _git(repo, "checkout", "-q", RUN)

    log_dir = repo / "data" / "speedrun" / "runs"
    log_dir.mkdir(parents=True)
    _events(log_dir, "run-issue1-010000", 1, RUN, rc=0)
    _events(log_dir, "run-issue4-020000", 4, RUN, rc=1)
    # A roll belonging to a different run must not be swept in.
    _events(log_dir, "run-issue9-030000", 9, "hardening-run-other", rc=0)

    lineage = repo / "docs" / "lineage" / "active" / "1-design"
    lineage.mkdir(parents=True)
    (lineage / "draft-01.md").write_text("# draft\n", encoding="utf-8")

    reset_artifacts = repo / "data" / "speedrun" / "reset-artifacts"
    reset_artifacts.mkdir(parents=True)
    (reset_artifacts / "old-lld.md").write_text("# stale lld\n", encoding="utf-8")

    return {"repo": repo, "log_dir": log_dir, "integration_sha": integration_sha}


# --- "index.json lists every roll, and every manifest sha256 matches" -------


def test_index_lists_every_roll_and_manifest_matches_disk(synthetic_run):
    result = archive_run(
        synthetic_run["repo"], RUN, log_dir=synthetic_run["log_dir"]
    )

    assert result.complete, result.missing
    tags = {r["tag"] for r in result.index["rolls"]}
    assert tags == {"run-issue1-010000", "run-issue4-020000"}

    by_tag = {r["tag"]: r for r in result.index["rolls"]}
    assert by_tag["run-issue1-010000"]["issue"] == 1
    assert by_tag["run-issue1-010000"]["outcome"] == "success"
    assert by_tag["run-issue4-020000"]["outcome"] == "failed rc=1"
    assert by_tag["run-issue1-010000"]["duration_s"] == 456.0

    assert result.index["manifest"], "manifest must not be empty"
    assert verify_manifest(result.path) == []

    on_disk = json.loads((result.path / "index.json").read_text(encoding="utf-8"))
    assert on_disk["manifest"] == result.index["manifest"]


def test_rolls_from_another_run_are_not_swept_in(synthetic_run):
    result = archive_run(synthetic_run["repo"], RUN, log_dir=synthetic_run["log_dir"])
    assert all(r["base"] == RUN for r in result.index["rolls"])
    assert not (result.path / "logs" / "run-issue9-030000.log").exists()


# --- "bundle verify passes, restore reproduces the tip SHA exactly" ---------


def test_bundle_verifies_and_restore_reproduces_tip_sha(synthetic_run, tmp_path):
    result = archive_run(synthetic_run["repo"], RUN, log_dir=synthetic_run["log_dir"])
    bundle = result.path / f"{RUN}.bundle"
    assert bundle.is_file()

    verify = subprocess.run(
        ["git", "bundle", "verify", str(bundle)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert verify.returncode == 0, verify.stderr

    dest = tmp_path / "restored"
    restore_archive(result.path, dest)

    restored_sha = subprocess.run(
        ["git", "-C", str(dest / "repo"), "rev-parse", RUN],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()
    assert restored_sha == synthetic_run["integration_sha"]

    assert (dest / "logs" / "run-issue1-010000-events.log").is_file()
    assert (dest / "artifacts" / "lineage" / "1-design" / "draft-01.md").is_file()


def test_graveyard_branch_is_bundled(synthetic_run, tmp_path):
    result = archive_run(synthetic_run["repo"], RUN, log_dir=synthetic_run["log_dir"])
    names = [b["name"] for b in result.index["branches"]["graveyard"]]
    assert names == [f"graveyard/{RUN}-attempt1"]

    dest = tmp_path / "restored"
    restore_archive(result.path, dest)
    branches = subprocess.run(
        ["git", "-C", str(dest / "repo"), "branch", "-a"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    assert f"graveyard/{RUN}-attempt1" in branches


# --- "on-disk worktree absent from git worktree list is captured" -----------


def test_orphan_worktree_is_captured_and_named(synthetic_run):
    repo = synthetic_run["repo"]
    # Models the verified boostgauge-2 case: a directory on disk that git does
    # not register, whose branch was deleted, so no ref reaches its content.
    orphan = repo.parent / f"{repo.name}-2"
    orphan.mkdir()
    (orphan / ".git").write_text("gitdir: /gone\n", encoding="utf-8")
    (orphan / "unreachable.py").write_text("only_copy = True\n", encoding="utf-8")

    assert orphan.resolve() in [p for p in find_orphan_worktrees(repo)]

    result = archive_run(repo, RUN, log_dir=synthetic_run["log_dir"])

    names = [o["name"] for o in result.index["orphans"]]
    assert f"{repo.name}-2" in names
    assert (result.path / "orphans" / f"{repo.name}-2.tar.gz").is_file()

    import tarfile

    with tarfile.open(result.path / "orphans" / f"{repo.name}-2.tar.gz") as tar:
        members = tar.getnames()
    assert any(m.endswith("unreachable.py") for m in members)


def test_registered_worktree_is_not_reported_as_orphan(synthetic_run):
    repo = synthetic_run["repo"]
    live = repo.parent / f"{repo.name}-live"
    _git(repo, "worktree", "add", "-q", "-b", "live-branch", str(live), "main")
    assert live.resolve() not in find_orphan_worktrees(repo)


# --- "an unreadable component: complete false, names it, exits nonzero" ----


def test_unreadable_component_marks_incomplete_and_names_it(synthetic_run):
    log_dir = synthetic_run["log_dir"]
    # A directory where the stdout log should be: it is listed, so it is an
    # expected component, and copying it raises. Unknown is not zero.
    broken = log_dir / "run-issue1-010000.log"
    broken.unlink()
    broken.mkdir()

    result = archive_run(synthetic_run["repo"], RUN, log_dir=log_dir)

    assert result.complete is False
    assert "logs/run-issue1-010000.log" in result.missing
    named = [c["name"] for c in result.index["incomplete_components"]]
    assert "logs/run-issue1-010000.log" in named
    assert result.index["complete"] is False


def test_cli_exits_nonzero_on_incomplete_archive(synthetic_run, tmp_path):
    import tools.speedrun_archive as cli

    broken = synthetic_run["log_dir"] / "run-issue1-010000.log"
    broken.unlink()
    broken.mkdir()

    code = cli.main([
        "--repo", str(synthetic_run["repo"]),
        "--run", RUN,
        "--log-dir", str(synthetic_run["log_dir"]),
        "--out", str(tmp_path / "arch"),
    ])
    assert code == 1


def test_missing_integration_branch_is_incomplete(synthetic_run):
    result = archive_run(
        synthetic_run["repo"], "no-such-run", log_dir=synthetic_run["log_dir"]
    )
    assert result.complete is False
    assert any("no-such-run" in name for name in result.missing)


# --- "archiving the same run twice produces an identical manifest" ---------


def test_archiving_twice_produces_identical_manifest(synthetic_run):
    first = archive_run(synthetic_run["repo"], RUN, log_dir=synthetic_run["log_dir"])
    first_manifest = dict(first.index["manifest"])

    second = archive_run(synthetic_run["repo"], RUN, log_dir=synthetic_run["log_dir"])

    assert second.index["manifest"] == first_manifest
    assert f"{RUN}.bundle" in first_manifest


# --- "restore of an incomplete archive refuses unless forced" --------------


def test_restore_refuses_incomplete_archive_and_names_component(
    synthetic_run, tmp_path
):
    broken = synthetic_run["log_dir"] / "run-issue1-010000.log"
    broken.unlink()
    broken.mkdir()

    result = archive_run(synthetic_run["repo"], RUN, log_dir=synthetic_run["log_dir"])
    assert result.complete is False

    with pytest.raises(RestoreRefused) as excinfo:
        restore_archive(result.path, tmp_path / "restored")
    assert "run-issue1-010000.log" in str(excinfo.value)

    index = restore_archive(result.path, tmp_path / "forced", force=True)
    assert index["complete"] is False
    assert (tmp_path / "forced" / "repo").is_dir()


# --- events-log parsing ----------------------------------------------------


def test_killed_roll_with_no_exit_line_is_incomplete_not_failed(tmp_path):
    _events(tmp_path, "run-issue2-040000", 2, RUN, rc=None)
    roll = parse_events_log(tmp_path / "run-issue2-040000-events.log")
    assert roll.outcome == "incomplete"
    assert roll.end is None
    assert roll.duration_s is None
    assert roll.issue == 2
    assert roll.base == RUN


def test_archiver_never_deletes_source_content(synthetic_run):
    repo = synthetic_run["repo"]
    before = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*"))
    archive_run(repo, RUN, log_dir=synthetic_run["log_dir"])
    after = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*"))
    # The archive itself is new; nothing that existed before may be gone.
    assert set(before) - set(after) == set()
