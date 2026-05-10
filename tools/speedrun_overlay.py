#!/usr/bin/env python3
"""Read a speed-run lap-splits JSON and print a clean overlay (#1076).

Designed to be piped into a `pet` overlay window during recording, OR
just printed to a side terminal so the operator can see lap times
develop in real-time.

Usage:

    # Latest attempt for an issue:
    poetry run python tools/speedrun_overlay.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge --issue 35

    # Specific attempt:
    poetry run python tools/speedrun_overlay.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge --issue 35 --attempt 7

    # Watch mode — re-render every second:
    poetry run python tools/speedrun_overlay.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge --issue 35 --watch
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def _latest_attempt(speedrun_dir: Path, issue: int) -> int | None:
    """Find the highest attempt number for this issue."""
    if not speedrun_dir.exists():
        return None
    max_attempt = 0
    for f in speedrun_dir.glob(f"{issue}-*.json"):
        parts = f.stem.rsplit("-", 1)
        if len(parts) != 2:
            continue
        try:
            n = int(parts[1])
            if n > max_attempt:
                max_attempt = n
        except ValueError:
            continue
    return max_attempt if max_attempt > 0 else None


def _format_t(t: float) -> str:
    """Format seconds as MM:SS."""
    minutes, seconds = divmod(int(t), 60)
    return f"{minutes:02d}:{seconds:02d}"


def render(splits_file: Path) -> str:
    """Read splits file and produce the overlay text."""
    if not splits_file.exists():
        return f"(no lap splits file at {splits_file})"
    try:
        data = json.loads(splits_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return f"(error reading splits: {e})"

    issue = data.get("issue", "?")
    attempt = data.get("attempt", "?")
    started_at = data.get("started_at", "?")
    splits = data.get("splits", [])

    lines = [
        f"=== speed-run #{issue} attempt {attempt} ===",
        f"started: {started_at}",
        "",
    ]
    if not splits:
        lines.append("(no beats yet)")
    else:
        for split in splits:
            beat = split.get("beat", "?")
            t = split.get("t", 0.0)
            failure_mode = split.get("failure_mode")
            line = f"  [{_format_t(t)}] {beat}"
            if failure_mode:
                line += f"  -- {failure_mode}"
            lines.append(line)
        # Live elapsed (if not yet finalized)
        last_beat = splits[-1].get("beat", "")
        if not last_beat.startswith("completed_"):
            lines.append("")
            lines.append("  (in progress)")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Speed-run lap split overlay")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument(
        "--attempt", type=int, default=None,
        help="Specific attempt number (default: latest)",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="Re-render every second until interrupted",
    )
    args = parser.parse_args()

    repo_root = args.repo.resolve()
    speedrun_dir = repo_root / "data" / "speedrun"

    attempt = args.attempt
    if attempt is None:
        attempt = _latest_attempt(speedrun_dir, args.issue)
        if attempt is None:
            print(f"No attempts found for issue #{args.issue}")
            return 1

    splits_file = speedrun_dir / f"{args.issue}-{attempt}.json"

    if not args.watch:
        print(render(splits_file))
        return 0

    try:
        while True:
            print("\033[2J\033[H", end="")  # clear screen + home
            print(render(splits_file))
            time.sleep(1)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
