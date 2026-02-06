"""LLD Approval Verification Module for Issue #177.

This module implements a pre-flight verification gate that ensures LLDs were
genuinely approved by Gemini review before implementation can proceed.

Verification checks (in priority order):
1. Gemini APPROVED footer (highest confidence)
2. Review log final verdict (medium confidence)
3. Detects false approvals (mismatched status)

Reference: LLD-177 - Implementation workflow gate to verify LLD was genuinely approved
"""

import re
from pathlib import Path
from typing import TypedDict


class LLDVerificationResult(TypedDict):
    """Result of LLD approval verification.
    
    Attributes:
        is_valid: Whether approval is genuine
        reason: Human-readable explanation
        approval_source: "footer" | "review_log" | None
        last_verdict: APPROVED | REVISE | REJECTED | PENDING | None
        confidence: "high" | "medium" | "low"
        error_type: "forgery" | "not_approved" | "no_evidence" | None
    """
    is_valid: bool
    reason: str
    approval_source: str | None
    last_verdict: str | None
    confidence: str
    error_type: str | None


class LLDVerificationError(Exception):
    """Raised when LLD fails approval verification.
    
    Attributes:
        reason: Why verification failed
        suggestion: How to fix
        error_type: "forgery" | "not_approved" | "no_evidence" | "security"
    """
    
    def __init__(self, reason: str, suggestion: str, error_type: str):
        """Initialize verification error.
        
        Args:
            reason: Why verification failed
            suggestion: How to fix
            error_type: "forgery" | "not_approved" | "no_evidence" | "security"
        """
        self.reason = reason
        self.suggestion = suggestion
        self.error_type = error_type
        super().__init__(f"{reason}\n\nSuggestion: {suggestion}")


def has_gemini_approved_footer(lld_content: str) -> bool:
    """Check for genuine Gemini APPROVED footer.
    
    The footer format is:
    <sub>**Gemini Review:** APPROVED | **Model:** ...
    
    Args:
        lld_content: The LLD markdown content
        
    Returns:
        True if the Gemini APPROVED footer is present
    """
    # Pattern: <sub>**Gemini Review:** APPROVED
    # Case-insensitive matching for the word APPROVED
    pattern = r"<sub>\s*\*\*Gemini\s+Review:\*\*\s*APPROVED"
    return bool(re.search(pattern, lld_content, re.IGNORECASE))


def extract_review_log_verdicts(lld_content: str) -> list[tuple[str, str, str]]:
    """Extract all verdicts from the review log table.
    
    Parses the Review Summary table which has format:
    | Review | Date | Verdict | Key Issue |
    |--------|------|---------|-----------|
    | 1 | 2026-01-01 | APPROVED | ... |
    
    Args:
        lld_content: The LLD markdown content
        
    Returns:
        List of (reviewer, date, verdict) tuples in table order (last = most recent)
    """
    verdicts: list[tuple[str, str, str]] = []
    
    # Find the Review Summary section
    if "### Review Summary" not in lld_content and "## Review Summary" not in lld_content:
        return verdicts
    
    # Extract the section
    lines = lld_content.split('\n')
    in_review_summary = False
    
    for line in lines:
        if "Review Summary" in line and (line.startswith('##') or line.startswith('###')):
            in_review_summary = True
            continue
        
        # Stop at next section or Final Status
        if in_review_summary and (
            (line.startswith('##') and 'Review Summary' not in line) or 
            line.startswith('**Final Status:**')
        ):
            break
        
        # Parse table rows
        if in_review_summary and line.strip().startswith('|') and '---' not in line:
            parts = [p.strip() for p in line.split('|')]
            # Skip header row and empty rows
            if len(parts) >= 4:
                reviewer = parts[1] if len(parts) > 1 else ''
                date = parts[2] if len(parts) > 2 else ''
                verdict_raw = parts[3] if len(parts) > 3 else ''
                
                # Skip header rows
                if reviewer.lower() in ['review', ''] or date.lower() in ['date', '']:
                    continue
                
                # Normalize verdict
                verdict_upper = verdict_raw.upper()
                if 'APPROVED' in verdict_upper:
                    verdict = 'APPROVED'
                elif 'REVISE' in verdict_upper:
                    verdict = 'REVISE'
                elif 'REJECTED' in verdict_upper:
                    verdict = 'REJECTED'
                elif 'PENDING' in verdict_upper or 'AWAITING' in verdict_upper:
                    verdict = 'PENDING'
                elif 'gemini' in verdict_raw.lower():
                    # Model name in verdict column indicates approval
                    verdict = 'APPROVED'
                else:
                    verdict = 'UNKNOWN'
                
                verdicts.append((reviewer, date, verdict))
    
    return verdicts


def detect_false_approval(lld_content: str, last_verdict: str | None) -> tuple[bool, str | None]:
    """Detect if Final Status says APPROVED but reviews say otherwise.
    
    A false approval occurs when:
    - Final Status says APPROVED
    - But the last review verdict is REVISE, REJECTED, PENDING, or None
    
    Args:
        lld_content: The LLD markdown content
        last_verdict: The most recent verdict from review log (or None)
    
    Returns:
        (is_false, details) - True if false approval detected, with explanation
    """
    # Check if Final Status says APPROVED
    has_final_status_approved = "**Final Status:** APPROVED" in lld_content
    
    if not has_final_status_approved:
        return (False, None)
    
    # Check if last verdict contradicts APPROVED status
    if last_verdict is not None and last_verdict not in ["APPROVED", "UNKNOWN"]:
        return (True, f"Final Status is APPROVED but last review verdict was {last_verdict}")
    
    # Check for "Awaiting review" marker when no valid verdict
    if last_verdict is None or last_verdict == "UNKNOWN":
        if "Awaiting review" in lld_content:
            return (True, "Final Status is APPROVED but document contains 'Awaiting review' marker")
    
    return (False, None)


