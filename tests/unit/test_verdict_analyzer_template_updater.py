"""Unit tests for verdict_analyzer/template_updater.py module.

Issue #228: Add unit tests for verdict_analyzer module.

Tests verify template modification functionality including:
- Template section parsing
- Recommendation generation
- Atomic file writes with backup
- Path validation
- Statistics formatting
"""

from pathlib import Path

import pytest

from tools.verdict_analyzer.template_updater import (
    Recommendation,
    atomic_write_template,
    format_stats,
    generate_recommendations,
    parse_template_sections,
    validate_template_path,
)


class TestRecommendation:
    """Tests for Recommendation dataclass."""

    def test_create_recommendation(self):
        """Should create recommendation with all fields."""
        rec = Recommendation(
            rec_type="add_section",
            section="Security Considerations",
            content="Add security section",
            pattern_count=5,
        )
        assert rec.rec_type == "add_section"
        assert rec.section == "Security Considerations"
        assert rec.content == "Add security section"
        assert rec.pattern_count == 5

    def test_recommendation_equality(self):
        """Two recommendations with same values should be equal."""
        rec1 = Recommendation("add_section", "Security", "content", 5)
        rec2 = Recommendation("add_section", "Security", "content", 5)
        assert rec1 == rec2

    def test_recommendation_inequality(self):
        """Recommendations with different values should not be equal."""
        rec1 = Recommendation("add_section", "Security", "content", 5)
        rec2 = Recommendation("add_checklist_item", "Security", "content", 5)
        assert rec1 != rec2


class TestParseTemplateSections:
    """Tests for parse_template_sections function."""

    def test_empty_content_returns_empty_dict(self):
        """Empty content should return empty dict."""
        result = parse_template_sections("")
        assert result == {}

    def test_no_headers_returns_empty_dict(self):
        """Content without headers should return empty dict."""
        result = parse_template_sections("Just some text without headers.")
        assert result == {}

    def test_parses_h2_headers(self):
        """Should parse ## headers."""
        content = """## Section One
Content for section one.

## Section Two
Content for section two.
"""
        result = parse_template_sections(content)
        assert "Section One" in result
        assert "Section Two" in result
        assert "Content for section one." in result["Section One"]

    def test_parses_h3_headers(self):
        """Should parse ### headers."""
        content = """### Subsection A
Subsection A content.

### Subsection B
Subsection B content.
"""
        result = parse_template_sections(content)
        assert "Subsection A" in result
        assert "Subsection B" in result

    def test_mixed_header_levels(self):
        """Should parse mixed ## and ### headers."""
        content = """## Main Section
Main content.

### Subsection
Sub content.

## Another Main
More content.
"""
        result = parse_template_sections(content)
        assert "Main Section" in result
        assert "Subsection" in result
        assert "Another Main" in result

    def test_strips_section_content(self):
        """Section content should be stripped of whitespace."""
        content = """## Section

   Content with spaces

## Next
"""
        result = parse_template_sections(content)
        assert result["Section"] == "Content with spaces"

    def test_single_section(self):
        """Should handle single section."""
        content = """## Only Section
This is the only section content.
"""
        result = parse_template_sections(content)
        assert len(result) == 1
        assert "Only Section" in result

    def test_ignores_h1_headers(self):
        """Should ignore # headers (only ## and ### are parsed)."""
        content = """# Title
Introduction.

## Section
Content.
"""
        result = parse_template_sections(content)
        assert "Title" not in result
        assert "Section" in result

    def test_preserves_multiline_content(self):
        """Should preserve multiline content in sections."""
        content = """## Section
Line one.
Line two.
Line three.

## Next
"""
        result = parse_template_sections(content)
        assert "Line one." in result["Section"]
        assert "Line two." in result["Section"]
        assert "Line three." in result["Section"]


