#!/usr/bin/env python3
"""
Unleashed - PTY Wrapper for Claude Code Auto-Approval

A convenience wrapper that auto-approves Claude Code permission prompts
after a 10-second countdown, giving users a window to cancel.

Usage:
  python tools/unleashed.py [--dry-run] [--help]

Environment Variables:
  UNLEASHED_DELAY=N  Override default 10-second countdown (default: 10)

Security Note:
  This is a convenience tool, not a security tool. It auto-approves ALL
  permission prompts after the countdown. Use at your own risk.

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
VERSION = "1.4.0"  # Clean production version - no debug output

# Handle --version before heavy imports
if "--version" in sys.argv or "-v" in sys.argv:
    print(f"unleashed.py {VERSION}")
    sys.exit(0)

try:
    import winpty
except ImportError:
    print("[UNLEASHED] Error: pywinpty not installed. Run: poetry add pywinpty", file=sys.stderr)
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

# Default dangerous path patterns (can be overridden by excluded_paths.txt)
DEFAULT_DANGEROUS_PATTERNS = [
    r'/c/Users/\w+$',           # User home root (Unix format)
    r'C:\\Users\\\w+$',         # User home root (Windows format)
    r'OneDrive',                # OneDrive cloud sync
    r'AppData',                 # Application data
    r'\.cache',                 # Cache directories
    r'Dropbox',                 # Dropbox cloud sync
    r'Google Drive',            # Google Drive cloud sync
    r'iCloud Drive',            # iCloud cloud sync
]

# Hard block command patterns - NEVER auto-approve outside safe paths
DEFAULT_HARD_BLOCK_PATTERNS = [
    # Unix/Linux/Mac file deletion
    r'\brm\s',                  # rm (any variant)
    r'\brmdir\s',               # rmdir
    r'\bunlink\s',              # unlink
    r'\btruncate\s',            # truncate
    # Windows CMD
    r'\bdel\s',                 # del
    r'\berase\s',               # erase
    r'\brd\s',                  # rd
    r'\bdeltree\s',             # deltree
    # PowerShell
    r'\bRemove-Item\b',         # Remove-Item
    r'\bClear-Content\b',       # Clear-Content
]

# ALWAYS hard blocked (regardless of path) - catastrophic commands
DEFAULT_ALWAYS_BLOCKED_PATTERNS = [
    r'\bdd\s+if=',              # dd disk operations
    r'\bmkfs\b',                # filesystem creation
    r'\bshred\s',               # secure delete
    r'\bformat\s',              # format disk
]

# Git destructive patterns - require explicit confirmation in Projects, hard block elsewhere
DEFAULT_GIT_DESTRUCTIVE_PATTERNS = [
    r'\bgit\s+reset\s+--hard\b',
    r'\bgit\s+clean\s+-fd',
    r'\bgit\s+push\s+--force\b',
    r'\bgit\s+push\s+-f\s',
    r'\bgit\s+branch\s+-D\b',
]

# Default safe paths where destructive commands are allowed
DEFAULT_SAFE_PATHS = [
    r'/c/Users/\w+/Projects/',      # Unix format Projects
    r'C:\\Users\\\w+\\Projects\\',  # Windows format Projects
    r'/Users/\w+/Projects/',        # Mac format Projects
    r'/home/\w+/Projects/',         # Linux format Projects
]

# ANSI escape sequences for overlay
CURSOR_SAVE = '\x1b[s'
CURSOR_RESTORE = '\x1b[u'
CURSOR_HOME = '\x1b[H'
CLEAR_LINE = '\x1b[2K'
BOLD = '\x1b[1m'
YELLOW = '\x1b[33m'
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


# Tool type patterns for detecting permission prompt type
# Used to determine if hard block checks should apply (only for Bash)
# IMPORTANT: Patterns must be specific enough to not match file content
# Claude Code format: "● Tool(args)" - the bullet (●) precedes tool names
TOOL_TYPE_PATTERNS = {
    # More specific patterns that require the bullet or newline before tool name
    # This prevents matching "Bash" in documentation content
    'write': re.compile(r'[●\n]\s*Write\s*\(', re.IGNORECASE),
    'edit': re.compile(r'[●\n]\s*Edit\s*\(', re.IGNORECASE),
    'bash': re.compile(r'[●\n]\s*Bash[:\s(]', re.IGNORECASE),
    'read': re.compile(r'[●\n]\s*Read\s*\(', re.IGNORECASE),
    'glob': re.compile(r'[●\n]\s*Glob\s*\(', re.IGNORECASE),
    'grep': re.compile(r'[●\n]\s*Grep\s*\(', re.IGNORECASE),
}


def detect_tool_type(text: str, full_buffer: str = '') -> str:
    """
    Detect the tool type from permission prompt screen context.

    Returns: 'bash', 'write', 'edit', 'read', 'glob', 'grep', or 'unknown'

    This is used to determine which safety checks to apply:
    - Bash commands: Apply hard block and git destructive checks
    - Other tools: Skip command pattern checks (file content may contain examples)

    IMPORTANT: Tool prompts appear at the TOP of the permission dialog.
    For large content (Write with 500+ lines), the tool prompt may scroll off
    the end of the buffer. We check:
    1. First 1000 chars of full buffer (where tool prompt lives)
    2. Then the provided context text
    """
    # First, check the START of the full buffer where tool prompt appears
    if full_buffer:
        clean_start = strip_ansi(full_buffer)[:1000]
        for tool_name, pattern in TOOL_TYPE_PATTERNS.items():
            if pattern.search(clean_start):
                return tool_name

    # Fall back to checking the provided context
    clean_text = strip_ansi(text)
    for tool_name, pattern in TOOL_TYPE_PATTERNS.items():
        if pattern.search(clean_text):
            return tool_name

    return 'unknown'


def extract_tool_target_path(text: str, tool_type: str) -> str:
    """
    Extract the target file path from Write(path) or Edit(path) permission prompts.

    Returns the extracted path, or empty string if not found.
    """
    clean_text = strip_ansi(text)

    if tool_type == 'write':
        # Match Write(path) or Write( path )
        match = re.search(r'\bWrite\s*\(\s*([^)]+)\s*\)', clean_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    elif tool_type == 'edit':
        # Match Edit(path) or Edit( path )
        match = re.search(r'\bEdit\s*\(\s*([^)]+)\s*\)', clean_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return ''


def check_path_is_dangerous(path: str, patterns: list[re.Pattern]) -> tuple[bool, str]:
    """
    Check if a specific file path matches dangerous path patterns.

    This is used for Write/Edit tools where we only want to check the target path,
    not the file content (which may contain shell command examples).

    Returns (is_dangerous, matched_pattern) tuple.
    """
    if not path:
        return (False, '')

    for pattern in patterns:
        if pattern.search(path):
            return (True, path)

    return (False, '')


def get_timestamp() -> str:
    """Get ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def load_excluded_paths() -> list[re.Pattern]:
    """Load dangerous path patterns from config file or use defaults."""
    patterns = []
    config_path = Path.home() / '.agentos' / 'excluded_paths.txt'

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    # Convert to regex pattern (escape special chars, allow partial match)
                    escaped = re.escape(line)
                    patterns.append(re.compile(escaped, re.IGNORECASE))
        except Exception as e:
            print(f"[UNLEASHED] Warning: Could not load excluded_paths.txt: {e}", file=sys.stderr)

    # Always include default patterns
    for pattern in DEFAULT_DANGEROUS_PATTERNS:
        patterns.append(re.compile(pattern, re.IGNORECASE))

    return patterns