def verify_lld_approval(lld_content: str) -> LLDVerificationResult:
    """Verify LLD was genuinely approved by Gemini review.
    
    Checks multiple signals in order:
    1. Gemini APPROVED footer (highest confidence)
    2. Review log final verdict (medium confidence)
    3. Detects false approvals (mismatched status)
    
    Args:
        lld_content: The LLD markdown content
        
    Returns:
        LLDVerificationResult with validation status and reason
    """
    # Step 1: Check for Gemini APPROVED footer (highest confidence)
    if has_gemini_approved_footer(lld_content):
        return LLDVerificationResult(
            is_valid=True,
            reason="Genuine Gemini APPROVED footer found",
            approval_source="footer",
            last_verdict="APPROVED",
            confidence="high",
            error_type=None,
        )
    
    # Step 2: Extract all verdicts from review log
    verdicts = extract_review_log_verdicts(lld_content)
    last_verdict = verdicts[-1][2] if verdicts else None
    
    # Step 3: If last verdict is APPROVED, pass with medium confidence
    if last_verdict == "APPROVED":
        return LLDVerificationResult(
            is_valid=True,
            reason="Review log shows APPROVED as final verdict",
            approval_source="review_log",
            last_verdict="APPROVED",
            confidence="medium",
            error_type=None,
        )
    
    # Step 4: Detect false approval
    is_false, false_details = detect_false_approval(lld_content, last_verdict)
    
    if is_false:
        return LLDVerificationResult(
            is_valid=False,
            reason=f"FALSE APPROVAL DETECTED: {false_details}",
            approval_source=None,
            last_verdict=last_verdict,
            confidence="high",
            error_type="forgery",
        )
    
    # Step 5: Check if Final Status exists but no valid evidence
    if "**Final Status:** APPROVED" in lld_content:
        # Final Status says APPROVED but we couldn't verify it
        return LLDVerificationResult(
            is_valid=False,
            reason="Final Status shows APPROVED but no valid approval evidence found",
            approval_source=None,
            last_verdict=last_verdict,
            confidence="high",
            error_type="no_evidence",
        )
    
    # Step 6: No approval at all
    return LLDVerificationResult(
        is_valid=False,
        reason="LLD has not been approved - no approval markers found",
        approval_source=None,
        last_verdict=last_verdict,
        confidence="high",
        error_type="not_approved",
    )


def validate_lld_path(lld_path: Path, project_root: Path | None = None) -> None:
    """Validate that LLD path is within project boundaries.
    
    Security check to prevent path traversal attacks.
    
    Args:
        lld_path: Path to the LLD file
        project_root: Project root directory (defaults to cwd)
        
    Raises:
        LLDVerificationError: If path is outside project root
    """
    if project_root is None:
        project_root = Path.cwd()
    
    try:
        resolved_path = lld_path.resolve()
        resolved_root = project_root.resolve()
        
        if not resolved_path.is_relative_to(resolved_root):
            raise LLDVerificationError(
                reason=f"Path traversal detected: {lld_path} is outside project root",
                suggestion="Use a path within the project directory",
                error_type="security",
            )
    except ValueError:
        # is_relative_to raises ValueError on incompatible paths
        raise LLDVerificationError(
            reason=f"Invalid path: {lld_path}",
            suggestion="Use a valid path within the project directory",
            error_type="security",
        )


def run_verification_gate(lld_path: Path, project_root: Path | None = None) -> LLDVerificationResult:
    """Pre-flight gate for implementation workflow.
    
    Validates path security and verifies LLD approval status.
    
    Args:
        lld_path: Path to the LLD file
        project_root: Project root directory (defaults to cwd)
        
    Returns:
        LLDVerificationResult if verification passes
        
    Raises:
        LLDVerificationError: If path is invalid or approval is not genuine
    """
    # Security: Validate path is within project
    if project_root:
        validate_lld_path(lld_path, project_root)
    
    # Read LLD content
    if not lld_path.exists():
        raise LLDVerificationError(
            reason=f"LLD file not found: {lld_path}",
            suggestion="Ensure the LLD file exists at the specified path",
            error_type="not_found",
        )
    
    try:
        lld_content = lld_path.read_text(encoding="utf-8")
    except OSError as e:
        raise LLDVerificationError(
            reason=f"Failed to read LLD file: {e}",
            suggestion="Check file permissions and try again",
            error_type="read_error",
        )
    
    # Verify approval
    result = verify_lld_approval(lld_content)
    
    if not result["is_valid"]:
        error_type = result["error_type"] or "not_approved"
        suggestion = _get_suggestion_for_error_type(error_type)
        raise LLDVerificationError(
            reason=result["reason"],
            suggestion=suggestion,
            error_type=error_type,
        )
    
    return result


def _get_suggestion_for_error_type(error_type: str) -> str:
    """Get actionable suggestion based on error type.
    
    Args:
        error_type: The type of verification error
        
    Returns:
        Human-readable suggestion for resolving the error
    """
    suggestions = {
        "forgery": "The LLD status was modified without a genuine review. "
                   "Re-run the LLD workflow with `--gates verdict` to get a genuine approval.",
        "not_approved": "Submit the LLD for Gemini review using the LLD workflow.",
        "no_evidence": "The approval cannot be verified. "
                       "Re-run the LLD workflow with `--gates verdict` to get a genuine approval.",
        "security": "Use a valid path within the project directory.",
        "not_found": "Ensure the LLD file exists at the specified path.",
        "read_error": "Check file permissions and try again.",
    }
    return suggestions.get(error_type, "Contact support for assistance.")