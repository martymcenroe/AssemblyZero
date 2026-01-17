#!/usr/bin/env python3
"""
Claude Code Usage Scraper

Automates Claude Code's TUI to extract usage quota data that isn't available
via any programmatic API.

Usage:
  poetry run python tools/claude-usage-scraper.py
  poetry run python tools/claude-usage-scraper.py --log /path/to/usage.log

Output:
  JSON to stdout with session, weekly_all, and weekly_sonnet usage percentages.

References:
  - GitHub Issue #8412: https://github.com/anthropics/claude-code/issues/8412
  - GitHub Issue #5621: https://github.com/anthropics/claude-code/issues/5621
"""
import json
import re
import sys
import time
import queue
import threading
import argparse
from datetime import datetime, timezone
from pathlib import Path

try:
    import winpty
except ImportError:
    print(json.dumps({
        "status": "error",
        "error": "pywinpty not installed. Run: poetry add pywinpty",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }))
    sys.exit(1)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from terminal output."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


class PtyReader:
    """Non-blocking PTY reader using a background thread."""

    def __init__(self, pty):
        self.pty = pty
        self.queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._reader_thread, daemon=True)
        self.thread.start()

    def _reader_thread(self):
        """Background thread that continuously reads from PTY."""
        while self.running and self.pty.isalive():
            try:
                chunk = self.pty.read(4096)
                if chunk:
                    self.queue.put(chunk)
            except EOFError:
                break
            except Exception:
                break

    def read(self, timeout: float = 1.0) -> str:
        """Read all available data with timeout."""
        result = ''
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                chunk = self.queue.get(timeout=0.1)
                result += chunk
            except queue.Empty:
                if result:
                    break
        return result

    def stop(self):
        self.running = False


def parse_usage_data(raw_output: str) -> dict:
    """Parse usage percentages and reset times from Claude Code /status output."""
    text = strip_ansi(raw_output)

    result = {
        "session": {"percent_used": None, "resets_at": None},
        "weekly_all": {"percent_used": None, "resets_at": None},
        "weekly_sonnet": {"percent_used": None, "resets_at": None}
    }

    # Session pattern - handles TUI box characters
    session_match = re.search(
        r'Current\s+session[^\d]*(\d+)%\s*used.*?Resets?\s+([^\n\r│]+)',
        text, re.IGNORECASE | re.DOTALL
    )
    if session_match:
        result["session"]["percent_used"] = int(session_match.group(1))
        result["session"]["resets_at"] = session_match.group(2).strip()

    # Weekly all models pattern
    weekly_all_match = re.search(
        r'Current\s+week\s*\(all\s+models?\)[^\d]*(\d+)%\s*used.*?Resets?\s+([^\n\r│]+)',
        text, re.IGNORECASE | re.DOTALL
    )
    if weekly_all_match:
        result["weekly_all"]["percent_used"] = int(weekly_all_match.group(1))
        result["weekly_all"]["resets_at"] = weekly_all_match.group(2).strip()

    # Weekly Sonnet only pattern - captures percentage and optional reset time
    weekly_sonnet_match = re.search(
        r'Current\s+week\s*\(Sonnet\s+only\)[^\d]*(\d+)%\s*used(?:.*?Resets?\s+([^\n\r│]+))?',
        text, re.IGNORECASE | re.DOTALL
    )
    if weekly_sonnet_match:
        result["weekly_sonnet"]["percent_used"] = int(weekly_sonnet_match.group(1))
        # Sonnet reset time may not be shown if 0% - capture if present
        if weekly_sonnet_match.group(2):
            result["weekly_sonnet"]["resets_at"] = weekly_sonnet_match.group(2).strip()

    return result


