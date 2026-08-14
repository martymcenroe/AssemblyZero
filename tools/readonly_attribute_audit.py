#!/usr/bin/env python3
"""Who marked the Projects tree ReadOnly, and when did they stop (#2277).

#2136 asked what in the pipeline sets the Windows ReadOnly attribute on
worktrees and answered: nothing does. #2277 asked what does. This is the
program that answers it, and re-answers it if the condition returns -- a
finding written down once is a claim about one afternoon.

Four measurements, in the order that narrows fastest:

1. **Is it Projects-specific?** If directories everywhere carry the attribute
   then nothing is walking Projects and there is no mystery. Sampling local,
   non-cloud roots settles that in a second.
2. **Directories or files?** A backup or antivirus product rewriting
   attributes generally touches both. Directories alone is a much narrower
   signature.
3. **When did the setter last run?** Sort by creation time and find the
   boundary between marked and unmarked. Everything created before the last
   pass is marked; everything after is not. The boundary is a timestamp, which
   is worth more than a guess at a culprit.
4. **Is a sync client staging in the tree?** Google Drive for Desktop leaves
   `.tmp.driveupload` / `.tmp.drivedownload` in any folder it backs up, and
   their mtimes date its last activity.

Read-only. It changes no attribute and deletes nothing: on this machine the
attribute costs nothing (a "ReadOnly" directory accepts writes -- on Windows the
flag on a *directory* is a shell hint, not a permission), so there is nothing
here worth a destructive fix.

    poetry run python tools/readonly_attribute_audit.py
    poetry run python tools/readonly_attribute_audit.py --root /c/Users/mcwiz/Projects

Exit codes:
    0  the tree looks the way #2277 recorded it, or is clean
    1  the marking is spreading again -- something is walking the tree now
    2  the audit could not run, so nothing was verified
"""
from __future__ import annotations

import argparse
import os
import stat as stat_mod
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# #2367: before anything prints. Repo and directory names are arbitrary text.
from assemblyzero.core.utf8_console import install as _install_utf8_console  # noqa: E402

_install_utf8_console()

EXIT_OK = 0
EXIT_SPREADING = 1
EXIT_ERROR = 2

READONLY = stat_mod.FILE_ATTRIBUTE_READONLY

#: Local, non-cloud roots. Never a mapped drive, a OneDrive path or a Drive
#: mount -- a stat there hydrates the file (root CLAUDE.md, earned 2026-07-24).
BASELINE_ROOTS = (
    Path(r"C:\Windows"),
    Path(r"C:\Program Files"),
    Path(r"C:\Program Files (x86)"),
)

#: Left behind in any folder Google Drive for Desktop backs up.
DRIVE_STAGING = (".tmp.driveupload", ".tmp.drivedownload")

#: The last pass recorded by #2277, from the boundary in AssemblyZero/data:
#: last marked 2026-07-31 08:23, first unmarked 2026-08-02 01:43, and the Drive
#: staging directories fell idle at 2026-08-01 16:15 between the two.
KNOWN_LAST_PASS = datetime(2026, 8, 2)


def is_readonly(path: Path) -> bool | None:
    try:
        return bool(os.stat(path).st_file_attributes & READONLY)
    except OSError:
        return None
    except AttributeError:  # not Windows
        return None


def child_dirs(root: Path, limit: int | None = None) -> list[Path]:
    try:
        found = [p for p in sorted(root.iterdir()) if p.is_dir()]
    except OSError:
        return []
    return found[:limit] if limit else found


def ratio(paths: list[Path]) -> tuple[int, int]:
    return sum(1 for p in paths if is_readonly(p)), len(paths)


