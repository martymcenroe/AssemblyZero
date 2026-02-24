"""Data models for the test gate.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

from typing import TypedDict


class SkippedTest(TypedDict):
    """Represents a single skipped test from pytest output."""

    name: str  # Full test path (e.g., tests/test_foo.py::test_bar)
    reason: str  # Skip reason from @pytest.mark.skip or skipif
    line_number: int  # Line in test file (0 if unknown)
    file_path: str  # Path to test file
    is_critical: bool  # Inferred from markers or naming


class AuditEntry(TypedDict):
    """Represents a single entry in the audit block."""

    test_pattern: str  # Glob or exact match pattern
    status: str  # "VERIFIED", "UNVERIFIED", or "EXPECTED"
    justification: str  # Why this skip is acceptable
    owner: str  # Who verified (may be empty)
    expires: str | None  # ISO date string or None


class AuditBlock(TypedDict):
    """Parsed SKIPPED TEST AUDIT block."""

    entries: list[AuditEntry]
    raw_text: str  # Original block text for error messages
    source: str  # "stdout" or "file"


class GateResult(TypedDict):
    """Result of running the test gate."""

    passed: bool
    exit_code: int
    skipped_tests: list[SkippedTest]
    audit: AuditBlock | None
    unaudited: list[SkippedTest]  # Skips without matching audit entries
    unverified: list[SkippedTest]  # Critical skips with UNVERIFIED status
    errors: list[str]  # Validation error messages