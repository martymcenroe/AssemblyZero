#!/usr/bin/env python3
"""
Sentinel.py - AI-Gated Permission Controller for Claude CLI

A safety wrapper that uses Haiku to approve/deny commands based on
forbidden path context from settings.local.json.

Usage:
    python sentinel.py

Environment:
    ANTHROPIC_API_KEY - Required for Haiku API calls
"""

import json
import os
import re
import sys
import threading
import queue
import signal
from pathlib import Path

import winpty
import msvcrt
import litellm
from colorama import Fore, Style, init as colorama_init
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

VERSION = "1.0.0"
BUFFER_SIZE = 2000
PROMPT_REGEX = re.compile(r"Allow this command to run\?")
DEFAULT_FORBIDDEN = [
    "OneDrive",
    "AppData",
    "~",
    "/c/Users/*/",
    "C:\\Users\\*\\",
]

SAFETY_PROMPT = """You are a Safety Sentinel.

**Critical Rules:**
1. NEVER approve commands touching Forbidden Paths: {forbidden}
2. NEVER approve recursive scans (ls -R, grep -r, find) on home directories.
3. Approve safe commands: read files, list specific dirs, run tests, git status.

**COMMAND:** {command}

Reply strictly: SAFE or UNSAFE"""


def load_forbidden_paths() -> list[str]:
    """Load forbidden paths from .claude/settings.local.json and merge with defaults."""
    paths = list(DEFAULT_FORBIDDEN)

    # Try to find settings.local.json
    settings_locations = [
        Path.home() / ".claude" / "settings.local.json",
        Path.cwd() / ".claude" / "settings.local.json",
    ]

    for settings_path in settings_locations:
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)

                # Extract permissions.deny
                if "permissions" in settings and "deny" in settings["permissions"]:
                    deny_list = settings["permissions"]["deny"]
                    if isinstance(deny_list, list):
                        paths.extend(deny_list)

                # Extract ignorePatterns
                if "ignorePatterns" in settings:
                    ignore_list = settings["ignorePatterns"]
                    if isinstance(ignore_list, list):
                        paths.extend(ignore_list)

            except (json.JSONDecodeError, IOError):
                pass  # Silently ignore malformed or unreadable files

    # Deduplicate while preserving order
    seen = set()
    result = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            result.append(path)

    return result


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


class PtyReader:
    """Threaded reader for PTY output."""

    def __init__(self, pty):
        self.pty = pty
        self.queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._reader_thread, daemon=True)
        self.thread.start()

    def _reader_thread(self):
        """Read from PTY and put chunks into queue."""
        while self.running:
            try:
                if self.pty.isalive():
                    data = self.pty.read(1024)
                    if data:
                        self.queue.put(data)
                else:
                    break
            except Exception:
                break

    def read_nowait(self) -> str:
        """Read available data from queue without blocking."""
        result = ""
        while True:
            try:
                result += self.queue.get_nowait()
            except queue.Empty:
                break
        return result

    def stop(self):
        """Stop the reader thread."""
        self.running = False


class InputReader:
    """Threaded reader for keyboard input."""

    def __init__(self):
        self.queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._reader_thread, daemon=True)
        self.thread.start()

    def _reader_thread(self):
        """Read keyboard input and put into queue."""
        while self.running:
            try:
                if msvcrt.kbhit():
                    char = msvcrt.getwch()
                    self.queue.put(char)
            except Exception:
                break

    def read_nowait(self) -> str:
        """Read available input from queue without blocking."""
        result = ""
        while True:
            try:
                result += self.queue.get_nowait()
            except queue.Empty:
                break
        return result

    def stop(self):
        """Stop the reader thread."""
        self.running = False


class Sentinel:
    """Main Sentinel controller class."""

    def __init__(self):
        self.buffer = ""
        self.forbidden = load_forbidden_paths()
        self.evaluating = False
        self.pty = None

    def run(self):
        """Main run loop - spawn Claude and intercept output."""
        try:
            self.pty = winpty.PtyProcess.spawn(['claude'])
        except Exception as e:
            sys.stderr.write(f"{Fore.RED}[SENTINEL] Failed to spawn Claude: {e}{Style.RESET_ALL}\n")
            return

        pty_reader = PtyReader(self.pty)
        input_reader = InputReader()

        try:
            while self.pty.isalive():
                # Read PTY output
                chunk = pty_reader.read_nowait()
                if chunk:
                    self._process_output(chunk)

                # Read user input and forward to PTY
                user_input = input_reader.read_nowait()
                if user_input:
                    for char in user_input:
                        if char == '\r' or char == '\n':
                            self.pty.write('\r')
                        else:
                            self.pty.write(char)

                # Small sleep to prevent CPU spinning
                import time
                time.sleep(0.01)

        finally:
            pty_reader.stop()
            input_reader.stop()

    def _process_output(self, chunk: str):
        """Process a chunk of output from Claude."""
        # Update rolling buffer
        self.buffer = (self.buffer + chunk)[-BUFFER_SIZE:]

        # Write to stdout
        sys.stdout.write(chunk)
        sys.stdout.flush()

        # Check for permission prompt
        if PROMPT_REGEX.search(chunk) and not self.evaluating:
            self.evaluating = True
            self._evaluate()

    def _evaluate(self):
        """Evaluate the command and auto-approve or alert."""
        try:
            # Extract command from buffer (look for command in last few lines)
            clean_buffer = strip_ansi(self.buffer)
            lines = clean_buffer.strip().split('\n')

            # Find command - typically in the lines before the prompt
            command = ""
            for line in lines[-15:]:  # Look at last 15 lines
                line = line.strip()
                if line and not PROMPT_REGEX.search(line):
                    # Skip menu lines like "(y)es, (n)o..."
                    if not line.startswith('(') and 'Allow' not in line:
                        command = line

            if not command:
                command = "Unknown command"

            verdict = self._ask_haiku(command)

            if verdict:
                sys.stderr.write(f"\n{Fore.GREEN}[SENTINEL] SAFE - auto-approved{Style.RESET_ALL}\n")
                sys.stderr.flush()
                self.pty.write('y\r')
            else:
                # Bell character for audio alert
                sys.stderr.write(f"\a\n{Fore.RED}[SENTINEL] UNSAFE - manual approval required{Style.RESET_ALL}\n")
                sys.stderr.flush()
                # Don't auto-respond - let user decide

        finally:
            self.evaluating = False

    def _ask_haiku(self, command: str) -> bool:
        """Ask Haiku to evaluate command safety."""
        prompt = SAFETY_PROMPT.format(
            forbidden=self.forbidden,
            command=command
        )

        try:
            response = litellm.completion(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
            )

            content = response.choices[0].message.content.upper()
            # Check UNSAFE first since it contains "SAFE" as substring
            if "UNSAFE" in content:
                return False
            return "SAFE" in content

        except Exception:
            # Fail closed - if we can't verify, don't auto-approve
            return False


def main():
    """Entry point."""
    # Ignore SIGINT - let it pass through to Claude
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    colorama_init()

    print(f"{Fore.CYAN}[SENTINEL v{VERSION}] AI-Gated Permission Controller{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[SENTINEL] Forbidden paths: {len(load_forbidden_paths())} patterns loaded{Style.RESET_ALL}")
    print()

    sentinel = Sentinel()
    sentinel.run()


if __name__ == "__main__":
    main()
