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

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from backfill_assemblyzero_flag import (
    SKIP_REPOS,
    discover_repos,
    flip_file,
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
