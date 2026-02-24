

```python
"""Audit block detection and validation.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

from tools.test_gate.models import AuditBlock, AuditEntry, SkippedTest

# Sentinel markers for audit blocks
_AUDIT_START = "<!-- SKIPPED TEST AUDIT -->"
_AUDIT_END = "<!-- END SKIPPED TEST AUDIT -->"

# Regex for parsing a markdown table row (pipe-delimited)
_TABLE_ROW = re.compile(
    r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|$"
)


def find_audit_block(
    output: str, audit_file: Path | None = None
) -> AuditBlock | None:
    """Locate and parse SKIPPED TEST AUDIT block from file or output.

    Search order:
    1. audit_file parameter (if provided and exists)
    2. .skip-audit.md in current directory
    3. stdout output

    Returns None if no audit block found anywhere.
    """
    # 1. Explicit audit file
    if audit_file is not None and audit_file.is_file():
        content = audit_file.read_text(encoding="utf-8")
        block = _extract_audit_text(content)
        if block is not None:
            return parse_audit_block(block, source="file")

    # 2. Default .skip-audit.md
    default_path = Path(".skip-audit.md")
    if default_path.is_file():
        content = default_path.read_text(encoding="utf-8")
        block = _extract_audit_text(content)
        if block is not None:
            return parse_audit_block(block, source="file")

    # 3. stdout
    block = _extract_audit_text(output)
    if block is not None:
        return parse_audit_block(block, source="stdout")

    return None


def _extract_audit_text(text: str) -> str | None:
    """Extract raw audit block text between sentinel markers.

    Returns None if markers not found or block is malformed.
    """
    start_idx = text.find(_AUDIT_START)
    if start_idx == -1:
        return None

    end_idx = text.find(_AUDIT_END, start_idx)
    if end_idx == -1:
        print(
            "WARNING: Found SKIPPED TEST AUDIT start marker but no end marker.",
            file=sys.stderr,
        )
        return None

    return text[start_idx : end_idx + len(_AUDIT_END)]


def parse_audit_block(raw_block: str, source: str = "unknown") -> AuditBlock:
    """Parse raw audit block text into structured AuditBlock.

    Expects markdown table format:
    | Test | Status | Justification | Owner | Expires |
    |------|--------|---------------|-------|---------|
    | pattern | VERIFIED | reason | owner | date |
    """
    entries: list[AuditEntry] = []

    lines = raw_block.strip().splitlines()
    header_seen = False
    separator_seen = False

    for line in lines:
        stripped = line.strip()

        # Skip sentinel markers
        if stripped.startswith("<!--"):
            continue

        # Skip empty lines
        if not stripped:
            continue

        # Detect header row (contains "Test" and "Status")
        if not header_seen and "Test" in stripped and "Status" in stripped:
            header_seen = True
            continue

        # Detect separator row (all dashes and pipes)
        if header_seen and not separator_seen and re.match(r"^[\|\s\-:]+$", stripped):
            separator_seen = True
            continue

        # Parse data rows
        if header_seen and separator_seen:
            match = _TABLE_ROW.match(stripped)
            if match:
                test_pattern = match.group(1).strip()
                status = match.group(2).strip().upper()
                justification = match.group(3).strip()
                owner = match.group(4).strip()
                expires_raw = match.group(5).strip()
                expires = expires_raw if expires_raw else None

                entries.append(
                    AuditEntry(
                        test_pattern=test_pattern,
                        status=status,
                        justification=justification,
                        owner=owner,
                        expires=expires,
                    )
                )

    return AuditBlock(
        entries=entries,
        raw_text=raw_block,
        source=source,
    )


def validate_audit(
    skipped: list[SkippedTest],
    audit: AuditBlock | None,
) -> tuple[list[SkippedTest], list[SkippedTest]]:
    """Validate skipped tests against audit block.

    Returns (unaudited_tests, unverified_critical_tests).
    - unaudited: skipped tests with no matching audit entry
    - unverified_critical: critical tests matched to UNVERIFIED entries
    """
    if audit is None:
        return (list(skipped), [])

    unaudited: list[SkippedTest] = []
    unverified_critical: list[SkippedTest] = []

    for test in skipped:
        matched_entry: AuditEntry | None = None
        for entry in audit["entries"]:
            if match_test_to_audit(test, entry):
                matched_entry = entry
                break

        if matched_entry is None:
            unaudited.append(test)
        elif test["is_critical"] and matched_entry["status"] == "UNVERIFIED":
            unverified_critical.append(test)

    return (unaudited, unverified_critical)


def match_test_to_audit(test: SkippedTest, entry: AuditEntry) -> bool:
    """Check if a test matches an audit entry pattern.

    Supports:
    - Exact match: "tests/test_foo.py::test_bar"
    - Glob patterns with fnmatch: "tests/test_foo.py::test_*"
    - Directory patterns: "tests/unit/*"
    """
    pattern = entry["test_pattern"]
    test_name = test["name"]

    if not pattern:
        return False

    # Exact match first (fast path)
    if test_name == pattern:
        return True

    # Glob match
    return fnmatch.fnmatch(test_name, pattern)
```
