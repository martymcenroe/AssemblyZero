# File: tests/test_issue_177.py

```python
"""Test file for Issue #177: LLD Verification Gate.

Tests for the LLD verification module that ensures LLDs were genuinely approved
by Gemini review before implementation work proceeds.
"""

from pathlib import Path
from unittest.mock import patch
import tempfile

import pytest

from agentos.core.lld_verification import (
    LLDVerificationResult,
    LLDVerificationError,
    verify_lld_approval,
    verify_lld_path_security,
    verify_lld_file,
    run_verification_gate,
)


# Test LLD content fixtures
@pytest.fixture
def lld_with_footer_approval():
    """LLD with genuine footer approval marker."""
    return """# 177 - Feature: LLD Verification Gate

## 1. Context & Goal
* **Issue:** #177
* **Objective:** Add verification gate

## 2. Proposed Changes
...implementation details...

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-02-01 | gemini-3-pro | APPROVED |

**Final Status:** APPROVED

<sub>**Gemini Review:** APPROVED (gemini-3-pro-preview, 2026-02-02)</sub>
"""


@pytest.fixture
def lld_with_review_log_approval():
    """LLD with approval in review log table (last row is APPROVED)."""
    return """# 177 - Feature: LLD Verification Gate

## 1. Context & Goal
* **Issue:** #177

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-02-01 | gemini-3-pro | APPROVED |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_with_forgery_revise():
    """LLD with FALSE APPROVAL - REVISE verdict but APPROVED status."""
    return """# 177 - Feature: LLD Verification Gate

## 1. Context & Goal
* **Issue:** #177

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-02-01 | gemini-3-pro | REVISE |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_with_forgery_pending():
    """LLD with FALSE APPROVAL - PENDING verdict but APPROVED status."""
    return """# 177 - Feature: LLD Verification Gate

## 1. Context & Goal
* **Issue:** #177

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-02-01 | gemini-3-pro | PENDING |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_no_approval():
    """LLD with no approval markers at all."""
    return """# 177 - Feature: LLD Verification Gate

## 1. Context & Goal
* **Issue:** #177
* **Objective:** Add verification gate

## 2. Proposed Changes
...implementation details...
"""


@pytest.fixture
def lld_multiple_reviews_last_approved():
    """LLD with multiple reviews where last is APPROVED."""
    return """# 177 - Feature: LLD Verification Gate

## 1. Context & Goal
* **Issue:** #177

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-01-30 | gemini-3-pro | REVISE |
| 2026-01-31 | gemini-3-pro | REVISE |
| 2026-02-01 | gemini-3-pro | APPROVED |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_multiple_reviews_last_revise():
    """LLD with multiple reviews where last is REVISE."""
    return """# 177 - Feature: LLD Verification Gate

## 1. Context & Goal
* **Issue:** #177

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-01-30 | gemini-3-pro | APPROVED |
| 2026-01-31 | gemini-3-pro | REVISE |

**Final Status:** REVISE
"""


@pytest.fixture
def lld_empty_review_log():
    """LLD with review log section but no entries."""
    return """# 177 - Feature: LLD Verification Gate

## 1. Context & Goal
* **Issue:** #177

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|

**Final Status:** Not Reviewed
"""


@pytest.fixture
def lld_status_approved_no_final_status():
    """LLD with Status APPROVED in header but no Final Status line."""
    return """# 177 - Feature: LLD Verification Gate

* **Status:** Approved

## 1. Context & Goal
* **Issue:** #177

## 2. Proposed Changes
...implementation details...
"""


@pytest.fixture
def test_client():
    """Test client for API calls."""
    yield None


# Unit Tests
# -----------

def test_010(lld_with_footer_approval):
    """
    Genuine footer approval | Auto | LLD with `<sub>**Gemini Review:**
    APPROVED...` | is_valid=True, confidence="high" | Returns pass
    """
    # TDD: Arrange
    content = lld_with_footer_approval

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is True, "Should be valid with footer approval"
    assert result.confidence == "high", "Footer approval should have high confidence"
    assert result.approval_source == "footer", "Source should be footer"


def test_020(lld_with_review_log_approval):
    """
    Review log approval (final) | Auto | LLD with `\ | APPROVED \ | ` as
    last row | is_valid=True, confidence="medium" | Returns pass
    """
    # TDD: Arrange
    content = lld_with_review_log_approval

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is True, "Should be valid with review log approval"
    assert result.confidence == "medium", "Review log approval should have medium confidence"
    assert result.approval_source == "review_log", "Source should be review_log"


def test_030(lld_with_forgery_revise):
    """
    False approval - REVISE then APPROVED status | Auto | Review shows
    REVISE, status APPROVED | is_valid=False, error_type="forgery" |
    Returns fail with "FALSE APPROVAL"
    """
    # TDD: Arrange
    content = lld_with_forgery_revise

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False, "Should be invalid with forgery"
    assert result.error_type == "forgery", "Error type should be forgery"
    assert "FALSE APPROVAL" in result.reason, "Reason should indicate false approval"


def test_040(lld_with_forgery_pending):
    """
    False approval - PENDING then APPROVED status | Auto | Review shows
    PENDING, status APPROVED | is_valid=False, error_type="forgery" |
    Returns fail with "FALSE APPROVAL"
    """
    # TDD: Arrange
    content = lld_with_forgery_pending

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False, "Should be invalid with forgery"
    assert result.error_type == "forgery", "Error type should be forgery"
    assert "FALSE APPROVAL" in result.reason, "Reason should indicate false approval"


def test_050(lld_no_approval):
    """
    No approval evidence | Auto | LLD with no approval markers |
    is_valid=False, error_type="not_approved" | Returns fail
    """
    # TDD: Arrange
    content = lld_no_approval

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False, "Should be invalid without approval"
    assert result.error_type == "not_approved", "Error type should be not_approved"


def test_060(lld_multiple_reviews_last_approved):
    """
    Multiple reviews, last is APPROVED | Auto | 3 reviews: REVISE,
    REVISE, APPROVED | is_valid=True | Returns pass
    """
    # TDD: Arrange
    content = lld_multiple_reviews_last_approved

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is True, "Should be valid when last review is APPROVED"
    assert "3 reviews" in result.reason, "Should mention number of reviews"


def test_070(lld_multiple_reviews_last_revise):
    """
    Multiple reviews, last is REVISE | Auto | 3 reviews: APPROVED, REVISE
    | is_valid=False | Returns fail
    """
    # TDD: Arrange
    content = lld_multiple_reviews_last_revise

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False, "Should be invalid when last review is REVISE"
    assert result.error_type == "not_approved", "Error type should be not_approved"


def test_080(lld_empty_review_log):
    """
    Empty review log | Auto | Review log section exists but empty |
    is_valid=False, error_type="not_approved" | Returns fail
    """
    # TDD: Arrange
    content = lld_empty_review_log

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False, "Should be invalid with empty review log"
    assert result.error_type == "not_approved", "Error type should be not_approved"


def test_110():
    """
    Path traversal attempt | Auto | Path outside project root | Raises
    exception before read | Security check blocks
    """
    # TDD: Arrange
    project_root = Path("/c/Users/mcwiz/Projects/AgentOS")
    malicious_path = Path("/c/Users/mcwiz/Projects/../../../etc/passwd")

    # TDD: Act & Assert
    with pytest.raises(LLDVerificationError) as exc_info:
        verify_lld_path_security(malicious_path, project_root)

    assert exc_info.value.error_type == "security", "Error type should be security"
    assert "traversal" in exc_info.value.message.lower(), "Should mention traversal"


def test_120(lld_status_approved_no_final_status):
    """
    Status APPROVED but no Final Status line | Auto | LLD missing Final
    Status section | is_valid=False, error_type="not_approved" | Returns
    fail
    """
    # TDD: Arrange
    content = lld_status_approved_no_final_status

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False, "Should be invalid without Final Status"
    assert result.error_type == "not_approved", "Error type should be not_approved"


# Integration Tests
# -----------------

def test_090(test_client, lld_with_footer_approval):
    """
    Gate integration - pass | Auto | Valid LLD path | No exception raised
    | Workflow continues
    """
    # TDD: Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        lld_path = Path(tmpdir) / "test-lld.md"
        lld_path.write_text(lld_with_footer_approval, encoding="utf-8")
        project_root = Path(tmpdir)

        # TDD: Act
        # Should not raise any exception
        run_verification_gate(lld_path, project_root)

        # TDD: Assert
        # If we get here without exception, the gate passed
        assert True, "Gate should pass for valid LLD"


def test_100(test_client, lld_no_approval):
    """
    Gate integration - fail | Auto | Invalid LLD path |
    LLDVerificationError raised | Exception has suggestion
    """
    # TDD: Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        lld_path = Path(tmpdir) / "unapproved-lld.md"
        lld_path.write_text(lld_no_approval, encoding="utf-8")
        project_root = Path(tmpdir)

        # TDD: Act & Assert
        with pytest.raises(LLDVerificationError) as exc_info:
            run_verification_gate(lld_path, project_root)

        assert exc_info.value.suggestion != "", "Exception should have suggestion"
        assert "review" in exc_info.value.suggestion.lower(), "Suggestion should mention review"
```