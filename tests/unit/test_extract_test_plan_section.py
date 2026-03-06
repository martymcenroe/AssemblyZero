"""Tests for extracting the test plan section from LLD/Spec (Issue #608)."""

import pytest
from assemblyzero.workflows.testing.nodes.load_lld import (
    extract_test_plan_section,
    WorkflowParsingError
)

SECTION_10_STANDARD = """
## 10. Test Mapping

### 10.1 Test Scenarios
| ID | Scenario | Expected |
|----|----------|----------|
| 010 | Happy path | Success |
"""

SECTION_10_ALT = """
## 10. Verification & Testing

Tests:
- Case 1
"""

def test_extract_test_plan_section_success():
    """T010: Successfully extracts Section 10 content."""
    result = extract_test_plan_section(SECTION_10_STANDARD)
    assert "### 10.1 Test Scenarios" in result
    assert "Happy path" in result

def test_extract_test_plan_section_alt_header():
    """T010: Successfully extracts Section 10 with alternative header."""
    result = extract_test_plan_section(SECTION_10_ALT)
    assert "Tests:" in result

def test_no_match_returns_error():
    """T020: Raises WorkflowParsingError when no test section found."""
    content = "# Just a README\n\nNo test section here.\n"
    with pytest.raises(WorkflowParsingError, match="Expected: ## 10. Test Mapping"):
        extract_test_plan_section(content)

def test_legacy_section_9_rejected():
    """T030: Explicitly rejects legacy Section 9."""
    content = "## 9. Test Mapping\n\nSome tests here."
    with pytest.raises(WorkflowParsingError, match="Legacy Section 9 test mapping detected"):
        extract_test_plan_section(content)
