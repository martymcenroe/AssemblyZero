"""The drive-root placeholder guard sees what a test leaves there (#4705).

On Windows a placeholder such as ``/fake/projects/Chiron`` resolves to
``C:\\fake\\projects\\Chiron`` and a write lands there; on Linux the root
refuses it. The guard is the suite's check on that: these tests point it at
roots under ``tmp_path`` and show it reports each kind of change, and that the
session fails with the path named when one appears.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import drive_root_guard as guard


def test_the_guarded_roots_are_the_four_placeholder_folders():
    assert [root.as_posix() for root in guard.GUARDED_ROOTS] == [
        "/nonexistent",
        "/fake",
        "/path",
        "/c",
    ]


def test_a_missing_root_contributes_nothing(tmp_path):
    assert guard.snapshot((tmp_path / "nonexistent",)) == {}


def test_an_unchanged_tree_reports_nothing(tmp_path):
    root = tmp_path / "fake"
    (root / "repo" / "data").mkdir(parents=True)
    (root / "repo" / "data" / "a.jsonl").write_text("{}\n", encoding="utf-8")

    assert guard.changes(guard.snapshot((root,)), guard.snapshot((root,))) == []


def test_a_root_that_appears_is_reported_with_what_is_under_it(tmp_path):
    """The inventory writer (#4703): the whole tree is built in one run."""
    root = tmp_path / "path"
    before = guard.snapshot((root,))

    inventory = root / "that" / "docs" / "0003-file-inventory.md"
    inventory.parent.mkdir(parents=True)
    inventory.write_text("# Documentation Inventory\n", encoding="utf-8")

    lines = guard.changes(before, guard.snapshot((root,)))

    assert f"added:   {root} (dir)" in lines
    assert f"added:   {inventory} (file)" in lines


def test_an_empty_folder_added_under_an_existing_root_is_reported(tmp_path):
    """The spec-stage writer (#4704) left only empty folders."""
    lineage = tmp_path / "fake" / "projects" / "Chiron" / "docs" / "lineage"
    lineage.mkdir(parents=True)
    before = guard.snapshot((tmp_path / "fake",))

    stamp = lineage / "active" / "5-implspec" / "2026-11-11T11-22-33Z"
    stamp.mkdir(parents=True)

    lines = guard.changes(before, guard.snapshot((tmp_path / "fake",)))

    assert f"added:   {stamp} (dir)" in lines


def test_a_removed_file_and_an_appended_file_are_reported(tmp_path):
    root = tmp_path / "nonexistent"
    buffer = root / "path" / "buffer"
    buffer.mkdir(parents=True)
    kept = buffer / "2026-10-25.jsonl"
    kept.write_text('{"event_type": "test"}\n', encoding="utf-8")
    gone = root / "001-draft.md"
    gone.write_text("# New Draft\n\nNew content", encoding="utf-8")
    before = guard.snapshot((root,))

    gone.unlink()
    with kept.open("a", encoding="utf-8") as handle:
        handle.write('{"event_type": "test"}\n')

    lines = guard.changes(before, guard.snapshot((root,)))

    assert f"removed: {gone} (file)" in lines
    assert any(line.startswith(f"changed: {kept} (file, size ") for line in lines), lines


def test_a_rewrite_of_the_same_length_is_reported(tmp_path):
    root = tmp_path / "c"
    root.mkdir()
    target = root / "status.json"
    target.write_text("{}", encoding="utf-8")
    before = guard.snapshot((root,))

    target.write_text("[]", encoding="utf-8")
    stat = target.stat()
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    lines = guard.changes(before, guard.snapshot((root,)))

    assert lines == [f"changed: {target} (file, size 2 -> 2)"]


def test_a_session_that_writes_into_a_placeholder_fails_with_the_path_named(
    tmp_path, monkeypatch
):
    """The conftest hooks, driven directly: a folder made between session
    start and finish fails the session, and the report names it."""
    from tests import conftest

    root = tmp_path / "fake"
    monkeypatch.setattr(guard, "GUARDED_ROOTS", (root,))
    written: list[str] = []
    reporter = SimpleNamespace(write_line=written.append)
    session = SimpleNamespace(
        config=SimpleNamespace(
            pluginmanager=SimpleNamespace(get_plugin=lambda name: reporter)
        ),
        exitstatus=0,
    )

    conftest.pytest_sessionstart(session)
    made = root / "projects" / "Chiron"
    made.mkdir(parents=True)
    conftest.pytest_sessionfinish(session, 0)

    assert session.exitstatus == 1
    assert any("placeholder folder off the drive root" in line for line in written), written
    assert any(str(made) in line for line in written), written


def test_a_session_that_writes_nothing_there_passes(tmp_path, monkeypatch):
    from tests import conftest

    root = tmp_path / "fake"
    (root / "repo").mkdir(parents=True)
    monkeypatch.setattr(guard, "GUARDED_ROOTS", (root,))
    written: list[str] = []
    session = SimpleNamespace(
        config=SimpleNamespace(
            pluginmanager=SimpleNamespace(
                get_plugin=lambda name: SimpleNamespace(write_line=written.append)
            )
        ),
        exitstatus=0,
    )

    conftest.pytest_sessionstart(session)
    conftest.pytest_sessionfinish(session, 0)

    assert not any("placeholder folder off the drive root" in line for line in written), written


def test_a_root_that_is_a_link_is_recorded_and_never_walked(tmp_path):
    """On the operator's Ubuntu ``/c`` links to ``/mnt/c``, the whole Windows
    drive. The guard must not walk it."""
    target = tmp_path / "drive"
    (target / "Users").mkdir(parents=True)
    (target / "Users" / "a.txt").write_text("x", encoding="utf-8")
    link = tmp_path / "c"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"cannot make a symlink here: {exc}")

    seen = guard.snapshot((link,))

    assert list(seen) == [str(link)]
    assert seen[str(link)][0] == "link"


def test_the_roots_sit_at_the_drive_root():
    """On Windows ``/fake`` is drive-relative and lands at the root of the
    current drive, which is where the writes went; on Linux it is the
    filesystem root."""
    for root in guard.GUARDED_ROOTS:
        absolute = Path(os.path.abspath(root))
        assert absolute.parent == Path(absolute.anchor), absolute
