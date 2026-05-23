"""Tests for tools/backfill_assemblyzero_flag.py.

Issue: #1212

Covers the file-handling and discovery helpers in isolation. The PR
orchestration (process_repo, poll_mergeable) is exercised via integration —
this test module does NOT spawn real git/gh subprocesses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from backfill_assemblyzero_flag import (
    SKIP_REPOS,
    current_branch,
    discover_repos,
    flip_file,
    is_safe_to_backfill,
    is_unleashed_json_clean,
    needs_flip,
)


# ===========================================================================
# needs_flip
# ===========================================================================


class TestNeedsFlip:
    """T010-T040."""

    def test_T010_missing_file_returns_false(self, tmp_path):
        """File doesn't exist → caller has nothing to do; return False."""
        assert needs_flip(tmp_path / "nonexistent.json") is False

    def test_T020_missing_field_returns_true(self, tmp_path):
        """File present, no assemblyZero key → needs flip."""
        p = tmp_path / ".unleashed.json"
        p.write_text(json.dumps({"profile": "default"}) + "\n", encoding="utf-8")
        assert needs_flip(p) is True

    def test_T030_false_value_returns_true(self, tmp_path):
        """File present, assemblyZero=false → needs flip."""
        p = tmp_path / ".unleashed.json"
        p.write_text(
            json.dumps({"profile": "default", "assemblyZero": False}) + "\n",
            encoding="utf-8",
        )
        assert needs_flip(p) is True

    def test_T040_true_value_returns_false(self, tmp_path):
        """File present, assemblyZero=true → already aligned, no flip."""
        p = tmp_path / ".unleashed.json"
        p.write_text(
            json.dumps({"profile": "default", "assemblyZero": True}) + "\n",
            encoding="utf-8",
        )
        assert needs_flip(p) is False

    def test_T050_invalid_json_returns_false(self, tmp_path):
        """Unparseable JSON → return False (caller decides what to do)."""
        p = tmp_path / ".unleashed.json"
        p.write_text("{not valid json!!", encoding="utf-8")
        assert needs_flip(p) is False


# ===========================================================================
# flip_file
# ===========================================================================


