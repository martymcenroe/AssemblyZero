

```python
"""Unit tests for load_lld mechanical parser.

Issue #608: Verify Section 10 extraction and Section 9 rejection.
"""

import pytest
from pathlib import Path
from assemblyzero.workflows.testing.nodes.load_lld import (
    extract_test_plan_section,
    validate_spec_structure,
    WorkflowParsingError,
)


def test_extract_valid_lld():
    """T020: Parse valid LLD to extract Section 10 (Verification & Testing)."""
    content = "## 10. Verification & Testing\nSome testing content\n## 11. Next"
    result = extract_test_plan_section(content)
    assert "Some testing content" in result


def test_extract_valid_spec():
    """T030: Parse valid Spec to extract Section 10 (Test Mapping)."""
    content = "## 10. Test Mapping\nSome test mapping content\n## 11. Next"
    result = extract_test_plan_section(content)
    assert "Some test mapping content" in result


def test_reject_legacy_section_9():
    """T040, T045: Reject invalid Spec using Section 9."""
    content = "## 9. Test Mapping\nOld content"
    with pytest.raises(WorkflowParsingError) as exc:
        extract_test_plan_section(content)
    assert "Expected: ## 10. Test Mapping" in str(exc.value)


def test_validate_rejects_section_9():
    """T045: validate_spec_structure raises WorkflowParsingError for Section 9."""
    content = "## 9. Test Mapping\nBody"
    with pytest.raises(WorkflowParsingError) as exc:
        validate_spec_structure(content)
    assert "Expected: ## 10. Test Mapping" in str(exc.value)


def test_extract_whitespace_tolerance():
    """T050: Parse Spec with whitespace via fixture."""
    fixture_path = Path("tests/fixtures/lld_tracking/spec_whitespace.md")
    # Use inline content if fixture doesn't exist yet during early tests
    content = (
        fixture_path.read_text()
        if fixture_path.exists()
        else "## 10 . Test Mapping\nWhitespace content\n## 11. Next"
    )
    result = extract_test_plan_section(content)
    assert "T010" in result or "Whitespace content" in result


def test_0701_template_valid():
    """T010: Verify Spec Template 0701 contains ## 10. Test Mapping."""
    template_path = Path("docs/standards/0701-implementation-spec-template.md")
    if template_path.exists():
        content = template_path.read_text()
        # Should not raise
        validate_spec_structure(content)


def test_extract_returns_body_only_for_verification():
    """T020 extended: extract_test_plan_section returns just the body text."""
    content = "## 10. Verification & Testing\nBody\n## 11. Notes"
    result = extract_test_plan_section(content)
    assert result == "Body"


def test_extract_returns_body_only_for_test_mapping():
    """T030 extended: extract_test_plan_section returns just the body text."""
    content = "## 10. Test Mapping\nBody\n## 11. Notes"
    result = extract_test_plan_section(content)
    assert result == "Body"


def test_extract_section_10_at_end_of_file():
    """Section 10 at EOF without a following heading still extracts content."""
    content = "## 10. Test Mapping\nFinal content here"
    result = extract_test_plan_section(content)
    assert "Final content here" in result


def test_no_section_10_raises():
    """Content with no Section 10 at all raises WorkflowParsingError."""
    content = "## 1. Overview\nSome overview\n## 2. Details\nSome details"
    with pytest.raises(WorkflowParsingError) as exc:
        extract_test_plan_section(content)
    assert "Expected: ## 10. Test Mapping" in str(exc.value)


def test_whitespace_inline_tolerance():
    """Whitespace between number and period is tolerated."""
    content = "## 10 . Test Mapping\nWhitespace content\n## 11. Next"
    result = extract_test_plan_section(content)
    assert "Whitespace content" in result


def test_validate_spec_structure_passes_section_10():
    """validate_spec_structure returns None for valid Section 10."""
    content = "## 10. Test Mapping\nBody"
    result = validate_spec_structure(content)
    assert result is None
```