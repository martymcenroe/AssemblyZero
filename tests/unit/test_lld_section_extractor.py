"""Unit tests for LLD section extractor.

Issue #642: Tests for extract_file_spec_section() and helpers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.utils.lld_section_extractor import (
    ExtractedSection,
    _score_section_for_file,
    _split_lld_into_sections,
    extract_file_spec_section,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "retry_prompt"


@pytest.fixture()
def full_lld() -> str:
    """Load the full LLD fixture."""
    return (FIXTURES_DIR / "full_lld.md").read_text(encoding="utf-8")


@pytest.fixture()
def minimal_lld() -> str:
    """Load the minimal LLD fixture."""
    return (FIXTURES_DIR / "minimal_lld.md").read_text(encoding="utf-8")


class TestExtractFileSpecSection:
    """Tests for extract_file_spec_section()."""

    def test_exact_path_match_returns_confidence_1(self, full_lld: str) -> None:
        """T090: Exact path match yields confidence=1.0."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/alpha_service.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "Alpha service" in result["section_body"]
        assert "create_alpha" in result["section_body"]

    def test_stem_match_returns_lower_confidence(self, full_lld: str) -> None:
        """T100: Stem-only match yields 0.0 < confidence < 1.0."""
        # Construct a target path not literally in the LLD but whose stem is
        result = extract_file_spec_section(
            full_lld, "some/other/path/alpha_service.py"
        )
        assert result is not None
        assert 0.0 < result["match_confidence"] < 1.0

    def test_no_match_returns_none(self, full_lld: str) -> None:
        """T110: No match returns None."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/nonexistent/zzz_module.py"
        )
        assert result is None

    def test_empty_lld_raises_value_error(self) -> None:
        """T120: Empty lld_content raises ValueError."""
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            extract_file_spec_section("", "assemblyzero/foo.py")

    def test_whitespace_only_lld_raises_value_error(self) -> None:
        """Edge case: whitespace-only lld_content raises ValueError."""
        with pytest.raises(ValueError, match="lld_content must not be empty"):
            extract_file_spec_section("   \n\t  ", "assemblyzero/foo.py")

    def test_minimal_lld_exact_match(self, minimal_lld: str) -> None:
        """Minimal LLD with single section returns exact match."""
        result = extract_file_spec_section(
            minimal_lld, "assemblyzero/utils/tiny_helper.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "tiny_format" in result["section_body"]

    def test_returns_extracted_section_typed_dict(self, full_lld: str) -> None:
        """Result has all required TypedDict keys."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/alpha_service.py"
        )
        assert result is not None
        assert "section_heading" in result
        assert "section_body" in result
        assert "match_confidence" in result

    def test_section_body_includes_heading(self, full_lld: str) -> None:
        """Section body includes the heading line."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/alpha_service.py"
        )
        assert result is not None
        assert result["section_heading"] in result["section_body"]

    def test_returns_most_relevant_section(self, full_lld: str) -> None:
        """Returns the highest-scoring section, not an unrelated one."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/workflows/epsilon_flow.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "epsilon" in result["section_body"].lower()

    def test_exact_match_excludes_unrelated_sections(self, full_lld: str) -> None:
        """Exact match result does not contain padding sections."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/utils/delta_helper.py"
        )
        assert result is not None
        assert "Padding Section" not in result["section_body"]

    def test_beta_service_match(self, full_lld: str) -> None:
        """Beta service section extracted correctly."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/services/beta_service.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "connect_beta" in result["section_body"]

    def test_gamma_model_match(self, full_lld: str) -> None:
        """Gamma model section extracted correctly."""
        result = extract_file_spec_section(
            full_lld, "assemblyzero/models/gamma_model.py"
        )
        assert result is not None
        assert result["match_confidence"] == 1.0
        assert "GammaModel" in result["section_body"]


