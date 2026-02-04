# File: tests/test_issue_177.py

```python
"""Test file for Issue #177: LLD Approval Verification Gate.

Tests the pre-flight verification gate that ensures LLDs were genuinely
approved by Gemini review before implementation can proceed.

Reference: LLD-177
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from agentos.utils.lld_verification import (
    LLDVerificationError,
    LLDVerificationResult,
    detect_false_approval,
    extract_review_log_verdicts,
    has_gemini_approved_footer,
    run_verification_gate,
    validate_lld_path,
    verify_lld_approval,
)


# Test Fixtures
# -------------

@pytest.fixture
def lld_with_footer_approval() -> str:
    """LLD with genuine Gemini APPROVED footer."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177
* **Status:** Approved

## 10. Test Plan
Some test content here.

---

<sub>**Gemini Review:** APPROVED | **Model:** gemini-3-pro-preview | **Date:** 2026-02-02</sub>
"""


@pytest.fixture
def lld_with_review_log_approved() -> str:
    """LLD with APPROVED as final review log verdict."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-02-01 | REVISE | Initial feedback |
| 2 | 2026-02-02 | APPROVED | gemini-3-pro-preview |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_with_false_approval_revise() -> str:
    """LLD with false approval - status APPROVED but last verdict REVISE."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-02-01 | REVISE | Needs changes |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_with_false_approval_pending() -> str:
    """LLD with false approval - status APPROVED but awaiting review."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-02-01 | PENDING | Awaiting review |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_with_no_approval() -> str:
    """LLD with no approval markers whatsoever."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## 2. Proposed Changes
Some changes here.

## 10. Test Plan
Some tests here.
"""


@pytest.fixture
def lld_with_multiple_reviews_last_approved() -> str:
    """LLD with multiple reviews where last is APPROVED."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-15 | REVISE | Security concerns |
| 2 | 2026-01-20 | REVISE | Performance issues |
| 3 | 2026-02-02 | APPROVED | All resolved |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_with_multiple_reviews_last_revise() -> str:
    """LLD with multiple reviews where last is REVISE."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-15 | APPROVED | Looks good |
| 2 | 2026-02-02 | REVISE | Found new issue |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_with_empty_review_log() -> str:
    """LLD with review log section but no entries."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_without_final_status() -> str:
    """LLD with APPROVED in document but no Final Status line."""
    return """# LLD-177: Test Feature

## 1. Context & Goal
* **Issue:** #177
* **Status:** Draft

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
"""


@pytest.fixture
def test_client():
    """Test client for API calls (unused in unit tests)."""
    yield None


# Unit Tests
# -----------

def test_010(lld_with_footer_approval):
    """
    Genuine footer approval | Auto | LLD with `<sub>**Gemini Review:**
    APPROVED...` | is_valid=True, confidence="high" | Returns pass
    """
    # TDD: Arrange
    lld_content = lld_with_footer_approval

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is True
    assert result["confidence"] == "high"
    assert result["approval_source"] == "footer"
    assert result["error_type"] is None


def test_020(lld_with_review_log_approved):
    """
    Review log approval (final) | Auto | LLD with `\ | APPROVED \ | ` as
    last row | is_valid=True, confidence="medium" | Returns pass
    """
    # TDD: Arrange
    lld_content = lld_with_review_log_approved

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is True
    assert result["confidence"] == "medium"
    assert result["approval_source"] == "review_log"
    assert result["error_type"] is None


def test_030(lld_with_false_approval_revise):
    """
    False approval - REVISE then APPROVED status | Auto | Review shows
    REVISE, status APPROVED | is_valid=False, error_type="forgery" |
    Returns fail with "FALSE APPROVAL"
    """
    # TDD: Arrange
    lld_content = lld_with_false_approval_revise

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    assert result["error_type"] == "forgery"
    assert "FALSE APPROVAL" in result["reason"]


def test_040(lld_with_false_approval_pending):
    """
    False approval - PENDING then APPROVED status | Auto | Review shows
    PENDING, status APPROVED | is_valid=False, error_type="forgery" |
    Returns fail with "FALSE APPROVAL"
    """
    # TDD: Arrange
    lld_content = lld_with_false_approval_pending

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    assert result["error_type"] == "forgery"
    assert "FALSE APPROVAL" in result["reason"]


def test_050(lld_with_no_approval):
    """
    No approval evidence | Auto | LLD with no approval markers |
    is_valid=False, error_type="not_approved" | Returns fail
    """
    # TDD: Arrange
    lld_content = lld_with_no_approval

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    assert result["error_type"] == "not_approved"


def test_060(lld_with_multiple_reviews_last_approved):
    """
    Multiple reviews, last is APPROVED | Auto | 3 reviews: REVISE,
    REVISE, APPROVED | is_valid=True | Returns pass
    """
    # TDD: Arrange
    lld_content = lld_with_multiple_reviews_last_approved

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is True
    assert result["approval_source"] == "review_log"


def test_070(lld_with_multiple_reviews_last_revise):
    """
    Multiple reviews, last is REVISE | Auto | 3 reviews: APPROVED, REVISE
    | is_valid=False | Returns fail
    """
    # TDD: Arrange
    lld_content = lld_with_multiple_reviews_last_revise

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    assert result["error_type"] == "forgery"


def test_080(lld_with_empty_review_log):
    """
    Empty review log | Auto | Review log section exists but empty |
    is_valid=False, error_type="not_approved" | Returns fail
    """
    # TDD: Arrange
    lld_content = lld_with_empty_review_log

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    # When Final Status is APPROVED but no evidence, it's "no_evidence"
    assert result["error_type"] in ["not_approved", "no_evidence"]


def test_110():
    """
    Path traversal attempt | Auto | Path outside project root | Raises
    exception before read | Security check blocks
    """
    # TDD: Arrange
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir) / "project"
        project_root.mkdir()
        
        # Create a path outside project
        outside_path = Path(tmpdir) / "outside" / "lld.md"
        outside_path.parent.mkdir(parents=True, exist_ok=True)
        outside_path.write_text("# Some LLD content")

        # TDD: Act & Assert
        with pytest.raises(LLDVerificationError) as excinfo:
            validate_lld_path(outside_path, project_root)
        
        assert excinfo.value.error_type == "security"
        assert "traversal" in excinfo.value.reason.lower() or "outside" in excinfo.value.reason.lower()


def test_120(lld_without_final_status):
    """
    Status APPROVED but no Final Status line | Auto | LLD missing Final
    Status section | is_valid=False, error_type="not_approved" | Returns
    fail
    """
    # TDD: Arrange
    lld_content = lld_without_final_status

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    assert result["error_type"] == "not_approved"


# Integration Tests
# -----------------

def test_090(test_client, lld_with_footer_approval):
    """
    Gate integration - pass | Auto | Valid LLD path | No exception raised
    | Workflow continues
    """
    # TDD: Arrange
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        lld_path = project_root / "docs" / "lld" / "active" / "LLD-177.md"
        lld_path.parent.mkdir(parents=True, exist_ok=True)
        lld_path.write_text(lld_with_footer_approval)

        # TDD: Act
        result = run_verification_gate(lld_path, project_root)

        # TDD: Assert
        assert result["is_valid"] is True
        assert result["confidence"] == "high"


def test_100(test_client, lld_with_no_approval):
    """
    Gate integration - fail | Auto | Invalid LLD path |
    LLDVerificationError raised | Exception has suggestion
    """
    # TDD: Arrange
    with TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        lld_path = project_root / "docs" / "lld" / "active" / "LLD-177.md"
        lld_path.parent.mkdir(parents=True, exist_ok=True)
        lld_path.write_text(lld_with_no_approval)

        # TDD: Act & Assert
        with pytest.raises(LLDVerificationError) as excinfo:
            run_verification_gate(lld_path, project_root)
        
        assert excinfo.value.suggestion is not None
        assert len(excinfo.value.suggestion) > 0
        assert excinfo.value.error_type == "not_approved"
```