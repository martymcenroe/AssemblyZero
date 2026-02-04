Now I have a good understanding of the codebase. Let me create the implementation files:

```python
# File: agentos/core/lld_verification.py

"""LLD Verification module for Issue #177.

This module provides verification logic to ensure LLDs were genuinely approved
by Gemini review before implementation work proceeds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class LLDVerificationResult:
    """Result of LLD verification check.

    Attributes:
        is_valid: Whether the approval is genuine.
        reason: Human-readable explanation.
        approval_source: Where the approval was found ("footer", "review_log", None).
        confidence: Confidence level of the verification ("high", "medium", "low").
        error_type: Type of error if not valid ("forgery", "not_approved", None).
    """

    is_valid: bool
    reason: str
    approval_source: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    error_type: Literal["forgery", "not_approved"] | None = None


class LLDVerificationError(Exception):
    """Exception raised when LLD verification fails.

    Attributes:
        message: Error message.
        suggestion: Suggested action to fix the issue.
        error_type: Type of verification error.
    """

    def __init__(
        self,
        message: str,
        suggestion: str = "",
        error_type: Literal["forgery", "not_approved", "security"] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion
        self.error_type = error_type


# Regex patterns for approval detection
FOOTER_APPROVAL_PATTERN = re.compile(
    r"<sub>\*\*Gemini Review:\*\*\s*APPROVED",
    re.IGNORECASE,
)

# Review log table row pattern: | Date | Reviewer | Verdict |
REVIEW_LOG_ROW_PATTERN = re.compile(
    r"^\s*\|\s*[^|]+\s*\|\s*[^|]+\s*\|\s*(APPROVED|REVISE|PENDING|BLOCK(?:ED)?)\s*\|",
    re.MULTILINE | re.IGNORECASE,
)

# Final Status line pattern
FINAL_STATUS_PATTERN = re.compile(
    r"\*\*Final Status:\*\*\s*(APPROVED|REVISE|PENDING|BLOCK(?:ED)?)",
    re.IGNORECASE,
)

# Status in header metadata
STATUS_HEADER_PATTERN = re.compile(
    r"\*\*Status:\*\*\s*(Approved|APPROVED)",
    re.IGNORECASE,
)


def _extract_review_verdicts(content: str) -> list[str]:
    """Extract all review verdicts from review log table.

    Args:
        content: LLD content.

    Returns:
        List of verdicts in order (e.g., ["REVISE", "REVISE", "APPROVED"]).
    """
    verdicts = []
    for match in REVIEW_LOG_ROW_PATTERN.finditer(content):
        verdict = match.group(1).upper()
        # Normalize BLOCKED to BLOCK
        if verdict == "BLOCKED":
            verdict = "BLOCK"
        verdicts.append(verdict)
    return verdicts


def _has_footer_approval(content: str) -> bool:
    """Check if content has the footer approval marker.

    The genuine footer approval looks like:
    <sub>**Gemini Review:** APPROVED (model-name, date)</sub>

    Args:
        content: LLD content.

    Returns:
        True if footer approval found.
    """
    return bool(FOOTER_APPROVAL_PATTERN.search(content))


def _has_final_status_approved(content: str) -> tuple[bool, str | None]:
    """Check if Final Status line shows APPROVED.

    Args:
        content: LLD content.

    Returns:
        Tuple of (has_final_status_line, status_value).
    """
    match = FINAL_STATUS_PATTERN.search(content)
    if match:
        return True, match.group(1).upper()
    return False, None


def verify_lld_approval(content: str) -> LLDVerificationResult:
    """Verify that an LLD has genuine Gemini approval.

    This function checks for genuine approval markers and detects forgery attempts
    where the status says APPROVED but the actual review verdict was different.

    Verification priority:
    1. Footer approval (<sub>**Gemini Review:** APPROVED...) - highest confidence
    2. Review log with last verdict APPROVED - medium confidence
    3. Final Status line alone (without supporting evidence) - rejected

    Args:
        content: Full LLD markdown content.

    Returns:
        LLDVerificationResult with verification status.
    """
    if not content or len(content.strip()) < 50:
        return LLDVerificationResult(
            is_valid=False,
            reason="LLD content is empty or too short",
            error_type="not_approved",
        )

    # Check for footer approval (highest confidence)
    if _has_footer_approval(content):
        return LLDVerificationResult(
            is_valid=True,
            reason="Genuine footer approval found",
            approval_source="footer",
            confidence="high",
        )

    # Extract review log verdicts
    verdicts = _extract_review_verdicts(content)

    # Check Final Status line
    has_final_status, final_status_value = _has_final_status_approved(content)

    # If we have verdicts from review log
    if verdicts:
        last_verdict = verdicts[-1]

        # Check for forgery: Final Status says APPROVED but last review doesn't
        if has_final_status and final_status_value == "APPROVED":
            if last_verdict != "APPROVED":
                return LLDVerificationResult(
                    is_valid=False,
                    reason=f"FALSE APPROVAL: Final Status says APPROVED but last review was {last_verdict}",
                    error_type="forgery",
                )

        # Last verdict is APPROVED
        if last_verdict == "APPROVED":
            return LLDVerificationResult(
                is_valid=True,
                reason=f"Review log shows APPROVED as final verdict ({len(verdicts)} reviews)",
                approval_source="review_log",
                confidence="medium",
            )
        else:
            return LLDVerificationResult(
                is_valid=False,
                reason=f"Last review verdict was {last_verdict}, not APPROVED",
                error_type="not_approved",
            )

    # No review log verdicts found
    # Check if Final Status exists but no supporting evidence
    if has_final_status:
        if final_status_value == "APPROVED":
            # Status says APPROVED but no review log to back it up
            # This could be a manual edit without actual review
            return LLDVerificationResult(
                is_valid=False,
                reason="Final Status says APPROVED but no review log entries found",
                error_type="not_approved",
            )
        else:
            return LLDVerificationResult(
                is_valid=False,
                reason=f"Final Status is {final_status_value}, not APPROVED",
                error_type="not_approved",
            )

    # Check for Status header (common in approved LLDs)
    if STATUS_HEADER_PATTERN.search(content):
        # Has status header but no other approval evidence
        return LLDVerificationResult(
            is_valid=False,
            reason="Status header shows Approved but no review evidence found",
            error_type="not_approved",
        )

    # No approval markers found at all
    return LLDVerificationResult(
        is_valid=False,
        reason="No approval evidence found in LLD",
        error_type="not_approved",
    )


def verify_lld_path_security(lld_path: Path, project_root: Path) -> None:
    """Verify that LLD path is within project root (security check).

    Prevents path traversal attacks where malicious paths could read files
    outside the project directory.

    Args:
        lld_path: Path to the LLD file.
        project_root: Root directory of the project.

    Raises:
        LLDVerificationError: If path is outside project root.
    """
    try:
        # Resolve both paths to absolute
        resolved_lld = lld_path.resolve()
        resolved_root = project_root.resolve()

        # Check if LLD is within project root
        resolved_lld.relative_to(resolved_root)
    except ValueError:
        raise LLDVerificationError(
            message=f"Path traversal blocked: {lld_path} is outside project root",
            suggestion="Ensure LLD path is within the project directory",
            error_type="security",
        )


def verify_lld_file(lld_path: Path, project_root: Path | None = None) -> LLDVerificationResult:
    """Verify an LLD file has genuine approval.

    This is the main entry point for file-based verification.

    Args:
        lld_path: Path to the LLD file.
        project_root: Optional project root for security check.

    Returns:
        LLDVerificationResult with verification status.

    Raises:
        LLDVerificationError: If path security check fails or file cannot be read.
    """
    # Security check if project_root provided
    if project_root is not None:
        verify_lld_path_security(lld_path, project_root)

    # Read file
    try:
        content = lld_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise LLDVerificationError(
            message=f"LLD file not found: {lld_path}",
            suggestion="Ensure the LLD file exists at the specified path",
            error_type="not_approved",
        )
    except OSError as e:
        raise LLDVerificationError(
            message=f"Failed to read LLD file: {e}",
            suggestion="Check file permissions and path",
            error_type="not_approved",
        )

    return verify_lld_approval(content)


def run_verification_gate(lld_path: Path, project_root: Path | None = None) -> None:
    """Run the LLD verification gate.

    This function is intended to be called before implementation work begins.
    It will raise an exception if verification fails.

    Args:
        lld_path: Path to the LLD file.
        project_root: Optional project root for security check.

    Raises:
        LLDVerificationError: If verification fails with details and suggestions.
    """
    result = verify_lld_file(lld_path, project_root)

    if not result.is_valid:
        error_type = result.error_type or "not_approved"

        if error_type == "forgery":
            suggestion = (
                "The LLD appears to have been manually marked as APPROVED without "
                "a genuine Gemini review. Please submit the LLD for review and wait "
                "for actual approval."
            )
        else:
            suggestion = (
                "The LLD has not been approved. Please submit it for Gemini review "
                "and wait for the orchestrator to provide approval results."
            )

        raise LLDVerificationError(
            message=result.reason,
            suggestion=suggestion,
            error_type=error_type,
        )
```

