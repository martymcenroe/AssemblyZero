"""Tests for the flat-to-run-scoped lineage migration tool.

Closes #1480.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _make_flat_layout(repo_root: Path) -> None:
    """Create a flat-layout lineage directory: docs/lineage/done/4-lld/001-issue.md."""
    flat = repo_root / "docs" / "lineage" / "done" / "4-lld"
    flat.mkdir(parents=True)
    (flat / "001-issue.md").write_text("issue\n")
    (flat / "002-draft.md").write_text("draft\n")
    (flat / "003-verdict.md").write_text("verdict\n")


def _make_run_scoped_layout(repo_root: Path) -> None:
    """Create an already-run-scoped lineage dir that should NOT be touched."""
    rs = repo_root / "docs" / "lineage" / "done" / "5-lld" / "2026-05-31T17-27-26Z"
    rs.mkdir(parents=True)
    (rs / "001-issue.md").write_text("scoped issue\n")


def test_plan_moves_finds_flat_files(tmp_path):
    from tools.migrate_lineage_flat_to_run_scoped import plan_moves

    _make_flat_layout(tmp_path)
    moves = plan_moves(tmp_path)

    assert len(moves) == 3
    for src, dst in moves:
        assert "legacy" in str(dst.parent)
        assert dst.name == src.name


def test_plan_moves_ignores_run_scoped_subdirs(tmp_path):
    from tools.migrate_lineage_flat_to_run_scoped import plan_moves

    _make_run_scoped_layout(tmp_path)
    moves = plan_moves(tmp_path)
    assert moves == []


def test_plan_moves_handles_mixed_layout(tmp_path):
    from tools.migrate_lineage_flat_to_run_scoped import plan_moves

    _make_flat_layout(tmp_path)
    _make_run_scoped_layout(tmp_path)
    moves = plan_moves(tmp_path)
    # Only the 3 flat files; the run-scoped ones are untouched.
    assert len(moves) == 3
    for src, _ in moves:
        assert "4-lld" in str(src)


def test_plan_moves_returns_empty_when_no_lineage_dir(tmp_path):
    from tools.migrate_lineage_flat_to_run_scoped import plan_moves

    # tmp_path has no docs/lineage/
    moves = plan_moves(tmp_path)
    assert moves == []


def test_apply_moves_relocates_files(tmp_path):
    from tools.migrate_lineage_flat_to_run_scoped import apply_moves, plan_moves

    _make_flat_layout(tmp_path)
    moves = plan_moves(tmp_path)
    apply_moves(moves)

    flat = tmp_path / "docs" / "lineage" / "done" / "4-lld"
    legacy = flat / "legacy"
    # Originals removed
    assert not (flat / "001-issue.md").exists()
    # Moved into legacy/
    assert (legacy / "001-issue.md").read_text() == "issue\n"
    assert (legacy / "002-draft.md").read_text() == "draft\n"
    assert (legacy / "003-verdict.md").read_text() == "verdict\n"


def test_idempotent_apply(tmp_path):
    """Running --apply twice is safe; second run finds no flat files."""
    from tools.migrate_lineage_flat_to_run_scoped import apply_moves, plan_moves

    _make_flat_layout(tmp_path)
    apply_moves(plan_moves(tmp_path))
    # Second plan finds nothing to do
    second_plan = plan_moves(tmp_path)
    assert second_plan == []


def test_dry_run_does_not_move(tmp_path, capsys):
    """`main()` without --apply leaves the filesystem unchanged."""
    from tools.migrate_lineage_flat_to_run_scoped import main

    _make_flat_layout(tmp_path)
    rc = main(["--repo", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "001-issue.md" in out
    # Files still in their original flat location
    flat = tmp_path / "docs" / "lineage" / "done" / "4-lld"
    assert (flat / "001-issue.md").exists()


def test_apply_via_main(tmp_path, capsys):
    """`main(['--apply'])` actually moves the files."""
    from tools.migrate_lineage_flat_to_run_scoped import main

    _make_flat_layout(tmp_path)
    rc = main(["--repo", str(tmp_path), "--apply"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "APPLY" in out
    # Files moved into legacy/
    legacy = tmp_path / "docs" / "lineage" / "done" / "4-lld" / "legacy"
    assert (legacy / "001-issue.md").exists()


def test_active_subtree_also_migrated(tmp_path):
    """Both active/ and done/ subtrees are walked."""
    from tools.migrate_lineage_flat_to_run_scoped import plan_moves

    active = tmp_path / "docs" / "lineage" / "active" / "9-lld"
    active.mkdir(parents=True)
    (active / "001-draft.md").write_text("a")
    done = tmp_path / "docs" / "lineage" / "done" / "10-lld"
    done.mkdir(parents=True)
    (done / "001-issue.md").write_text("b")

    moves = plan_moves(tmp_path)
    assert len(moves) == 2
    state_dirs = {m[0].parent.parent.name for m in moves}
    assert state_dirs == {"active", "done"}


def test_nonexistent_repo_returns_nonzero(tmp_path, capsys):
    from tools.migrate_lineage_flat_to_run_scoped import main

    rc = main(["--repo", str(tmp_path / "nope")])
    assert rc != 0
    assert "ERROR" in capsys.readouterr().out


def test_empty_repo_prints_no_migration_needed(tmp_path, capsys):
    from tools.migrate_lineage_flat_to_run_scoped import main

    (tmp_path / "README.md").write_text("noise")  # not a lineage repo
    rc = main(["--repo", str(tmp_path)])
    assert rc == 0
    assert "no migration needed" in capsys.readouterr().out
