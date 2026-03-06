"""Tests for load_lld.py Section 10 enforcement (Issue #608).

Validates that:
- Section 10 is required for test plan extraction
- Legacy Section 9 is explicitly rejected with migration guidance
- Whitespace variations around the period are tolerated
- validate_spec_structure and extract_test_plan_section enforce the new rules
"""

import pytest

from assemblyzero.workflows.testing.nodes.load_lld import (
    WorkflowParsingError,
    extract_test_plan_section,
    validate_spec_structure,
)


# ---------------------------------------------------------------------------
# Fixtures: spec content variants
# ---------------------------------------------------------------------------

SECTION_10_STANDARD = """\
## 1. Overview

Some overview text.

## 10. Test Mapping

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | Standard Section 10 parsing | Success |

## 11. Implementation Notes

None.
"""

SECTION_10_VERIFICATION_TESTING = """\
## 1. Overview

Overview.

## 10. Verification & Testing

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T001 | Verification test | Pass |
"""

SECTION_10_TEST_PLAN = """\
## 1. Overview

Overview.

## 10. Test Plan

### test_something
Verify something works.
"""

SECTION_10_WHITESPACE_VARIATION = """\
## 1. Overview

Overview.

## 10 . Test Mapping

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | Whitespace around period | Success |
"""

SECTION_10_EXTRA_WHITESPACE = """\
## 1. Overview

Overview.

##  10  .  Test Mapping

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | Extra whitespace | Success |
"""

LEGACY_SECTION_9 = """\
## 1. Overview

Overview.

## 9. Test Mapping

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T001 | Legacy test | Pass |
"""

LEGACY_SECTION_9_VERIFICATION = """\
## 1. Overview

Overview.

## 9. Verification & Testing

Some test content.
"""

NO_TEST_SECTION = """\
## 1. Overview

Overview.

## 2. Files to Implement

Some files.
"""

SECTION_10_INSIDE_CODE_FENCE = """\
## 1. Overview

Overview.

```python
heading = "## 10. Test Mapping"
print(heading)
```

## 3. Requirements

Stuff.
"""

BOTH_SECTIONS_9_AND_10 = """\
## 1. Overview

Overview.

## 9. Test Mapping

Old content.

## 10. Test Mapping

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | New content | Success |
"""


# ---------------------------------------------------------------------------
# T010: Standard Section 10 parsing
# ---------------------------------------------------------------------------

class TestValidateSpecStructure:
    """Tests for validate_spec_structure()."""

    def test_t010_standard_section_10(self):
        """Standard Section 10 parsing succeeds."""
        # Should not raise
        validate_spec_structure(SECTION_10_STANDARD)

    def test_section_10_verification_testing(self):
        """Section 10 with 'Verification & Testing' heading succeeds."""
        validate_spec_structure(SECTION_10_VERIFICATION_TESTING)

    def test_section_10_test_plan(self):
        """Section 10 with 'Test Plan' heading succeeds."""
        validate_spec_structure(SECTION_10_TEST_PLAN)

    def test_section_10_whitespace_around_period(self):
        """Section 10 with whitespace around the period succeeds."""
        validate_spec_structure(SECTION_10_WHITESPACE_VARIATION)

    def test_section_10_extra_whitespace(self):
        """Section 10 with extra whitespace succeeds."""
        validate_spec_structure(SECTION_10_EXTRA_WHITESPACE)

    def test_legacy_section_9_rejected(self):
        """Legacy Section 9 'Test Mapping' is rejected with migration message."""
        with pytest.raises(WorkflowParsingError, match="Legacy Section 9"):
            validate_spec_structure(LEGACY_SECTION_9)

    def test_legacy_section_9_verification_rejected(self):
        """Legacy Section 9 'Verification & Testing' is rejected."""
        with pytest.raises(WorkflowParsingError, match="Legacy Section 9"):
            validate_spec_structure(LEGACY_SECTION_9_VERIFICATION)

    def test_legacy_section_9_error_mentions_section_10(self):
        """Rejection message directs authors to Section 10."""
        with pytest.raises(WorkflowParsingError, match="Section 10"):
            validate_spec_structure(LEGACY_SECTION_9)

    def test_no_test_section_rejected(self):
        """Spec with no test section at all is rejected."""
        with pytest.raises(WorkflowParsingError, match="Expected.*10.*Test Mapping"):
            validate_spec_structure(NO_TEST_SECTION)

    def test_both_sections_9_and_10_rejects_section_9(self):
        """If both Section 9 and 10 exist, Section 9 is still rejected."""
        with pytest.raises(WorkflowParsingError, match="Legacy Section 9"):
            validate_spec_structure(BOTH_SECTIONS_9_AND_10)


class TestExtractTestPlanSection:
    """Tests for extract_test_plan_section()."""

    def test_t010_extracts_standard_section_10(self):
        """Standard Section 10 table content is extracted correctly."""
        result = extract_test_plan_section(SECTION_10_STANDARD)
        assert "T010" in result
        assert "Standard Section 10 parsing" in result
        assert "Success" in result

    def test_extracts_until_next_h2(self):
        """Extraction stops at the next ## heading."""
        result = extract_test_plan_section(SECTION_10_STANDARD)
        assert "Implementation Notes" not in result

    def test_extracts_verification_testing(self):
        """Extracts content from '## 10. Verification & Testing'."""
        result = extract_test_plan_section(SECTION_10_VERIFICATION_TESTING)
        assert "T001" in result

    def test_extracts_test_plan_heading(self):
        """Extracts content from '## 10. Test Plan'."""
        result = extract_test_plan_section(SECTION_10_TEST_PLAN)
        assert "test_something" in result

    def test_extracts_with_whitespace_variation(self):
        """Extracts content when period has surrounding whitespace."""
        result = extract_test_plan_section(SECTION_10_WHITESPACE_VARIATION)
        assert "T010" in result

    def test_rejects_legacy_section_9(self):
        """extract_test_plan_section raises on legacy Section 9."""
        with pytest.raises(WorkflowParsingError, match="Legacy Section 9"):
            extract_test_plan_section(LEGACY_SECTION_9)

    def test_rejects_missing_section(self):
        """extract_test_plan_section raises when no test section exists."""
        with pytest.raises(WorkflowParsingError, match="Expected.*10.*Test Mapping"):
            extract_test_plan_section(NO_TEST_SECTION)

    def test_ignores_section_10_inside_code_fence(self):
        """Section 10 heading inside a code fence is not matched."""
        with pytest.raises(WorkflowParsingError, match="Expected.*10.*Test Mapping"):
            extract_test_plan_section(SECTION_10_INSIDE_CODE_FENCE)

    def test_extracted_content_is_stripped(self):
        """Extracted content has leading/trailing whitespace removed."""
        result = extract_test_plan_section(SECTION_10_STANDARD)
        assert result == result.strip()