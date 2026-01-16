#!/usr/bin/env python3
"""
Unleashed Danger - PTY Wrapper for Claude Code Auto-Approval (No Safety Checks)

DANGER MODE: This version has NO safety checks - it auto-approves EVERYTHING.
- No hard block checks
- No dangerous path checks
- No git destructive checks
- NEVER sends Escape to Claude (cannot interrupt)

Use this when you need uninterrupted Claude operation and accept all risks.

Usage:
  python tools/unleashed-danger.py [--dry-run] [--help]

Environment Variables:
  UNLEASHED_DELAY=N  Override default 10-second countdown (default: 10)

Security Note:
  This tool auto-approves ALL permission prompts with ZERO safety checks.
  Use at your own risk.

References:
  - Issue #10: https://github.com/martymcenroe/AgentOS/issues/10
"""

import argparse
import json
import os
import queue
import re
import select
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# Version constant (defined early for --version flag)
VERSION = "1.4.0-danger"  # Danger mode - no safety checks, no escape

# Handle --version before heavy imports
if "--version" in sys.argv or "-v" in sys.argv:
    print(f"unleashed-danger.py {VERSION}")
    sys.exit(0)

try:
    import winpty
except ImportError:
    print("[UNLEASHED-DANGER] Error: pywinpty not installed. Run: poetry add pywinpty", file=sys.stderr)
    sys.exit(1)

# Try to import msvcrt for Windows keyboard input
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False


# =============================================================================
# Constants
# =============================================================================

DEFAULT_DELAY = 10  # seconds
FOOTER_PATTERN = re.compile(
    r'Esc to cancel[-·–—\s]+Tab to add additional instructions',
    re.IGNORECASE
)
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# ANSI escape sequences for overlay
CURSOR_SAVE = '\x1b[s'
CURSOR_RESTORE = '\x1b[u'
CURSOR_HOME = '\x1b[H'
CLEAR_LINE = '\x1b[2K'
BOLD = '\x1b[1m'
YELLOW = '\x1b[33m'
RED = '\x1b[31m'
RESET = '\x1b[0m'


# =============================================================================
# Utility Functions
# =============================================================================

def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from terminal output."""
    return ANSI_ESCAPE.sub('', text)


def is_printable_key(char: str) -> bool:
    """Check if a character is a printable key (not a modifier alone)."""
    if not char:
        return False
    # Printable ASCII range or common keys
    return len(char) == 1 and (char.isprintable() or char in '\r\n\t')


def get_timestamp() -> str:
    """Get ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# PTY Reader (from claude-usage-scraper.py pattern)
# =============================================================================

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

    def read_nowait(self) -> str:
        """Read all available data without blocking."""
        result = ''
        while True:
            try:
                chunk = self.queue.get_nowait()
                result += chunk
            except queue.Empty:
                break
        return result

    def read(self, timeout: float = 0.1) -> str:
        """Read all available data with timeout."""
        result = ''
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                chunk = self.queue.get(timeout=0.05)
                result += chunk
            except queue.Empty:
                if result:
                    break
        return result

    def stop(self):
        self.running = False


# =============================================================================
# Input Reader (for user keyboard input) - DANGER MODE
# =============================================================================

