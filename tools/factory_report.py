#!/usr/bin/env python3
"""Roll up every factory store into one counted picture (#2575).

The factory records everything and aggregates nothing: prompt-failure
telemetry (#2074), the healing ledger (#2164), the preservation record
(#2355), run logs, and since 2026-08-28 the halt evidence bundles (#2574).
Each judgment call of the 2026-08-27 campaign was decided by whichever kill
happened most recently, while the counts to decide them properly already
sat on disk.

    poetry run python tools/factory_report.py --repo /c/.../boostgauge
    poetry run python tools/factory_report.py --repo <path> --since 7d
    poetry run python tools/factory_report.py --repo <path> --since 2026-08-27 --save

Read-only by construction: v1 adds no instrumentation and writes nothing
except the optional saved copy under `docs/audits/`.

Exit codes: 0 always, including "nothing recorded" -- an empty store is a
fact about the pipeline, not an error in this tool.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# #2367: before anything prints. Fingerprints and heal details quote model
# and checker prose verbatim.
from assemblyzero.core.utf8_console import install as _install_utf8_console  # noqa: E402

_install_utf8_console()

from assemblyzero.speedrun.factory_report import (  # noqa: E402
    build_report,
    parse_since,
    render_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def default_save_path(repo: Path, when: datetime | None = None) -> Path:
    """`docs/audits/0904-factory-report-<repo>-<date>.md` in AssemblyZero.

    The report is about a TARGET repo but is an AssemblyZero audit artifact,
    so it lands in this repo's audits directory with the target named in the
    filename -- one file per target per day, overwritten on re-run so a
    second run the same day corrects rather than accumulates.
    """
    stamp = (when or datetime.now()).strftime("%Y-%m-%d")
    return (
        REPO_ROOT
        / "docs"
        / "audits"
        / f"0904-factory-report-{repo.name.lower()}-{stamp}.md"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Roll up the factory's telemetry stores into one counted picture."
    )
    parser.add_argument(
        "--repo", required=True, help="target repository whose stores to read"
    )
    parser.add_argument(
        "--since",
        default="",
        help="window lower bound: 7d, 24h, 2w, YYYY-MM-DD, or 'YYYY-MM-DD HH:MM:SS'",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="also write the report under docs/audits/ in AssemblyZero",
    )
    parser.add_argument(
        "--save-path",
        default="",
        help="explicit destination for --save (default: docs/audits/0904-...)",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"No such repository: {repo}", flush=True)
        return 0

    try:
        since = parse_since(args.since)
    except ValueError as exc:
        # A window the operator asked for and this tool could not parse is
        # the one error worth refusing on: reading everything instead would
        # put a wrong denominator under every number that follows.
        parser.error(str(exc))
        return 2  # unreachable; parser.error exits 2

    data = build_report(repo, since=since)
    text = render_report(data)
    print(text, end="", flush=True)

    if args.save or args.save_path:
        target = (
            Path(args.save_path) if args.save_path else default_save_path(repo)
        )
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            print(f"Saved to {target}", flush=True)
        except OSError as exc:
            # The report already printed; failing to ALSO save it is not a
            # reason to report failure for work that succeeded.
            print(f"[WARN] could not save report: {exc}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
