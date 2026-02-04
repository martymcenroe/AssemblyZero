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

    def test_validation_ignores_definition_of_done_checkboxes(self):
        """DoD checkboxes should not block validation.

        Issue #245: Definition of Done checkboxes are supposed to be unchecked
        until implementation is complete.
        """
        content = """# LLD-123

## 1. Context

### Open Questions

- [x] Resolved question

## 12. Definition of Done

- [ ] All tests written before implementation
- [ ] Implementation complete
- [ ] Documentation updated
"""
        result = validate_draft_structure(content)
        assert result is None  # Should pass - no unchecked in Open Questions

    def test_validation_catches_unchecked_open_questions(self):
        """Unchecked Open Questions should block.

        Issue #245: Only Open Questions section should be checked.
        """
        content = """# LLD-123

## 1. Context

### Open Questions

- [ ] Unresolved question

## 12. Definition of Done

- [ ] All tests written
"""
        result = validate_draft_structure(content)
        assert result is not None
        assert "1 unresolved" in result  # Should block - 1 unchecked Open Question

    def test_validation_only_checks_open_questions_section(self):
        """Only the Open Questions section matters.

        Issue #245: Random checkboxes in other sections should be ignored.
        """
        content = """# LLD-123

## 1. Context

### Open Questions

- [x] All resolved

## 5. Implementation Tasks

- [ ] Random checkbox here
- [ ] Another task checkbox

## 12. Definition of Done

- [ ] Tests written
"""
        result = validate_draft_structure(content)
        assert result is None  # Pass - Open Questions are all checked


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
        """Test catching both unchecked open question and TODO."""
        content = """# LLD-123

## Open Questions

- [ ] Unresolved

## Implementation

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

    def test_final_ignores_definition_of_done_checkboxes(self):
        """DoD checkboxes should not block final validation.

        Issue #245: Definition of Done checkboxes are supposed to be unchecked
        until implementation is complete.
        """
        content = """# LLD-123

## 1. Context

### Open Questions

- [x] Resolved question

## 12. Definition of Done

- [ ] All tests written
- [ ] Implementation complete
"""
        errors = validate_lld_final(content)
        # Should pass - only TODO in tables and unchecked Open Questions matter
        open_question_errors = [e for e in errors if "open questions" in e.lower()]
        assert len(open_question_errors) == 0

    def test_final_catches_unchecked_open_questions(self):
        """Unchecked Open Questions should block final validation.

        Issue #245: Only Open Questions section should be checked.
        """
        content = """# LLD-123

## 1. Context

### Open Questions

- [ ] Unresolved question

## 12. Definition of Done

- [ ] All tests written
"""
        errors = validate_lld_final(content)
        assert len(errors) == 1
        assert "open questions" in errors[0].lower()

    def test_skips_open_questions_when_resolved_flag_set(self):
        """Issue #259: Skip open questions check when reviewer resolved them.

        When the review node determines that Gemini resolved all open questions
        in the verdict, we should trust that determination and skip the check.
        """
        content = """# LLD-123

## Open Questions

- [ ] Question that Gemini answered in verdict but draft wasn't updated
"""
        # Default behavior: catches unchecked questions
        errors_default = validate_lld_final(content)
        assert len(errors_default) == 1
        assert "open questions" in errors_default[0].lower()

        # With flag: skips open questions check
        errors_resolved = validate_lld_final(content, open_questions_resolved=True)
        assert len(errors_resolved) == 0

    def test_still_catches_todo_when_open_questions_resolved(self):
        """Issue #259: TODO check should still work when open questions are resolved.

        Even when we skip the open questions check, we should still catch
        TODO in table cells.
        """
        content = """# LLD-123

## Open Questions

- [ ] Resolved by Gemini but not in draft

## Status

| Task   | Status |
|--------|--------|
| Part 1 | TODO   |
"""
        # With open_questions_resolved=True, should skip open questions
        # but still catch TODO
        errors = validate_lld_final(content, open_questions_resolved=True)
        assert len(errors) == 1
        assert "TODO" in errors[0]

    def test_catches_both_when_not_resolved(self):
        """Verify both checks work when open_questions_resolved=False."""
        content = """# LLD-123

## Open Questions

- [ ] Unresolved

| Status |
|--------|
| TODO   |
"""
        errors = validate_lld_final(content, open_questions_resolved=False)
        assert len(errors) == 2