class InputReader:
    """Non-blocking input reader - DANGER MODE with aggressive filtering.

    This reader aggressively filters out terminal response characters
    to prevent them from being passed to Claude and interrupting it.
    """

    def __init__(self):
        self.queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._reader_thread, daemon=True)
        self.thread.start()

    def _is_safe_char(self, char: str) -> bool:
        """Check if character is safe user input (not terminal garbage).

        AGGRESSIVE filtering - only pass through:
        - Printable ASCII (32-126)
        - Tab (9), Enter (13), Backspace (8)
        - Escape (27) - but only standalone, not in sequences

        FILTERED (terminal response garbage):
        - Digits (0-9) - often part of terminal responses
        - Semicolons (;) - CSI parameter separator
        - Brackets ([ ]) - CSI sequences
        - Question mark (?) - terminal mode queries
        - Letter 'c' - device attributes response terminator
        """
        if not char:
            return False
        code = ord(char)
        # Safe: printable ASCII (32-126), Tab(9), Enter(13), Backspace(8)
        # Note: We filter Escape(27) separately via sequence detection
        safe_controls = {8, 9, 10, 13}
        return (32 <= code <= 126) or code in safe_controls

    def _reader_thread(self):
        """Background thread for reading stdin via msvcrt - with aggressive filtering."""
        while self.running:
            try:
                if HAS_MSVCRT:
                    if msvcrt.kbhit():
                        char = msvcrt.getwch()

                        # FILTER: Drop anything that looks like terminal response
                        # Terminal responses often contain digits, semicolons, brackets
                        # after escape sequences - drop ALL of these
                        if char in '0123456789;[]?c':
                            # Likely terminal response garbage - drop it
                            # Drain any remaining garbage
                            while msvcrt.kbhit():
                                garbage = msvcrt.getwch()
                                if garbage in '\r\n':  # Stop at newline
                                    break
                            continue

                        # Handle Windows special keys
                        if char in ('\xe0', '\x00'):
                            scan = msvcrt.getwch()
                            key_map = {
                                'H': '\x1b[A',  # Up
                                'P': '\x1b[B',  # Down
                                'K': '\x1b[D',  # Left
                                'M': '\x1b[C',  # Right
                                'G': '\x1b[H',  # Home
                                'O': '\x1b[F',  # End
                                'I': '\x1b[5~', # Page Up
                                'Q': '\x1b[6~', # Page Down
                                'R': '\x1b[2~', # Insert
                                'S': '\x1b[3~', # Delete
                            }
                            if scan in key_map:
                                self.queue.put(key_map[scan])
                        elif char == '\x1b':
                            # Escape character - might be terminal response
                            # Try to read the full sequence
                            seq = char
                            while msvcrt.kbhit():
                                seq += msvcrt.getwch()

                            # AGGRESSIVE FILTER: Drop ALL escape sequences
                            # In danger mode, we don't want ANY escape sequences
                            # going to Claude - they could interrupt it
                            if len(seq) > 1:
                                # Multi-char escape sequence - definitely terminal response
                                continue
                            # Single escape - also drop it to be safe
                            # User can still cancel via the countdown overlay
                            continue
                        elif self._is_safe_char(char):
                            self.queue.put(char)
                        # else: drop unsafe character
                    else:
                        time.sleep(0.01)
                else:
                    if select.select([sys.stdin], [], [], 0.01)[0]:
                        char = sys.stdin.read(1)
                        if char and self._is_safe_char(char):
                            self.queue.put(char)
            except Exception:
                time.sleep(0.01)

    def read_nowait(self) -> str:
        """Read all available input without blocking."""
        result = ''
        while True:
            try:
                char = self.queue.get_nowait()
                result += char
            except queue.Empty:
                break
        return result

    def stop(self):
        self.running = False


# =============================================================================
# Event Logger
# =============================================================================

class EventLogger:
    """Structured event logger for unleashed sessions."""

    def __init__(self, log_dir: Path, session_id: str):
        self.log_dir = log_dir
        self.session_id = session_id
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Raw output log
        self.raw_log_path = log_dir / f"unleashed-danger_{session_id}.log"
        self.raw_log = open(self.raw_log_path, 'wb')

        # Structured event log
        self.event_log_path = log_dir / f"unleashed-danger_events_{session_id}.jsonl"
        self.event_log = open(self.event_log_path, 'a', encoding='utf-8')

    def log_raw(self, data: bytes):
        """Log raw bytes to session log."""
        self.raw_log.write(data)
        self.raw_log.flush()

    def log_event(self, event_type: str, **kwargs):
        """Log structured event."""
        event = {
            "ts": get_timestamp(),
            "event": event_type,
            **kwargs
        }
        self.event_log.write(json.dumps(event) + '\n')
        self.event_log.flush()

    def close(self):
        """Close all log files."""
        self.raw_log.close()
        self.event_log.close()


# =============================================================================
# Countdown Overlay
# =============================================================================

class CountdownOverlay:
    """Manages the ANSI overlay for countdown display."""

    def __init__(self, writer):
        self.writer = writer  # Function to write to stdout
        self.active = False

    def show(self, seconds_remaining: int):
        """Show countdown overlay."""
        self.active = True
        message = f"{CURSOR_SAVE}{CURSOR_HOME}{BOLD}{RED}[UNLEASHED-DANGER]{YELLOW} Auto-approving in {seconds_remaining}s... (Press any key to cancel){RESET}{CLEAR_LINE}{CURSOR_RESTORE}"
        self.writer(message)

    def hide(self):
        """Hide countdown overlay."""
        if self.active:
            # Clear the overlay line
            message = f"{CURSOR_SAVE}{CURSOR_HOME}{CLEAR_LINE}{CURSOR_RESTORE}"
            self.writer(message)
            self.active = False

    def show_approved(self):
        """Show approval message briefly."""
        message = f"{CURSOR_SAVE}{CURSOR_HOME}{BOLD}{RED}[UNLEASHED-DANGER]{YELLOW} Auto-approved!{RESET}{CLEAR_LINE}{CURSOR_RESTORE}"
        self.writer(message)

    def show_cancelled(self):
        """Show cancellation message briefly."""
        message = f"{CURSOR_SAVE}{CURSOR_HOME}{BOLD}{RED}[UNLEASHED-DANGER]{YELLOW} Cancelled by user{RESET}{CLEAR_LINE}{CURSOR_RESTORE}"
        self.writer(message)


