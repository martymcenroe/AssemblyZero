"""Tests for spelunking claim extraction logic.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.spelunking.extractors import (
    extract_claims_from_markdown,
    extract_file_count_claims,
    extract_file_reference_claims,
    extract_technical_claims,
    extract_timestamp_claims,
)
from assemblyzero.spelunking.models import ClaimType


class TestExtractFileCountClaims:
    """Tests for file count claim extraction."""

    def test_T040_extracts_file_count(self) -> None:
        """T040: Extract '11 tools in tools/' as FILE_COUNT claim."""
        content = "There are 11 tools in tools/"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        claim = claims[0]
        assert claim.claim_type == ClaimType.FILE_COUNT
        assert claim.expected_value == "11"
        assert claim.source_line == 1

    def test_extracts_multiple_counts(self) -> None:
        """Extract multiple count claims from multi-line content."""
        content = "11 tools in tools/\n6 ADRs in docs/adrs/"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 2

    def test_extracts_count_with_backticks(self) -> None:
        """Extract count claims where directory is in backticks."""
        content = "5 tools in `tools/`"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].expected_value == "5"

    def test_no_counts_returns_empty(self) -> None:
        """Content with no numeric counts returns empty list."""
        content = "This is just a regular paragraph with no numbers or directories."
        source = Path("doc.md")

        claims = extract_file_count_claims(content, source)

        assert claims == []

    def test_correct_line_numbers(self) -> None:
        """Line numbers are correctly tracked across multiple lines."""
        content = "Header line\nAnother line\n3 files in src/"
        source = Path("doc.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].source_line == 3

    def test_adr_uses_md_glob(self) -> None:
        """ADR count claims use *.md glob pattern."""
        content = "6 ADRs in docs/adrs/"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        assert "*.md" in claims[0].verification_command

    def test_tools_uses_py_glob(self) -> None:
        """Tool count claims use *.py glob pattern."""
        content = "11 tools in tools/"
        source = Path("inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        assert "*.py" in claims[0].verification_command

    def test_source_file_preserved(self) -> None:
        """Source file path is preserved in extracted claims."""
        content = "5 files in src/"
        source = Path("docs/standards/0003-file-inventory.md")

        claims = extract_file_count_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].source_file == source


class TestExtractFileReferenceClaims:
    """Tests for file reference claim extraction."""

    def test_T050_extracts_backtick_reference(self) -> None:
        """T050: Extract backtick file reference."""
        content = "See `tools/death.py` for details."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.FILE_EXISTS
        assert claims[0].expected_value == "tools/death.py"

    def test_extracts_link_reference(self) -> None:
        """Extract markdown link file reference."""
        content = "Check [config](config/settings.yaml) for options."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1
        assert claims[0].expected_value == "config/settings.yaml"

    def test_skips_urls(self) -> None:
        """Skip http/https URLs."""
        content = "See `https://example.com/file.py` for details."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 0

    def test_deduplicates_paths(self) -> None:
        """Same path referenced twice is only extracted once."""
        content = "See `tools/death.py` here.\nAnd `tools/death.py` again."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1

    def test_multiple_references_on_same_line(self) -> None:
        """Multiple references on one line are all extracted."""
        content = "See `tools/a.py` and `tools/b.py` for details."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 2
        paths = {c.expected_value for c in claims}
        assert "tools/a.py" in paths
        assert "tools/b.py" in paths

    def test_no_references_returns_empty(self) -> None:
        """Content with no file references returns empty list."""
        content = "This is just plain text without any file paths."
        source = Path("doc.md")

        claims = extract_file_reference_claims(content, source)

        assert claims == []

    def test_verification_command_format(self) -> None:
        """Verification command uses path_exists format."""
        content = "See `tools/death.py` for details."
        source = Path("README.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1
        assert claims[0].verification_command == "path_exists tools/death.py"

    def test_correct_line_numbers(self) -> None:
        """Line numbers are tracked correctly for file references."""
        content = "Line one.\nLine two.\nSee `tools/thing.py` here."
        source = Path("doc.md")

        claims = extract_file_reference_claims(content, source)

        assert len(claims) == 1
        assert claims[0].source_line == 3


class TestExtractTechnicalClaims:
    """Tests for technical claim extraction."""

    def test_T060_extracts_negation(self) -> None:
        """T060: Extract 'not vector embeddings' as TECHNICAL_FACT."""
        content = "This system uses deterministic techniques, not vector embeddings."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        assert len(claims) >= 1
        found = any(
            c.claim_type == ClaimType.TECHNICAL_FACT
            and "vector embeddings" in c.expected_value
            for c in claims
        )
        assert found

    def test_extracts_without_negation(self) -> None:
        """Extract 'without chromadb' as TECHNICAL_FACT."""
        content = "Built without chromadb for storage."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        assert len(claims) >= 1
        found = any(
            "chromadb" in c.expected_value for c in claims
        )
        assert found

    def test_extracts_no_negation(self) -> None:
        """Extract 'no machine learning' as TECHNICAL_FACT."""
        content = "Uses no machine learning techniques."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        assert len(claims) >= 1
        found = any(
            "machine learning" in c.expected_value for c in claims
        )
        assert found

    def test_no_negations_returns_empty(self) -> None:
        """Content without negation patterns returns empty list."""
        content = "This system uses Python and pytest for testing."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        assert claims == []

    def test_short_terms_excluded(self) -> None:
        """Terms shorter than 3 chars after 'not' are excluded."""
        content = "This is not an issue."
        source = Path("doc.md")

        claims = extract_technical_claims(content, source)

        # "an" is only 2 chars, should be excluded
        short_claims = [c for c in claims if len(c.expected_value) < 3]
        assert len(short_claims) == 0

    def test_deduplicates_terms(self) -> None:
        """Same negated term mentioned twice is only extracted once."""
        content = "not chromadb here.\nAlso not chromadb there."
        source = Path("doc.md")

        claims = extract_technical_claims(content, source)

        chromadb_claims = [c for c in claims if "chromadb" in c.expected_value]
        assert len(chromadb_claims) == 1

    def test_custom_negation_patterns(self) -> None:
        """Custom negation patterns are appended to defaults."""
        content = "excludes tensorflow from the stack."
        source = Path("README.md")

        claims = extract_technical_claims(
            content, source, negation_patterns=[r"excludes\s+([a-zA-Z][a-zA-Z0-9_ ]{2,})"]
        )

        found = any("tensorflow" in c.expected_value for c in claims)
        assert found

    def test_verification_command_format(self) -> None:
        """Verification command uses grep_absent format."""
        content = "This system does not use chromadb."
        source = Path("README.md")

        claims = extract_technical_claims(content, source)

        chromadb_claims = [c for c in claims if "chromadb" in c.expected_value]
        assert len(chromadb_claims) >= 1
        assert "grep_absent" in chromadb_claims[0].verification_command


class TestExtractTimestampClaims:
    """Tests for timestamp claim extraction."""

    def test_T070_extracts_last_updated(self) -> None:
        """T070: Extract 'Last Updated: 2026-01-15' as TIMESTAMP."""
        content = "<!-- Last Updated: 2026-01-15 -->"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.TIMESTAMP
        assert claims[0].expected_value == "2026-01-15"

    def test_extracts_date_field(self) -> None:
        """Extract 'Date: 2026-02-17' as TIMESTAMP."""
        content = "Date: 2026-02-17"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].expected_value == "2026-02-17"

    def test_no_timestamp_returns_empty(self) -> None:
        """Content without timestamps returns empty list."""
        content = "# Just a title\n\nSome content."
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert claims == []

    def test_verification_command_format(self) -> None:
        """Verification command uses check_freshness format."""
        content = "Last Updated: 2026-01-15"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].verification_command == "check_freshness 2026-01-15"

    def test_correct_line_number(self) -> None:
        """Line number is tracked correctly for timestamp claims."""
        content = "# Title\n\n<!-- Last Updated: 2026-01-15 -->"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].source_line == 3

    def test_case_insensitive_last_updated(self) -> None:
        """Case variations of 'Last Updated' are matched."""
        content = "last updated: 2026-01-15"
        source = Path("doc.md")

        claims = extract_timestamp_claims(content, source)

        assert len(claims) >= 1
        assert claims[0].expected_value == "2026-01-15"


class TestExtractClaimsFromMarkdown:
    """Tests for the top-level extraction function."""

    def test_T080_no_claims_in_simple_doc(self, tmp_path: Path) -> None:
        """T080: Return empty list for non-factual document."""
        doc = tmp_path / "hello.md"
        doc.write_text("# Hello\n\nJust a greeting.")

        claims = extract_claims_from_markdown(doc)

        assert claims == []

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Return empty list for nonexistent file."""
        claims = extract_claims_from_markdown(tmp_path / "nope.md")

        assert claims == []

    def test_filtered_claim_types(self, tmp_path: Path) -> None:
        """Only extract specified claim types."""
        doc = tmp_path / "mixed.md"
        doc.write_text("11 tools in tools/\nSee `tools/death.py`\nLast Updated: 2026-01-15")

        claims = extract_claims_from_markdown(doc, claim_types=[ClaimType.FILE_COUNT])

        assert all(c.claim_type == ClaimType.FILE_COUNT for c in claims)

    def test_extracts_all_types_by_default(self, tmp_path: Path) -> None:
        """Without claim_types filter, extracts all supported types."""
        doc = tmp_path / "mixed.md"
        doc.write_text(
            "11 tools in tools/\n"
            "See `tools/death.py` for details.\n"
            "Last Updated: 2026-01-15\n"
            "This project does not use chromadb."
        )

        claims = extract_claims_from_markdown(doc)

        claim_types = {c.claim_type for c in claims}
        assert ClaimType.FILE_COUNT in claim_types
        assert ClaimType.FILE_EXISTS in claim_types
        assert ClaimType.TIMESTAMP in claim_types
        assert ClaimType.TECHNICAL_FACT in claim_types

    def test_multiple_claim_types_filter(self, tmp_path: Path) -> None:
        """Filter to multiple claim types simultaneously."""
        doc = tmp_path / "mixed.md"
        doc.write_text(
            "11 tools in tools/\n"
            "See `tools/death.py` for details.\n"
            "Last Updated: 2026-01-15"
        )

        claims = extract_claims_from_markdown(
            doc, claim_types=[ClaimType.FILE_COUNT, ClaimType.TIMESTAMP]
        )

        claim_types = {c.claim_type for c in claims}
        assert ClaimType.FILE_EXISTS not in claim_types
        assert len(claims) >= 2

    def test_source_file_matches_input(self, tmp_path: Path) -> None:
        """All extracted claims reference the correct source file."""
        doc = tmp_path / "inventory.md"
        doc.write_text("5 tools in tools/\nSee `tools/real.py`.")

        claims = extract_claims_from_markdown(doc)

        for claim in claims:
            assert claim.source_file == doc