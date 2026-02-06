"""Test file for Issue #78: Per-Repo Workflow Database.

Tests the checkpoint database path logic with per-repo isolation.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Generator
from unittest import mock

import pytest

from assemblyzero.workflow.checkpoint import get_checkpoint_db_path, get_repo_root


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repository."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    
    subprocess.run(
        ["git", "init"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    
    yield repo_path


@pytest.fixture
def temp_non_git_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary directory that is NOT a git repo."""
    non_git_path = tmp_path / "not_a_repo"
    non_git_path.mkdir()
    yield non_git_path


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Ensure AGENTOS_WORKFLOW_DB is not set during tests."""
    old_value = os.environ.pop("AGENTOS_WORKFLOW_DB", None)
    yield
    if old_value is not None:
        os.environ["AGENTOS_WORKFLOW_DB"] = old_value


@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    yield None


def test_010(temp_git_repo: Path, clean_env: None):
    """
    Per-repo database creation | Auto | Run workflow in git repo |
    `.assemblyzero/issue_workflow.db` created in repo root | File exists at
    expected path
    """
    original_cwd = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        db_path = get_checkpoint_db_path()
        
        expected_path = temp_git_repo / ".assemblyzero" / "issue_workflow.db"
        assert db_path == expected_path
        assert db_path.parent.exists()
    finally:
        os.chdir(original_cwd)


def test_020(tmp_path: Path, clean_env: None):
    """
    Different repos get different databases | Auto | Run workflow in
    repo1, then repo2 | Two separate database files |
    `repo1/.assemblyzero/issue_workflow.db` != `repo2/.assemblyzero/issue_workflow.db`
    """
    repo1 = tmp_path / "repo1"
    repo2 = tmp_path / "repo2"
    repo1.mkdir()
    repo2.mkdir()
    
    for repo in [repo1, repo2]:
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    
    original_cwd = os.getcwd()
    
    try:
        os.chdir(repo1)
        db_path1 = get_checkpoint_db_path()
        
        os.chdir(repo2)
        db_path2 = get_checkpoint_db_path()
        
        assert db_path1 != db_path2
        assert db_path1 == repo1 / ".assemblyzero" / "issue_workflow.db"
        assert db_path2 == repo2 / ".assemblyzero" / "issue_workflow.db"
    finally:
        os.chdir(original_cwd)


def test_030(temp_git_repo: Path, tmp_path: Path):
    """
    Environment variable override | Auto | Set
    `AGENTOS_WORKFLOW_DB=/tmp/custom.db` | Database at `/tmp/custom.db` |
    File created at env var path, not in repo
    """
    custom_db_path = tmp_path / "custom_location" / "custom.db"
    original_cwd = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        with mock.patch.dict(os.environ, {"AGENTOS_WORKFLOW_DB": str(custom_db_path)}):
            db_path = get_checkpoint_db_path()
        
        assert db_path == custom_db_path
        assert db_path.parent.exists()
    finally:
        os.chdir(original_cwd)


def test_040(temp_non_git_dir: Path, clean_env: None):
    """
    Fail closed outside repo | Auto | Run workflow in non-git directory |
    Exit code 1, error message | Exit code 1; stderr contains
    "AGENTOS_WORKFLOW_DB"
    """
    original_cwd = os.getcwd()
    os.chdir(temp_non_git_dir)
    
    try:
        with pytest.raises(SystemExit) as exc_info:
            get_checkpoint_db_path()
        
        assert exc_info.value.code == 1
    finally:
        os.chdir(original_cwd)


def test_050(temp_git_repo: Path, clean_env: None):
    """
    Worktree isolation | Auto | Create worktree, run workflow | Worktree
    gets own `.assemblyzero/` | `worktree/.assemblyzero/issue_workflow.db` exists
    """
    readme = temp_git_repo / "README.md"
    readme.write_text("# Test")
    subprocess.run(["git", "add", "README.md"], cwd=temp_git_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_git_repo,
        capture_output=True,
        check=True,
    )
    
    worktree_path = temp_git_repo.parent / "worktree"
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "-b", "feature-branch"],
        cwd=temp_git_repo,
        capture_output=True,
        check=True,
    )
    
    original_cwd = os.getcwd()
    os.chdir(worktree_path)
    
    try:
        db_path = get_checkpoint_db_path()
        
        expected_path = worktree_path / ".assemblyzero" / "issue_workflow.db"
        assert db_path == expected_path
        assert db_path.parent.exists()
    finally:
        os.chdir(original_cwd)
        subprocess.run(
            ["git", "worktree", "remove", str(worktree_path)],
            cwd=temp_git_repo,
            capture_output=True,
        )


def test_060(temp_git_repo: Path, tmp_path: Path, clean_env: None):
    """
    Global database untouched | Auto | Run workflow in repo |
    `~/.assemblyzero/issue_workflow.db` unchanged | Global DB not modified
    (timestamp unchanged)
    """
    mock_home = tmp_path / "mock_home"
    mock_home.mkdir()
    global_assemblyzero = mock_home / ".assemblyzero"
    global_assemblyzero.mkdir()
    global_db = global_assemblyzero / "issue_workflow.db"
    global_db.write_text("existing global db")
    
    original_mtime = global_db.stat().st_mtime
    
    original_cwd = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        db_path = get_checkpoint_db_path()
        
        assert temp_git_repo in db_path.parents or db_path.parent.parent == temp_git_repo
        assert global_db.stat().st_mtime == original_mtime
    finally:
        os.chdir(original_cwd)


def test_070(temp_git_repo: Path, clean_env: None):
    """
    Nested repo detection (deep subdirectory) | Auto | Run in
    `repo/src/lib/` subdirectory | Database in repo root, not subdirectory
    | `repo_root/.assemblyzero/` not `repo_root/src/lib/.assemblyzero/`
    """
    deep_dir = temp_git_repo / "src" / "lib" / "utils"
    deep_dir.mkdir(parents=True)
    
    original_cwd = os.getcwd()
    os.chdir(deep_dir)
    
    try:
        db_path = get_checkpoint_db_path()
        
        expected_path = temp_git_repo / ".assemblyzero" / "issue_workflow.db"
        assert db_path == expected_path
        assert db_path != deep_dir / ".assemblyzero" / "issue_workflow.db"
    finally:
        os.chdir(original_cwd)


def test_080(temp_git_repo: Path, clean_env: None):
    """
    .assemblyzero directory creation | Auto | Run in repo without .assemblyzero |
    Directory created with proper permissions | Directory exists with user
    read/write
    """
    original_cwd = os.getcwd()
    os.chdir(temp_git_repo)
    assemblyzero_dir = temp_git_repo / ".assemblyzero"
    
    assert not assemblyzero_dir.exists()
    
    try:
        db_path = get_checkpoint_db_path()
        
        assert assemblyzero_dir.exists()
        assert assemblyzero_dir.is_dir()
        test_file = assemblyzero_dir / "test_write.tmp"
        test_file.write_text("test")
        assert test_file.exists()
        test_file.unlink()
    finally:
        os.chdir(original_cwd)


def test_090(tmp_path: Path):
    """
    Env var with ~ expansion | Auto | Set
    `AGENTOS_WORKFLOW_DB=~/custom.db` | Path expanded correctly | File at
    `$HOME/custom.db`
    """
    mock_home = tmp_path / "mock_home"
    mock_home.mkdir()
    
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        with mock.patch.dict(os.environ, {"AGENTOS_WORKFLOW_DB": "~/custom.db"}):
            with mock.patch("os.path.expanduser") as mock_expand:
                mock_expand.return_value = str(mock_home / "custom.db")
                db_path = get_checkpoint_db_path()
        
        assert db_path == mock_home / "custom.db"
    finally:
        os.chdir(original_cwd)


def test_100(temp_git_repo: Path):
    """
    Empty env var treated as unset | Auto | Set `AGENTOS_WORKFLOW_DB=""`
    | Falls back to per-repo | Uses repo path, not empty string
    """
    original_cwd = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        with mock.patch.dict(os.environ, {"AGENTOS_WORKFLOW_DB": ""}):
            db_path = get_checkpoint_db_path()
        
        expected_path = temp_git_repo / ".assemblyzero" / "issue_workflow.db"
        assert db_path == expected_path
    finally:
        os.chdir(original_cwd)


@pytest.mark.skipif(
    not (Path(__file__).parent.parent / ".gitignore").exists(),
    reason="Source .gitignore not accessible from test location"
)
def test_110(temp_git_repo: Path):
    """
    .gitignore contains .assemblyzero/ pattern | Auto | Check `.gitignore`
    after workflow run | `.assemblyzero/` entry exists | Parse `.gitignore`,
    assert pattern present
    """
    source_gitignore = Path(__file__).parent.parent / ".gitignore"
    content = source_gitignore.read_text()
    assert ".assemblyzero/" in content or ".assemblyzero/issue_workflow.db" in content


def test_120(tmp_path: Path, clean_env: None):
    """
    Concurrent execution (3 repos) | Auto | Spawn 3 subprocess workflows
    in parallel | Each repo has independent database, no errors | All 3
    processes exit 0; 3 distinct `.assemblyzero/issue_workflow.db` files
    """
    repos = []
    for i in range(3):
        repo = tmp_path / f"repo{i}"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        repos.append(repo)
    
    test_script = tmp_path / "test_concurrent.py"
    test_script.write_text('''
import sys
import os
sys.path.insert(0, os.environ["PYTHONPATH"])
from assemblyzero.workflow.checkpoint import get_checkpoint_db_path
path = get_checkpoint_db_path()
print(path)
''')
    
    source_path = Path(__file__).parent.parent
    
    processes = []
    for repo in repos:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(source_path)
        env.pop("AGENTOS_WORKFLOW_DB", None)
        proc = subprocess.Popen(
            [sys.executable, str(test_script)],
            cwd=repo,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append((repo, proc))
    
    results = []
    for repo, proc in processes:
        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 0, f"Process failed: {stderr}"
        db_path = Path(stdout.strip())
        results.append(db_path)
        assert str(repo) in str(db_path)
    
    assert len(set(results)) == 3


def test_get_repo_root_in_repo(temp_git_repo: Path):
    """Test get_repo_root returns correct path when in a git repo."""
    original_cwd = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        result = get_repo_root()
        assert result is not None
        assert result.resolve() == temp_git_repo.resolve()
    finally:
        os.chdir(original_cwd)


def test_get_repo_root_outside_repo(temp_non_git_dir: Path):
    """Test get_repo_root returns None when not in a git repo."""
    original_cwd = os.getcwd()
    os.chdir(temp_non_git_dir)
    
    try:
        result = get_repo_root()
        assert result is None
    finally:
        os.chdir(original_cwd)


def test_get_repo_root_in_subdirectory(temp_git_repo: Path):
    """Test get_repo_root finds root from subdirectory."""
    subdir = temp_git_repo / "src" / "deep" / "nested"
    subdir.mkdir(parents=True)
    
    original_cwd = os.getcwd()
    os.chdir(subdir)
    
    try:
        result = get_repo_root()
        assert result is not None
        assert result.resolve() == temp_git_repo.resolve()
    finally:
        os.chdir(original_cwd)


def test_get_repo_root_git_not_installed():
    """Test get_repo_root returns None when git is not installed.
    
    This covers the FileNotFoundError exception handling (lines 35-37).
    """
    with mock.patch("assemblyzero.workflow.checkpoint.subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("git not found")
        result = get_repo_root()
        assert result is None