# =============================================================================
# Main Unleashed Wrapper
# =============================================================================

class Unleashed:
    """Main PTY wrapper for auto-approval - DANGER MODE.

    DANGER MODE means:
    - NO safety checks (hard block, dangerous path, git destructive)
    - NEVER sends Escape to Claude
    - Aggressive input filtering
    - Just countdown and auto-approve
    """

    def __init__(self, delay: int = DEFAULT_DELAY, dry_run: bool = False, cwd: str = None):
        self.delay = delay
        self.dry_run = dry_run
        self.cwd = cwd or os.getcwd()
        self.pty_process = None
        self.pty_reader = None
        self.input_reader = None
        self.logger = None
        self.overlay = None
        self.running = False
        self.in_countdown = False
        self.screen_buffer = ""  # Recent screen content for context
        self.buffer_max_size = 8192  # Keep last 8KB for context

    def _write_stdout(self, data: str):
        """Write to stdout and flush."""
        sys.stdout.write(data)
        sys.stdout.flush()

    def _detect_footer(self, text: str) -> bool:
        """Check if the permission footer is present in text."""
        clean_text = strip_ansi(text)
        return bool(FOOTER_PATTERN.search(clean_text))

    def _detect_three_options(self) -> bool:
        """Check if the current prompt has 3 options (includes 'remember' option).

        When there are 3 options, option 2 is typically "Yes, and don't ask again..."
        which we prefer to select to reduce future prompts.
        """
        clean_text = strip_ansi(self.screen_buffer)
        # Look for "3. No" or "3." followed by "No" near end of buffer
        recent = clean_text[-500:]
        return bool(re.search(r'3\.\s*No', recent))

    def _capture_screen_context(self) -> str:
        """Capture current screen context for logging."""
        return strip_ansi(self.screen_buffer)[-2000:]  # Last 2KB stripped

    def _handle_countdown(self) -> bool:
        """
        Handle the countdown sequence.
        Returns True if auto-approved, False if cancelled.

        DANGER MODE: No safety checks - just countdown and auto-approve.
        NEVER sends Escape to Claude.
        """
        self.in_countdown = True
        screen_context = self._capture_screen_context()

        self.logger.log_event("FOOTER_DETECTED")
        self.logger.log_event("COUNTDOWN_START", delay=self.delay, mode="DANGER")

        for remaining in range(self.delay, 0, -1):
            self.overlay.show(remaining)

            # Check for user input during this second
            start = time.time()
            while time.time() - start < 1.0:
                user_input = self.input_reader.read_nowait()
                if user_input:
                    for char in user_input:
                        if is_printable_key(char):
                            # User cancelled
                            self.overlay.show_cancelled()
                            time.sleep(0.5)
                            self.overlay.hide()
                            self.in_countdown = False
                            self.logger.log_event("CANCELLED_BY_USER", key=repr(char))

                            # Pass the keypress through to Claude
                            # DANGER MODE: Never send Escape, but can send other chars
                            if self.pty_process and self.pty_process.isalive():
                                # Only pass through safe characters (no escape)
                                if char != '\x1b':
                                    self.pty_process.write(char)

                            return False

                time.sleep(0.05)

        # Countdown completed - auto-approve
        self.overlay.show_approved()
        time.sleep(0.3)
        self.overlay.hide()
        self.in_countdown = False

        # Check if 3-option prompt (has "remember" option)
        has_three = self._detect_three_options()

        if not self.dry_run:
            if self.pty_process and self.pty_process.isalive():
                if has_three:
                    # Send Shift+Tab to select option 2 ("Yes, and don't ask again...")
                    self.pty_process.write('\x1b[Z')  # Shift+Tab (this is OK - it's not bare Escape)
                    time.sleep(0.05)  # Small delay for UI to update
                self.pty_process.write('\r')  # Enter to confirm
            self.logger.log_event("AUTO_APPROVED", option=2 if has_three else 1, context=screen_context[:500])
        else:
            self.logger.log_event("AUTO_APPROVED_DRY_RUN", option=2 if has_three else 1, context=screen_context[:500])

        return True

    def _show_banner(self):
        """Display startup banner to stderr (avoids Claude's stdout cursor positioning)."""
        banner = f"{BOLD}{RED}[UNLEASHED-DANGER v{VERSION}]{YELLOW} Auto-approval | {self.delay}s | NO SAFETY CHECKS | Dir: {self.cwd}{RESET}\n"
        sys.stderr.write(banner)
        sys.stderr.flush()

    def run(self):
        """Main run loop."""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path(__file__).parent.parent / "logs"

        self.logger = EventLogger(log_dir, session_id)
        self.logger.log_event("START", version=VERSION, delay=self.delay, dry_run=self.dry_run, mode="DANGER")

        # Set environment variable so Claude can check version via /unleashed-version
        os.environ['UNLEASHED_VERSION'] = VERSION

        self.overlay = CountdownOverlay(self._write_stdout)
        self._show_banner()

        try:
            # Get terminal dimensions
            try:
                import shutil
                cols, rows = shutil.get_terminal_size()
            except Exception:
                cols, rows = 120, 40

            # Spawn Claude Code in user's current working directory
            self.pty_process = winpty.PtyProcess.spawn(
                ['claude'],
                dimensions=(rows, cols),
                cwd=self.cwd
            )

            self.pty_reader = PtyReader(self.pty_process)
            self.input_reader = InputReader()
            self.running = True

            # Main loop
            while self.running and self.pty_process.isalive():
                # Read PTY output
                pty_output = self.pty_reader.read_nowait()
                if pty_output:
                    # Log raw output
                    self.logger.log_raw(pty_output.encode('utf-8', errors='replace'))

                    # Update screen buffer
                    self.screen_buffer += pty_output
                    if len(self.screen_buffer) > self.buffer_max_size:
                        self.screen_buffer = self.screen_buffer[-self.buffer_max_size:]

                    # Display output
                    self._write_stdout(pty_output)

                    # Check for footer (permission prompt)
                    # Check both latest output AND full buffer (footer might be split across chunks)
                    if not self.in_countdown:
                        if self._detect_footer(pty_output) or self._detect_footer(self.screen_buffer[-500:]):
                            self._handle_countdown()

                # Read user input (when not in countdown)
                if not self.in_countdown:
                    user_input = self.input_reader.read_nowait()
                    if user_input:
                        if self.pty_process.isalive():
                            self.pty_process.write(user_input)

                # Small sleep to prevent CPU spin
                time.sleep(0.01)

        except KeyboardInterrupt:
            self.logger.log_event("INTERRUPTED")
        except Exception as e:
            self.logger.log_event("ERROR", error=str(e))
            raise
        finally:
            self._cleanup()

    def _cleanup(self):
        """Clean up resources."""
        self.running = False

        if self.pty_reader:
            self.pty_reader.stop()

        if self.input_reader:
            self.input_reader.stop()

        if self.pty_process:
            exit_code = None
            if self.pty_process.isalive():
                try:
                    self.pty_process.terminate()
                    time.sleep(0.3)
                except Exception:
                    pass

            try:
                exit_code = self.pty_process.exitstatus
            except Exception:
                pass

            if self.logger:
                self.logger.log_event("CHILD_EXITED", exit_code=exit_code)

        if self.logger:
            self.logger.log_event("END")
            self.logger.close()
            print(f"\n[UNLEASHED-DANGER] Logs saved to: {self.logger.log_dir}", file=sys.stderr)

        # Reset terminal state
        sys.stdout.write('\x1b[0m')  # Reset attributes
        sys.stdout.write('\x1bc')     # Full terminal reset (RIS)
        sys.stdout.flush()

        # Force exit - daemon threads may be blocking on I/O
        sys.exit(0)