class TestGenerateRecommendations:
    """Tests for generate_recommendations function."""

    def test_empty_stats_returns_empty_list(self):
        """Empty stats should return no recommendations."""
        result = generate_recommendations({}, {})
        assert result == []

    def test_below_threshold_no_recommendations(self):
        """Categories below min_pattern_count should not generate recommendations."""
        stats = {"categories": {"security": 2}}  # Below default of 3
        result = generate_recommendations(stats, {})
        assert result == []

    def test_at_threshold_generates_recommendation(self):
        """Categories at min_pattern_count should generate recommendations."""
        stats = {"categories": {"security": 3}}
        result = generate_recommendations(stats, {})
        assert len(result) == 1

    def test_above_threshold_generates_recommendation(self):
        """Categories above min_pattern_count should generate recommendations."""
        stats = {"categories": {"security": 10}}
        result = generate_recommendations(stats, {})
        assert len(result) == 1

    def test_custom_min_pattern_count(self):
        """Should respect custom min_pattern_count."""
        stats = {"categories": {"security": 5}}

        # With default threshold (3), should generate
        result = generate_recommendations(stats, {}, min_pattern_count=3)
        assert len(result) == 1

        # With higher threshold, should not generate
        result = generate_recommendations(stats, {}, min_pattern_count=10)
        assert len(result) == 0

    def test_missing_section_recommends_add_section(self):
        """Should recommend add_section when section doesn't exist."""
        stats = {"categories": {"security": 5}}
        existing = {}  # No existing sections

        result = generate_recommendations(stats, existing)

        assert len(result) == 1
        assert result[0].rec_type == "add_section"
        assert result[0].section == "Security Considerations"

    def test_existing_section_recommends_checklist_item(self):
        """Should recommend add_checklist_item when section exists."""
        stats = {"categories": {"security": 5}}
        existing = {"Security Considerations": "Some existing content"}

        result = generate_recommendations(stats, existing)

        assert len(result) == 1
        assert result[0].rec_type == "add_checklist_item"
        assert result[0].section == "Security Considerations"

    def test_multiple_categories(self):
        """Should generate recommendations for multiple categories."""
        stats = {"categories": {"security": 5, "testing": 4, "documentation": 3}}
        existing = {"Security Considerations": "exists"}

        result = generate_recommendations(stats, existing)

        assert len(result) == 3
        rec_types = {r.rec_type for r in result}
        assert "add_section" in rec_types
        assert "add_checklist_item" in rec_types

    def test_unknown_category_maps_to_implementation_notes(self):
        """Unknown categories should map to Implementation Notes section."""
        stats = {"categories": {"unknown_category": 5}}
        existing = {}

        result = generate_recommendations(stats, existing)

        assert len(result) == 1
        assert result[0].section == "Implementation Notes"

    def test_recommendation_contains_pattern_count(self):
        """Recommendation should include pattern count."""
        stats = {"categories": {"security": 7}}
        result = generate_recommendations(stats, {})

        assert result[0].pattern_count == 7

    def test_recommendation_content_includes_category(self):
        """Recommendation content should mention the category."""
        stats = {"categories": {"testing": 5}}
        result = generate_recommendations(stats, {})

        assert "testing" in result[0].content


class TestAtomicWriteTemplate:
    """Tests for atomic_write_template function."""

    def test_creates_backup_file(self, tmp_path):
        """Should create backup file with .bak extension."""
        template = tmp_path / "template.md"
        template.write_text("Original content")

        backup = atomic_write_template(template, "New content")

        assert backup.exists()
        assert backup.suffix == ".bak"
        assert backup.read_text() == "Original content"

    def test_writes_new_content(self, tmp_path):
        """Should write new content to template."""
        template = tmp_path / "template.md"
        template.write_text("Original content")

        atomic_write_template(template, "New content")

        assert template.read_text() == "New content"

    def test_backup_path_format(self, tmp_path):
        """Backup path should be original path with .bak appended."""
        template = tmp_path / "my-template.md"
        template.write_text("content")

        backup = atomic_write_template(template, "new")

        assert backup == tmp_path / "my-template.md.bak"

    def test_preserves_file_metadata(self, tmp_path):
        """Backup should preserve original file metadata."""
        template = tmp_path / "template.md"
        template.write_text("Original")
        original_stat = template.stat()

        backup = atomic_write_template(template, "New")

        # shutil.copy2 preserves metadata
        assert backup.stat().st_size == len("Original")

    def test_overwrites_existing_backup(self, tmp_path):
        """Should overwrite existing backup file."""
        template = tmp_path / "template.md"
        template.write_text("Version 1")

        # First write
        atomic_write_template(template, "Version 2")

        # Second write should overwrite backup
        atomic_write_template(template, "Version 3")

        backup = tmp_path / "template.md.bak"
        assert backup.read_text() == "Version 2"

    def test_writes_with_utf8_encoding(self, tmp_path):
        """Should write content with UTF-8 encoding."""
        template = tmp_path / "template.md"
        template.write_text("Original", encoding="utf-8")

        unicode_content = "Content with unicode: café, naïve, 日本語"
        atomic_write_template(template, unicode_content)

        assert template.read_text(encoding="utf-8") == unicode_content


