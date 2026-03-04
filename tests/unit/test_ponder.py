"""Unit tests for Ponder Stibbons auto-fix node and rules.

Issue #307: Tests for mechanical auto-fix rules and the Ponder node.
"""

import pytest
from pathlib import Path

from assemblyzero.workflows.requirements.nodes.ponder_rules import (
    AutoFix,
    apply_all_rules,
    fix_title_issue_number,
    fix_section_heading_format,
    fix_trailing_whitespace,
    fix_missing_blank_before_heading,
    fix_directory_ordering,
)
from assemblyzero.workflows.requirements.nodes.ponder import (
    ponder_stibbons_node,
)


class TestFixTitleIssueNumber:
    """Tests for title issue number auto-fix."""

    def test_fixes_wrong_number(self):
        draft = "# 199 - Feature Name\n\nContent here."
        fixed, fixes = fix_title_issue_number(draft, {"issue_number": 99})
        assert "# 99 -" in fixed
        assert len(fixes) == 1
        assert fixes[0].rule == "title_issue_number"

    def test_no_change_when_correct(self):
        draft = "# 99 - Feature Name\n\nContent here."
        fixed, fixes = fix_title_issue_number(draft, {"issue_number": 99})
        assert fixed == draft
        assert len(fixes) == 0

    def test_no_change_without_issue_number(self):
        draft = "# 199 - Feature Name\n\nContent here."
        fixed, fixes = fix_title_issue_number(draft, {})
        assert fixed == draft
        assert len(fixes) == 0

    def test_no_change_without_h1(self):
        draft = "No heading here.\n\nJust content."
        fixed, fixes = fix_title_issue_number(draft, {"issue_number": 99})
        assert fixed == draft
        assert len(fixes) == 0

    def test_handles_em_dash_separator(self):
        draft = "# 500 \u2014 Big Feature\n\nContent."
        fixed, fixes = fix_title_issue_number(draft, {"issue_number": 50})
        assert "# 50 \u2014" in fixed
        assert len(fixes) == 1

    def test_handles_colon_separator(self):
        draft = "# 500: Big Feature\n\nContent."
        fixed, fixes = fix_title_issue_number(draft, {"issue_number": 50})
        assert "# 50:" in fixed
        assert len(fixes) == 1


class TestFixSectionHeadingFormat:
    """Tests for section heading format normalization."""

    def test_fixes_triple_hash_to_double(self):
        draft = "### 11 Section Title\n"
        fixed, fixes = fix_section_heading_format(draft, {})
        assert fixed.startswith("## 11.")
        assert len(fixes) > 0

    def test_adds_missing_dot(self):
        draft = "## 11 Section Title\n"
        fixed, fixes = fix_section_heading_format(draft, {})
        assert "## 11." in fixed
        assert len(fixes) > 0

    def test_no_change_when_correct(self):
        draft = "## 11. Section Title\n"
        fixed, fixes = fix_section_heading_format(draft, {})
        assert fixed == draft
        assert len(fixes) == 0

    def test_subsection_uses_triple_hash(self):
        draft = "## 2.1 Subsection\n"
        fixed, fixes = fix_section_heading_format(draft, {})
        assert fixed.startswith("### 2.1")
        assert len(fixes) > 0

    def test_subsection_correct_already(self):
        draft = "### 2.1 Subsection\n"
        fixed, fixes = fix_section_heading_format(draft, {})
        assert fixed == draft
        assert len(fixes) == 0

    def test_multiple_headings_fixed(self):
        draft = "### 1 First\n\nContent\n\n### 2 Second\n"
        fixed, fixes = fix_section_heading_format(draft, {})
        assert "## 1." in fixed
        assert "## 2." in fixed
        assert len(fixes) == 2


class TestFixTrailingWhitespace:
    """Tests for trailing whitespace removal."""

    def test_strips_trailing_spaces(self):
        draft = "Line one   \nLine two  \nLine three\n"
        fixed, fixes = fix_trailing_whitespace(draft, {})
        assert "   \n" not in fixed
        assert "  \n" not in fixed
        assert len(fixes) == 1
        assert "2 lines" in fixes[0].description

    def test_no_change_when_clean(self):
        draft = "Line one\nLine two\nLine three\n"
        fixed, fixes = fix_trailing_whitespace(draft, {})
        assert fixed == draft
        assert len(fixes) == 0


class TestFixMissingBlankBeforeHeading:
    """Tests for blank line insertion before headings."""

    def test_inserts_blank_line(self):
        draft = "Some content\n## 2. Section\n"
        fixed, fixes = fix_missing_blank_before_heading(draft, {})
        assert "\n\n## 2. Section" in fixed
        assert len(fixes) == 1

    def test_no_change_when_blank_exists(self):
        draft = "Some content\n\n## 2. Section\n"
        fixed, fixes = fix_missing_blank_before_heading(draft, {})
        assert fixed == draft
        assert len(fixes) == 0

    def test_no_change_for_first_heading(self):
        draft = "## 1. First Section\n\nContent\n"
        fixed, fixes = fix_missing_blank_before_heading(draft, {})
        # First line is a heading — no blank needed before it
        assert fixed == draft
        assert len(fixes) == 0


