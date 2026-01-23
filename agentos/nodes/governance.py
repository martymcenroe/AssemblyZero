"""Governance nodes for AgentOS LangGraph workflows.

This module contains the governance node that gates LLDs through
Gemini 3 Pro review, enforcing model hierarchy and credential rotation.
"""

import json
import re
from pathlib import Path
from typing import Any

from agentos.core.audit import GovernanceAuditLog, create_log_entry
from agentos.core.config import GOVERNANCE_MODEL, LLD_REVIEW_PROMPT_PATH
from agentos.core.gemini_client import GeminiClient, GeminiErrorType
from agentos.core.state import AgentState


def review_lld_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph node that gates LLDs through Gemini 3 Pro review.

    Uses GeminiClient for API calls with:
    - Enforced model hierarchy (Pro only, never Flash/Haiku)
    - Automatic credential rotation on quota exhaustion
    - Full observability logging

    Args:
        state: The current AgentState containing lld_content and issue_id.

    Returns:
        dict with keys: lld_status, gemini_critique, iteration_count

    Fail-safe: Returns BLOCK if:
    - JSON parsing fails
    - All credentials exhausted
    - Model verification fails (wrong model used)
    - Any unexpected error
    """
    # Initialize audit log
    audit_log = GovernanceAuditLog()

    # Increment iteration count
    iteration_count = state.get("iteration_count", 0) + 1

    try:
        # Load system instruction
        system_instruction = _load_system_instruction()

        # Get LLD content - check for Designer Node flow first (Issue #56)
        # If lld_draft_path exists, read from disk to capture human edits
        lld_draft_path = state.get("lld_draft_path", "")
        if lld_draft_path and Path(lld_draft_path).exists():
            lld_content = Path(lld_draft_path).read_text(encoding="utf-8")
        else:
            lld_content = state.get("lld_content", "")
        issue_id = state.get("issue_id", 0)

        if not lld_content:
            # No LLD content - fail closed
            entry = create_log_entry(
                node="review_lld",
                model=GOVERNANCE_MODEL,
                model_verified="",
                issue_id=issue_id,
                verdict="BLOCK",
                critique="No LLD content provided",
                tier_1_issues=["Missing LLD content"],
                raw_response="",
                duration_ms=0,
                credential_used="",
                rotation_occurred=False,
                attempts=0,
                sequence_id=iteration_count,
            )
            audit_log.log(entry)

            return {
                "lld_status": "BLOCKED",
                "gemini_critique": "No LLD content provided",
                "iteration_count": iteration_count,
            }

        # Initialize Gemini client with strict model enforcement
        client = GeminiClient(model=GOVERNANCE_MODEL)

        # Invoke Gemini with rotation logic
        result = client.invoke(
            system_instruction=system_instruction,
            content=f"## LLD Content for Review\n\n{lld_content}",
        )

        if result.success:
            # Parse the response to extract verdict
            verdict, critique, tier_1_issues = _parse_gemini_response(
                result.response or ""
            )

            # Verify model used is Pro-tier
            if result.model_verified and "pro" not in result.model_verified.lower():
                # Model mismatch - fail closed
                verdict = "BLOCK"
                critique = f"Model verification failed: {result.model_verified} is not Pro-tier"
                tier_1_issues = ["Model downgrade detected"]

            # Log to audit trail
            entry = create_log_entry(
                node="review_lld",
                model=GOVERNANCE_MODEL,
                model_verified=result.model_verified,
                issue_id=issue_id,
                verdict=verdict,
                critique=critique,
                tier_1_issues=tier_1_issues,
                raw_response=result.raw_response or "",
                duration_ms=result.duration_ms,
                credential_used=result.credential_used,
                rotation_occurred=result.rotation_occurred,
                attempts=result.attempts,
                sequence_id=iteration_count,
            )
            audit_log.log(entry)

            return {
                "lld_status": verdict,
                "gemini_critique": critique,
                "iteration_count": iteration_count,
            }

        else:
            # API call failed - log and return BLOCK
            error_msg = result.error_message or "Unknown error"

            entry = create_log_entry(
                node="review_lld",
                model=GOVERNANCE_MODEL,
                model_verified="",
                issue_id=issue_id,
                verdict="BLOCK",
                critique=f"Gemini API error: {error_msg}",
                tier_1_issues=["API call failed"],
                raw_response="",
                duration_ms=result.duration_ms,
                credential_used=result.credential_used,
                rotation_occurred=result.rotation_occurred,
                attempts=result.attempts,
                sequence_id=iteration_count,
            )
            audit_log.log(entry)

            return {
                "lld_status": "BLOCKED",
                "gemini_critique": f"Gemini API error: {error_msg}",
                "iteration_count": iteration_count,
            }

    except FileNotFoundError as e:
        # Missing prompt file or credentials
        entry = create_log_entry(
            node="review_lld",
            model=GOVERNANCE_MODEL,
            model_verified="",
            issue_id=state.get("issue_id", 0),
            verdict="BLOCK",
            critique=f"Configuration error: {e}",
            tier_1_issues=["Missing required file"],
            raw_response="",
            duration_ms=0,
            credential_used="",
            rotation_occurred=False,
            attempts=0,
            sequence_id=iteration_count,
        )
        audit_log.log(entry)

        return {
            "lld_status": "BLOCKED",
            "gemini_critique": f"Configuration error: {e}",
            "iteration_count": iteration_count,
        }

    except ValueError as e:
        # Model validation error
        entry = create_log_entry(
            node="review_lld",
            model=GOVERNANCE_MODEL,
            model_verified="",
            issue_id=state.get("issue_id", 0),
            verdict="BLOCK",
            critique=f"Model configuration error: {e}",
            tier_1_issues=["Invalid model configuration"],
            raw_response="",
            duration_ms=0,
            credential_used="",
            rotation_occurred=False,
            attempts=0,
            sequence_id=iteration_count,
        )
        audit_log.log(entry)

        return {
            "lld_status": "BLOCKED",
            "gemini_critique": f"Model configuration error: {e}",
            "iteration_count": iteration_count,
        }

    except Exception as e:
        # Unexpected error - fail closed
        entry = create_log_entry(
            node="review_lld",
            model=GOVERNANCE_MODEL,
            model_verified="",
            issue_id=state.get("issue_id", 0),
            verdict="BLOCK",
            critique=f"Unexpected error: {e}",
            tier_1_issues=["Fail-safe triggered"],
            raw_response="",
            duration_ms=0,
            credential_used="",
            rotation_occurred=False,
            attempts=0,
            sequence_id=iteration_count,
        )
        audit_log.log(entry)

        return {
            "lld_status": "BLOCKED",
            "gemini_critique": f"Fail-safe triggered: {e}",
            "iteration_count": iteration_count,
        }


def _load_system_instruction() -> str:
    """Load LLD review prompt from docs/skills/0702c-LLD-Review-Prompt.md.

    Returns:
        The system instruction text.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    # Try relative path first (for testing)
    if LLD_REVIEW_PROMPT_PATH.exists():
        prompt_path = LLD_REVIEW_PROMPT_PATH
    else:
        # Try from project root
        project_root = Path(__file__).parent.parent.parent
        prompt_path = project_root / LLD_REVIEW_PROMPT_PATH

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"LLD review prompt not found at: {prompt_path}\n"
            f"Expected path: {LLD_REVIEW_PROMPT_PATH}"
        )

    return prompt_path.read_text(encoding="utf-8")