class TestFlipFile:
    """T100-T120."""

    def test_T100_sets_field_from_false_to_true(self, tmp_path):
        p = tmp_path / ".unleashed.json"
        p.write_text(
            json.dumps({"profile": "default", "assemblyZero": False}) + "\n",
            encoding="utf-8",
        )
        flip_file(p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["assemblyZero"] is True

    def test_T110_adds_field_when_missing(self, tmp_path):
        p = tmp_path / ".unleashed.json"
        p.write_text(
            json.dumps({"profile": "default", "claude": {"model": "opus"}}) + "\n",
            encoding="utf-8",
        )
        flip_file(p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["assemblyZero"] is True
        # other fields preserved
        assert data["profile"] == "default"
        assert data["claude"]["model"] == "opus"

    def test_T120_idempotent_when_already_true(self, tmp_path):
        p = tmp_path / ".unleashed.json"
        original = {"profile": "default", "assemblyZero": True}
        p.write_text(json.dumps(original) + "\n", encoding="utf-8")
        flip_file(p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["assemblyZero"] is True


# ===========================================================================
# discover_repos
# ===========================================================================


class TestDiscoverRepos:
    """T200-T230."""

    def test_T200_finds_repos_with_unleashed_json(self, tmp_path):
        """Discovery returns dirs containing .unleashed.json."""
        (tmp_path / "RepoA").mkdir()
        (tmp_path / "RepoA" / ".unleashed.json").write_text("{}", encoding="utf-8")
        (tmp_path / "RepoB").mkdir()
        (tmp_path / "RepoB" / ".unleashed.json").write_text("{}", encoding="utf-8")
        (tmp_path / "RepoC").mkdir()  # no .unleashed.json

        found = discover_repos(tmp_path)
        names = [p.name for p in found]
        assert "RepoA" in names
        assert "RepoB" in names
        assert "RepoC" not in names

    def test_T210_skips_assemblyzero(self, tmp_path):
        """AssemblyZero (the governance layer) is always excluded."""
        (tmp_path / "AssemblyZero").mkdir()
        (tmp_path / "AssemblyZero" / ".unleashed.json").write_text("{}", encoding="utf-8")
        (tmp_path / "OtherRepo").mkdir()
        (tmp_path / "OtherRepo" / ".unleashed.json").write_text("{}", encoding="utf-8")

        found = discover_repos(tmp_path)
        names = [p.name for p in found]
        assert "AssemblyZero" not in names
        assert "OtherRepo" in names

    def test_T220_returns_empty_when_projects_root_missing(self, tmp_path):
        nonexistent = tmp_path / "does-not-exist"
        assert discover_repos(nonexistent) == []

    def test_T230_skips_non_directories(self, tmp_path):
        """A file in projects-root (not a dir) is ignored."""
        (tmp_path / "Repo").mkdir()
        (tmp_path / "Repo" / ".unleashed.json").write_text("{}", encoding="utf-8")
        (tmp_path / "loose-file.txt").write_text("not a repo", encoding="utf-8")

        found = discover_repos(tmp_path)
        names = [p.name for p in found]
        assert "Repo" in names
        assert "loose-file.txt" not in names


# ===========================================================================
# Module-level invariants
# ===========================================================================


def test_skip_repos_contains_assemblyzero():
    """Defensive: AssemblyZero must always be in SKIP_REPOS."""
    assert "AssemblyZero" in SKIP_REPOS


def test_pr_body_has_no_issue_exemption():
    """#1226: PR_BODY must contain the No-Issue: exemption tag so pr-sentinel
    doesn't block cross-repo PRs that have no per-repo issue to close."""
    from backfill_assemblyzero_flag import PR_BODY
    assert "No-Issue:" in PR_BODY
    # And the body should still reference the tracking issue for traceability
    assert "AssemblyZero#" in PR_BODY


# ===========================================================================
# #1222 — precise safety check (replaces coarse working-tree check)
# ===========================================================================


class TestIsUnleashedJsonClean:
    """T300-T320: is_unleashed_json_clean."""

    @patch("backfill_assemblyzero_flag.run")
    def test_T300_returns_true_when_porcelain_empty(self, mock_run, tmp_path):
        """git status --porcelain returns empty → clean."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert is_unleashed_json_clean(tmp_path) is True

    @patch("backfill_assemblyzero_flag.run")
    def test_T310_returns_false_when_modified(self, mock_run, tmp_path):
        """M .unleashed.json → dirty."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=" M .unleashed.json\n", stderr="",
        )
        assert is_unleashed_json_clean(tmp_path) is False

    @patch("backfill_assemblyzero_flag.run")
    def test_T315_returns_false_when_untracked(self, mock_run, tmp_path):
        """?? .unleashed.json → dirty (file exists locally, not in git)."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="?? .unleashed.json\n", stderr="",
        )
        assert is_unleashed_json_clean(tmp_path) is False

    @patch("backfill_assemblyzero_flag.run")
    def test_T320_returns_false_on_git_error(self, mock_run, tmp_path):
        """Non-zero exit (not a git repo, etc.) → not safe."""
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="not a git repo")
        assert is_unleashed_json_clean(tmp_path) is False


class TestCurrentBranch:
    """T400-T420: current_branch."""

    @patch("backfill_assemblyzero_flag.run")
    def test_T400_returns_branch_name(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="main\n", stderr="")
        assert current_branch(tmp_path) == "main"

    @patch("backfill_assemblyzero_flag.run")
    def test_T410_returns_feature_branch(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="feature-foo\n", stderr="",
        )
        assert current_branch(tmp_path) == "feature-foo"

    @patch("backfill_assemblyzero_flag.run")
    def test_T420_returns_none_on_error(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=128, stdout="", stderr="not a git repo",
        )
        assert current_branch(tmp_path) is None


class TestIsSafeToBackfill:
    """T500-T530: is_safe_to_backfill (the precise replacement for the
    coarse working-tree check). Per #1222, only .unleashed.json clean +
    on main matter."""

    @patch("backfill_assemblyzero_flag.run")
    def test_T500_safe_when_on_main_and_clean(self, mock_run, tmp_path):
        """on main, .unleashed.json clean → safe."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),       # porcelain check
            MagicMock(returncode=0, stdout="main\n", stderr=""),  # branch check
        ]
        ok, reason = is_safe_to_backfill(tmp_path)
        assert ok is True
        assert reason == ""

    @patch("backfill_assemblyzero_flag.run")
    def test_T510_unsafe_when_unleashed_json_dirty_on_main(self, mock_run, tmp_path):
        """on main, .unleashed.json modified → not safe."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M .unleashed.json\n", stderr=""),
        ]
        ok, reason = is_safe_to_backfill(tmp_path)
        assert ok is False
        assert ".unleashed.json" in reason

    @patch("backfill_assemblyzero_flag.run")
    def test_T520_unsafe_when_on_feature_branch_clean(self, mock_run, tmp_path):
        """on feature-branch, .unleashed.json clean → not safe (other agent owns)."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="feature-foo\n", stderr=""),
        ]
        ok, reason = is_safe_to_backfill(tmp_path)
        assert ok is False
        assert "feature-foo" in reason
        assert "main" in reason

    @patch("backfill_assemblyzero_flag.run")
    def test_T530_unsafe_when_on_feature_branch_and_dirty(self, mock_run, tmp_path):
        """on feature-branch, .unleashed.json dirty → not safe (dirty fires first)."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M .unleashed.json\n", stderr=""),
        ]
        ok, reason = is_safe_to_backfill(tmp_path)
        assert ok is False
        # Implementation short-circuits on dirty before checking branch.
        assert ".unleashed.json" in reason
