"""The ReadOnly audit measures rather than asserts (#2277).

The finding it encodes -- that Google Drive for Desktop marked the Projects
tree and stopped on 2026-08-01 -- is only worth writing down if something
re-checks it. These tests build real directories and set the real Windows
attribute, because the whole subject is a filesystem attribute and a mocked
`os.stat` would let every claim here pass without being true.
"""
from __future__ import annotations

import os
import stat as stat_mod
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import readonly_attribute_audit as audit  # noqa: E402

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows file attributes only exist on Windows"
)


def mark_readonly(path: Path) -> None:
    os.chmod(path, stat_mod.S_IREAD)


def clear_readonly(path: Path) -> None:
    os.chmod(path, stat_mod.S_IWRITE)


@windows_only
class TestItReadsTheRealAttribute:
    def test_a_plain_directory_is_unmarked(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert audit.is_readonly(plain) is False

    def test_a_marked_directory_is_detected(self, tmp_path):
        marked = tmp_path / "marked"
        marked.mkdir()
        mark_readonly(marked)
        try:
            assert audit.is_readonly(marked) is True
        finally:
            clear_readonly(marked)

    def test_clearing_it_is_detected_too(self, tmp_path):
        """The falsifier. Without this, `is_readonly` returning True always
        would pass the test above."""
        d = tmp_path / "toggled"
        d.mkdir()
        mark_readonly(d)
        clear_readonly(d)
        assert audit.is_readonly(d) is False

    def test_a_missing_path_is_none_not_false(self, tmp_path):
        """None means unknown. Reporting a path that does not exist as
        'unmarked' would quietly deflate the ratio."""
        assert audit.is_readonly(tmp_path / "nope") is None


@windows_only
class TestTheMarkedDirectoryIsStillWritable:
    """The finding that makes this whole issue low priority: on Windows the
    ReadOnly flag on a DIRECTORY is a shell hint, not a permission. If this
    ever fails, #2277 stops being a curiosity and becomes an outage."""

    def test_a_file_can_be_created_inside_a_marked_directory(self, tmp_path):
        d = tmp_path / "marked"
        d.mkdir()
        mark_readonly(d)
        try:
            probe = d / "probe.txt"
            probe.write_text("x", encoding="utf-8")
            assert probe.read_text(encoding="utf-8") == "x"
            probe.unlink()
        finally:
            clear_readonly(d)


class TestTheRatio:
    def test_an_empty_set_does_not_divide_by_zero(self):
        assert audit.ratio([]) == (0, 0)

    @windows_only
    def test_it_counts_only_the_marked(self, tmp_path):
        dirs = []
        for i in range(4):
            d = tmp_path / f"d{i}"
            d.mkdir()
            dirs.append(d)
        mark_readonly(dirs[0])
        mark_readonly(dirs[2])
        try:
            assert audit.ratio(dirs) == (2, 4)
        finally:
            for d in dirs[::2]:
                clear_readonly(d)


@windows_only
class TestTheBoundaryDatesTheLastPass:
    """A timestamp is worth more than a guess at a culprit: everything created
    before the setter's last pass is marked, everything after is not."""

    def test_it_finds_the_newest_marked_and_oldest_unmarked(self, tmp_path):
        old = tmp_path / "old_marked"
        new = tmp_path / "new_unmarked"
        old.mkdir()
        new.mkdir()
        mark_readonly(old)
        try:
            newest_marked, oldest_unmarked = audit.newest_marked_and_oldest_unmarked(
                [old, new]
            )
            assert newest_marked is not None and newest_marked[0] == old
            assert oldest_unmarked is not None and oldest_unmarked[0] == new
        finally:
            clear_readonly(old)

    def test_an_all_marked_tree_reports_no_unmarked_side(self, tmp_path):
        d = tmp_path / "only"
        d.mkdir()
        mark_readonly(d)
        try:
            newest_marked, oldest_unmarked = audit.newest_marked_and_oldest_unmarked([d])
            assert newest_marked is not None
            assert oldest_unmarked is None
        finally:
            clear_readonly(d)

    def test_an_all_unmarked_tree_reports_no_marked_side(self, tmp_path):
        d = tmp_path / "only"
        d.mkdir()
        newest_marked, oldest_unmarked = audit.newest_marked_and_oldest_unmarked([d])
        assert newest_marked is None
        assert oldest_unmarked is not None


class TestTheRecordedFinding:
    def test_the_last_pass_is_the_measured_boundary(self):
        """#2277 measured: last marked 2026-07-31 08:23, first unmarked
        2026-08-02 01:43, Drive staging idle from 2026-08-01 16:15 between the
        two. The constant must sit inside that window, not near it."""
        assert datetime(2026, 8, 1) <= audit.KNOWN_LAST_PASS <= datetime(2026, 8, 3)

    def test_drive_staging_names_are_the_ones_drive_actually_uses(self):
        assert set(audit.DRIVE_STAGING) == {".tmp.driveupload", ".tmp.drivedownload"}

    def test_the_baseline_roots_are_local_only(self):
        """A cloud or mapped root would hydrate on stat -- the 70 GB incident in
        the root CLAUDE.md, earned 2026-07-24."""
        for base in audit.BASELINE_ROOTS:
            text = str(base).lower()
            assert text.startswith("c:\\")
            for forbidden in ("onedrive", "google", "drive file stream", "\\\\"):
                assert forbidden not in text

    def test_a_directory_created_after_the_last_pass_would_read_as_spreading(self):
        """The condition the audit exits 1 on, checked as arithmetic rather
        than by waiting for it to happen."""
        after = audit.KNOWN_LAST_PASS + timedelta(days=1)
        assert after > audit.KNOWN_LAST_PASS


class TestItRefusesRatherThanGuessing:
    def test_a_missing_root_is_an_error_not_an_empty_pass(self, tmp_path, capsys):
        code = audit.main(["--root", str(tmp_path / "absent")])
        assert code == audit.EXIT_ERROR
        assert "Nothing has been verified" in capsys.readouterr().err