class TestSplitLldIntoSections:
    """Tests for _split_lld_into_sections()."""

    def test_splits_at_heading_boundaries(self) -> None:
        """Sections are split at ## and ### boundaries."""
        content = "# Title\n\nPreamble.\n\n## A\n\nBody A.\n\n## B\n\nBody B.\n"
        sections = _split_lld_into_sections(content)
        assert len(sections) == 3
        assert sections[0][0] == "# Title"
        assert sections[1][0] == "## A"
        assert sections[2][0] == "## B"

    def test_no_headings_returns_full_content(self) -> None:
        """Content without headings returns single section."""
        content = "Just some text\nwith no headings.\n"
        sections = _split_lld_into_sections(content)
        assert len(sections) == 1
        assert sections[0][0] == ""
        assert sections[0][1] == content

    def test_section_bodies_contain_headings(self) -> None:
        """Each section body includes its own heading."""
        content = "## Section A\n\nContent A.\n\n## Section B\n\nContent B.\n"
        sections = _split_lld_into_sections(content)
        assert "## Section A" in sections[0][1]
        assert "## Section B" in sections[1][1]

    def test_section_bodies_are_contiguous(self) -> None:
        """All section bodies together reconstruct the full document."""
        content = "# Title\n\nPreamble.\n\n## A\n\nBody A.\n\n## B\n\nBody B.\n"
        sections = _split_lld_into_sections(content)
        reconstructed = "".join(body for _, body in sections)
        assert reconstructed == content

    def test_handles_triple_hash_headings(self) -> None:
        """### headings are kept within their parent ## section."""
        content = "## Parent\n\nParent body.\n\n### Child\n\nChild body.\n"
        sections = _split_lld_into_sections(content)
        assert len(sections) == 1
        assert sections[0][0] == "## Parent"
        assert "Child body." in sections[0][1]

    def test_single_heading_only(self) -> None:
        """Single # heading returns one section covering all content."""
        content = "# Only Title\n\nAll the content.\n"
        sections = _split_lld_into_sections(content)
        assert len(sections) == 1
        assert sections[0][0] == "# Only Title"
        assert sections[0][1] == content

    def test_full_lld_fixture_splits_correctly(self, full_lld: str) -> None:
        """Full LLD fixture produces multiple sections."""
        sections = _split_lld_into_sections(full_lld)
        assert len(sections) > 5

    def test_headings_matched_correctly(self) -> None:
        """Heading text is captured accurately."""
        content = "## Section for assemblyzero/services/alpha_service.py\n\nContent.\n"
        sections = _split_lld_into_sections(content)
        assert sections[0][0] == "## Section for assemblyzero/services/alpha_service.py"


class TestScoreSectionForFile:
    """Tests for _score_section_for_file()."""

    def test_exact_path_scores_1(self) -> None:
        """Exact path in section scores 1.0."""
        section = "## Section for assemblyzero/services/alpha.py\n\nDetails."
        assert _score_section_for_file(section, "assemblyzero/services/alpha.py") == 1.0

    def test_stem_match_scores_0_6(self) -> None:
        """Filename stem match scores 0.6."""
        section = "## Alpha Module\n\nalpha details and alpha reference."
        assert _score_section_for_file(section, "some/path/alpha.py") == 0.6

    def test_directory_match_scores_0_3(self) -> None:
        """Directory path match scores 0.3."""
        section = "## Overview of assemblyzero/services/ directory.\n\nGeneral."
        assert (
            _score_section_for_file(
                section, "assemblyzero/services/nonexistent_file.py"
            )
            == 0.3
        )

    def test_no_match_scores_0(self) -> None:
        """No match scores 0.0."""
        section = "## Security Notes\n\nNothing relevant here."
        assert (
            _score_section_for_file(section, "assemblyzero/services/alpha.py") == 0.0
        )

    def test_exact_match_beats_stem_match(self) -> None:
        """Exact path match (1.0) outscores stem match (0.6)."""
        exact_section = "## Section for assemblyzero/foo/bar.py\n\nContent."
        stem_section = "## Bar Module\n\nbar.py docs."
        exact_score = _score_section_for_file(exact_section, "assemblyzero/foo/bar.py")
        stem_score = _score_section_for_file(stem_section, "assemblyzero/foo/bar.py")
        assert exact_score > stem_score

    def test_stem_match_beats_directory_match(self) -> None:
        """Stem match (0.6) outscores directory match (0.3)."""
        stem_section = "## Alpha Module\n\nalpha_service referenced here."
        dir_section = "## Overview of assemblyzero/services/\n\nServices overview."
        stem_score = _score_section_for_file(
            stem_section, "assemblyzero/services/alpha_service.py"
        )
        dir_score = _score_section_for_file(
            dir_section, "assemblyzero/services/alpha_service.py"
        )
        assert stem_score > dir_score

    def test_backslash_path_normalized(self) -> None:
        """Windows-style backslash paths are normalized before scoring."""
        section = "## Section for assemblyzero/services/alpha.py\n\nDetails."
        # Target file with backslashes should still match
        score = _score_section_for_file(section, "assemblyzero\\services\\alpha.py")
        assert score == 1.0

    def test_empty_section_scores_0(self) -> None:
        """Empty section text scores 0.0."""
        assert _score_section_for_file("", "assemblyzero/services/alpha.py") == 0.0

    def test_padding_section_scores_0_for_file(self) -> None:
        """Padding sections with no file references score 0.0."""
        section = "## Padding Section Alpha\n\nLorem ipsum dolor sit amet."
        assert (
            _score_section_for_file(section, "assemblyzero/services/alpha_service.py")
            == 0.0
        )