```python
# File: tests/test_issue_177.py

"""Test file for Issue #177.

Generated by AgentOS TDD Testing Workflow.
Tests for LLD verification functionality.
"""

import pytest
from pathlib import Path
import tempfile

from agentos.core.lld_verification import (
    verify_lld_approval,
    verify_lld_path_security,
    verify_lld_file,
    run_verification_gate,
    LLDVerificationResult,
    LLDVerificationError,
)


# Sample LLD content fixtures
LLD_WITH_FOOTER_APPROVAL = """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177
* **Status:** Approved (gemini-3-pro-preview, 2026-02-02)

## 10. Test Plan

Test scenarios here.

---

<sub>**Gemini Review:** APPROVED (gemini-3-pro-preview, 2026-02-02)</sub>
"""

LLD_WITH_REVIEW_LOG_APPROVED = """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-02-01 | gemini-3-pro | REVISE |
| 2026-02-02 | gemini-3-pro | APPROVED |

## 10. Test Plan

Test scenarios here.

**Final Status:** APPROVED
"""

LLD_WITH_REVISE_THEN_APPROVED_STATUS = """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-02-01 | gemini-3-pro | REVISE |

**Final Status:** APPROVED
"""

LLD_WITH_PENDING_THEN_APPROVED_STATUS = """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-02-01 | gemini-3-pro | PENDING |

**Final Status:** APPROVED
"""

LLD_NO_APPROVAL = """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

## 10. Test Plan

Test scenarios here.
"""

LLD_MULTIPLE_REVIEWS_LAST_APPROVED = """# LLD-177: Test Feature

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-01-30 | gemini-3-pro | REVISE |
| 2026-01-31 | gemini-3-pro | REVISE |
| 2026-02-01 | gemini-3-pro | APPROVED |

**Final Status:** APPROVED
"""

LLD_MULTIPLE_REVIEWS_LAST_REVISE = """# LLD-177: Test Feature

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|
| 2026-01-30 | gemini-3-pro | APPROVED |
| 2026-01-31 | gemini-3-pro | REVISE |

**Final Status:** REVISE
"""

LLD_EMPTY_REVIEW_LOG = """# LLD-177: Test Feature

## Review Log

| Date | Reviewer | Verdict |
|------|----------|---------|

## 10. Test Plan

Test scenarios here.
"""

LLD_APPROVED_STATUS_NO_FINAL_STATUS = """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177
* **Status:** Approved (gemini-3-pro-preview, 2026-02-02)

## 10. Test Plan

Test scenarios here.
"""


# Integration/E2E fixtures
@pytest.fixture
def test_client():
    """Test client for API calls."""
    yield None


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        lld_dir = project_root / "docs" / "lld" / "active"
        lld_dir.mkdir(parents=True)
        yield project_root


# Unit Tests
# -----------

def test_010():
    """
    Genuine footer approval | Auto | LLD with `<sub>**Gemini Review:**
    APPROVED...` | is_valid=True, confidence="high" | Returns pass
    """
    # TDD: Arrange
    content = LLD_WITH_FOOTER_APPROVAL

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is True
    assert result.confidence == "high"
    assert result.approval_source == "footer"
    assert result.error_type is None


def test_020():
    """
    Review log approval (final) | Auto | LLD with `| APPROVED |` as
    last row | is_valid=True, confidence="medium" | Returns pass
    """
    # TDD: Arrange
    content = LLD_WITH_REVIEW_LOG_APPROVED

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is True
    assert result.confidence == "medium"
    assert result.approval_source == "review_log"


def test_030():
    """
    False approval - REVISE then APPROVED status | Auto | Review shows
    REVISE, status APPROVED | is_valid=False, error_type="forgery" |
    Returns fail with "FALSE APPROVAL"
    """
    # TDD: Arrange
    content = LLD_WITH_REVISE_THEN_APPROVED_STATUS

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False
    assert result.error_type == "forgery"
    assert "FALSE APPROVAL" in result.reason


def test_040():
    """
    False approval - PENDING then APPROVED status | Auto | Review shows
    PENDING, status APPROVED | is_valid=False, error_type="forgery" |
    Returns fail with "FALSE APPROVAL"
    """
    # TDD: Arrange
    content = LLD_WITH_PENDING_THEN_APPROVED_STATUS

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False
    assert result.error_type == "forgery"
    assert "FALSE APPROVAL" in result.reason


def test_050():
    """
    No approval evidence | Auto | LLD with no approval markers |
    is_valid=False, error_type="not_approved" | Returns fail
    """
    # TDD: Arrange
    content = LLD_NO_APPROVAL

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False
    assert result.error_type == "not_approved"


def test_060():
    """
    Multiple reviews, last is APPROVED | Auto | 3 reviews: REVISE,
    REVISE, APPROVED | is_valid=True | Returns pass
    """
    # TDD: Arrange
    content = LLD_MULTIPLE_REVIEWS_LAST_APPROVED

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is True
    assert result.approval_source == "review_log"


def test_070():
    """
    Multiple reviews, last is REVISE | Auto | 3 reviews: APPROVED, REVISE
    | is_valid=False | Returns fail
    """
    # TDD: Arrange
    content = LLD_MULTIPLE_REVIEWS_LAST_REVISE

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False
    assert result.error_type == "not_approved"


def test_080():
    """
    Empty review log | Auto | Review log section exists but empty |
    is_valid=False, error_type="not_approved" | Returns fail
    """
    # TDD: Arrange
    content = LLD_EMPTY_REVIEW_LOG

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False
    assert result.error_type == "not_approved"


def test_110():
    """
    Path traversal attempt | Auto | Path outside project root | Raises
    exception before read | Security check blocks
    """
    # TDD: Arrange
    project_root = Path("/home/user/projects/myproject")
    malicious_path = Path("/etc/passwd")

    # TDD: Act & Assert
    with pytest.raises(LLDVerificationError) as exc_info:
        verify_lld_path_security(malicious_path, project_root)

    assert exc_info.value.error_type == "security"
    assert "traversal" in exc_info.value.message.lower()


def test_120():
    """
    Status APPROVED but no Final Status line | Auto | LLD missing Final
    Status section | is_valid=False, error_type="not_approved" | Returns
    fail
    """
    # TDD: Arrange
    content = LLD_APPROVED_STATUS_NO_FINAL_STATUS

    # TDD: Act
    result = verify_lld_approval(content)

    # TDD: Assert
    assert result.is_valid is False
    assert result.error_type == "not_approved"


# Integration Tests
# -----------------

def test_090(test_client, temp_project_dir):
    """
    Gate integration - pass | Auto | Valid LLD path | No exception raised
    | Workflow continues
    """
    # TDD: Arrange
    lld_path = temp_project_dir / "docs" / "lld" / "active" / "LLD-177.md"
    lld_path.write_text(LLD_WITH_FOOTER_APPROVAL, encoding="utf-8")

    # TDD: Act - should not raise
    run_verification_gate(lld_path, temp_project_dir)

    # TDD: Assert - if we reach here, the gate passed
    assert True


def test_100(test_client, temp_project_dir):
    """
    Gate integration - fail | Auto | Invalid LLD path |
    LLDVerificationError raised | Exception has suggestion
    """
    # TDD: Arrange
    lld_path = temp_project_dir / "docs" / "lld" / "active" / "LLD-177.md"
    lld_path.write_text(LLD_NO_APPROVAL, encoding="utf-8")

    # TDD: Act & Assert
    with pytest.raises(LLDVerificationError) as exc_info:
        run_verification_gate(lld_path, temp_project_dir)

    assert exc_info.value.suggestion != ""
    assert "review" in exc_info.value.suggestion.lower()
```

