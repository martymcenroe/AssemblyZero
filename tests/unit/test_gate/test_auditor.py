"""Unit tests for tools/test_gate/auditor.py.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.test_gate.auditor import (
    find_audit_block,
    match_test_to_audit,
    parse_audit_block,
    validate_audit,
)
from tools.test_gate.models import AuditBlock, AuditEntry, SkippedTest


# --- Sample data ---

SAMPLE_AUDIT_BLOCK = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_auth.py::test_oauth | VERIFIED | External provider not in CI | marty | 2026-06-01 |
| tests/test_utils.py::test_deprecated_* | EXPECTED | Removal in v0.3.0 | marty | |
<!-- END SKIPPED TEST AUDIT -->"""

SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_security.py::test_xss | UNVERIFIED | Needs review | | |
<!-- END SKIPPED TEST AUDIT -->"""


def _make_skipped(
    name: str,
    reason: str = "test reason",
    is_critical: bool = False,
) -> SkippedTest:
    """Helper to create SkippedTest instances."""
    file_path = name.split("::")[0] if "::" in name else name
    return SkippedTest(
        name=name,
        reason=reason,
        line_number=0,
        file_path=file_path,
        is_critical=is_critical,
    )


# --- T070: test_find_audit_stdout ---


class TestFindAuditBlock:
    """Tests for find_audit_block()."""

    def test_find_in_stdout(self) -> None:
        """T070: Audit block found in pytest stdout output."""
        output = f"some output\n{SAMPLE_AUDIT_BLOCK}\nmore output"
        result = find_audit_block(output)
        assert result is not None
        assert result["source"] == "stdout"
        assert len(result["entries"]) == 2

    def test_find_in_file(self, tmp_path: Path) -> None:
        """T080: Audit block found in external file."""
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(SAMPLE_AUDIT_BLOCK)

        result = find_audit_block("no audit here", audit_file=audit_file)
        assert result is not None
        assert result["source"] == "file"
        assert len(result["entries"]) == 2

    def test_find_in_default_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T080: Audit block found in default .skip-audit.md."""
        monkeypatch.chdir(tmp_path)
        default_file = tmp_path / ".skip-audit.md"
        default_file.write_text(SAMPLE_AUDIT_BLOCK)

        result = find_audit_block("no audit here")
        assert result is not None
        assert result["source"] == "file"

    def test_file_takes_priority_over_stdout(self, tmp_path: Path) -> None:
        """Explicit file is checked before stdout."""
        audit_file = tmp_path / "custom-audit.md"
        audit_file.write_text(SAMPLE_AUDIT_BLOCK)

        # stdout also has an audit block but file should win
        result = find_audit_block(
            SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED, audit_file=audit_file
        )
        assert result is not None
        assert result["source"] == "file"
        assert len(result["entries"]) == 2  # from file, not 1 from stdout

    def test_returns_none_when_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No audit block anywhere returns None."""
        monkeypatch.chdir(tmp_path)
        result = find_audit_block("no audit block here")
        assert result is None

    def test_malformed_block_no_end_marker(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing end marker returns None with warning."""
        monkeypatch.chdir(tmp_path)
        malformed = "<!-- SKIPPED TEST AUDIT -->\n| Test | Status |\nno end"
        result = find_audit_block(malformed)
        assert result is None

    def test_nonexistent_audit_file_falls_through(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Nonexistent audit file falls through to other sources."""
        monkeypatch.chdir(tmp_path)
        result = find_audit_block(
            SAMPLE_AUDIT_BLOCK,
            audit_file=Path("/nonexistent/path.md"),
        )
        assert result is not None
        assert result["source"] == "stdout"


# --- T090: test_validate_audit_match ---


class TestParseAuditBlock:
    """Tests for parse_audit_block()."""

    def test_parse_standard_block(self) -> None:
        """Parses a well-formed audit block."""
        result = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")
        assert len(result["entries"]) == 2
        assert result["entries"][0]["test_pattern"] == "tests/test_auth.py::test_oauth"
        assert result["entries"][0]["status"] == "VERIFIED"
        assert result["entries"][0]["justification"] == "External provider not in CI"
        assert result["entries"][0]["owner"] == "marty"
        assert result["entries"][0]["expires"] == "2026-06-01"
        assert result["entries"][1]["expires"] is None
        assert result["source"] == "file"

    def test_parse_empty_table(self) -> None:
        """Table with header only returns empty entries."""
        block = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
<!-- END SKIPPED TEST AUDIT -->"""
        result = parse_audit_block(block)
        assert result["entries"] == []

    def test_parse_strips_whitespace(self) -> None:
        """Extra whitespace in cells is stripped."""
        block = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
|  tests/test_a.py::test_x  |  VERIFIED  |  some reason  |  owner  |  2026-01-01  |
<!-- END SKIPPED TEST AUDIT -->"""
        result = parse_audit_block(block)
        assert result["entries"][0]["test_pattern"] == "tests/test_a.py::test_x"
        assert result["entries"][0]["status"] == "VERIFIED"
        assert result["entries"][0]["owner"] == "owner"


class TestMatchTestToAudit:
    """Tests for match_test_to_audit()."""

    def test_exact_match(self) -> None:
        """T090: Exact test name matches exact pattern."""
        test = _make_skipped("tests/test_auth.py::test_oauth")
        entry = AuditEntry(
            test_pattern="tests/test_auth.py::test_oauth",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is True

    def test_glob_match(self) -> None:
        """T090: Glob pattern matches test name."""
        test = _make_skipped("tests/test_utils.py::test_deprecated_helper")
        entry = AuditEntry(
            test_pattern="tests/test_utils.py::test_deprecated_*",
            status="EXPECTED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is True

    def test_no_match(self) -> None:
        """Non-matching pattern returns False."""
        test = _make_skipped("tests/test_utils.py::test_format")
        entry = AuditEntry(
            test_pattern="tests/test_auth.py::test_*",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is False

    def test_empty_pattern_no_match(self) -> None:
        """Empty pattern never matches."""
        test = _make_skipped("tests/test_a.py::test_x")
        entry = AuditEntry(
            test_pattern="",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is False

    def test_directory_glob(self) -> None:
        """Directory-level glob pattern."""
        test = _make_skipped("tests/unit/test_auth.py::test_oauth")
        entry = AuditEntry(
            test_pattern="tests/unit/*",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is True


# --- T100, T110, T120, T130: validation tests ---


class TestValidateAudit:
    """Tests for validate_audit()."""

    def test_all_audited_passes(self) -> None:
        """T130: All skipped tests have matching audit entries."""
        skipped = [_make_skipped("tests/test_auth.py::test_oauth")]
        audit = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert unverified == []

    def test_missing_audit_all_unaudited(self) -> None:
        """T100: No audit block means all tests are unaudited."""
        skipped = [_make_skipped("tests/test_a.py::test_x")]
        unaudited, unverified = validate_audit(skipped, None)
        assert len(unaudited) == 1
        assert unverified == []

    def test_unaudited_test_detected(self) -> None:
        """T110: Test without matching entry is unaudited."""
        skipped = [
            _make_skipped("tests/test_auth.py::test_oauth"),
            _make_skipped("tests/test_new.py::test_something"),  # not in audit
        ]
        audit = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")

        unaudited, unverified = validate_audit(skipped, audit)
        assert len(unaudited) == 1
        assert unaudited[0]["name"] == "tests/test_new.py::test_something"

    def test_unverified_critical_detected(self) -> None:
        """T120: Critical test with UNVERIFIED status is flagged."""
        skipped = [
            _make_skipped(
                "tests/test_security.py::test_xss",
                is_critical=True,
            )
        ]
        audit = parse_audit_block(
            SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED, source="file"
        )

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert len(unverified) == 1
        assert unverified[0]["name"] == "tests/test_security.py::test_xss"

    def test_non_critical_unverified_ok(self) -> None:
        """Non-critical test with UNVERIFIED status passes."""
        skipped = [
            _make_skipped(
                "tests/test_security.py::test_xss",
                is_critical=False,  # not critical
            )
        ]
        audit = parse_audit_block(
            SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED, source="file"
        )

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert unverified == []

    def test_glob_pattern_covers_test(self) -> None:
        """Glob pattern in audit covers matching tests."""
        skipped = [
            _make_skipped("tests/test_utils.py::test_deprecated_foo"),
            _make_skipped("tests/test_utils.py::test_deprecated_bar"),
        ]
        audit = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert unverified == []