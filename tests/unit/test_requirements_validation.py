"""Tests for requirements workflow validation gates.

Issue #235: Mechanical LLD validation gates to catch structural issues.
"""

import pytest

from agentos.workflows.requirements.nodes.finalize import validate_lld_final
from agentos.workflows.requirements.nodes.generate_draft import validate_draft_structure


class TestValidateDraftStructure:
    """Tests for validate_draft_structure function (Gate 1)."""

    def test_catches_unchecked_question(self):
        """Test that unchecked open questions are caught."""
        content = """# LLD-123

## Open Questions

- [ ] Unresolved question
- [x] Resolved question
"""
        result = validate_draft_structure(content)
        assert result is not None
        assert "1 unresolved" in result
        assert "BLOCKED" in result

    def test_catches_multiple_unchecked(self):
        """Test counting multiple unchecked items."""
        content = """# LLD-123

## Open Questions

- [ ] First unresolved
- [ ] Second unresolved
- [x] Resolved
- [ ] Third unresolved
"""
        result = validate_draft_structure(content)
        assert result is not None
        assert "3 unresolved" in result

    def test_passes_all_checked(self):
        """Test that all checked items pass validation."""
        content = """# LLD-123

## Open Questions

- [x] Resolved question 1
- [x] Resolved question 2
"""
        result = validate_draft_structure(content)
        assert result is None

    def test_passes_no_open_questions_section(self):
        """Test that content without open questions passes."""
        content = """# LLD-123

## Implementation

Just some implementation details.
"""
        result = validate_draft_structure(content)
        assert result is None

    def test_passes_empty_content(self):
        """Test that empty content passes (edge case)."""
        result = validate_draft_structure("")
        assert result is None

    def test_unchecked_in_any_section(self):
        """Test that unchecked items anywhere are caught."""
        content = """# LLD-123

## Tasks

- [ ] Task not done
"""
        result = validate_draft_structure(content)
        assert result is not None
        assert "1 unresolved" in result


class TestValidateLldFinal:
    """Tests for validate_lld_final function (Gate 2)."""

    def test_catches_unchecked_question(self):
        """Test that unchecked open questions are caught."""
        content = """# LLD-123

## Open Questions

- [ ] Still unresolved
"""
        errors = validate_lld_final(content)
        assert len(errors) == 1
        assert "open questions" in errors[0].lower()

    def test_catches_todo_in_table(self):
        """Test that TODO in table cell is caught."""
        content = """# LLD-123

| Status | Description |
|--------|-------------|
| TODO   | Need to fill |
"""
        errors = validate_lld_final(content)
        assert len(errors) == 1
        assert "TODO" in errors[0]

    def test_catches_todo_with_spacing(self):
        """Test TODO with various spacing in table."""
        content = """| Status |
|  TODO  |"""
        errors = validate_lld_final(content)
        assert len(errors) == 1
        assert "TODO" in errors[0]

    def test_catches_multiple_issues(self):
        """Test catching both unchecked and TODO."""
        content = """# LLD-123

- [ ] Unresolved

| Status |
| TODO   |
"""
        errors = validate_lld_final(content)
        assert len(errors) == 2

    def test_passes_clean_lld(self):
        """Test that clean LLD passes validation."""
        content = """# LLD-123

## Open Questions

- [x] Resolved question

## Implementation

| Status    | Description |
|-----------|-------------|
| Completed | Done        |
"""
        errors = validate_lld_final(content)
        assert len(errors) == 0

    def test_passes_empty_content(self):
        """Test that empty content passes."""
        errors = validate_lld_final("")
        assert len(errors) == 0

    def test_todo_in_prose_not_caught(self):
        """Test that TODO in regular prose is not caught (only in tables)."""
        content = """# LLD-123

TODO: This is a note in prose, not a table cell.
"""
        errors = validate_lld_final(content)
        assert len(errors) == 0

    def test_checked_items_pass(self):
        """Test that checked checkbox items pass."""
        content = """# LLD-123

- [x] Done item 1
- [x] Done item 2
"""
        errors = validate_lld_final(content)
        assert len(errors) == 0
