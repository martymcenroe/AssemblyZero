"""No test writes into a placeholder folder off the drive root (#4705).

A test that hands ``/nonexistent`` or ``/fake/repo`` to code that writes gets
a refusal on Linux, where the filesystem root is not writable. On Windows the
same path resolves against the current drive, to ``C:\\nonexistent`` or
``C:\\fake\\repo``, and the write lands. Once the folder exists, every later
run writes into it again. Through 2026 this suite left 785 drafts and 98
telemetry buffers in ``C:\\nonexistent``, 386 empty lineage folders under
``C:\\fake`` and an inventory under ``C:\\path`` (#4703, #4704), each found
months later by someone opening C:.

``conftest.py`` snapshots these folders at session start and compares at
session end, as it does for the home state (#3531), and a difference fails the
session with the paths named. Unlike that guard, folders count as well as
files: the spec-stage writer (#4704) added only empty folders.

The list is closed: the four placeholder folders found on the operator's
machine. ``/c`` is where a Git Bash path such as ``/c/Users/...`` lands when
native Windows Python opens it. A folder that does not exist contributes
nothing, so on Linux the guard costs four ``stat`` calls.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The drive-root placeholder folders no test may write into.
GUARDED_ROOTS: tuple[Path, ...] = (
    Path("/nonexistent"),
    Path("/fake"),
    Path("/path"),
    Path("/c"),
)

Entry = tuple[str, int, int]


def _entry(path: str) -> Entry:
    """``(kind, size, mtime_ns)`` for one path, without following a link.

    An entry that cannot be read is recorded as such rather than skipped, so
    it still counts when it appears, disappears or becomes readable.
    """
    try:
        stat = os.stat(path, follow_symlinks=False)
    except OSError:
        return ("unreadable", -1, -1)
    if os.path.islink(path):
        return ("link", 0, stat.st_mtime_ns)
    if os.path.isdir(path):
        return ("dir", 0, stat.st_mtime_ns)
    return ("file", stat.st_size, stat.st_mtime_ns)


def snapshot(roots: tuple[Path, ...] | None = None) -> dict[str, Entry]:
    """``{path: (kind, size, mtime_ns)}`` for each root and everything under it.

    ``roots`` defaults to ``GUARDED_ROOTS``, read when called, so a test can
    point the guard at a directory of its own. A root that does not exist
    contributes nothing, and its later appearance is a change like any other.
    A folder's mtime moves when an entry is added to or removed from it, and
    every folder is listed, so an empty folder a test made is seen.

    A root that is a link is recorded and never walked. On the operator's
    Ubuntu, ``/c`` is a link to ``/mnt/c``, the whole Windows drive.
    """
    seen: dict[str, Entry] = {}
    for root in GUARDED_ROOTS if roots is None else roots:
        top = str(root)
        if not os.path.lexists(top):
            continue
        seen[top] = _entry(top)
        if seen[top][0] != "dir":
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            for name in dirnames + filenames:
                path = os.path.join(dirpath, name)
                seen[path] = _entry(path)
    return seen


def changes(before: dict[str, Entry], after: dict[str, Entry]) -> list[str]:
    """One line per path whose presence, kind, size or mtime differs."""
    lines: list[str] = []
    for path in sorted(set(before) | set(after)):
        old, new = before.get(path), after.get(path)
        if old == new:
            continue
        if old is None:
            lines.append(f"added:   {path} ({new[0]})")
        elif new is None:
            lines.append(f"removed: {path} ({old[0]})")
        else:
            lines.append(
                f"changed: {path} ({old[0]}, size {old[1]} -> {new[1]})"
            )
    return lines
