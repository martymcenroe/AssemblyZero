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