def check_dangerous_path(text: str, patterns: list[re.Pattern]) -> tuple[bool, str]:
    """
    Check if text contains commands targeting dangerous paths.

    Returns (is_dangerous, matched_pattern) tuple.
    """
    # Look for common command patterns that access paths
    # find, grep, rg, ls, cat, head, tail with path arguments
    path_commands = [
        r'find\s+["\']?([^"\']+)',              # find /path
        r'grep\s+.*?["\']?(/[^\s"\']+)',        # grep ... /path
        r'\brg\s+.*?["\']?(/[^\s"\']+)',        # rg ... /path
        r'ls\s+.*?["\']?([A-Za-z]:\\[^"\']+)',  # ls C:\path (Windows)
        r'ls\s+.*?["\']?(/[^\s"\']+)',          # ls /path
        r'Search:\s*([^\n]+)',                   # Claude's Search: pattern
    ]

    for cmd_pattern in path_commands:
        matches = re.findall(cmd_pattern, text, re.IGNORECASE)
        for match in matches:
            for danger_pattern in patterns:
                if danger_pattern.search(match):
                    return (True, match)

    return (False, '')


def load_hard_block_patterns() -> tuple[list[re.Pattern], list[re.Pattern], list[re.Pattern]]:
    """
    Load hard block command patterns.
    Returns (hard_block_patterns, always_blocked_patterns, git_destructive_patterns)
    """
    hard_block = []
    always_blocked = []
    git_destructive = []

    config_path = Path.home() / '.agentos' / 'hard_block_commands.txt'

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    hard_block.append(re.compile(line, re.IGNORECASE))
        except Exception as e:
            print(f"[UNLEASHED] Warning: Could not load hard_block_commands.txt: {e}", file=sys.stderr)

    # Always include defaults
    for pattern in DEFAULT_HARD_BLOCK_PATTERNS:
        hard_block.append(re.compile(pattern, re.IGNORECASE))

    for pattern in DEFAULT_ALWAYS_BLOCKED_PATTERNS:
        always_blocked.append(re.compile(pattern, re.IGNORECASE))

    for pattern in DEFAULT_GIT_DESTRUCTIVE_PATTERNS:
        git_destructive.append(re.compile(pattern, re.IGNORECASE))

    return (hard_block, always_blocked, git_destructive)


