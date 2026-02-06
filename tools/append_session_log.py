#!/usr/bin/env python3
"""
Append Session Log Entry (AssemblyZero - Parent Level)

Appends a new session log entry to the correct daily file at the Projects level.
Day boundary: 3:00 AM CT to following day 2:59 AM CT.

Usage:
    poetry run python tools/append_session_log.py --model "Claude Opus 4.5" --summary "Did stuff"
    poetry run python tools/append_session_log.py --template  # Just append template for manual fill-in

This is the PARENT-level session log for cross-project work.
Individual projects (Aletheia, Talos) have their own session logs.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


# Configuration - Parent level session logs
SESSION_LOGS_DIR = Path("C:/Users/mcwiz/Projects/session-logs")
CT_TIMEZONE = ZoneInfo("America/Chicago")


def get_session_date() -> datetime:
    """
    Get the date for the current session's log file.

    Day boundary: 3:00 AM CT to following day 2:59 AM CT.
    Work done at 2am belongs to the previous calendar day's log.
    """
    now = datetime.now(CT_TIMEZONE)

    # If before 3:00 AM, use previous day
    if now.hour < 3:
        session_date = now - timedelta(days=1)
    else:
        session_date = now

    # Return just the date portion
    return session_date.replace(hour=0, minute=0, second=0, microsecond=0)


def get_session_filename() -> str:
    """Get the filename for the current day's session log."""
    session_date = get_session_date()
    return f"{session_date.strftime('%Y-%m-%d')}.md"


def get_current_timestamp() -> str:
    """Get current timestamp in CT."""
    now = datetime.now(CT_TIMEZONE)
    return now.strftime("%Y-%m-%d %H:%M")


def format_entry(
    model: str,
    summary: str | None = None,
    projects: str | None = None,
    next_action: str | None = None,
    template_only: bool = False,
) -> str:
    """Format a session log entry for parent-level work."""
    timestamp = get_current_timestamp()

    if template_only:
        # Return template with placeholders
        return f"""
---

## {timestamp} CT | {model}

### Summary
[One paragraph describing the session's main accomplishment]

### Projects Touched
[List of projects modified: Aletheia, Talos, AssemblyZero, etc.]

### Next
[What the next session should pick up]
"""
    else:
        # Return filled-in entry
        projects_touched = projects or "AssemblyZero"
        next_step = next_action or "Per user direction"

        return f"""
---

## {timestamp} CT | {model}

### Summary
{summary}

### Projects Touched
{projects_touched}

### Next
{next_step}
"""


def ensure_session_file_exists(filepath: Path) -> None:
    """Create daily session file with header if it doesn't exist."""
    if not filepath.exists():
        session_date = get_session_date()
        next_day = session_date + timedelta(days=1)

        header = f"""# AssemblyZero Session Log: {session_date.strftime('%Y-%m-%d')}

**Period:** {session_date.strftime('%Y-%m-%d')} 3:00 AM CT -> {next_day.strftime('%Y-%m-%d')} 2:59 AM CT

This is the PARENT-level session log for cross-project orchestration work.
Individual projects have their own session logs.

---
"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(header, encoding="utf-8")
        print(f"Created new session file: {filepath}")


def append_entry(entry: str) -> Path:
    """Append entry to the current day's session log."""
    filename = get_session_filename()
    filepath = SESSION_LOGS_DIR / filename

    ensure_session_file_exists(filepath)

    # Append the entry
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(entry)

    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Append a session log entry to the parent-level session log"
    )
    parser.add_argument(
        "--model",
        default="Claude Opus 4.5",
        help="Model name (default: Claude Opus 4.5)",
    )
    parser.add_argument(
        "--summary",
        help="One paragraph summary of the session",
    )
    parser.add_argument(
        "--projects",
        help="Projects touched (e.g., 'Aletheia, AssemblyZero')",
    )
    parser.add_argument(
        "--next",
        dest="next_action",
        help="What the next session should pick up",
    )
    parser.add_argument(
        "--template",
        action="store_true",
        help="Append a template with placeholders for manual fill-in",
    )

    args = parser.parse_args()

    # Validate: either --template or --summary required
    if not args.template and not args.summary:
        print("Error: Either --template or --summary is required", file=sys.stderr)
        print("  Use --template for a placeholder template", file=sys.stderr)
        print("  Use --summary 'text' for a filled-in entry", file=sys.stderr)
        sys.exit(1)

    entry = format_entry(
        model=args.model,
        summary=args.summary,
        projects=args.projects,
        next_action=args.next_action,
        template_only=args.template,
    )

    filepath = append_entry(entry)

    print(f"Appended session log entry to: {filepath}")
    print(f"Timestamp: {get_current_timestamp()} CT")
    if args.template:
        print("Note: Template appended - edit file to fill in placeholders")


if __name__ == "__main__":
    main()