# =============================================================================
# Signal Handlers
# =============================================================================

def setup_signal_handlers(unleashed_instance):
    """Set up signal handlers for graceful shutdown."""
    def handler(signum, frame):
        unleashed_instance.running = False

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unleashed Danger - Auto-approval wrapper for Claude Code (NO SAFETY CHECKS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  UNLEASHED_DELAY=N  Override countdown delay (default: 10 seconds)

Examples:
  python tools/unleashed-danger.py              # Danger mode
  python tools/unleashed-danger.py --dry-run    # Test detection without injection
  UNLEASHED_DELAY=5 python tools/unleashed-danger.py  # 5-second countdown

WARNING:
  DANGER MODE has NO safety checks:
  - No hard block for destructive commands
  - No dangerous path detection
  - No git destructive warnings
  - NEVER sends Escape to Claude (cannot interrupt)

  Use at your own risk.
        """
    )
    # Note: --version is handled early (before imports) for faster response
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test detection without actually injecting Enter"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=None,
        help="Countdown delay in seconds (overrides UNLEASHED_DELAY env var)"
    )
    parser.add_argument(
        "--cwd",
        type=str,
        default=None,
        help="Working directory for Claude (use when poetry changes cwd)"
    )

    args = parser.parse_args()

    # Determine delay
    delay = args.delay
    if delay is None:
        delay = int(os.environ.get("UNLEASHED_DELAY", DEFAULT_DELAY))

    # Create and run unleashed
    unleashed = Unleashed(delay=delay, dry_run=args.dry_run, cwd=args.cwd)
    setup_signal_handlers(unleashed)

    try:
        unleashed.run()
    except Exception as e:
        print(f"[UNLEASHED-DANGER] Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
