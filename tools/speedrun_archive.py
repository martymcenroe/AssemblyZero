#!/usr/bin/env python3
"""Archive a completed speedrun into one restorable record (#2076).

An arc is deliberately never merged to main, so a run's product lives only on
integration and `graveyard/*` branches, in the log triplets, and in lineage and
reset artifacts. This captures all of it under
`<repo>/data/speedrun/archives/<run>/` -- already gitignored, per-repo, and it
adds nothing to `~/Projects` (see #2077).

    # archive a run
    poetry run python tools/speedrun_archive.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge --run hardening-run-15

    # what would be captured, without writing
    poetry run python tools/speedrun_archive.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge --run hardening-run-15 --dry-run

    # restore
    poetry run python tools/speedrun_archive.py \\
        --restore /c/.../archives/hardening-run-15 /c/.../restored

Exit codes: 0 complete archive; 1 archive written but incomplete (a named
component could not be read); 2 usage or restore error.

This tool only ever writes. It deletes nothing, on any path -- deletion is
gated on a verified restore and belongs to #2077 and later work.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assemblyzero.speedrun.archive import (  # noqa: E402
    RestoreRefused,
    archive_run,
    discover_rolls,
    find_orphan_worktrees,
    graveyard_branches_for,
    restore_archive,
    verify_manifest,
)


def _log(msg: str) -> None:
    """Print and flush -- a zero-byte log makes a slow run look like a dead one."""
    print(msg, flush=True)


def cmd_archive(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    log_dir = Path(args.log_dir) if args.log_dir else None

    if args.dry_run:
        rolls, problems = discover_rolls(
            log_dir or repo / "data/speedrun/runs", args.run
        )
        _log(f"run           {args.run}")
        _log(f"repo          {repo}")
        _log(f"rolls         {len(rolls)}")
        for roll in rolls:
            _log(f"  {roll.tag}  issue #{roll.issue}  {roll.outcome}")
        graves = graveyard_branches_for(repo, args.run)
        _log(f"graveyard     {len(graves)}")
        for branch in graves:
            _log(f"  {branch}")
        orphans = find_orphan_worktrees(repo)
        _log(f"orphans       {len(orphans)}")
        for orphan in orphans:
            _log(f"  {orphan}")
        for problem in problems:
            _log(f"  PROBLEM {problem.name}: {problem.detail}")
        _log("\nDry run. Nothing written.")
        return 0

    result = archive_run(
        repo,
        args.run,
        out_dir=Path(args.out) if args.out else None,
        log_dir=log_dir,
        extra_branches=args.branch,
    )

    _log(f"archived  {result.path}")
    _log(f"rolls     {len(result.index['rolls'])}")
    _log(f"branches  {1 if result.index['branches']['integration']['sha'] else 0}"
         f" integration + {len(result.index['branches']['graveyard'])} graveyard")
    _log(f"orphans   {len(result.index['orphans'])}")
    _log(f"files     {len(result.index['manifest'])}")

    if result.complete:
        _log("complete  yes")
        return 0

    _log("complete  NO -- this archive does not authorize deleting anything")
    for name in result.missing:
        detail = next(
            (c.detail for c in result.components if c.name == name and not c.ok), ""
        )
        _log(f"  missing: {name} -- {detail}")
    return 1


def cmd_restore(args: argparse.Namespace) -> int:
    archive_dir, dest = Path(args.restore[0]), Path(args.restore[1])
    try:
        index = restore_archive(archive_dir, dest, force=args.force)
    except RestoreRefused as exc:
        _log(f"REFUSED: {exc}")
        return 2
    except (OSError, RuntimeError) as exc:
        _log(f"ERROR: {exc}")
        return 2

    _log(f"restored  {dest}")
    _log(f"run       {index['run']}")
    if not index.get("complete", False):
        _log("WARNING: restored from an archive marked incomplete")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    mismatched = verify_manifest(Path(args.verify))
    if not mismatched:
        _log("manifest OK -- every recorded file matches its sha256")
        return 0
    _log(f"MANIFEST MISMATCH on {len(mismatched)} file(s):")
    for rel in mismatched:
        _log(f"  {rel}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Archive a completed speedrun into one restorable record."
    )
    parser.add_argument("--repo", help="target repository root")
    parser.add_argument("--run", help="run name, i.e. its integration branch")
    parser.add_argument("--out", help="archive destination (default: <repo>/data/speedrun/archives/<run>)")
    parser.add_argument("--log-dir", help="where the events/heartbeat/stdout triplets live")
    parser.add_argument(
        "--branch",
        action="append",
        help="extra branch to bundle, repeatable; for attempts outside the graveyard/<run>* rule",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would be captured")
    parser.add_argument("--restore", nargs=2, metavar=("ARCHIVE", "DEST"))
    parser.add_argument("--force", action="store_true", help="restore an incomplete archive anyway")
    parser.add_argument("--verify", metavar="ARCHIVE", help="re-hash an archive against its manifest")
    args = parser.parse_args(argv)

    if args.restore:
        return cmd_restore(args)
    if args.verify:
        return cmd_verify(args)
    if not args.repo or not args.run:
        parser.error("--repo and --run are required unless --restore or --verify is used")
    return cmd_archive(args)


if __name__ == "__main__":
    raise SystemExit(main())