def scrape_usage(timeout: int = 30) -> dict:
    """
    Spawn Claude Code, navigate to /status Usage tab, and scrape the data.

    Returns dict with usage data or error information.
    """
    output_buffer = ""
    pty_process = None
    reader = None

    try:
        # Spawn Claude Code in a PTY with adequate dimensions
        pty_process = winpty.PtyProcess.spawn(['claude'], dimensions=(50, 150))

        # Create non-blocking reader
        reader = PtyReader(pty_process)

        # Wait for Claude to initialize (takes a few seconds)
        time.sleep(6)
        initial = reader.read(timeout=2.0)
        output_buffer += initial

        if not pty_process.isalive():
            return {
                "status": "error",
                "error": "Claude Code process exited unexpectedly",
                "raw_output": strip_ansi(output_buffer)
            }

        # Type /status command
        pty_process.write('/status')
        time.sleep(1)
        _ = reader.read(timeout=1.0)  # Discard autocomplete output

        # Press Escape to dismiss autocomplete
        pty_process.write('\x1b')
        time.sleep(0.5)
        _ = reader.read(timeout=0.5)

        # Press Enter to execute /status
        pty_process.write('\r')
        time.sleep(3)

        status_output = reader.read(timeout=3.0)
        output_buffer += status_output

        # Now we're on the Status tab. Tab twice to get to Usage tab
        # Status → Config → Usage
        pty_process.write('\t')
        time.sleep(1)
        _ = reader.read(timeout=1.0)

        pty_process.write('\t')
        time.sleep(2)

        usage_output = reader.read(timeout=2.0)
        output_buffer += usage_output

        # Parse the usage data
        usage_data = parse_usage_data(output_buffer)

        # Check if we got any data
        has_data = any(
            usage_data[key]["percent_used"] is not None
            for key in ["session", "weekly_all", "weekly_sonnet"]
        )

        if not has_data:
            return {
                "status": "error",
                "error": "Could not parse usage data from output",
                "raw_output": strip_ansi(output_buffer)[-2000:]
            }

        return {
            "status": "success",
            **usage_data
        }

    except FileNotFoundError:
        return {
            "status": "error",
            "error": "Claude Code not found. Ensure 'claude' is in PATH."
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "raw_output": strip_ansi(output_buffer)[-1000:] if output_buffer else None
        }
    finally:
        # Stop the reader thread
        if reader:
            reader.stop()

        # Clean up: exit Claude Code
        if pty_process and pty_process.isalive():
            try:
                pty_process.write('\x1b')  # Escape to close dialog
                time.sleep(0.3)
                pty_process.write('/exit\r')
                time.sleep(0.5)
                if pty_process.isalive():
                    pty_process.terminate()
            except Exception:
                try:
                    pty_process.terminate()
                except Exception:
                    pass


def append_to_log(log_path: Path, data: dict):
    """Append a NDJSON (newline-delimited JSON) log entry.

    Each line is a complete JSON object for easy parsing by log aggregators
    (Splunk, Datadog, etc.) and standard tools like jq.
    """
    # Ensure timestamp is present
    if "timestamp" not in data:
        data["timestamp"] = datetime.now(timezone.utc).isoformat()

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Claude Code usage quota data via terminal automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  poetry run python tools/claude-usage-scraper.py
  poetry run python tools/claude-usage-scraper.py --log ~/Projects/claude-usage.log
  poetry run python tools/claude-usage-scraper.py --timeout 45
        """
    )
    parser.add_argument(
        "--log", "-l",
        default=None,
        help="Path to append NDJSON log entries (one JSON object per line)"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        help="Timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress JSON output to stdout (only write to log if specified)"
    )

    args = parser.parse_args()

    # Scrape usage data
    result = scrape_usage(timeout=args.timeout)

    # Add timestamp
    result["timestamp"] = datetime.now(timezone.utc).isoformat()

    # Append to log if specified
    if args.log:
        log_path = Path(args.log).expanduser()
        append_to_log(log_path, result)

    # Output JSON to stdout
    if not args.quiet:
        print(json.dumps(result, indent=2))

    # Exit with error code if scraping failed
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
