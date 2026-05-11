"""Tests for tools/dependabot_review.py cleanup behavior (Issue #1107)."""
import importlib.util
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

# Load the tools/ script as a module without polluting sys.path.
TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_spec = importlib.util.spec_from_file_location(
    "dependabot_review", TOOLS_DIR / "dependabot_review.py"
)
dependabot_review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dependabot_review)


def _mk_completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ---- Bug 1: cleanup_worktree must use `branch -d` (safe), never `branch -D` ----

def test_cleanup_worktree_uses_safe_branch_d_not_capital_D(tmp_path):
    main_repo = tmp_path / "repo"
    worktree = tmp_path / "repo-dependabot-756"
    (worktree / "pyproject.toml").parent.mkdir(parents=True, exist_ok=True)
    (worktree / "pyproject.toml").write_text("")  # so evict_poetry_venv runs

    calls: list[list[str]] = []
    def fake_run(cmd, cwd=None, timeout=None):
        calls.append(cmd)
        return _mk_completed()

    with patch.object(dependabot_review, "run", side_effect=fake_run):
        dependabot_review.cleanup_worktree(main_repo, worktree, "dependabot-audit-756")

    # Find every git branch ... call and assert they all use -d, never -D.
    branch_calls = [c for c in calls if len(c) >= 4 and c[0] == "git" and "branch" in c]
    assert branch_calls, "expected at least one git branch call"
    for c in branch_calls:
        assert "-d" in c, f"expected -d (lowercase) in {c}"
        assert "-D" not in c, f"BANNED: -D found in {c}"


def test_cleanup_worktree_call_order_evict_remove_branch(tmp_path):
    main_repo = tmp_path / "repo"
    worktree = tmp_path / "repo-dependabot-756"
    worktree.mkdir(parents=True)
    (worktree / "pyproject.toml").write_text("")

    calls: list[list[str]] = []
    def fake_run(cmd, cwd=None, timeout=None):
        calls.append(cmd)
        return _mk_completed()

    with patch.object(dependabot_review, "run", side_effect=fake_run):
        dependabot_review.cleanup_worktree(main_repo, worktree, "dependabot-audit-756")

    # poetry env remove --all  ->  worktree remove  ->  branch -d
    cmd_summaries = [" ".join(c) for c in calls]
    assert any("poetry env remove" in s for s in cmd_summaries), cmd_summaries
    assert any("worktree remove" in s for s in cmd_summaries), cmd_summaries
    assert any("branch -d" in s for s in cmd_summaries), cmd_summaries


# ---- Bug 2: checkout_pr_into_worktree must pass --detach ----

def test_checkout_pr_into_worktree_uses_detach_flag(tmp_path):
    worktree = tmp_path / "wt"
    worktree.mkdir()

    captured: list[list[str]] = []
    def fake_run(cmd, cwd=None, timeout=None):
        captured.append(cmd)
        return _mk_completed(returncode=0)

    with patch.object(dependabot_review, "run", side_effect=fake_run):
        ok = dependabot_review.checkout_pr_into_worktree(worktree, 1234, "owner/repo")

    assert ok is True
    assert len(captured) == 1
    cmd = captured[0]
    assert cmd[0:3] == ["gh", "pr", "checkout"]
    assert "--detach" in cmd, f"--detach missing from {cmd} -- bug #1107 regression"
    assert "1234" in cmd
    assert "owner/repo" in cmd


# ---- Bug 3: gc_stale_forensic_worktrees age + registration filtering ----

def test_gc_returns_empty_when_no_dependabot_directories_exist(tmp_path):
    main_repo = tmp_path / "repo"
    main_repo.mkdir()
    with patch.object(dependabot_review, "run", return_value=_mk_completed()):
        cleaned = dependabot_review.gc_stale_forensic_worktrees(main_repo)
    assert cleaned == []


def test_gc_returns_empty_when_parent_directory_missing(tmp_path):
    # main_repo points at something whose parent doesn't exist
    nowhere = tmp_path / "deeply" / "missing" / "repo"
    cleaned = dependabot_review.gc_stale_forensic_worktrees(nowhere)
    assert cleaned == []


