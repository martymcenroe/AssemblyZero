"""Tests for move_lineage_to_done() utility.

Issue #100: Lineage active→done moves on workflow completion.
"""

from __future__ import annotations

from pathlib import Path

from assemblyzero.workflows.requirements.audit import move_lineage_to_done


def _setup_lineage(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a mock repo with lineage/active/ and lineage/done/ dirs.

    Returns:
        (target_repo, active_dir, done_dir_parent)
    """
    target_repo = tmp_path / "repo"
    active_dir = target_repo / "docs" / "lineage" / "active" / "42-lld"
    active_dir.mkdir(parents=True)
    # Add a file so we can verify it moved
    (active_dir / "001-brief.md").write_text("# Brief\n")
    return target_repo, active_dir, target_repo / "docs" / "lineage" / "done"


def test_happy_path(tmp_path: Path) -> None:
    """Move lineage dir from active/ to done/ successfully."""
    target_repo, active_dir, done_parent = _setup_lineage(tmp_path)

    result = move_lineage_to_done(active_dir, target_repo)

    assert result is not None
    assert result == done_parent / "42-lld"
    assert result.exists()
    assert (result / "001-brief.md").read_text() == "# Brief\n"
    # Source should be gone
    assert not active_dir.exists()


def test_dir_not_found(tmp_path: Path) -> None:
    """Returns None when the active lineage dir doesn't exist."""
    target_repo = tmp_path / "repo"
    nonexistent = target_repo / "docs" / "lineage" / "active" / "99-lld"

    result = move_lineage_to_done(nonexistent, target_repo)

    assert result is None


def test_dest_exists_skip(tmp_path: Path) -> None:
    """Returns existing done/ path when destination already exists (idempotent)."""
    target_repo, active_dir, done_parent = _setup_lineage(tmp_path)

    # Pre-create done target
    done_dir = done_parent / "42-lld"
    done_dir.mkdir(parents=True)
    (done_dir / "old-file.md").write_text("old content")

    result = move_lineage_to_done(active_dir, target_repo)

    assert result == done_dir
    # Active dir should still exist (wasn't moved)
    assert active_dir.exists()
    # Done dir should still have old content (wasn't overwritten)
    assert (done_dir / "old-file.md").read_text() == "old content"


def test_os_error_returns_none(tmp_path: Path, monkeypatch) -> None:
    """Returns None on OSError during move."""
    target_repo, active_dir, _ = _setup_lineage(tmp_path)

    def failing_move(src, dst):
        raise OSError("Permission denied")

    monkeypatch.setattr("assemblyzero.workflows.requirements.audit.shutil.move", failing_move)

    result = move_lineage_to_done(active_dir, target_repo)

    assert result is None
    # Active dir should still exist (move failed)
    assert active_dir.exists()


def test_creates_done_parent(tmp_path: Path) -> None:
    """Creates the done/ parent directory if it doesn't exist."""
    target_repo, active_dir, done_parent = _setup_lineage(tmp_path)

    # Verify done/ doesn't exist yet
    assert not done_parent.exists()

    result = move_lineage_to_done(active_dir, target_repo)

    assert result is not None
    assert done_parent.exists()


def test_preserves_run_subdir_under_done(tmp_path: Path) -> None:
    """Run-scoped subdir layout: docs/lineage/active/{N}-lld/{run_id}/ moves
    to docs/lineage/done/{N}-lld/{run_id}/. The {N}-lld/ parent is preserved
    so operators can browse done/ by issue, then by run, in the same
    hierarchy. Closes #1467.
    """
    target_repo = tmp_path / "repo"
    run_id = "2026-05-31T17-27-26Z"
    active_dir = target_repo / "docs" / "lineage" / "active" / "42-lld" / run_id
    active_dir.mkdir(parents=True)
    (active_dir / "001-draft.md").write_text("# Draft\n")

    result = move_lineage_to_done(active_dir, target_repo)

    expected = target_repo / "docs" / "lineage" / "done" / "42-lld" / run_id
    assert result == expected, f"Expected {expected}, got {result}"
    assert result.exists()
    assert (result / "001-draft.md").read_text() == "# Draft\n"
    assert not active_dir.exists()


def test_multiple_runs_under_same_issue_dont_collide(tmp_path: Path) -> None:
    """Two runs of issue #4 produce two separate done/ subdirectories;
    moving the second does not overwrite the first. Closes #1467."""
    target_repo = tmp_path / "repo"
    run_a = "2026-05-31T17-27-26Z"
    run_b = "2026-05-31T18-14-09Z"

    active_a = target_repo / "docs" / "lineage" / "active" / "4-lld" / run_a
    active_a.mkdir(parents=True)
    (active_a / "001-draft.md").write_text("A\n")

    active_b = target_repo / "docs" / "lineage" / "active" / "4-lld" / run_b
    active_b.mkdir(parents=True)
    (active_b / "001-draft.md").write_text("B\n")

    result_a = move_lineage_to_done(active_a, target_repo)
    result_b = move_lineage_to_done(active_b, target_repo)

    assert result_a == target_repo / "docs" / "lineage" / "done" / "4-lld" / run_a
    assert result_b == target_repo / "docs" / "lineage" / "done" / "4-lld" / run_b
    assert (result_a / "001-draft.md").read_text() == "A\n"
    assert (result_b / "001-draft.md").read_text() == "B\n"


def test_legacy_layout_without_run_id_still_moves(tmp_path: Path) -> None:
    """Old flat-layout audit_dirs (no run_id subdir) keep moving correctly —
    backward compat. Closes #1467."""
    target_repo, active_dir, done_parent = _setup_lineage(tmp_path)

    result = move_lineage_to_done(active_dir, target_repo)

    assert result == done_parent / "42-lld"
    assert (result / "001-brief.md").read_text() == "# Brief\n"
