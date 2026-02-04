# File: tests/test_lld_verification.py

```python
"""Unit tests for LLD verification module.

These tests focus on the individual functions in the verification module.
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
    run_verification_gate,
)


class TestHasGeminiApprovedFooter:
    """Tests for has_gemini_approved_footer function."""

    def test_footer_present(self):
        """Detects genuine APPROVED footer."""
        content = """# LLD

<sub>**Gemini Review:** APPROVED | **Model:** gemini-3-pro-preview</sub>
"""
        assert has_gemini_approved_footer(content) is True

    def test_footer_absent(self):
        """Returns False when no footer."""
        content = """# LLD

No footer here.
"""
        assert has_gemini_approved_footer(content) is False

    def test_footer_revise_not_approved(self):
        """REVISE footer is not an approval."""
        content = """# LLD

<sub>**Gemini Review:** REVISE | **Model:** gemini-3-pro-preview</sub>
"""
        assert has_gemini_approved_footer(content) is False


class TestExtractReviewLogVerdicts:
    """Tests for extract_review_log_verdicts function."""

    def test_extracts_multiple_verdicts(self):
        """Extracts all verdicts from review log table."""
        content = """# LLD

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| R1 | 2026-01-10 | REVISE | Issue 1 |
| R2 | 2026-01-15 | REVISE | Issue 2 |
| R3 | 2026-02-01 | APPROVED | None |

**Final Status:** APPROVED
"""
        verdicts = extract_review_log_verdicts(content)

        assert len(verdicts) == 3
        assert verdicts[0] == ("R1", "2026-01-10", "REVISE")
        assert verdicts[1] == ("R2", "2026-01-15", "REVISE")
        assert verdicts[2] == ("R3", "2026-02-01", "APPROVED")

    def test_no_review_summary_section(self):
        """Returns empty list when no Review Summary."""
        content = """# LLD

Just content, no review summary.
"""
        verdicts = extract_review_log_verdicts(content)
        assert verdicts == []

    def test_empty_table(self):
        """Returns empty list for empty table."""
        content = """# LLD

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|

**Final Status:** Pending
"""
        verdicts = extract_review_log_verdicts(content)
        assert verdicts == []


class TestDetectFalseApproval:
    """Tests for detect_false_approval function."""

    def test_no_false_approval_when_status_matches(self):
        """No false approval when status matches verdict."""
        content = """**Final Status:** APPROVED"""
        is_false, details = detect_false_approval(content, "APPROVED")
        assert is_false is False

    def test_detects_revise_with_approved_status(self):
        """Detects false approval: REVISE verdict but APPROVED status."""
        content = """**Final Status:** APPROVED"""
        is_false, details = detect_false_approval(content, "REVISE")
        assert is_false is True
        assert "REVISE" in details

    def test_detects_pending_with_approved_status(self):
        """Detects false approval: PENDING verdict but APPROVED status."""
        content = """**Final Status:** APPROVED"""
        is_false, details = detect_false_approval(content, "PENDING")
        assert is_false is True
        assert "PENDING" in details

    def test_no_false_approval_when_no_final_status(self):
        """No false approval if Final Status line is missing."""
        content = """Some content without Final Status"""
        is_false, details = detect_false_approval(content, "REVISE")
        assert is_false is False


class TestVerifyLldApproval:
    """Tests for verify_lld_approval function."""

    def test_high_confidence_footer(self):
        """Footer approval gives high confidence."""
        content = """<sub>**Gemini Review:** APPROVED | **Model:** gemini-3-pro</sub>"""
        result = verify_lld_approval(content)
        assert result['is_valid'] is True
        assert result['confidence'] == "high"
        assert result['approval_source'] == "footer"

    def test_medium_confidence_review_log(self):
        """Review log approval gives medium confidence."""
        content = """### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| R1 | 2026-02-01 | APPROVED | None |

**Final Status:** APPROVED
"""
        result = verify_lld_approval(content)
        assert result['is_valid'] is True
        assert result['confidence'] == "medium"
        assert result['approval_source'] == "review_log"

    def test_invalid_no_evidence(self):
        """No approval evidence results in invalid."""
        content = """# Just an LLD with no approval markers"""
        result = verify_lld_approval(content)
        assert result['is_valid'] is False


class TestRunVerificationGate:
    """Tests for run_verification_gate function."""

    def test_passes_for_approved_lld(self):
        """Gate passes silently for approved LLD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            lld_path = project_root / "test.md"
            lld_path.write_text(
                "<sub>**Gemini Review:** APPROVED | **Model:** gemini-3-pro</sub>",
                encoding='utf-8'
            )

            # Should not raise
            run_verification_gate(lld_path, project_root=project_root)

    def test_raises_for_unapproved_lld(self):
        """Gate raises LLDVerificationError for unapproved LLD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            lld_path = project_root / "test.md"
            lld_path.write_text("# Not approved", encoding='utf-8')

            with pytest.raises(LLDVerificationError) as exc_info:
                run_verification_gate(lld_path, project_root=project_root)

            assert exc_info.value.error_type == "not_approved"

    def test_raises_for_missing_file(self):
        """Gate raises LLDVerificationError for missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            lld_path = project_root / "does_not_exist.md"

            with pytest.raises(LLDVerificationError) as exc_info:
                run_verification_gate(lld_path, project_root=project_root)

            assert "not found" in exc_info.value.reason

    def test_security_blocks_path_traversal(self):
        """Gate blocks path traversal attempts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            # Try to escape project root
            malicious_path = project_root / ".." / ".." / "etc" / "passwd"

            with pytest.raises(ValueError) as exc_info:
                run_verification_gate(malicious_path, project_root=project_root)

            assert "outside project root" in str(exc_info.value)


class TestLLDVerificationError:
    """Tests for LLDVerificationError exception."""

    def test_error_has_all_attributes(self):
        """Error contains reason, suggestion, and error_type."""
        error = LLDVerificationError(
            reason="Test reason",
            suggestion="Test suggestion",
            error_type="not_approved"
        )

        assert error.reason == "Test reason"
        assert error.suggestion == "Test suggestion"
        assert error.error_type == "not_approved"
        assert "Test reason" in str(error)
        assert "Test suggestion" in str(error)
```