class TestApplyAllRules:
    """Tests for the rule registry."""

    def test_applies_multiple_rules(self):
        draft = "# 999 - Feature   \nContent\n### 3 Section\n"
        ctx = {"issue_number": 99}
        fixed, fixes = apply_all_rules(draft, ctx)
        # Title fixed
        assert "# 99 -" in fixed
        # Trailing whitespace fixed
        assert "   \n" not in fixed
        # Section heading fixed
        assert "## 3." in fixed
        assert len(fixes) >= 3

    def test_no_fixes_on_clean_draft(self):
        draft = "# 99 - Feature\n\n## 1. Section\n\nContent.\n"
        fixed, fixes = apply_all_rules(draft, {"issue_number": 99})
        assert fixed == draft
        assert len(fixes) == 0


class TestPonderStibbonsNode:
    """Tests for the Ponder node function."""

    def test_no_draft_skips(self):
        state = {"current_draft": "", "iteration_count": 5}
        result = ponder_stibbons_node(state)
        assert result["iteration_count"] == 6
        assert "current_draft" not in result

    def test_clean_draft_no_changes(self):
        state = {
            "current_draft": "# 99 - Feature\n\n## 1. Section\n\nContent.\n",
            "issue_number": 99,
            "iteration_count": 3,
        }
        result = ponder_stibbons_node(state)
        assert result["iteration_count"] == 4
        assert "current_draft" not in result

    def test_fixes_applied_to_draft(self):
        state = {
            "current_draft": "# 999 - Feature\n\nContent\n",
            "issue_number": 99,
            "iteration_count": 0,
        }
        result = ponder_stibbons_node(state)
        assert result["iteration_count"] == 1
        assert "# 99 -" in result["current_draft"]

    def test_saves_to_lineage(self, tmp_path):
        lineage = tmp_path / "lineage"
        state = {
            "current_draft": "# 999 - Feature\n\nContent\n",
            "issue_number": 99,
            "iteration_count": 0,
            "lineage_path": str(lineage),
            "file_counter": 5,
            "draft_number": 2,
        }
        result = ponder_stibbons_node(state)
        assert result["iteration_count"] == 1
        # Check lineage file was created
        fix_files = list(lineage.glob("*ponder*"))
        assert len(fix_files) == 1
        content = fix_files[0].read_text(encoding="utf-8")
        assert "title_issue_number" in content

    def test_persists_draft_to_disk(self, tmp_path):
        draft_file = tmp_path / "draft.md"
        draft_file.write_text("# 999 - Feature\n\nContent\n", encoding="utf-8")
        state = {
            "current_draft": "# 999 - Feature\n\nContent\n",
            "issue_number": 99,
            "iteration_count": 0,
            "current_draft_path": str(draft_file),
        }
        result = ponder_stibbons_node(state)
        saved = draft_file.read_text(encoding="utf-8")
        assert "# 99 -" in saved
        assert saved == result["current_draft"]


class TestFixDirectoryOrdering:
    """Tests for directory ordering auto-fix rule (Issue #566)."""

    def test_moves_directories_before_files(self):
        draft = (
            "### 2.1 Proposed Changes\n"
            "| Path | Change Type |\n"
            "|------|-------------|\n"
            "| src/foo.py | Modify file |\n"
            "| src/bar/ | Create directory |\n"
            "| src/baz.py | Create file |\n"
        )
        fixed, fixes = fix_directory_ordering(draft, {"workflow_type": "lld"})
        assert len(fixes) == 1
        assert fixes[0].rule == "directory_ordering"
        # Directory row should come before file rows
        dir_pos = fixed.index("directory")
        file_pos = fixed.index("foo.py")
        assert dir_pos < file_pos

    def test_no_change_when_already_ordered(self):
        draft = (
            "### 2.1 Proposed Changes\n"
            "| Path | Change Type |\n"
            "|------|-------------|\n"
            "| src/bar/ | Create directory |\n"
            "| src/foo.py | Modify file |\n"
            "| src/baz.py | Create file |\n"
        )
        fixed, fixes = fix_directory_ordering(draft, {"workflow_type": "lld"})
        assert fixed == draft
        assert len(fixes) == 0

    def test_no_change_for_issue_workflow(self):
        draft = (
            "### 2.1 Proposed Changes\n"
            "| Path | Change Type |\n"
            "|------|-------------|\n"
            "| src/foo.py | Modify file |\n"
            "| src/bar/ | Create directory |\n"
        )
        fixed, fixes = fix_directory_ordering(draft, {"workflow_type": "issue"})
        assert fixed == draft
        assert len(fixes) == 0

    def test_no_change_without_section_21(self):
        draft = (
            "### 2.2 Other Section\n"
            "| Path | Change Type |\n"
            "|------|-------------|\n"
            "| src/foo.py | Modify file |\n"
        )
        fixed, fixes = fix_directory_ordering(draft, {"workflow_type": "lld"})
        assert fixed == draft
        assert len(fixes) == 0

    def test_no_change_when_no_directories(self):
        draft = (
            "### 2.1 Proposed Changes\n"
            "| Path | Change Type |\n"
            "|------|-------------|\n"
            "| src/foo.py | Modify file |\n"
            "| src/bar.py | Create file |\n"
        )
        fixed, fixes = fix_directory_ordering(draft, {"workflow_type": "lld"})
        assert fixed == draft
        assert len(fixes) == 0
