#!/usr/bin/env python3
"""
Zugzwang - Permission Friction Logger

Real-time logger for Claude Code permission prompts. Run in a separate terminal,
paste what you see when permission is requested, press Enter.

Usage:
  poetry run python tools/zugzwang.py                    # Interactive mode
  poetry run python tools/zugzwang.py --log "event"      # One-shot log
  poetry run python tools/zugzwang.py --tail 10          # View last 10 entries
  poetry run python tools/zugzwang.py --clear            # Clear log file

Interactive shortcuts:
  .b <text>   Log as BASH category
  .s <text>   Log as SPAWNED category
  .d <text>   Log as DENIED category
  .a <text>   Log as APPROVED category
  .m          Multi-line mode (end with . on its own line)
  .t [n]      Show last n entries (default 10)
  .c / clear  Clear log
  .q / exit   Quit
  .h          Show shortcuts

Multi-line paste is auto-detected and captured as single entry.
"""
import argparse
import datetime
import msvcrt
import sys
import time
from pathlib import Path


# Log file in AssemblyZero/logs/
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
LOG_FILE = PROJECT_ROOT / "logs" / "zugzwang.log"


def get_timestamp() -> str:
    """ISO format timestamp."""
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def get_entry_count() -> int:
    """Count entries in log file."""
    if not LOG_FILE.exists():
        return 0
    content = LOG_FILE.read_text(encoding="utf-8").strip()
    if not content:
        return 0
    return len(content.split("\n"))


def log_event(event: str, category: str | None = None) -> tuple[str, str, int]:
    """Append event to log file. Returns (entry, timestamp, total_count)."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    timestamp = get_timestamp()

    if category:
        entry = f"{timestamp} | {category} | {event}"
    else:
        entry = f"{timestamp} | {event}"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

    count = get_entry_count()
    return entry, timestamp, count


def show_tail(n: int = 10) -> None:
    """Show last n entries."""
    if not LOG_FILE.exists():
        print("No log file yet.")
        return

    lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
    if not lines or lines == [""]:
        print("Log is empty.")
        return

    print(f"\n--- Last {min(n, len(lines))} entries ---")
    for line in lines[-n:]:
        print(line)
    print("---")


def clear_log() -> None:
    """Clear the log file."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text("", encoding="utf-8")
    print("Log cleared.")


def print_shortcuts() -> None:
    """Print interactive mode shortcuts."""
    print("""
Shortcuts:
  .b <text>   Log as BASH category
  .s <text>   Log as SPAWNED category
  .d <text>   Log as DENIED category
  .a <text>   Log as APPROVED category
  .m          Start multi-line mode (end with . on its own line)
  .t [n]      Show last n entries (default 10)
  .c / clear  Clear log
  .q / exit   Quit
  .h          This help

Or just type/paste anything - free-form logging.
""")


def read_input_with_paste_detection() -> str | None:
    """Read input, detecting and buffering multi-line paste."""
    raw = input("> ").strip()

    if not raw:
        return None

    lines = [raw]

    # Paste detection: check if more lines are immediately in buffer
    time.sleep(0.03)  # Brief wait for paste buffer to fill
    while msvcrt.kbhit():
        try:
            extra = input().strip()  # No prompt for continuation
            if extra:
                lines.append(extra)
            time.sleep(0.01)
        except EOFError:
            break

    if len(lines) > 1:
        combined = " | ".join(lines)
        print(f"  (captured {len(lines)} lines as single entry)")
        return combined

    return raw


def interactive_mode() -> None:
    """Run interactive prompt loop."""
    print("=" * 50)
    print("ZUGZWANG - Permission Friction Logger")
    print("=" * 50)
    print(f"Log: {LOG_FILE}")
    print("Type .h for shortcuts, .q to quit")
    print()

    while True:
        try:
            raw = read_input_with_paste_detection()

            if not raw:
                continue

            # Handle shortcuts
            if raw == ".q" or raw == "exit":
                break
            elif raw == ".h":
                print_shortcuts()
            elif raw == ".c" or raw == "clear":
                clear_log()
            elif raw == ".m":
                # Multi-line mode
                print("  Multi-line mode. End with '.' on its own line:")
                lines = []
                while True:
                    line = input("  | ")
                    if line == ".":
                        break
                    lines.append(line)
                if lines:
                    combined = " | ".join(lines)  # Join with delimiter for single-line storage
                    entry, ts, count = log_event(combined)
                    print(f"  Appended @ {ts} (#{count}) -> {LOG_FILE}")
                else:
                    print("  (empty, not logged)")
            elif raw.startswith(".t"):
                parts = raw.split(maxsplit=1)
                n = int(parts[1]) if len(parts) > 1 else 10
                show_tail(n)
            elif raw.startswith(".b "):
                entry, ts, count = log_event(raw[3:], "BASH")
                print(f"  Appended @ {ts} (#{count}) -> {LOG_FILE}")
            elif raw.startswith(".s "):
                entry, ts, count = log_event(raw[3:], "SPAWNED")
                print(f"  Appended @ {ts} (#{count}) -> {LOG_FILE}")
            elif raw.startswith(".d "):
                entry, ts, count = log_event(raw[3:], "DENIED")
                print(f"  Appended @ {ts} (#{count}) -> {LOG_FILE}")
            elif raw.startswith(".a "):
                entry, ts, count = log_event(raw[3:], "APPROVED")
                print(f"  Appended @ {ts} (#{count}) -> {LOG_FILE}")
            else:
                # Free-form entry
                entry, ts, count = log_event(raw)
                print(f"  Appended @ {ts} (#{count}) -> {LOG_FILE}")

        except KeyboardInterrupt:
            print()
            break
        except EOFError:
            break

    print("\nBye!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zugzwang - Permission Friction Logger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  poetry run python tools/zugzwang.py
      Start interactive mode - paste events as they happen

  poetry run python tools/zugzwang.py --log "head -n 5 ~/.claude/file"
      Log a single event and exit

  poetry run python tools/zugzwang.py --tail 20
      Show last 20 log entries

  poetry run python tools/zugzwang.py --clear
      Clear the log file

Interactive shortcuts:
  .b <text>   Log as BASH category
  .s <text>   Log as SPAWNED category
  .d <text>   Log as DENIED category
  .a <text>   Log as APPROVED category
  .m          Multi-line mode (end with . on its own line)
  .t [n]      Show last n entries (default 10)
  .c / clear  Clear log
  .q / exit   Quit
  .h          Show shortcuts

Multi-line paste is auto-detected and captured as single entry.
"""
    )

    parser.add_argument(
        "--log", "-l",
        metavar="EVENT",
        help="Log a single event and exit"
    )
    parser.add_argument(
        "--tail", "-t",
        type=int,
        nargs="?",
        const=10,
        metavar="N",
        help="Show last N log entries (default: 10)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the log file"
    )
    parser.add_argument(
        "--category", "-c",
        choices=["BASH", "SPAWNED", "DENIED", "APPROVED"],
        help="Category for --log event"
    )

    args = parser.parse_args()

    # Handle modes
    if args.clear:
        clear_log()
    elif args.tail is not None:
        show_tail(args.tail)
    elif args.log:
        entry, ts, count = log_event(args.log, args.category)
        print(f"Appended @ {ts} (#{count} total entries)")
        print(f"Log: {LOG_FILE}")
    else:
        # No args = interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()