class TestValidateTemplatePath:
    """Tests for validate_template_path function."""

    def test_valid_path_within_base(self, tmp_path):
        """Should accept paths within base directory."""
        base = tmp_path / "base"
        base.mkdir()
        filepath = base / "subdir" / "template.md"
        filepath.parent.mkdir(parents=True)
        filepath.write_text("content")

        # Should not raise
        validate_template_path(filepath, base)

    def test_rejects_path_outside_base(self, tmp_path):
        """Should reject paths outside base directory."""
        base = tmp_path / "base"
        base.mkdir()
        outside = tmp_path / "outside" / "template.md"
        outside.parent.mkdir(parents=True)
        outside.write_text("content")

        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_template_path(outside, base)

    def test_rejects_parent_traversal(self, tmp_path):
        """Should reject paths with parent traversal."""
        base = tmp_path / "base"
        base.mkdir()

        # Path that tries to escape via ..
        traversal = base / ".." / "escaped.md"

        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_template_path(traversal, base)

    def test_accepts_nested_path(self, tmp_path):
        """Should accept deeply nested paths within base."""
        base = tmp_path / "base"
        nested = base / "a" / "b" / "c" / "template.md"
        nested.parent.mkdir(parents=True)
        nested.write_text("content")

        # Should not raise
        validate_template_path(nested, base)

    def test_error_message_includes_paths(self, tmp_path):
        """Error message should include both paths."""
        base = tmp_path / "base"
        base.mkdir()
        outside = tmp_path / "outside.md"
        outside.write_text("content")

        with pytest.raises(ValueError) as exc_info:
            validate_template_path(outside, base)

        assert "outside.md" in str(exc_info.value)
        assert "base" in str(exc_info.value)


class TestFormatStats:
    """Tests for format_stats function."""

    def test_formats_empty_stats(self):
        """Should handle empty stats dict."""
        result = format_stats({})

        assert "Total Verdicts: 0" in result
        assert "Total Blocking Issues: 0" in result

    def test_formats_total_verdicts(self):
        """Should format total verdicts count."""
        stats = {"total_verdicts": 42}
        result = format_stats(stats)

        assert "Total Verdicts: 42" in result

    def test_formats_total_issues(self):
        """Should format total blocking issues count."""
        stats = {"total_issues": 15}
        result = format_stats(stats)

        assert "Total Blocking Issues: 15" in result

    def test_formats_decisions(self):
        """Should format decisions breakdown."""
        stats = {
            "decisions": {
                "APPROVED": 10,
                "BLOCKED": 5,
                "UNKNOWN": 2,
            }
        }
        result = format_stats(stats)

        assert "Decisions:" in result
        assert "APPROVED: 10" in result
        assert "BLOCKED: 5" in result
        assert "UNKNOWN: 2" in result

    def test_formats_tiers(self):
        """Should format tiers breakdown."""
        stats = {
            "tiers": {
                1: 8,
                2: 12,
                3: 5,
            }
        }
        result = format_stats(stats)

        assert "By Tier:" in result
        assert "Tier 1: 8" in result
        assert "Tier 2: 12" in result
        assert "Tier 3: 5" in result

    def test_formats_categories(self):
        """Should format categories breakdown."""
        stats = {
            "categories": {
                "security": 15,
                "testing": 10,
                "documentation": 5,
            }
        }
        result = format_stats(stats)

        assert "By Category:" in result
        assert "security: 15" in result
        assert "testing: 10" in result
        assert "documentation: 5" in result

    def test_formats_complete_stats(self):
        """Should format complete statistics."""
        stats = {
            "total_verdicts": 50,
            "total_issues": 75,
            "decisions": {"APPROVED": 30, "BLOCKED": 20},
            "tiers": {1: 25, 2: 30, 3: 20},
            "categories": {"security": 40, "testing": 35},
        }
        result = format_stats(stats)

        # Check structure
        assert "Total Verdicts: 50" in result
        assert "Total Blocking Issues: 75" in result
        assert "Decisions:" in result
        assert "By Tier:" in result
        assert "By Category:" in result

    def test_empty_decisions(self):
        """Should handle empty decisions dict."""
        stats = {"decisions": {}}
        result = format_stats(stats)

        assert "Decisions:" in result
        # No decision entries after the header

    def test_empty_tiers(self):
        """Should handle empty tiers dict."""
        stats = {"tiers": {}}
        result = format_stats(stats)

        assert "By Tier:" in result

    def test_empty_categories(self):
        """Should handle empty categories dict."""
        stats = {"categories": {}}
        result = format_stats(stats)

        assert "By Category:" in result

    def test_returns_string(self):
        """Should return a string."""
        result = format_stats({})
        assert isinstance(result, str)

    def test_newlines_separate_sections(self):
        """Sections should be separated by blank lines."""
        stats = {
            "total_verdicts": 1,
            "decisions": {"APPROVED": 1},
            "tiers": {1: 1},
            "categories": {"security": 1},
        }
        result = format_stats(stats)

        # Should have blank lines between sections
        assert "\n\n" in result
