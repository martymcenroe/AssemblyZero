# File: tests/test_issue_177.py

```python
"""Test file for Issue #177: LLD Approval Verification Gate.

Tests that the implementation workflow gate correctly verifies LLD approvals
and rejects false approvals where status was modified without genuine review.

Reference: LLD-177 - Implementation workflow gate to verify LLD was genuinely approved
"""

import pytest
from pathlib import Path
import tempfile

from agentos.utils.lld_verification import (
    LLDVerificationResult,
    LLDVerificationError,
    has_gemini_approved_footer,
    extract_review_log_verdicts,
    detect_false_approval,
    verify_lld_approval,
    validate_lld_path,
    run_verification_gate,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def lld_genuine_footer_approved():
    """LLD with genuine Gemini APPROVED footer."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177
* **Status:** Approved (gemini-3-pro-preview, 2026-02-02)

## 2. Proposed Changes

Some content here.

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-02-02 | APPROVED | gemini-3-pro-preview |

**Final Status:** APPROVED

<sub>**Gemini Review:** APPROVED | **Model:** gemini-3-pro-preview | **Date:** 2026-02-02</sub>
"""


@pytest.fixture
def lld_review_log_approved():
    """LLD with APPROVED as last verdict in review log (no footer)."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## 2. Proposed Changes

Some content here.

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Gemini #1 | 2026-01-30 | REVISE | Missing tests |
| Gemini #2 | 2026-02-01 | REVISE | Security concern |
| Gemini #3 | 2026-02-02 | APPROVED | gemini-3-pro-preview |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_false_approval_revise():
    """LLD with REVISE verdict but APPROVED status (false approval)."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## 2. Proposed Changes

Some content here.

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Gemini #1 | 2026-02-02 | REVISE | Major issues found |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_false_approval_pending():
    """LLD with PENDING verdict but APPROVED status (false approval)."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## 2. Proposed Changes

Some content here.

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-02-02 | PENDING | Awaiting review |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_no_approval():
    """LLD with no approval markers at all."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## 2. Proposed Changes

Some content here.

## 3. Requirements

Some requirements.
"""


@pytest.fixture
def lld_multiple_reviews_approved():
    """LLD with multiple reviews, last is APPROVED."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Gemini #1 | 2026-01-28 | REVISE | Missing section |
| Gemini #2 | 2026-01-30 | REVISE | Security issues |
| Gemini #3 | 2026-02-02 | APPROVED | All issues resolved |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_multiple_reviews_revise():
    """LLD with multiple reviews, last is REVISE."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Gemini #1 | 2026-01-28 | APPROVED | All good |
| Gemini #2 | 2026-02-02 | REVISE | New requirements found |

**Final Status:** REVISE_REQUIRED
"""


@pytest.fixture
def lld_empty_review_log():
    """LLD with review log section but no entries."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|

**Final Status:** PENDING
"""


@pytest.fixture
def lld_no_final_status():
    """LLD missing Final Status line entirely."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Gemini #1 | 2026-02-02 | REVISE | Issues found |
"""


@pytest.fixture
def test_client():
    """Test client for API calls."""
    yield None


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for path validation tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# Unit Tests
# =============================================================================

def test_010(lld_genuine_footer_approved):
    """
    Genuine footer approval | Auto | LLD with `<sub>**Gemini Review:**
    APPROVED...` | is_valid=True, confidence="high" | Returns pass
    """
    # TDD: Arrange
    lld_content = lld_genuine_footer_approved

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is True, "Should be valid with genuine footer"
    assert result["confidence"] == "high", "Footer gives high confidence"
    assert result["approval_source"] == "footer", "Source should be footer"
    assert result["error_type"] is None, "No error for valid approval"


def test_020(lld_review_log_approved):
    """
    Review log approval (final) | Auto | LLD with `\\ | APPROVED \\ | ` as
    last row | is_valid=True, confidence="medium" | Returns pass
    """
    # TDD: Arrange
    lld_content = lld_review_log_approved

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is True, "Should be valid with review log approval"
    assert result["confidence"] == "medium", "Review log gives medium confidence"
    assert result["approval_source"] == "review_log", "Source should be review_log"
    assert result["error_type"] is None, "No error for valid approval"


def test_030(lld_false_approval_revise):
    """
    False approval - REVISE then APPROVED status | Auto | Review shows
    REVISE, status APPROVED | is_valid=False, error_type="forgery" |
    Returns fail with "FALSE APPROVAL"
    """
    # TDD: Arrange
    lld_content = lld_false_approval_revise

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False, "Should be invalid - false approval"
    assert result["error_type"] == "forgery", "Error type should be forgery"
    assert "FALSE APPROVAL" in result["reason"], "Reason should mention false approval"
    assert result["last_verdict"] == "REVISE", "Should capture last verdict as REVISE"


def test_040(lld_false_approval_pending):
    """
    False approval - PENDING then APPROVED status | Auto | Review shows
    PENDING, status APPROVED | is_valid=False, error_type="forgery" |
    Returns fail with "FALSE APPROVAL"
    """
    # TDD: Arrange
    lld_content = lld_false_approval_pending

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False, "Should be invalid - false approval"
    assert result["error_type"] == "forgery", "Error type should be forgery"
    assert "FALSE APPROVAL" in result["reason"], "Reason should mention false approval"
    assert result["last_verdict"] == "PENDING", "Should capture last verdict as PENDING"


def test_050(lld_no_approval):
    """
    No approval evidence | Auto | LLD with no approval markers |
    is_valid=False, error_type="not_approved" | Returns fail
    """
    # TDD: Arrange
    lld_content = lld_no_approval

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False, "Should be invalid - no approval"
    assert result["error_type"] == "not_approved", "Error type should be not_approved"
    assert result["approval_source"] is None, "No approval source"


def test_060(lld_multiple_reviews_approved):
    """
    Multiple reviews, last is APPROVED | Auto | 3 reviews: REVISE,
    REVISE, APPROVED | is_valid=True | Returns pass
    """
    # TDD: Arrange
    lld_content = lld_multiple_reviews_approved

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is True, "Should be valid when last review is APPROVED"
    assert result["last_verdict"] == "APPROVED", "Last verdict should be APPROVED"


def test_070(lld_multiple_reviews_revise):
    """
    Multiple reviews, last is REVISE | Auto | 3 reviews: APPROVED, REVISE
    | is_valid=False | Returns fail
    """
    # TDD: Arrange
    lld_content = lld_multiple_reviews_revise

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False, "Should be invalid when last review is REVISE"
    assert result["last_verdict"] == "REVISE", "Last verdict should be REVISE"


def test_080(lld_empty_review_log):
    """
    Empty review log | Auto | Review log section exists but empty |
    is_valid=False, error_type="not_approved" | Returns fail
    """
    # TDD: Arrange
    lld_content = lld_empty_review_log

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False, "Should be invalid with empty review log"
    assert result["error_type"] == "not_approved", "Error type should be not_approved"
    assert result["last_verdict"] is None, "No verdict in empty log"


def test_110(temp_project_dir):
    """
    Path traversal attempt | Auto | Path outside project root | Raises
    exception before read | Security check blocks
    """
    # TDD: Arrange
    # Create a path outside the temp project directory
    outside_path = Path("/etc/passwd")  # Classic path traversal target
    
    # TDD: Act & Assert
    with pytest.raises(LLDVerificationError) as exc_info:
        validate_lld_path(outside_path, temp_project_dir)
    
    assert exc_info.value.error_type == "security", "Should be security error"
    assert "traversal" in exc_info.value.reason.lower() or "outside" in exc_info.value.reason.lower()


def test_120(lld_no_final_status):
    """
    Status APPROVED but no Final Status line | Auto | LLD missing Final
    Status section | is_valid=False, error_type="not_approved" | Returns
    fail
    """
    # TDD: Arrange
    lld_content = lld_no_final_status

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False, "Should be invalid without final status"
    assert result["error_type"] == "not_approved", "Error type should be not_approved"


# =============================================================================
# Integration Tests
# =============================================================================

def test_090(test_client, temp_project_dir, lld_genuine_footer_approved):
    """
    Gate integration - pass | Auto | Valid LLD path | No exception raised
    | Workflow continues
    """
    # TDD: Arrange
    # Create a valid LLD file in the temp project directory
    lld_dir = temp_project_dir / "docs" / "lld" / "active"
    lld_dir.mkdir(parents=True, exist_ok=True)
    lld_path = lld_dir / "LLD-177.md"
    lld_path.write_text(lld_genuine_footer_approved, encoding="utf-8")

    # TDD: Act
    # Should not raise any exception
    result = run_verification_gate(lld_path, temp_project_dir)

    # TDD: Assert
    assert result["is_valid"] is True, "Gate should pass for valid LLD"
    assert result["confidence"] == "high", "Should have high confidence"


def test_100(test_client, temp_project_dir, lld_false_approval_revise):
    """
    Gate integration - fail | Auto | Invalid LLD path |
    LLDVerificationError raised | Exception has suggestion
    """
    # TDD: Arrange
    # Create an LLD with false approval in the temp project directory
    lld_dir = temp_project_dir / "docs" / "lld" / "active"
    lld_dir.mkdir(parents=True, exist_ok=True)
    lld_path = lld_dir / "LLD-177-invalid.md"
    lld_path.write_text(lld_false_approval_revise, encoding="utf-8")

    # TDD: Act & Assert
    with pytest.raises(LLDVerificationError) as exc_info:
        run_verification_gate(lld_path, temp_project_dir)
    
    error = exc_info.value
    assert error.error_type == "forgery", "Should be forgery error"
    assert error.suggestion, "Error should have a suggestion"
    assert "Re-run" in error.suggestion or "workflow" in error.suggestion.lower()
```