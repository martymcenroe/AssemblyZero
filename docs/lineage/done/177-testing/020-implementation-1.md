# File: tests/test_lld_verification.py

```python
"""Unit tests for LLD verification module.

This file provides comprehensive unit tests for the lld_verification module,
following the test matrix from Issue #177 LLD.
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
    _get_suggestion_for_error_type,
)


class TestHasGeminiApprovedFooter:
    """Tests for has_gemini_approved_footer function."""

    def test_detects_standard_footer(self):
        """Detects standard Gemini APPROVED footer."""
        content = '<sub>**Gemini Review:** APPROVED | **Model:** gemini-3-pro</sub>'
        assert has_gemini_approved_footer(content) is True

    def test_detects_footer_with_whitespace(self):
        """Detects footer with extra whitespace."""
        content = '<sub>  **Gemini  Review:**  APPROVED | **Model:** gemini-3-pro</sub>'
        assert has_gemini_approved_footer(content) is True

    def test_case_insensitive_approved(self):
        """APPROVED is detected case-insensitively."""
        content = '<sub>**Gemini Review:** approved | **Model:** gemini-3-pro</sub>'
        assert has_gemini_approved_footer(content) is True

    def test_no_footer_returns_false(self):
        """Returns False when no footer present."""
        content = '# Just a regular document\n\nNo footer here.'
        assert has_gemini_approved_footer(content) is False

    def test_revise_footer_returns_false(self):
        """REVISE footer should not match."""
        content = '<sub>**Gemini Review:** REVISE | **Model:** gemini-3-pro</sub>'
        assert has_gemini_approved_footer(content) is False


class TestExtractReviewLogVerdicts:
    """Tests for extract_review_log_verdicts function."""

    def test_extracts_single_verdict(self):
        """Extracts single review verdict from table."""
        content = """### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-15 | APPROVED | None |
"""
        verdicts = extract_review_log_verdicts(content)
        assert len(verdicts) == 1
        assert verdicts[0][2] == "APPROVED"

    def test_extracts_multiple_verdicts(self):
        """Extracts multiple review verdicts in order."""
        content = """### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-10 | REVISE | Missing section |
| 2 | 2026-01-12 | REVISE | Needs work |
| 3 | 2026-01-15 | APPROVED | All good |
"""
        verdicts = extract_review_log_verdicts(content)
        assert len(verdicts) == 3
        assert verdicts[0][2] == "REVISE"
        assert verdicts[1][2] == "REVISE"
        assert verdicts[2][2] == "APPROVED"

    def test_handles_no_review_section(self):
        """Returns empty list when no Review Summary section."""
        content = "# Just a document\n\nNo review section here."
        verdicts = extract_review_log_verdicts(content)
        assert verdicts == []

    def test_handles_empty_table(self):
        """Returns empty list for empty review table."""
        content = """### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|

## Next Section
"""
        verdicts = extract_review_log_verdicts(content)
        assert verdicts == []

    def test_normalizes_pending_verdict(self):
        """Normalizes PENDING and AWAITING to PENDING."""
        content = """### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-15 | Awaiting review | - |
"""
        verdicts = extract_review_log_verdicts(content)
        assert len(verdicts) == 1
        assert verdicts[0][2] == "PENDING"


class TestDetectFalseApproval:
    """Tests for detect_false_approval function."""

    def test_no_false_when_matching(self):
        """No false approval when status matches verdict."""
        content = "**Final Status:** APPROVED"
        is_false, details = detect_false_approval(content, "APPROVED")
        assert is_false is False

    def test_detects_revise_vs_approved(self):
        """Detects mismatch: REVISE verdict with APPROVED status."""
        content = "**Final Status:** APPROVED"
        is_false, details = detect_false_approval(content, "REVISE")
        assert is_false is True
        assert "REVISE" in details

    def test_detects_pending_vs_approved(self):
        """Detects mismatch: PENDING verdict with APPROVED status."""
        content = "**Final Status:** APPROVED"
        is_false, details = detect_false_approval(content, "PENDING")
        assert is_false is True
        assert "PENDING" in details

    def test_no_false_without_final_status(self):
        """No false approval if Final Status line is missing."""
        content = "Some content without status"
        is_false, details = detect_false_approval(content, "REVISE")
        assert is_false is False


class TestVerifyLldApproval:
    """Tests for verify_lld_approval main function."""

    def test_high_confidence_with_footer(self):
        """Footer gives high confidence approval."""
        content = """# LLD

<sub>**Gemini Review:** APPROVED | **Model:** gemini-3-pro</sub>
"""
        result = verify_lld_approval(content)
        assert result["is_valid"] is True
        assert result["confidence"] == "high"
        assert result["approval_source"] == "footer"

    def test_medium_confidence_with_review_log(self):
        """Review log gives medium confidence approval."""
        content = """# LLD

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-15 | APPROVED | None |

**Final Status:** APPROVED
"""
        result = verify_lld_approval(content)
        assert result["is_valid"] is True
        assert result["confidence"] == "medium"
        assert result["approval_source"] == "review_log"

    def test_forgery_detection(self):
        """Detects forgery when verdicts don't match status."""
        content = """# LLD

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-15 | REVISE | Needs work |

**Final Status:** APPROVED
"""
        result = verify_lld_approval(content)
        assert result["is_valid"] is False
        assert result["error_type"] == "forgery"
        assert "FALSE APPROVAL" in result["reason"]

    def test_not_approved_no_markers(self):
        """Returns not_approved when no approval markers."""
        content = "# Just a document without any approval"
        result = verify_lld_approval(content)
        assert result["is_valid"] is False
        assert result["error_type"] == "not_approved"


class TestValidateLldPath:
    """Tests for validate_lld_path security function."""

    def test_accepts_path_within_project(self):
        """Accepts paths within project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            lld_path = project_root / "docs" / "LLDs" / "test.md"
            # Should not raise
            validate_lld_path(lld_path, project_root)

    def test_rejects_path_outside_project(self):
        """Rejects paths outside project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            outside_path = Path("/etc/passwd")
            
            with pytest.raises(LLDVerificationError) as exc_info:
                validate_lld_path(outside_path, project_root)
            
            assert exc_info.value.error_type == "security"

    def test_rejects_parent_traversal(self):
        """Rejects parent directory traversal attempts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            traversal_path = project_root / ".." / ".." / "etc" / "passwd"
            
            with pytest.raises(LLDVerificationError) as exc_info:
                validate_lld_path(traversal_path, project_root)
            
            assert exc_info.value.error_type == "security"


class TestRunVerificationGate:
    """Tests for run_verification_gate integration function."""

    def test_passes_valid_lld(self):
        """Gate passes for valid approved LLD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            lld_path = project_root / "test.md"
            lld_path.write_text("""# LLD
            
<sub>**Gemini Review:** APPROVED | **Model:** gemini-3-pro</sub>
""")
            result = run_verification_gate(lld_path, project_root)
            assert result["is_valid"] is True

    def test_raises_for_unapproved_lld(self):
        """Gate raises error for unapproved LLD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            lld_path = project_root / "test.md"
            lld_path.write_text("# LLD without approval")
            
            with pytest.raises(LLDVerificationError) as exc_info:
                run_verification_gate(lld_path, project_root)
            
            assert exc_info.value.error_type == "not_approved"

    def test_raises_for_missing_file(self):
        """Gate raises error for missing LLD file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            lld_path = project_root / "nonexistent.md"
            
            with pytest.raises(LLDVerificationError) as exc_info:
                run_verification_gate(lld_path, project_root)
            
            assert exc_info.value.error_type == "not_found"

    def test_suggestion_included_in_error(self):
        """Errors include actionable suggestions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            lld_path = project_root / "test.md"
            lld_path.write_text("# LLD without approval")
            
            with pytest.raises(LLDVerificationError) as exc_info:
                run_verification_gate(lld_path, project_root)
            
            assert exc_info.value.suggestion is not None
            assert len(exc_info.value.suggestion) > 0


class TestGetSuggestionForErrorType:
    """Tests for _get_suggestion_for_error_type helper."""

    def test_forgery_suggestion(self):
        """Forgery error gets re-review suggestion."""
        suggestion = _get_suggestion_for_error_type("forgery")
        assert "workflow" in suggestion.lower() or "review" in suggestion.lower()

    def test_not_approved_suggestion(self):
        """Not approved error gets submission suggestion."""
        suggestion = _get_suggestion_for_error_type("not_approved")
        assert "submit" in suggestion.lower() or "review" in suggestion.lower()

    def test_unknown_type_gets_fallback(self):
        """Unknown error types get fallback suggestion."""
        suggestion = _get_suggestion_for_error_type("unknown_error")
        assert suggestion is not None
        assert len(suggestion) > 0
```