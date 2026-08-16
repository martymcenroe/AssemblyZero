"""The archiver tolerates ReadOnly-attributed paths (#2404).

A successful roll's auto-archive died with `[WinError 5] Access is denied` on
an EMPTY directory under `data/speedrun/archives/` carrying the Windows
ReadOnly attribute -- the signature #2277 forensically attributed to Google
Drive for Desktop's attribute-setting. A sweep found 62 such directories.

The roll's verdict was unaffected, as designed. But the archive step is the
instrument the roll is READ with, and it failed on an environmental condition
the fleet has already named and cannot remove: the setter has a standing
presence, so a one-time `attrib -r` sweep is not a durable repair. The tool has
to tolerate the attribute rather than assume its absence.

`os.chmod(path, stat.S_IWRITE)` clears FILE_ATTRIBUTE_READONLY on Windows and
is a no-op-ish permission change elsewhere, so these fixtures run on both --
which matters, since the defect only manifests on the platform CI does not run
(#2431).
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from assemblyzero.speedrun.archive import (
    _clear_readonly,
    _copy_tree,
    _reset_readonly_clearings,
    _rmtree,
    readonly_clearings,
)


@pytest.fixture(autouse=True)
def _clean_ledger():
    _reset_readonly_clearings()
    yield
    _reset_readonly_clearings()


def _make_readonly(path: Path) -> None:
    os.chmod(path, stat.S_IREAD)


def _is_readonly(path: Path) -> bool:
    return not os.access(path, os.W_OK)


class TestCopyingOverAReadOnlyDestination:
    """The measured failure: a re-archive over an existing ReadOnly tree."""

    def test_it_copies_without_operator_intervention(self, tmp_path):
        src = tmp_path / "src"
        (src / "inner").mkdir(parents=True)
        (src / "inner" / "a.txt").write_text("payload", encoding="utf-8")

        dest = tmp_path / "dest"
        (dest / "inner").mkdir(parents=True)
        stale = dest / "inner" / "a.txt"
        stale.write_text("stale", encoding="utf-8")
        _make_readonly(stale)

        _copy_tree(src, dest)

        assert (dest / "inner" / "a.txt").read_text(encoding="utf-8") == "payload"

    def test_an_empty_readonly_directory_does_not_stop_it(self, tmp_path):
        """The exact shape on disk: the directory that killed the archive was
        EMPTY and carried the attribute."""
        src = tmp_path / "src"
        (src / "lineage" / "1-lld" / "2026-07-29T17-53-39Z").mkdir(parents=True)
        (src / "keep.txt").write_text("x", encoding="utf-8")

        dest = tmp_path / "dest"
        empty = dest / "lineage" / "1-lld" / "2026-07-29T17-53-39Z"
        empty.mkdir(parents=True)
        _make_readonly(empty)

        _copy_tree(src, dest)
        assert (dest / "keep.txt").is_file()

    def test_an_ordinary_copy_is_unchanged(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("payload", encoding="utf-8")
        dest = tmp_path / "dest"

        _copy_tree(src, dest)

        assert (dest / "a.txt").read_text(encoding="utf-8") == "payload"
        assert readonly_clearings() == [], (
            "a clean copy must not report clearings it did not make"
        )


class TestTheArchiveItselfStaysWritable:
    """A ReadOnly SOURCE produces a ReadOnly archive under `copy2`, which
    makes the NEXT re-archive fail in exactly the way this repair prevents."""

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="POSIX copy2 does not reproduce the read-only-copy trap the "
               "same way; the Windows attribute is what this guards",
    )
    def test_a_readonly_source_yields_a_writable_copy(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        locked = src / "locked.txt"
        locked.write_text("payload", encoding="utf-8")
        _make_readonly(locked)

        dest = tmp_path / "dest"
        (dest).mkdir()
        (dest / "locked.txt").write_text("stale", encoding="utf-8")
        _make_readonly(dest / "locked.txt")

        _copy_tree(src, dest)
        assert not _is_readonly(dest / "locked.txt")


class TestRemovingAReadOnlyTree:
    def test_rmtree_clears_and_removes(self, tmp_path):
        target = tmp_path / "archive"
        (target / "inner").mkdir(parents=True)
        locked = target / "inner" / "a.txt"
        locked.write_text("x", encoding="utf-8")
        _make_readonly(locked)

        _rmtree(target)
        assert not target.exists()

    def test_an_ordinary_tree_still_removes(self, tmp_path):
        target = tmp_path / "archive"
        target.mkdir()
        (target / "a.txt").write_text("x", encoding="utf-8")
        _rmtree(target)
        assert not target.exists()


class TestTheClearingIsReported:
    """'the attribute-clearing path is logged so recurrence stays visible
    rather than silent' -- the issue's acceptance. The #2277 setter has a
    standing presence, so silence would turn a durable environmental condition
    into folklore."""

    def test_a_cleared_path_is_recorded(self, tmp_path):
        locked = tmp_path / "a.txt"
        locked.write_text("x", encoding="utf-8")
        _make_readonly(locked)

        assert _clear_readonly(locked) is True
        assert str(locked) in readonly_clearings()

    def test_an_unclearable_path_is_not_recorded(self, tmp_path):
        assert _clear_readonly(tmp_path / "does-not-exist") is False
        assert readonly_clearings() == []

    def test_the_ledger_resets_between_archives(self, tmp_path):
        locked = tmp_path / "a.txt"
        locked.write_text("x", encoding="utf-8")
        _make_readonly(locked)
        _clear_readonly(locked)
        assert readonly_clearings()

        _reset_readonly_clearings()
        assert readonly_clearings() == []

    def test_the_roll_prints_it(self):
        """The report must reach the verdict the operator reads, not merely
        exist on a module."""
        import sys as _sys

        tools = Path(__file__).resolve().parents[2] / "tools"
        if str(tools) not in _sys.path:
            _sys.path.insert(0, str(tools))
        import inspect

        import speedrun_roll

        source = inspect.getsource(speedrun_roll._archive_successful_run)
        assert "readonly_clearings()" in source
        assert "#2404" in source
