#!/usr/bin/env python3
"""Morning status: what happened in last night's dependabot fleet run?

Four checks in one place:

1. Scheduled-task log: did the wrapper actually run and complete?
2. Open dependabot PRs across the fleet: count and titles.
3. Review-credit count: total unique PRs reviewed by the user
   (the GitHub "Code Review" profile-stat metric).
4. Dependabot PRs closed today: merged or otherwise.

Stdlib only -- no third-party imports. Runs from anywhere; uses the
local `gh` CLI for GitHub queries and reads the fixed log file path
written by tools/run_dependabot_fleet.ps1.

Usage:
    poetry run python tools/dependabot_morning_status.py
    poetry run python tools/dependabot_morning_status.py --date 2026-05-13
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
from pathlib import Path

GITHUB_USER = "martymcenroe"
LOG_FILE = Path("C:/Users/mcwiz/Projects/dependabot-fleet.log")
LOG_TAIL_LINES = 10
TITLE_TRUNC = 80


def _gh(*args: str) -> subprocess.CompletedProcess:
    """Run a gh CLI invocation; UTF-8 decoded, error-tolerant."""
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _section(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def check_log_tail() -> None:
    _section("1. SCHEDULED-TASK LOG")
    if not LOG_FILE.exists():
        print(f"  log file not found: {LOG_FILE}")
        print("  -> the Windows scheduled task may never have fired")
        return

    text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        print(f"  log file is empty: {LOG_FILE}")
        return

    for line in lines[-LOG_TAIL_LINES:]:
        print(f"  {line}")

    print()
    last = lines[-1].strip()
    if "| OK |" in last:
        print("  Verdict: task completed cleanly")
    elif "| EXIT " in last:
        print(f"  Verdict: task exited non-zero -- {last}")
    elif "| ERROR |" in last:
        print(f"  Verdict: wrapper-level error -- {last}")
    elif "| START |" in last:
        print("  Verdict: task started but never logged a completion line "
              "(still running, or crashed silently)")
    else:
        print(f"  Verdict: log ends on an unexpected line -- {last}")


def check_open_prs() -> None:
    _section("2. OPEN DEPENDABOT PRs")
    result = _gh(
        "search", "prs",
        "--author", "app/dependabot",
        "--state", "open",
        "--owner", GITHUB_USER,
        "--limit", "100",
        "--json", "repository,number,title",
    )
    if result.returncode != 0:
        print(f"  gh search failed: {result.stderr.strip()}")
        return
    prs = json.loads(result.stdout or "[]")
    print(f"  count: {len(prs)}")
    for pr in prs:
        repo = pr["repository"]["name"]
        num = pr["number"]
        title = pr["title"]
        if len(title) > TITLE_TRUNC:
            title = title[: TITLE_TRUNC - 1] + "..."
        print(f"  - {repo}#{num}: {title}")


def check_review_count() -> None:
    _section("3. CODE-REVIEW COUNT")
    result = _gh(
        "api",
        f"search/issues?q=reviewed-by:{GITHUB_USER}+type:pr",
        "--jq", ".total_count",
    )
    if result.returncode != 0:
        print(f"  gh api failed: {result.stderr.strip()}")
        return
    count = (result.stdout or "").strip() or "?"
    print(f"  unique PRs reviewed (all-time): {count}")


def check_closed_today(date_str: str) -> None:
    _section(f"4. DEPENDABOT PRs CLOSED ON {date_str}")
    result = _gh(
        "search", "prs",
        "--author", "app/dependabot",
        "--owner", GITHUB_USER,
        "--closed", f"{date_str}..{date_str}",
        "--limit", "100",
        "--json", "repository,number,title,state",
    )
    if result.returncode != 0:
        print(f"  gh search failed: {result.stderr.strip()}")
        return
    prs = json.loads(result.stdout or "[]")
    if not prs:
        print(f"  no dependabot PRs closed on {date_str}")
        return

    merged = [pr for pr in prs if pr["state"].upper() == "MERGED"]
    closed = [pr for pr in prs if pr["state"].upper() != "MERGED"]

    if merged:
        print(f"  MERGED: {len(merged)}")
        for pr in merged:
            title = pr["title"]
            if len(title) > TITLE_TRUNC:
                title = title[: TITLE_TRUNC - 1] + "..."
            print(f"    - {pr['repository']['name']}#{pr['number']}: {title}")
    if closed:
        print(f"  CLOSED (not merged): {len(closed)}")
        for pr in closed:
            title = pr["title"]
            if len(title) > TITLE_TRUNC:
                title = title[: TITLE_TRUNC - 1] + "..."
            print(f"    - {pr['repository']['name']}#{pr['number']}: {title}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.strip().split("\n")[0],
    )
    parser.add_argument(
        "--date",
        default=datetime.date.today().isoformat(),
        help="Date to check for closed PRs (default: today, format YYYY-MM-DD)",
    )
    args = parser.parse_args(argv)

    check_log_tail()
    check_open_prs()
    check_review_count()
    check_closed_today(args.date)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