def load_safe_paths() -> list[re.Pattern]:
    """Load safe paths where destructive commands are allowed."""
    patterns = []
    config_path = Path.home() / '.agentos' / 'safe_paths.txt'

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    escaped = re.escape(line)
                    patterns.append(re.compile(escaped, re.IGNORECASE))
        except Exception as e:
            print(f"[UNLEASHED] Warning: Could not load safe_paths.txt: {e}", file=sys.stderr)

    # Always include defaults
    for pattern in DEFAULT_SAFE_PATHS:
        patterns.append(re.compile(pattern, re.IGNORECASE))

    return patterns


def extract_command_path(text: str) -> str:
    """Extract the target path from a command in screen context."""
    # Look for path-like arguments in the command
    path_patterns = [
        r'(?:rm|del|erase|rd|rmdir|Remove-Item|unlink)\s+.*?(["\']?)(/[^\s"\']+|[A-Za-z]:\\[^\s"\']+)\1',
        r'(?:rm|del|erase|rd|rmdir|Remove-Item|unlink)\s+(-\w+\s+)*(["\']?)(/[^\s"\']+|[A-Za-z]:\\[^\s"\']+)\2',
    ]

    for pattern in path_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Return the path group (last captured group)
            groups = [g for g in match.groups() if g and (g.startswith('/') or ':' in g)]
            if groups:
                return groups[-1]

    return ''


def check_hard_block(text: str, hard_block_patterns: list, always_blocked: list,
                     safe_paths: list) -> tuple[bool, str, str]:
    """
    Check if command should be hard blocked.
    Returns (should_block, matched_command, reason)
    """
    clean_text = strip_ansi(text)

    # First check ALWAYS blocked commands (catastrophic, regardless of path)
    for pattern in always_blocked:
        match = pattern.search(clean_text)
        if match:
            return (True, match.group(0), "ALWAYS_BLOCKED: Catastrophic command")

    # Then check path-dependent hard block commands
    for pattern in hard_block_patterns:
        match = pattern.search(clean_text)
        if match:
            matched_cmd = match.group(0)
            # Extract the target path from the command
            target_path = extract_command_path(clean_text)

            if not target_path:
                # No path found - could be operating on current directory
                # Be conservative and block
                return (True, matched_cmd, "NO_PATH: Cannot determine target path")

            # Check if target path is in safe paths
            is_safe = False
            for safe_pattern in safe_paths:
                if safe_pattern.search(target_path):
                    is_safe = True
                    break

            if not is_safe:
                return (True, matched_cmd, f"UNSAFE_PATH: {target_path}")

    return (False, '', '')


