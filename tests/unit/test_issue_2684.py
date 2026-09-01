"""#2684: the LLD stage reads and cuts from the ARC, never from the checkout's HEAD.

A temp repo whose default branch is AHEAD of the arc in code — the shape a
filmed speedrun has the moment v1 ships — discriminates every case: the file
and README text that exist only on the default branch must be absent from
what the LLD stage reads and from the branch its PR rides.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.requirements.git_operations import (
    GitOperationError,
    lld_start_point,
    setup_lld_worktree,
)
from assemblyzero.workflows.requirements.nodes.analyze_codebase import analyze_codebase

MAIN_ONLY_MARKER = "MAIN-ONLY-CONTENT-2684"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def divergent_repo(tmp_path: Path) -> Path:
    """Default branch `main` ahead of arc `arc`: main carries extra.py and a README the arc lacks."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("# demo\n\nThe arc's README.\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "base.py").write_text("def on_the_arc():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", "arc")
    (repo / "src" / "extra.py").write_text("def only_on_main():\n    return 2\n", encoding="utf-8")
    (repo / "README.md").write_text(f"# demo\n\n{MAIN_ONLY_MARKER}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "main is ahead of the arc")
    (repo / "data").mkdir()
    return repo


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True, text=True,
    )
    return result.returncode == 0


# ---- setup_lld_worktree -----------------------------------------------------


def test_worktree_with_base_is_cut_from_the_arc_not_head(divergent_repo: Path):
    worktree, branch = setup_lld_worktree(divergent_repo, 41, base_branch="arc")
    assert branch == "41-lld"
    assert worktree.is_dir()
    assert not (worktree / "src" / "extra.py").exists()          # main-only code is absent
    assert (worktree / "src" / "base.py").exists()
    assert MAIN_ONLY_MARKER not in (worktree / "README.md").read_text(encoding="utf-8")
    assert _is_ancestor(divergent_repo, "arc", "41-lld")
    assert not _is_ancestor(divergent_repo, "main", "41-lld")     # HEAD was never in the lineage


def test_worktree_without_base_keeps_the_old_behaviour(divergent_repo: Path):
    worktree, _ = setup_lld_worktree(divergent_repo, 42)
    assert (worktree / "src" / "extra.py").exists()               # cut from HEAD, as before #2684
    assert _is_ancestor(divergent_repo, "main", "42-lld")


def test_worktree_is_reused_when_present(divergent_repo: Path):
    first, _ = setup_lld_worktree(divergent_repo, 43, base_branch="arc")
    second, _ = setup_lld_worktree(divergent_repo, 43, base_branch="arc")
    assert first == second


def test_start_point_prefers_origin_then_local_then_refuses(divergent_repo: Path):
    assert lld_start_point(divergent_repo, "arc") == "arc"        # no remote in the temp repo
    with pytest.raises(GitOperationError, match="resolves neither"):
        lld_start_point(divergent_repo, "no-such-branch")


def test_worktree_with_unresolvable_base_refuses(divergent_repo: Path):
    with pytest.raises(GitOperationError):
        setup_lld_worktree(divergent_repo, 44, base_branch="no-such-branch")
    assert not (divergent_repo / "data" / "worktrees" / "44-lld").exists()


# ---- analyze_codebase -------------------------------------------------------


def test_analysis_with_base_reads_the_arc(divergent_repo: Path, capsys):
    result = analyze_codebase({
        "repo_path": str(divergent_repo), "issue_number": 41, "base_branch": "arc",
        "issue_text": "add a thing to base.py",
    })
    assert not result.get("error_message")
    context = result["codebase_context"]
    blob = str(context)
    assert MAIN_ONLY_MARKER not in blob                          # the checkout's README did not leak
    assert "only_on_main" not in blob and "only_on_main" not in str(result.get("interface_map", {}))
    assert "[BASE] LLD analysis reads origin/arc via" in capsys.readouterr().out


def test_analysis_without_base_reads_the_checkout(divergent_repo: Path):
    result = analyze_codebase({
        "repo_path": str(divergent_repo), "issue_number": 41,
        "issue_text": "add a thing to base.py",
    })
    assert MAIN_ONLY_MARKER in str(result["codebase_context"])   # pre-#2684 behaviour, unchanged


def test_analysis_fails_closed_when_the_arc_cannot_be_cut(divergent_repo: Path):
    result = analyze_codebase({
        "repo_path": str(divergent_repo), "issue_number": 41, "base_branch": "no-such-branch",
        "issue_text": "anything",
    })
    assert "cannot read the arc" in result["error_message"]
    assert "Refusing to read the checkout" in result["error_message"]
    assert result["codebase_context"]["key_file_excerpts"] == {}


# ---- finalize threads the base into the cut ---------------------------------


@patch("assemblyzero.workflows.requirements.nodes.finalize.setup_lld_worktree")
@patch("assemblyzero.workflows.requirements.nodes.finalize.commit_and_pr")
@patch("assemblyzero.workflows.requirements.nodes.finalize._mirror_to_worktree")
def test_finalize_cuts_the_worktree_from_the_base(mock_mirror, mock_commit_and_pr, mock_setup, tmp_path):
    from assemblyzero.workflows.requirements.nodes.finalize import _commit_and_push_files

    mock_setup.return_value = (tmp_path / "wt", "42-lld")
    mock_mirror.return_value = ["mirrored/file1.md"]
    mock_commit_and_pr.return_value = ("abc123", "https://example.com/pr/1")
    _commit_and_push_files({
        "target_repo": str(tmp_path), "issue_number": 42, "base_branch": "arc",
        "created_files": ["docs/lld/active/LLD-042.md"], "input_type": "issue",
    })
    mock_setup.assert_called_once()
    assert mock_setup.call_args.kwargs.get("base_branch") == "arc"
    assert mock_commit_and_pr.call_args.kwargs["base_branch"] == "arc"
