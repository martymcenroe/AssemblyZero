"""Unit tests for verdict_analyzer/parser.py module.

Issue #228: Add unit tests for verdict_analyzer module.

Tests verify parsing of verdict markdown files including:
- Decision extraction from multiple formats
- Verdict type detection (LLD vs Issue)
- Blocking issue extraction by tier
- Category inference
- Content hash computation
"""

from pathlib import Path

import pytest

from tools.verdict_analyzer.parser import (
    PARSER_VERSION,
    BlockingIssue,
    VerdictRecord,
    _infer_category,
    compute_content_hash,
    parse_verdict,
)


# Fixtures directory path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "verdict_analyzer"


class TestComputeContentHash:
    """Tests for compute_content_hash function."""

    def test_hash_is_deterministic(self):
        """Same content should produce same hash."""
        content = "# Test verdict content"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Different content should produce different hashes."""
        hash1 = compute_content_hash("Content A")
        hash2 = compute_content_hash("Content B")
        assert hash1 != hash2

    def test_hash_is_sha256_hex(self):
        """Hash should be 64-character hex string (SHA-256)."""
        hash_value = compute_content_hash("test")
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_empty_content_has_hash(self):
        """Empty string should still produce a valid hash."""
        hash_value = compute_content_hash("")
        assert len(hash_value) == 64


class TestParseVerdictDecision:
    """Tests for decision extraction from verdict files."""

    def test_parse_approved_header_format(self):
        """Parse verdict with header format: # Governance Verdict: APPROVED."""
        verdict_path = FIXTURES_DIR / "approved_verdict.md"
        record = parse_verdict(verdict_path)
        assert record.decision == "APPROVED"

    def test_parse_blocked_bold_format(self):
        """Parse verdict with bold format: **Verdict: REJECTED**."""
        verdict_path = FIXTURES_DIR / "blocked_verdict.md"
        record = parse_verdict(verdict_path)
        assert record.decision == "BLOCKED"

    def test_parse_checkbox_format(self):
        """Parse verdict with checkbox format: [x] **REVISE**."""
        verdict_path = FIXTURES_DIR / "checkbox_verdict.md"
        record = parse_verdict(verdict_path)
        assert record.decision == "BLOCKED"  # REVISE maps to BLOCKED

    def test_parse_malformed_returns_unknown(self):
        """Malformed verdict without decision section returns UNKNOWN."""
        verdict_path = FIXTURES_DIR / "malformed_verdict.md"
        record = parse_verdict(verdict_path)
        assert record.decision == "UNKNOWN"

    def test_parse_legacy_blocked_format(self):
        """Parse legacy format: # Governance Verdict: BLOCKED."""
        verdict_path = FIXTURES_DIR / "legacy_format_verdict.md"
        record = parse_verdict(verdict_path)
        assert record.decision == "BLOCKED"


class TestParseVerdictType:
    """Tests for verdict type detection (LLD vs Issue)."""

    def test_lld_verdict_type_from_header(self):
        """LLD Review header should set verdict_type to 'lld'."""
        verdict_path = FIXTURES_DIR / "blocked_verdict.md"
        record = parse_verdict(verdict_path)
        assert record.verdict_type == "lld"

    def test_issue_verdict_type_from_header(self):
        """Issue Review header should set verdict_type to 'issue'."""
        verdict_path = FIXTURES_DIR / "issue_verdict.md"
        record = parse_verdict(verdict_path)
        assert record.verdict_type == "issue"

    def test_governance_verdict_header_is_lld(self):
        """Governance Verdict header should set verdict_type to 'lld'."""
        verdict_path = FIXTURES_DIR / "approved_verdict.md"
        record = parse_verdict(verdict_path)
        assert record.verdict_type == "lld"

    def test_fallback_to_filename_issue(self, tmp_path):
        """Fallback to filename-based detection for 'issue'."""
        # Create temp file with "issue" in name but no header
        issue_file = tmp_path / "test_issue_review.md"
        issue_file.write_text("# Random Title\nNo verdict markers.")
        record = parse_verdict(issue_file)
        assert record.verdict_type == "issue"

    def test_fallback_default_is_lld(self, tmp_path):
        """Default verdict_type is 'lld' when no markers found."""
        # Create temp file without any markers
        generic_file = tmp_path / "random_file.md"
        generic_file.write_text("# Random Title\nNo verdict markers.")
        record = parse_verdict(generic_file)
        assert record.verdict_type == "lld"


