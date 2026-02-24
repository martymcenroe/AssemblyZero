

```python
"""Pytest output parsing utilities.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from tools.test_gate.models import SkippedTest

# Keywords that indicate a critical test when found in the test name (case-insensitive)
CRITICAL_KEYWORDS: list[str] = ["security", "auth", "payment", "critical"]

# Regex patterns for pytest verbose skip output formats
# Format 1: "tests/test_foo.py::test_bar SKIPPED (reason)"
_PATTERN_INLINE = re.compile(
    r"^([\w/\\.\-]+\.py::[\w\[\]\-]+)\s+SKIPPED\s+\((.+?)\)\s*$",
    re.MULTILINE,
)
# Format 2: "SKIPPED [N] path/file.py:line: reason"
_PATTERN_BLOCK = re.compile(
    r"^SKIPPED\s+\[\d+\]\s+([\w/\\.\-]+\.py):(\d+):\s+(.+?)\s*$",
    re.MULTILINE,
)


def run_pytest(args: list[str], timeout: int = 1800) -> tuple[int, str, str]:
    """Execute pytest with given args, return (exit_code, stdout, stderr).

    Forwards SIGINT to the subprocess for clean Ctrl+C handling.
    Uses subprocess with list args (no shell=True) to prevent injection.
    """
    cmd = [sys.executable, "-m", "pytest"] + args

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Forward SIGINT to subprocess on Unix systems
        original_handler = None
        if hasattr(signal, "SIGINT"):
            def _forward_sigint(signum: int, frame: object) -> None:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGINT)

            original_handler = signal.signal(signal.SIGINT, _forward_sigint)

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return (1, "", f"pytest timed out after {timeout} seconds")
        finally:
            if original_handler is not None:
                signal.signal(signal.SIGINT, original_handler)

        return (proc.returncode, stdout, stderr)

    except FileNotFoundError as exc:
        return (1, "", f"pytest not found: {exc}")


def ensure_verbose_flag(args: list[str]) -> list[str]:
    """Ensure -v flag is present in args for skip detection.

    Returns a new list (does not mutate input). If any verbose flag
    (-v, -vv, -vvv, --verbose) is already present, returns a copy unchanged.
    """
    new_args = list(args)

    for arg in new_args:
        # Check for -v, -vv, -vvv, etc.
        if arg == "--verbose":
            return new_args
        if re.match(r"^-v+$", arg):
            return new_args

    new_args.append("-v")
    return new_args


def parse_skipped_tests(output: str) -> list[SkippedTest]:
    """Parse pytest verbose output for skipped test information.

    Handles two common pytest verbose output formats:
    1. "tests/test_foo.py::test_bar SKIPPED (reason)"
    2. "SKIPPED [N] tests/test_foo.py:line: reason"
    """
    results: list[SkippedTest] = []

    # Pattern 1: inline SKIPPED
    for match in _PATTERN_INLINE.finditer(output):
        test_name = match.group(1)
        reason = match.group(2)
        # Extract file path from test name (before ::)
        file_path = test_name.split("::")[0] if "::" in test_name else test_name
        results.append(
            SkippedTest(
                name=test_name,
                reason=reason,
                line_number=0,
                file_path=file_path,
                is_critical=False,
            )
        )

    # Pattern 2: block SKIPPED
    for match in _PATTERN_BLOCK.finditer(output):
        file_path = match.group(1)
        line_number = int(match.group(2))
        reason = match.group(3)
        test_name = f"{file_path}:{line_number}"
        results.append(
            SkippedTest(
                name=test_name,
                reason=reason,
                line_number=line_number,
                file_path=file_path,
                is_critical=False,
            )
        )

    return results


def detect_critical_tests(tests: list[SkippedTest]) -> list[SkippedTest]:
    """Return new list with is_critical set based on naming conventions.

    A test is marked critical if any CRITICAL_KEYWORDS appear in the
    test name (case-insensitive). Does not mutate input list.
    Tests already marked critical remain critical.
    """
    results: list[SkippedTest] = []
    for test in tests:
        name_lower = test["name"].lower()
        is_critical = test["is_critical"] or any(
            kw in name_lower for kw in CRITICAL_KEYWORDS
        )
        results.append(
            SkippedTest(
                name=test["name"],
                reason=test["reason"],
                line_number=test["line_number"],
                file_path=test["file_path"],
                is_critical=is_critical,
            )
        )
    return results
```
