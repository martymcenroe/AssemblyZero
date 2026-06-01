"""Migrate legacy flat-layout lineage files into per-run subdirectories.

Closes #1480.

PR #1468 introduced per-run subdirectories for new lineage writes:
    docs/lineage/{active,done}/{N}-{type}/{run_id}/NNN-*.md

Lineage that landed before that PR is flat:
    docs/lineage/{active,done}/{N}-{type}/NNN-*.md

This tool walks both `active/` and `done/`, finds each `{N}-{type}/` issue
directory, detects any flat NNN-*.md files at its top level, and moves them
into a synthetic `legacy/` run-id subdirectory:
    docs/lineage/{active,done}/{N}-{type}/legacy/NNN-*.md

The `legacy` run-id is filesystem-safe and visually distinct from real
timestamp run-ids (which contain `T` and end in `Z`), so a reader can tell
at a glance which files predate PR #1468.

The tool defaults to dry-run (preview). Pass `--apply` to actually move.
Idempotent: a second `--apply` invocation finds no flat files and exits
without changes.

This tool does NOT commit the moves. Run it, review `git status`, then
commit or revert.

Usage:
    poetry run python tools/migrate_lineage_flat_to_run_scoped.py --repo <path>
    poetry run python tools/migrate_lineage_flat_to_run_scoped.py --repo <path> --apply
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

LEGACY_RUN_ID = "legacy"
NNN_PREFIX = re.compile(r"^\d{3}-")


def find_flat_files(issue_dir: Path) -> list[Path]:
    """Return NNN-*.md files at the top level of an issue directory.

    Files inside any subdirectory (whether `legacy/` or a real run-id like
    `2026-05-31T17-27-26Z/`) are excluded — those are already run-scoped.
    """
    if not issue_dir.is_dir():
        return []
    flat: list[Path] = []
    for child in issue_dir.iterdir():
        if child.is_file() and NNN_PREFIX.match(child.name):
            flat.append(child)
    return sorted(flat)


def plan_moves(repo_root: Path) -> list[tuple[Path, Path]]:
    """Walk active/ and done/ to compute all (src, dst) move pairs.

    Returns an empty list if no migration is needed. Skips repos that don't
    have a `docs/lineage/` directory at all.
    """
    lineage_root = repo_root / "docs" / "lineage"
    if not lineage_root.is_dir():
        return []
    moves: list[tuple[Path, Path]] = []
    for state_dir_name in ("active", "done"):
        state_dir = lineage_root / state_dir_name
        if not state_dir.is_dir():
            continue
        for issue_dir in sorted(state_dir.iterdir()):
            if not issue_dir.is_dir():
                continue
            for src in find_flat_files(issue_dir):
                dst = issue_dir / LEGACY_RUN_ID / src.name
                moves.append((src, dst))
    return moves


def apply_moves(moves: list[tuple[Path, Path]]) -> None:
    """Execute each (src, dst) move via shutil.move, creating parent dirs."""
    for src, dst in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate legacy flat-layout docs/lineage/ files into per-run "
            "subdirectories under a synthetic 'legacy/' run-id. Closes #1480."
        ),
    )
    parser.add_argument(
        "--repo",
        required=True,
        type=Path,
        help="Path to the target repository (containing docs/lineage/).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Actually move files. Without --apply, runs in dry-run mode "
            "and prints the planned moves without touching the filesystem."
        ),
    )
    args = parser.parse_args(argv)

    repo_root = args.repo.resolve()
    if not repo_root.is_dir():
        print(f"[ERROR] repo path does not exist or is not a directory: {repo_root}")
        return 2

    moves = plan_moves(repo_root)
    if not moves:
        print(f"[OK] no migration needed for {repo_root}")
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] {len(moves)} flat lineage file(s) to migrate under {repo_root}")
    for src, dst in moves:
        rel_src = src.relative_to(repo_root)
        rel_dst = dst.relative_to(repo_root)
        print(f"    {rel_src}  ->  {rel_dst}")

    if args.apply:
        apply_moves(moves)
        print(f"[OK] {len(moves)} file(s) moved. Review `git status` and commit.")
    else:
        print("[DRY-RUN] pass --apply to actually move the files above.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