class TestParseBlockingIssues:
    """Tests for blocking issue extraction."""

    def test_extract_tier1_blocking_issues(self):
        """Extract blocking issues from Tier 1 section."""
        verdict_path = FIXTURES_DIR / "blocked_verdict.md"
        record = parse_verdict(verdict_path)

        tier1_issues = [i for i in record.blocking_issues if i.tier == 1]
        assert len(tier1_issues) >= 2

        # Check categories
        categories = {i.category for i in tier1_issues}
        assert "security" in categories or "safety" in categories

    def test_extract_tier2_issues(self):
        """Extract issues from Tier 2 section."""
        verdict_path = FIXTURES_DIR / "blocked_verdict.md"
        record = parse_verdict(verdict_path)

        tier2_issues = [i for i in record.blocking_issues if i.tier == 2]
        assert len(tier2_issues) >= 2

    def test_extract_tier3_suggestions(self):
        """Extract suggestions from Tier 3 section."""
        verdict_path = FIXTURES_DIR / "blocked_verdict.md"
        record = parse_verdict(verdict_path)

        tier3_issues = [i for i in record.blocking_issues if i.tier == 3]
        assert len(tier3_issues) >= 2

    def test_skip_no_issues_found_entries(self):
        """Entries with 'No issues found' should be skipped."""
        verdict_path = FIXTURES_DIR / "approved_verdict.md"
        record = parse_verdict(verdict_path)

        # Should have very few or no blocking issues
        # Only the suggestion in Tier 3 should be present
        assert len(record.blocking_issues) <= 1

    def test_legacy_format_extracts_issues(self):
        """Legacy format (## Blocking Issues / ### Tier N) should work."""
        verdict_path = FIXTURES_DIR / "legacy_format_verdict.md"
        record = parse_verdict(verdict_path)

        # Should extract issues from legacy format
        assert len(record.blocking_issues) >= 2

        # Check tier assignment
        tier1_issues = [i for i in record.blocking_issues if i.tier == 1]
        assert len(tier1_issues) >= 1

    def test_blocking_issue_description_cleaned(self):
        """Bold markers should be removed from descriptions."""
        verdict_path = FIXTURES_DIR / "blocked_verdict.md"
        record = parse_verdict(verdict_path)

        for issue in record.blocking_issues:
            assert "**" not in issue.description


class TestInferCategory:
    """Tests for _infer_category function."""

    def test_infer_security_category(self):
        """Security-related keywords should return 'security'."""
        assert _infer_category("SQL injection vulnerability") == "security"
        assert _infer_category("XSS attack vector") == "security"
        assert _infer_category("Auth bypass risk") == "security"

    def test_infer_testing_category(self):
        """Testing-related keywords should return 'testing'."""
        assert _infer_category("Test coverage insufficient") == "testing"
        assert _infer_category("Missing unit tests") == "testing"

    def test_infer_error_handling_category(self):
        """Error handling keywords should return 'error_handling'."""
        assert _infer_category("Exception not caught") == "error_handling"
        assert _infer_category("Error handling missing") == "error_handling"

    def test_infer_documentation_category(self):
        """Documentation keywords should return 'documentation'."""
        assert _infer_category("Missing README section") == "documentation"
        assert _infer_category("Code comments needed") == "documentation"

    def test_infer_performance_category(self):
        """Performance keywords should return 'performance'."""
        assert _infer_category("Slow database queries") == "performance"
        assert _infer_category("Need to optimize queries") == "performance"
        # Note: "optimization" not matched, only "optimize"
        assert _infer_category("Cache mechanism needed") == "performance"

    def test_infer_general_category(self):
        """Unknown keywords should return 'general'."""
        assert _infer_category("Random issue description") == "general"
        assert _infer_category("Something unclear") == "general"


class TestVerdictRecord:
    """Tests for VerdictRecord structure."""

    def test_record_contains_filepath(self):
        """Record should contain the original filepath."""
        verdict_path = FIXTURES_DIR / "approved_verdict.md"
        record = parse_verdict(verdict_path)
        assert str(verdict_path) in record.filepath

    def test_record_contains_content_hash(self):
        """Record should contain content hash."""
        verdict_path = FIXTURES_DIR / "approved_verdict.md"
        record = parse_verdict(verdict_path)
        assert len(record.content_hash) == 64

    def test_record_contains_parser_version(self):
        """Record should contain parser version."""
        verdict_path = FIXTURES_DIR / "approved_verdict.md"
        record = parse_verdict(verdict_path)
        assert record.parser_version == PARSER_VERSION

    def test_blocking_issues_is_list(self):
        """Blocking issues should be a list."""
        verdict_path = FIXTURES_DIR / "approved_verdict.md"
        record = parse_verdict(verdict_path)
        assert isinstance(record.blocking_issues, list)


class TestEdgeCases:
    """Edge case tests for parser robustness."""

    def test_empty_file_does_not_crash(self, tmp_path):
        """Empty file should not crash parser."""
        empty_file = tmp_path / "empty_verdict.md"
        empty_file.write_text("")
        record = parse_verdict(empty_file)
        assert record.decision == "UNKNOWN"
        assert record.blocking_issues == []

    def test_unicode_content_handled(self, tmp_path):
        """Unicode content should be handled correctly."""
        unicode_file = tmp_path / "unicode_verdict.md"
        unicode_file.write_text(
            "# Governance Verdict: APPROVED\n\nUnicode content here",
            encoding="utf-8"
        )
        record = parse_verdict(unicode_file)
        assert record.decision == "APPROVED"

    def test_very_long_file(self, tmp_path):
        """Very long file should be handled."""
        long_file = tmp_path / "long_verdict.md"
        content = "# Governance Verdict: APPROVED\n\n" + "x" * 100000
        long_file.write_text(content)
        record = parse_verdict(long_file)
        assert record.decision == "APPROVED"