def check_git_destructive(text: str, git_patterns: list, safe_paths: list) -> tuple[bool, str]:
    """
    Check if command is a git destructive command.
    Returns (is_git_destructive, matched_command)

    Git destructive commands require explicit confirmation in Projects,
    and are hard blocked outside Projects.
    """
    clean_text = strip_ansi(text)

    for pattern in git_patterns:
        match = pattern.search(clean_text)
        if match:
            return (True, match.group(0))

    return (False, '')


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
# Input Reader (for user keyboard input)
# =============================================================================

def is_mintty() -> bool:
    """Detect if running in mintty (Git Bash) terminal.

    Mintty sends ANSI escape sequences to stdin instead of using Windows
    console input buffer. msvcrt cannot read these sequences, so we need
    to use a different input method.
    """
    # MSYSTEM is set in Git Bash/MSYS2 environments
    return bool(os.environ.get('MSYSTEM'))


class InputReader:
    """Non-blocking input reader using msvcrt (for native Windows console)."""

    def __init__(self):
        self.queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._reader_thread, daemon=True)
        self.thread.start()

    def _reader_thread(self):
        """Background thread for reading stdin via msvcrt."""
        while self.running:
            try:
                if HAS_MSVCRT:
                    # Windows: use msvcrt for non-blocking input
                    if msvcrt.kbhit():
                        char = msvcrt.getwch()
                        # Handle Windows special keys (arrows, function keys, etc.)
                        # They come as two-char sequences: \xe0 or \x00 followed by scan code
                        if char in ('\xe0', '\x00'):
                            # Read scan code immediately - it's already buffered
                            scan = msvcrt.getwch()
                            # Convert to ANSI escape sequences
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
                                '\x0f': '\x1b[Z',  # Shift+Tab (scan code 15)
                            }
                            if scan in key_map:
                                self.queue.put(key_map[scan])
                        elif char == '\x1b':
                            # Escape character - might be start of escape sequence from mintty
                            # Try to read more characters for the sequence
                            seq = char
                            while msvcrt.kbhit():
                                seq += msvcrt.getwch()
                            # Filter out terminal responses - they're NOT user input
                            # DA1 response: \x1b[?...c  (device attributes)
                            # CPR response: \x1b[...R   (cursor position report)
                            # These should NOT be passed to Claude
                            if seq.startswith('\x1b[?') and seq.endswith('c'):
                                # Terminal DA1 response - discard
                                pass
                            elif len(seq) > 3 and seq[-1] == 'R' and seq[2].isdigit():
                                # Cursor position report - discard
                                pass
                            else:
                                # User input escape sequence - pass through
                                self.queue.put(seq)
                        else:
                            self.queue.put(char)
                    else:
                        time.sleep(0.01)
                else:
                    # Unix: use select for non-blocking input
                    if select.select([sys.stdin], [], [], 0.01)[0]:
                        char = sys.stdin.read(1)
                        if char:
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


