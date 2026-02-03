"""Unit tests for verdict_analyzer/patterns.py module.

Issue #228: Add unit tests for verdict_analyzer module.

Tests verify pattern extraction and normalization including:
- Pattern normalization (file paths, line numbers)
- Category to section mapping
- Pattern extraction from issues
"""

import pytest

from tools.verdict_analyzer.parser import BlockingIssue
from tools.verdict_analyzer.patterns import (
    CATEGORY_TO_SECTION,
    extract_patterns_from_issues,
    map_category_to_section,
    normalize_pattern,
)


class TestNormalizePattern:
    """Tests for normalize_pattern function."""

    def test_replaces_python_files(self):
        """Should replace .py files with <file>."""
        result = normalize_pattern("Error in test_module.py at line 42")
        assert "<file>" in result
        assert "test_module.py" not in result

    def test_replaces_javascript_files(self):
        """Should replace .js files with <file>."""
        result = normalize_pattern("Missing export in utils.js")
        assert "<file>" in result
        assert "utils.js" not in result

    def test_replaces_line_numbers(self):
        """Should replace line numbers with <line>."""
        result = normalize_pattern("Error at line 123")
        assert "line <line>" in result
        assert "123" not in result

    def test_replaces_paths(self):
        """Should replace paths with <path>."""
        result = normalize_pattern("File at /usr/local/bin/script missing")
        assert "<path>" in result
        assert "/usr/local/bin/script" not in result

    def test_replaces_large_numbers(self):
        """Should replace multi-digit numbers with <num>."""
        result = normalize_pattern("Found 1234 issues in codebase")
        assert "<num>" in result
        assert "1234" not in result

    def test_normalizes_whitespace(self):
        """Should collapse multiple spaces."""
        result = normalize_pattern("Too    many   spaces")
        assert "  " not in result

    def test_preserves_meaningful_text(self):
        """Should preserve meaningful description text."""
        result = normalize_pattern("Missing input validation")
        assert "Missing input validation" == result


class TestMapCategoryToSection:
    """Tests for map_category_to_section function."""

    def test_maps_security(self):
        """Should map security to Security Considerations."""
        assert map_category_to_section("security") == "Security Considerations"

    def test_maps_testing(self):
        """Should map testing to Testing Strategy."""
        assert map_category_to_section("testing") == "Testing Strategy"

    def test_maps_unknown_to_default(self):
        """Should return default for unknown categories."""
        assert map_category_to_section("unknown_category") == "Implementation Notes"

    def test_all_categories_mapped(self):
        """All defined categories should be in mapping."""
        categories = ["security", "testing", "error_handling", "documentation",
                      "performance", "logging", "validation", "architecture",
                      "general", "database", "api"]
        for cat in categories:
            assert cat in CATEGORY_TO_SECTION


class TestExtractPatternsFromIssues:
    """Tests for extract_patterns_from_issues function."""

    def test_empty_list_returns_empty_dict(self):
        """Should return empty dict for empty list."""
        result = extract_patterns_from_issues([])
        assert result == {}

    def test_counts_single_pattern(self):
        """Should count occurrences of patterns."""
        issues = [
            BlockingIssue(tier=1, category="security", description="SQL injection risk"),
            BlockingIssue(tier=1, category="security", description="SQL injection risk"),
        ]
        result = extract_patterns_from_issues(issues)

        assert len(result) == 1
        assert result["SQL injection risk"] == 2

    def test_counts_multiple_patterns(self):
        """Should count different patterns separately."""
        issues = [
            BlockingIssue(tier=1, category="security", description="SQL injection risk"),
            BlockingIssue(tier=2, category="testing", description="Missing tests"),
        ]
        result = extract_patterns_from_issues(issues)

        assert len(result) == 2
        assert "SQL injection risk" in result
        assert "Missing tests" in result

    def test_normalizes_before_counting(self):
        """Should normalize patterns before counting."""
        issues = [
            BlockingIssue(tier=1, category="security", description="Error in foo.py"),
            BlockingIssue(tier=1, category="security", description="Error in bar.py"),
        ]
        result = extract_patterns_from_issues(issues)

        # Both should normalize to same pattern
        assert "Error in <file>" in result
        assert result["Error in <file>"] == 2