def test_gc_skips_unregistered_directory_even_if_old(tmp_path):
    """A dependabot-shaped directory that ISN'T a registered worktree must
    be left alone -- could be user data."""
    main_repo = tmp_path / "repo"
    main_repo.mkdir()
    stray = tmp_path / "repo-dependabot-999"
    stray.mkdir()
    (stray / ".git").write_text("gitdir: irrelevant")
    # Backdate the .git file mtime so the age filter would otherwise match.
    old_ts = time.time() - (30 * 86400)
    (stray / ".git").touch()
    import os
    os.utime(stray / ".git", (old_ts, old_ts))

    # Mock run() so worktree list returns NOTHING (not registered).
    def fake_run(cmd, cwd=None, timeout=None):
        if "worktree" in cmd and "list" in cmd:
            return _mk_completed(stdout="worktree /c/Users/mcwiz/Projects/repo\nHEAD abc\nbranch refs/heads/main\n")
        return _mk_completed()

    with patch.object(dependabot_review, "run", side_effect=fake_run):
        cleaned = dependabot_review.gc_stale_forensic_worktrees(main_repo, max_age_days=14)

    assert cleaned == []  # stray dir not in worktree list -> skipped
    assert stray.exists()


def test_gc_skips_young_registered_worktree(tmp_path):
    main_repo = tmp_path / "repo"
    main_repo.mkdir()
    young = tmp_path / "repo-dependabot-100"
    young.mkdir()
    (young / ".git").write_text("gitdir: x")
    # Default mtime = now -> too young

    young_str = str(young).replace("\\", "/")

    def fake_run(cmd, cwd=None, timeout=None):
        if "worktree" in cmd and "list" in cmd:
            return _mk_completed(stdout=f"worktree {young_str}\nHEAD x\nbranch refs/heads/y\n")
        return _mk_completed()

    with patch.object(dependabot_review, "run", side_effect=fake_run):
        cleaned = dependabot_review.gc_stale_forensic_worktrees(main_repo, max_age_days=14)

    assert cleaned == []
    assert young.exists()


def test_gc_removes_old_registered_worktree(tmp_path):
    main_repo = tmp_path / "repo"
    main_repo.mkdir()
    old = tmp_path / "repo-dependabot-200"
    old.mkdir()
    (old / ".git").write_text("gitdir: x")
    # Backdate the .git file mtime to look stale.
    old_ts = time.time() - (30 * 86400)
    import os
    os.utime(old / ".git", (old_ts, old_ts))

    old_str = str(old).replace("\\", "/")

    captured: list[list[str]] = []

    def fake_run(cmd, cwd=None, timeout=None):
        captured.append(cmd)
        if "worktree" in cmd and "list" in cmd:
            return _mk_completed(stdout=f"worktree {old_str}\nHEAD x\nbranch refs/heads/y\n")
        return _mk_completed()

    with patch.object(dependabot_review, "run", side_effect=fake_run):
        cleaned = dependabot_review.gc_stale_forensic_worktrees(main_repo, max_age_days=14)

    assert cleaned == [str(old)]
    # Verify cleanup_worktree was invoked (saw worktree remove + branch -d for audit-200)
    cmd_strs = [" ".join(c) for c in captured]
    assert any("worktree remove" in s for s in cmd_strs), cmd_strs
    assert any("branch -d dependabot-audit-200" in s for s in cmd_strs), cmd_strs
    # And critically: NEVER -D
    assert not any("branch -D" in s for s in cmd_strs), \
        f"BANNED: -D found in GC path -- {cmd_strs}"


def test_gc_skips_directory_with_unparseable_pr_number(tmp_path):
    main_repo = tmp_path / "repo"
    main_repo.mkdir()
    # Looks like a worktree dir but PR-number suffix is garbage
    bad = tmp_path / "repo-dependabot-foobar"
    bad.mkdir()
    (bad / ".git").write_text("gitdir: x")
    old_ts = time.time() - (30 * 86400)
    import os
    os.utime(bad / ".git", (old_ts, old_ts))

    bad_str = str(bad).replace("\\", "/")

    def fake_run(cmd, cwd=None, timeout=None):
        if "worktree" in cmd and "list" in cmd:
            return _mk_completed(stdout=f"worktree {bad_str}\nHEAD x\nbranch refs/heads/y\n")
        return _mk_completed()

    with patch.object(dependabot_review, "run", side_effect=fake_run):
        cleaned = dependabot_review.gc_stale_forensic_worktrees(main_repo, max_age_days=14)

    assert cleaned == []
    assert bad.exists()


# ---- Constants sanity ----

def test_forensic_age_constant_is_reasonable_days():
    # If anyone changes this to seconds-typed or zero, fail loudly.
    assert isinstance(dependabot_review.FORENSIC_WORKTREE_AGE_DAYS, int)
    assert 1 <= dependabot_review.FORENSIC_WORKTREE_AGE_DAYS <= 90