class StdinReader:
    """Non-blocking input reader using stdin (for mintty/Git Bash).

    This reader is used when running in mintty because msvcrt cannot read
    the ANSI escape sequences that mintty sends for special keys like Shift+Tab.

    Key difference from InputReader:
    - Reads directly from sys.stdin.buffer (binary mode)
    - Can receive \x1b[Z (Shift+Tab escape sequence) from mintty
    - Does NOT mix with msvcrt (which was the cause of v1.3.8 failure)
    """

    def __init__(self):
        self.queue = queue.Queue()
        self.running = True
        # Get the stdin file descriptor for select (works in mintty)
        self.stdin_fd = sys.stdin.fileno()
        self.thread = threading.Thread(target=self._reader_thread, daemon=True)
        self.thread.start()

    def _reader_thread(self):
        """Background thread for reading stdin directly.

        In mintty, stdin is a proper file descriptor that works with select().
        This is different from native Windows console where select() on stdin fails.
        """
        stdin = sys.stdin.buffer

        while self.running:
            try:
                # In mintty, select works on stdin (it's a pty, not console)
                # Use a short timeout so we can check self.running
                readable, _, _ = select.select([self.stdin_fd], [], [], 0.1)
                if not readable:
                    continue

                # Read available byte
                byte = stdin.read(1)
                if not byte:
                    continue

                char = byte.decode('utf-8', errors='replace')

                # Handle escape sequences
                if char == '\x1b':
                    # Start of escape sequence - read more bytes
                    # Mintty sends escape sequences atomically, so more bytes
                    # should be immediately available
                    seq_bytes = byte
                    max_seq_len = 16  # Reasonable max for any escape sequence

                    # Read more bytes with short timeout
                    for _ in range(max_seq_len):
                        readable, _, _ = select.select([self.stdin_fd], [], [], 0.02)
                        if not readable:
                            break
                        next_byte = stdin.read(1)
                        if not next_byte:
                            break
                        seq_bytes += next_byte
                        # Check if sequence is complete
                        seq = seq_bytes.decode('utf-8', errors='replace')
                        if len(seq) >= 3:
                            last = seq[-1]
                            # Most escape sequences end with a letter or ~
                            if last.isalpha() or last == '~':
                                break

                    seq = seq_bytes.decode('utf-8', errors='replace')

                    # Filter terminal responses (not user input)
                    if seq.startswith('\x1b[?') and seq.endswith('c'):
                        # DA1 response - discard
                        continue
                    if len(seq) > 3 and seq[-1] == 'R' and seq[2].isdigit():
                        # Cursor position report - discard
                        continue

                    # Queue the escape sequence (e.g., \x1b[Z for Shift+Tab)
                    self.queue.put(seq)
                else:
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
        self.raw_log_path = log_dir / f"unleashed_{session_id}.log"
        self.raw_log = open(self.raw_log_path, 'wb')

        # Structured event log
        self.event_log_path = log_dir / f"unleashed_events_{session_id}.jsonl"
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
        message = f"{CURSOR_SAVE}{CURSOR_HOME}{BOLD}{YELLOW}[UNLEASHED] Auto-approving in {seconds_remaining}s... (Press any key to cancel){RESET}{CLEAR_LINE}{CURSOR_RESTORE}"
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
        message = f"{CURSOR_SAVE}{CURSOR_HOME}{BOLD}{YELLOW}[UNLEASHED] Auto-approved!{RESET}{CLEAR_LINE}{CURSOR_RESTORE}"
        self.writer(message)

    def show_cancelled(self):
        """Show cancellation message briefly."""
        message = f"{CURSOR_SAVE}{CURSOR_HOME}{BOLD}{YELLOW}[UNLEASHED] Cancelled by user{RESET}{CLEAR_LINE}{CURSOR_RESTORE}"
        self.writer(message)

    def show_dangerous_warning(self, matched_path: str):
        """Show warning for dangerous path - requires explicit confirmation."""
        RED = '\x1b[31m'
        message = f"{CURSOR_SAVE}{CURSOR_HOME}{BOLD}{RED}[UNLEASHED] DANGEROUS PATH: {matched_path[:50]}{RESET}{CLEAR_LINE}{CURSOR_RESTORE}"
        self.writer(message)

    def show_confirmation_prompt(self):
        """Show prompt requiring 'yes' to proceed."""
        RED = '\x1b[31m'
        message = f"{CURSOR_SAVE}{CURSOR_HOME}{BOLD}{RED}[UNLEASHED] Type 'yes' + Enter to proceed, any other key to cancel: {RESET}"
        self.writer(message)

    def show_hard_block(self, command: str, reason: str):
        """Show hard block message - command is NEVER approved."""
        RED = '\x1b[31m'
        BG_RED = '\x1b[41m'
        message = f"{CURSOR_SAVE}{CURSOR_HOME}{BOLD}{BG_RED}[UNLEASHED] HARD BLOCKED: {command[:40]}{RESET}{CLEAR_LINE}{CURSOR_RESTORE}"
        self.writer(message)

    def show_hard_block_reason(self, reason: str):
        """Show the reason for hard block."""
        RED = '\x1b[31m'
        # Show on line 2
        message = f"{CURSOR_SAVE}\x1b[2H{BOLD}{RED}  Reason: {reason[:60]}{RESET}{CLEAR_LINE}{CURSOR_RESTORE}"
        self.writer(message)

    def show_git_warning(self, command: str):
        """Show warning for git destructive command - requires explicit confirmation."""
        MAGENTA = '\x1b[35m'
        message = f"{CURSOR_SAVE}{CURSOR_HOME}{BOLD}{MAGENTA}[UNLEASHED] GIT DESTRUCTIVE: {command[:40]}{RESET}{CLEAR_LINE}{CURSOR_RESTORE}"
        self.writer(message)


