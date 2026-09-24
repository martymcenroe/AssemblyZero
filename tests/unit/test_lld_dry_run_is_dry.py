"""`run_requirements_workflow.py --dry-run` touches nothing (#3507).

The pre-generation check ran before the dry-run exit, so `--dry-run --yes`
on an issue with an LLD deleted it, shifted its lineage, then printed DRY
RUN. `test_dry_run_flag_skips_execution` checked the flag parsed and
nothing else (#3294). These read the filesystem after the call.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.requirements.audit import AUDIT_ACTIVE_DIR, LLD_ACTIVE_DIR


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
        capture_output=True, text=True, check=True,
    )
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-qu", "origin", "main")
    return root


def _seed_existing_lld(target: Path) -> tuple[Path, Path]:
    lld = target / LLD_ACTIVE_DIR / "LLD-042.md"
    lld.parent.mkdir(parents=True, exist_ok=True)
    lld.write_text("# Existing LLD\n", encoding="utf-8")
    lineage = target / AUDIT_ACTIVE_DIR / "42-lld"
    lineage.mkdir(parents=True, exist_ok=True)
    (lineage / "001-issue.md").write_text("content\n", encoding="utf-8")
    return lld, lineage


def _run_main(target: Path, *extra: str) -> tuple[int, str]:
    import io
    from contextlib import redirect_stdout

    from tools.run_requirements_workflow import main

    argv = [
        "prog", "--type", "lld", "--issue", "42", "--dry-run",
        "--repo", str(target), "--base-branch", "main", *extra,
    ]
    out = io.StringIO()
    with patch("sys.argv", argv), patch(
        "tools.run_requirements_workflow.resolve_roots",
        return_value=(target.parent, target),
    ), redirect_stdout(out):
        rc = main()
    return rc, out.getvalue()


class TestTheDryRunIsDry:
    def test_dry_run_with_yes_keeps_the_lld_and_its_lineage(self, target_repo):
        lld, lineage = _seed_existing_lld(target_repo)
        before = lld.read_text(encoding="utf-8")

        rc, out = _run_main(target_repo, "--yes")

        assert rc == 0
        assert lld.exists() and lld.read_text(encoding="utf-8") == before
        assert lineage.exists() and (lineage / "001-issue.md").exists()
        assert not (target_repo / AUDIT_ACTIVE_DIR / "42-lld-n1").exists()
        assert "nothing was written, deleted, shifted, cut or pushed" in out

    def test_dry_run_reports_what_regeneration_would_do(self, target_repo):
        _seed_existing_lld(target_repo)
        rc, out = _run_main(target_repo)
        assert rc == 0
        assert "delete docs" in out.replace("\\", "/") or "delete docs" in out
        assert "42-lld-n1" in out
        assert "ask for YES first" in out

    def test_dry_run_cuts_no_worktree_and_no_branch(self, target_repo):
        rc, _ = _run_main(target_repo, "--yes")
        assert rc == 0
        worktrees = _git(target_repo, "worktree", "list", "--porcelain").stdout
        assert worktrees.count("worktree ") == 1
        assert _git(target_repo, "branch", "--list", "42-lld").stdout.strip() == ""
        assert not (target_repo / "data" / "worktrees").exists()

    def test_dry_run_writes_no_run_record(self, target_repo):
        rc, _ = _run_main(target_repo, "--yes")
        assert rc == 0
        assert not (target_repo / "data" / "speedrun").exists()
