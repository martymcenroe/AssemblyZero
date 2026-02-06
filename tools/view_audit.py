#!/usr/bin/env python3
"""Live audit viewer for AssemblyZero governance log.

Usage:
    python tools/view_audit.py [--tail N] [--live|--follow]

Examples:
    python tools/view_audit.py              # Show last 10 entries
    python tools/view_audit.py --tail 20    # Show last 20 entries
    python tools/view_audit.py --live       # Watch for new entries in real-time
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from assemblyzero.core.audit import GovernanceAuditLog, GovernanceLogEntry
from assemblyzero.core.config import DEFAULT_AUDIT_LOG_PATH


def format_timestamp(iso_timestamp: str) -> str:
    """Format ISO timestamp to human-readable format."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return iso_timestamp[:19] if iso_timestamp else "N/A"


def format_verdict(verdict: str) -> str:
    """Format verdict with visual indicator."""
    if verdict == "APPROVED":
        return "APPROVED"
    else:
        return "BLOCKED"


def print_entry(entry: GovernanceLogEntry, verbose: bool = False) -> None:
    """Print a single log entry in formatted table row."""
    timestamp = format_timestamp(entry.get("timestamp", ""))
    verdict = format_verdict(entry.get("verdict", "UNKNOWN"))
    issue_id = entry.get("issue_id", "?")
    node = entry.get("node", "?")
    credential = entry.get("credential_used", "N/A")
    rotated = "YES" if entry.get("rotation_occurred", False) else "no"
    attempts = entry.get("attempts", 0)
    duration = entry.get("duration_ms", 0)

    # Main row
    print(
        f"{timestamp} | #{issue_id:<4} | {node:<12} | {verdict:<8} | "
        f"{credential:<15} | rot:{rotated:<3} | att:{attempts} | {duration}ms"
    )

    if verbose:
        critique = entry.get("critique", "")
        if critique:
            # Truncate long critiques
            if len(critique) > 100:
                critique = critique[:100] + "..."
            print(f"    Critique: {critique}")

        tier_1 = entry.get("tier_1_issues", [])
        if tier_1:
            print(f"    Tier 1 Issues: {', '.join(tier_1[:3])}")


def print_header() -> None:
    """Print table header."""
    print("=" * 100)
    print(
        f"{'Timestamp':<19} | {'Issue':<5} | {'Node':<12} | {'Verdict':<8} | "
        f"{'Credential':<15} | {'Rot':<7} | {'Att':<4} | Duration"
    )
    print("-" * 100)


def print_table(entries: list[GovernanceLogEntry], verbose: bool = False) -> None:
    """Print entries as formatted table."""
    if not entries:
        print("No governance log entries found.")
        return

    print_header()
    for entry in entries:
        print_entry(entry, verbose)
    print("=" * 100)
    print(f"Total: {len(entries)} entries")


def watch_live(log_path: Path, verbose: bool = False) -> None:
    """Watch log file and print new entries as they appear.

    Uses watchdog for efficient file monitoring when available,
    falls back to polling otherwise.
    """
    print(f"Watching {log_path} for new entries... (Ctrl+C to stop)")
    print_header()

    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        class LogHandler(FileSystemEventHandler):
            def __init__(self):
                self.last_position = 0
                if log_path.exists():
                    self.last_position = log_path.stat().st_size

            def on_modified(self, event):
                if event.src_path == str(log_path):
                    self._read_new_entries()

            def _read_new_entries(self):
                if not log_path.exists():
                    return

                with open(log_path, encoding="utf-8") as f:
                    f.seek(self.last_position)
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                import json

                                entry = json.loads(line)
                                print_entry(entry, verbose)
                            except Exception:
                                pass
                    self.last_position = f.tell()

        handler = LogHandler()
        observer = Observer()
        observer.schedule(handler, str(log_path.parent), recursive=False)
        observer.start()

        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    except ImportError:
        # Fallback to polling
        print("(watchdog not available, using polling)")
        last_position = 0
        if log_path.exists():
            last_position = log_path.stat().st_size

        try:
            while True:
                if log_path.exists():
                    current_size = log_path.stat().st_size
                    if current_size > last_position:
                        with open(log_path, encoding="utf-8") as f:
                            f.seek(last_position)
                            for line in f:
                                line = line.strip()
                                if line:
                                    try:
                                        import json

                                        entry = json.loads(line)
                                        print_entry(entry, verbose)
                                    except Exception:
                                        pass
                            last_position = f.tell()
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    print("\nStopped watching.")


def main() -> None:
    """CLI entry point for audit viewer."""
    parser = argparse.ArgumentParser(
        description="View AssemblyZero governance audit log",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/view_audit.py              # Show last 10 entries
  python tools/view_audit.py --tail 20    # Show last 20 entries
  python tools/view_audit.py --live       # Watch for new entries
  python tools/view_audit.py -v           # Verbose mode with critiques
""",
    )

    parser.add_argument(
        "--tail",
        "-n",
        type=int,
        default=10,
        help="Number of recent entries to show (default: 10)",
    )
    parser.add_argument(
        "--live",
        "--follow",
        "-f",
        action="store_true",
        help="Watch for new entries in real-time",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show critique and tier 1 issues",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=DEFAULT_AUDIT_LOG_PATH,
        help=f"Path to audit log file (default: {DEFAULT_AUDIT_LOG_PATH})",
    )

    args = parser.parse_args()

    audit_log = GovernanceAuditLog(log_path=args.log_path)

    if args.live:
        # Show recent entries first, then watch
        entries = audit_log.tail(args.tail)
        if entries:
            print(f"Recent {len(entries)} entries:")
            print_table(entries, args.verbose)
            print()
        watch_live(args.log_path, args.verbose)
    else:
        entries = audit_log.tail(args.tail)
        print_table(entries, args.verbose)


if __name__ == "__main__":
    main()