def newest_marked_and_oldest_unmarked(
    paths: list[Path],
) -> tuple[tuple[Path, datetime] | None, tuple[Path, datetime] | None]:
    marked, unmarked = [], []
    for p in paths:
        try:
            created = datetime.fromtimestamp(os.stat(p).st_ctime)
        except OSError:
            continue
        (marked if is_readonly(p) else unmarked).append((p, created))
    return (
        max(marked, key=lambda r: r[1]) if marked else None,
        min(unmarked, key=lambda r: r[1]) if unmarked else None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure the ambient Windows ReadOnly attribute across the "
            "Projects tree, and date the last pass that applied it. Read-only."
        )
    )
    parser.add_argument(
        "--root",
        default=r"C:\Users\mcwiz\Projects",
        help="tree to audit (default: the Projects root)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"ERROR -- not a directory: {root}", file=sys.stderr)
        print("Nothing has been verified.", file=sys.stderr)
        return EXIT_ERROR
    if not hasattr(os.stat(root), "st_file_attributes"):
        print("ERROR -- no Windows file attributes here; this audit is Windows-only.",
              file=sys.stderr)
        return EXIT_ERROR

    rule = "=" * 70
    print(rule)
    print(f"ReadOnly attribute audit -- {root}")
    print(rule)
    print()

    tree_dirs = child_dirs(root)
    marked, total = ratio(tree_dirs)
    share = (marked / total * 100) if total else 0.0
    print(f"Inside the tree:  {marked}/{total} directories marked ({share:.0f}%)")

    print()
    print("Baseline, local roots outside the tree:")
    baseline_marked = baseline_total = 0
    for base in BASELINE_ROOTS:
        m, t = ratio(child_dirs(base, limit=25))
        baseline_marked += m
        baseline_total += t
        if t:
            print(f"  {str(base):<26} {m}/{t}")
    baseline_share = (
        (baseline_marked / baseline_total * 100) if baseline_total else 0.0
    )
    print(f"  {'combined':<26} {baseline_marked}/{baseline_total} ({baseline_share:.0f}%)")

    print()
    if share > baseline_share + 25:
        print("VERDICT: specific to this tree, not a machine-wide property.")
    else:
        print("VERDICT: no excess over baseline -- nothing is singling this tree out.")

    files = []
    try:
        files = [p for p in root.iterdir() if p.is_file()]
    except OSError:
        pass
    if files:
        fm, ft = ratio(files)
        print()
        print(f"Files at this level: {fm}/{ft} marked")
        if fm == 0 and marked:
            print("  Directories only. A backup or AV product rewriting attributes")
            print("  would generally touch files too; a sync client marking the")
            print("  folders it manages would not.")

    print()
    print("Google Drive for Desktop staging directories:")
    drive_seen = False
    for name in DRIVE_STAGING:
        staging = root / name
        if not staging.exists():
            print(f"  {name:<22} absent")
            continue
        drive_seen = True
        try:
            idle_since = datetime.fromtimestamp(os.stat(staging).st_mtime)
            print(f"  {name:<22} present, last active {idle_since:%Y-%m-%d %H:%M:%S}")
        except OSError:
            print(f"  {name:<22} present, mtime unreadable")
    if drive_seen:
        print("  Drive backs up this folder. It is the setter #2277 identified.")

    print()
    print("Last pass, from the marked/unmarked boundary:")
    newest_marked, oldest_unmarked = newest_marked_and_oldest_unmarked(tree_dirs)
    if newest_marked:
        print(f"  newest MARKED    {newest_marked[1]:%Y-%m-%d %H:%M:%S}  {newest_marked[0].name}")
    if oldest_unmarked:
        print(f"  oldest UNMARKED  {oldest_unmarked[1]:%Y-%m-%d %H:%M:%S}  {oldest_unmarked[0].name}")

    spreading = bool(newest_marked and newest_marked[1] > KNOWN_LAST_PASS)
    print()
    if spreading:
        print(rule)
        print("SPREADING: a directory created after the recorded last pass is")
        print(f"marked. Something walked this tree after {KNOWN_LAST_PASS:%Y-%m-%d}.")
        print("Check whether Drive backup was re-enabled for this folder.")
        print(rule)
    else:
        print("Stable: nothing created since the recorded last pass is marked.")

    print()
    print("Not verified: whether the attribute costs anything. It does not --")
    print("on Windows the ReadOnly flag on a DIRECTORY is a shell hint, not a")
    print("permission, and writes into a marked directory succeed. #2135 already")
    print("clears it where a worktree removal trips over it.")
    print()
    return EXIT_SPREADING if spreading else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