```python
# File: agentos/core/__init__.py

"""Core components for AgentOS state management and infrastructure."""

from agentos.core.audit import (
    ReviewAuditLog,
    ReviewLogEntry,
    GeminiReviewResponse,
    create_log_entry,
)
from agentos.core.config import (
    REVIEWER_MODEL,
    REVIEWER_MODEL_FALLBACKS,
    FORBIDDEN_MODELS,
    CREDENTIALS_FILE,
    ROTATION_STATE_FILE,
    MAX_RETRIES_PER_CREDENTIAL,
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_SECONDS,
    DEFAULT_AUDIT_LOG_PATH,
    LLD_REVIEW_PROMPT_PATH,
)
from agentos.core.gemini_client import (
    GeminiClient,
    GeminiCallResult,
    GeminiErrorType,
    Credential,
    RotationState,
)
from agentos.core.lld_verification import (
    LLDVerificationResult,
    LLDVerificationError,
    verify_lld_approval,
    verify_lld_path_security,
    verify_lld_file,
    run_verification_gate,
)
from agentos.core.state import AgentState

__all__ = [
    # State
    "AgentState",
    # Config
    "REVIEWER_MODEL",
    "REVIEWER_MODEL_FALLBACKS",
    "FORBIDDEN_MODELS",
    "CREDENTIALS_FILE",
    "ROTATION_STATE_FILE",
    "MAX_RETRIES_PER_CREDENTIAL",
    "BACKOFF_BASE_SECONDS",
    "BACKOFF_MAX_SECONDS",
    "DEFAULT_AUDIT_LOG_PATH",
    "LLD_REVIEW_PROMPT_PATH",
    # Gemini Client
    "GeminiClient",
    "GeminiCallResult",
    "GeminiErrorType",
    "Credential",
    "RotationState",
    # Audit
    "ReviewAuditLog",
    "ReviewLogEntry",
    "GeminiReviewResponse",
    "create_log_entry",
    # LLD Verification (Issue #177)
    "LLDVerificationResult",
    "LLDVerificationError",
    "verify_lld_approval",
    "verify_lld_path_security",
    "verify_lld_file",
    "run_verification_gate",
]
```