def _parse_gemini_response(response: str) -> tuple[str, str, list[str]]:
    """Parse Gemini's response to extract verdict, critique, and issues.

    Args:
        response: The raw response text from Gemini.

    Returns:
        Tuple of (verdict, critique, tier_1_issues).
        Defaults to BLOCK if parsing fails (fail-safe).
    """
    # Default to BLOCK (fail-safe)
    verdict = "BLOCK"
    critique = "Failed to parse Gemini response"
    tier_1_issues: list[str] = []

    try:
        # Look for verdict pattern
        # [x] **APPROVED** or [ ] **APPROVED**
        if re.search(r"\[x\]\s*\*\*APPROVED\*\*", response, re.IGNORECASE):
            verdict = "APPROVED"
        elif re.search(r"\[x\]\s*\*\*REVISE\*\*", response, re.IGNORECASE):
            verdict = "BLOCK"
        elif re.search(r"\[x\]\s*\*\*DISCUSS\*\*", response, re.IGNORECASE):
            verdict = "BLOCK"

        # Also check for Pre-Flight Gate failure
        if "Pre-Flight Gate: FAILED" in response:
            verdict = "BLOCK"

        # Extract review summary for critique
        summary_match = re.search(
            r"## Review Summary\s*\n(.*?)(?=\n##|\Z)", response, re.DOTALL
        )
        if summary_match:
            critique = summary_match.group(1).strip()
        else:
            # Fallback: use first paragraph after Identity Confirmation
            identity_match = re.search(
                r"## Identity Confirmation.*?\n\n(.*?)(?=\n##|\Z)", response, re.DOTALL
            )
            if identity_match:
                critique = identity_match.group(1).strip()[:500]

        # Extract Tier 1 issues
        tier1_match = re.search(
            r"## Tier 1: BLOCKING Issues\s*\n(.*?)(?=\n## Tier 2|\Z)",
            response,
            re.DOTALL,
        )
        if tier1_match:
            tier1_section = tier1_match.group(1)
            # Find all checkbox items
            issues = re.findall(r"-\s*\[.\]\s*(.+?)(?=\n-|\n###|\Z)", tier1_section)
            tier_1_issues = [issue.strip() for issue in issues if issue.strip()]

            # If no issues found but verdict is BLOCK, add generic message
            if not tier_1_issues and verdict == "BLOCK":
                tier_1_issues = ["Blocking issues found - see full response"]

    except Exception:
        # Any parsing error - fail closed
        verdict = "BLOCK"
        critique = "Failed to parse Gemini response"
        tier_1_issues = ["Parse error - fail-safe triggered"]

    return verdict, critique, tier_1_issues