# =============================================================================
# Main Unleashed Wrapper
# =============================================================================

class Unleashed:
    """Main PTY wrapper for auto-approval."""

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
        self.dangerous_patterns = load_excluded_paths()  # Load at startup
        # Load hard block patterns
        self.hard_block_patterns, self.always_blocked, self.git_destructive = load_hard_block_patterns()
        self.safe_paths = load_safe_paths()

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

        Safety check order:
        1. DETECT TOOL TYPE - determine if this is Bash, Write, Edit, etc.
        2. HARD BLOCK - destructive commands outside Projects (Bash only)
        3. GIT DESTRUCTIVE - require explicit 'yes' confirmation (Bash only)
        4. DANGEROUS PATH - require explicit 'yes' confirmation (all tools)
        5. NORMAL - auto-approve after countdown
        """
        self.in_countdown = True
        screen_context = self._capture_screen_context()

        self.logger.log_event("FOOTER_DETECTED")

        # FIRST: Detect tool type from permission prompt
        # This determines which safety checks to apply
        # Pass full buffer so we can check the START where tool prompt lives
        tool_type = detect_tool_type(screen_context, self.screen_buffer)
        self.logger.log_event("PERMISSION_PROMPT",
            tool_type=tool_type,
            context_preview=screen_context[:300]
        )

        # Hard block and git destructive checks apply to Bash AND unknown tools
        # SECURITY: Fail closed - if we can't identify the tool, assume dangerous
        # Only SKIP checks for positively identified safe tools (write, edit, read, etc.)
        safe_tool_types = ('write', 'edit', 'read', 'glob', 'grep')
        if tool_type not in safe_tool_types:
            # Check hard block (destructive commands outside Projects)
            is_blocked, blocked_cmd, reason = check_hard_block(
                screen_context,
                self.hard_block_patterns,
                self.always_blocked,
                self.safe_paths
            )
            if is_blocked:
                return self._handle_hard_block(blocked_cmd, reason)

            # Check git destructive (require explicit confirmation)
            is_git, git_cmd = check_git_destructive(screen_context, self.git_destructive, self.safe_paths)
            if is_git:
                return self._handle_git_confirmation(screen_context, git_cmd)

        # Dangerous PATH check - different logic for different tools
        # For Write/Edit: Check ONLY the target file path (content may have examples)
        # For Bash/Unknown: Check command patterns in full screen context
        # SECURITY: Fail closed - unknown tools get full checks
        if tool_type in ('write', 'edit'):
            # Extract target path and check only that
            target_path = extract_tool_target_path(screen_context, tool_type)
            is_dangerous, matched_path = check_path_is_dangerous(target_path, self.dangerous_patterns)
            self.logger.log_event("PATH_CHECK",
                tool_type=tool_type,
                target_path=target_path,
                is_dangerous=is_dangerous
            )
        else:
            # For Bash and unknown tool types, check full screen for command patterns
            # SECURITY: Unknown = assume dangerous (fail closed)
            is_dangerous, matched_path = check_dangerous_path(screen_context, self.dangerous_patterns)

        if is_dangerous:
            return self._handle_dangerous_confirmation(screen_context, matched_path)

        self.logger.log_event("COUNTDOWN_START", delay=self.delay)

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
                            if self.pty_process and self.pty_process.isalive():
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
                    self.pty_process.write('\x1b[Z')  # Shift+Tab
                    time.sleep(0.05)  # Small delay for UI to update
                self.pty_process.write('\r')  # Enter to confirm
            self.logger.log_event("AUTO_APPROVED", option=2 if has_three else 1, context=screen_context[:500])
        else:
            self.logger.log_event("AUTO_APPROVED_DRY_RUN", option=2 if has_three else 1, context=screen_context[:500])

        return True

    def _handle_dangerous_confirmation(self, screen_context: str, matched_path: str) -> bool:
        """
        Handle dangerous path - requires explicit 'yes' confirmation.
        NO auto-approval. User must type 'yes' + Enter.
        """
        self.logger.log_event("DANGEROUS_PATH_DETECTED", path=matched_path)

        # Show warning
        self.overlay.show_dangerous_warning(matched_path)
        time.sleep(1.0)

        # Show confirmation prompt
        self.overlay.show_confirmation_prompt()

        # Collect user input until Enter is pressed
        user_response = ""
        timeout_seconds = 60  # Give user 60 seconds to respond
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            user_input = self.input_reader.read_nowait()
            if user_input:
                for char in user_input:
                    if char == '\r' or char == '\n':
                        # User pressed Enter - check response
                        self.overlay.hide()
                        self.in_countdown = False

                        if user_response.strip().lower() == 'yes':
                            # User explicitly confirmed
                            self.logger.log_event("DANGEROUS_PATH_CONFIRMED", path=matched_path, response=user_response)

                            # Send Enter to approve (don't use "remember" for dangerous paths)
                            if not self.dry_run and self.pty_process and self.pty_process.isalive():
                                self.pty_process.write('\r')

                            return True
                        else:
                            # User did not confirm - cancel
                            self.overlay.show_cancelled()
                            time.sleep(0.5)
                            self.overlay.hide()
                            self.logger.log_event("DANGEROUS_PATH_REJECTED", path=matched_path, response=user_response)

                            # Send Escape to cancel the prompt
                            if self.pty_process and self.pty_process.isalive():
                                self.pty_process.write('\x1b')  # Escape

                            return False
                    elif char == '\x1b':
                        # User pressed Escape - cancel immediately
                        self.overlay.show_cancelled()
                        time.sleep(0.5)
                        self.overlay.hide()
                        self.in_countdown = False
                        self.logger.log_event("DANGEROUS_PATH_ESCAPED", path=matched_path)

                        # Pass Escape through
                        if self.pty_process and self.pty_process.isalive():
                            self.pty_process.write('\x1b')

                        return False
                    elif is_printable_key(char):
                        user_response += char

            time.sleep(0.05)

        # Timeout - cancel
        self.overlay.hide()
        self.in_countdown = False
        self.logger.log_event("DANGEROUS_PATH_TIMEOUT", path=matched_path)

        # Send Escape to cancel
        if self.pty_process and self.pty_process.isalive():
            self.pty_process.write('\x1b')

        return False

    def _handle_hard_block(self, command: str, reason: str) -> bool:
        """
        Hard block - NEVER approve.
        Shows error message and cancels after brief display.
        """
        self.logger.log_event("HARD_BLOCK_TRIGGERED", command=command, reason=reason)

        # Show hard block message (red background, prominent)
        self.overlay.show_hard_block(command, reason)
        time.sleep(1.0)
        self.overlay.show_hard_block_reason(reason)
        time.sleep(2.0)

        # Hide and send Escape to cancel
        self.overlay.hide()
        self.in_countdown = False

        if self.pty_process and self.pty_process.isalive():
            self.pty_process.write('\x1b')  # Escape

        return False  # Always returns False (never approved)

    def _handle_git_confirmation(self, screen_context: str, git_cmd: str) -> bool:
        """
        Handle git destructive command - requires explicit 'yes' confirmation.
        Similar to dangerous path confirmation but with different messaging.
        """
        self.logger.log_event("GIT_DESTRUCTIVE_DETECTED", command=git_cmd)

        # Show warning
        self.overlay.show_git_warning(git_cmd)
        time.sleep(1.0)

        # Show confirmation prompt
        self.overlay.show_confirmation_prompt()

        # Collect user input until Enter is pressed
        user_response = ""
        timeout_seconds = 60  # Give user 60 seconds to respond
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            user_input = self.input_reader.read_nowait()
            if user_input:
                for char in user_input:
                    if char == '\r' or char == '\n':
                        # User pressed Enter - check response
                        self.overlay.hide()
                        self.in_countdown = False

                        if user_response.strip().lower() == 'yes':
                            # User explicitly confirmed
                            self.logger.log_event("GIT_DESTRUCTIVE_CONFIRMED", command=git_cmd, response=user_response)

                            # Send Enter to approve
                            if not self.dry_run and self.pty_process and self.pty_process.isalive():
                                self.pty_process.write('\r')

                            return True
                        else:
                            # User did not confirm - cancel
                            self.overlay.show_cancelled()
                            time.sleep(0.5)
                            self.overlay.hide()
                            self.logger.log_event("GIT_DESTRUCTIVE_REJECTED", command=git_cmd, response=user_response)

                            # Send Escape to cancel the prompt
                            if self.pty_process and self.pty_process.isalive():
                                self.pty_process.write('\x1b')  # Escape

                            return False
                    elif char == '\x1b':
                        # User pressed Escape - cancel immediately
                        self.overlay.show_cancelled()
                        time.sleep(0.5)
                        self.overlay.hide()
                        self.in_countdown = False
                        self.logger.log_event("GIT_DESTRUCTIVE_ESCAPED", command=git_cmd)

                        # Pass Escape through
                        if self.pty_process and self.pty_process.isalive():
                            self.pty_process.write('\x1b')

                        return False
                    elif is_printable_key(char):
                        user_response += char

            time.sleep(0.05)

        # Timeout - cancel
        self.overlay.hide()
        self.in_countdown = False
        self.logger.log_event("GIT_DESTRUCTIVE_TIMEOUT", command=git_cmd)

        # Send Escape to cancel
        if self.pty_process and self.pty_process.isalive():
            self.pty_process.write('\x1b')

        return False

    def _show_banner(self):
        """Display startup banner to stderr (avoids Claude's stdout cursor positioning)."""
        term_type = "mintty" if is_mintty() else "console"
        banner = f"{BOLD}{YELLOW}[UNLEASHED v{VERSION}] Auto-approval | {self.delay}s | {term_type} | Dir: {self.cwd}{RESET}\n"
        sys.stderr.write(banner)
        sys.stderr.flush()

    def run(self):
        """Main run loop."""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path(__file__).parent.parent / "logs"

        self.logger = EventLogger(log_dir, session_id)
        self.logger.log_event("START", version=VERSION, delay=self.delay, dry_run=self.dry_run)

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

            # Choose input reader based on terminal environment
            # Key fix for Issue #20: mintty sends Shift+Tab as \x1b[Z to stdin,
            # which msvcrt cannot see. Use StdinReader for mintty.
            if is_mintty():
                self.input_reader = StdinReader()
                self.logger.log_event("INPUT_READER", reader="StdinReader", reason="mintty detected")
            else:
                self.input_reader = InputReader()
                self.logger.log_event("INPUT_READER", reader="InputReader", reason="native Windows console")

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
                    if not self.in_countdown and self._detect_footer(pty_output):
                        self._handle_countdown()

                # Read user input (when not in countdown)
                if not self.in_countdown:
                    user_input = self.input_reader.read_nowait()
                    if user_input:
                        # Pass through to PTY
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
            print(f"\n[UNLEASHED] Logs saved to: {self.logger.log_dir}", file=sys.stderr)

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
        description="Unleashed - Auto-approval wrapper for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  UNLEASHED_DELAY=N  Override countdown delay (default: 10 seconds)

Examples:
  python tools/unleashed.py              # Normal mode
  python tools/unleashed.py --dry-run    # Test detection without injection
  UNLEASHED_DELAY=5 python tools/unleashed.py  # 5-second countdown

Security Note:
  This tool auto-approves ALL permission prompts. Use at your own risk.
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
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit"
    )

    args = parser.parse_args()

    # Handle --version flag
    if args.version:
        print(f"unleashed.py {VERSION}")
        sys.exit(0)

    # Set environment variable for /unleashed-version skill
    os.environ['UNLEASHED_VERSION'] = VERSION

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
        print(f"[UNLEASHED] Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
