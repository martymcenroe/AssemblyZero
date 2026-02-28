"""N3: Review node for Requirements Workflow.

Issue #101: Unified Requirements Workflow
Issue #248: Add post-review open questions check
Issue #257: Update draft with resolved open questions after approval

Uses the configured reviewer LLM to review the current draft.
Saves verdict to audit trail and updates verdict history.
"""

import difflib
import re
from pathlib import Path
from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost, get_provider
from assemblyzero.core.verdict_schema import VERDICT_SCHEMA, parse_structured_verdict
from assemblyzero.workflows.requirements.audit import (
    load_review_prompt,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.requirements.state import RequirementsWorkflowState


def review(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N3: Review draft using configured reviewer.

    Steps:
    1. Load review prompt from assemblyzero_root
    2. Build review content (draft + context)
    3. Call reviewer LLM
    4. Save verdict to audit trail
    5. Update verdict_count and verdict_history
    6. Determine lld_status from verdict
    7. Check for open questions resolution (Issue #248)
    8. Update draft with resolutions if APPROVED (Issue #257)

    Args:
        state: Current workflow state.

    Returns:
        State updates with current_verdict, verdict_count, verdict_history,
        open_questions_status, and updated_draft (if APPROVED).
    """
    workflow_type = state.get("workflow_type", "lld")
    assemblyzero_root = Path(state.get("assemblyzero_root", ""))
    mock_mode = state.get("config_mock_mode", False)
    audit_dir = Path(state.get("audit_dir", ""))
    current_draft = state.get("current_draft", "")
    verdict_history = list(state.get("verdict_history", []))

    verdict_count = state.get("verdict_count", 0) + 1
    print(f"\n[N3] Reviewing draft (review #{verdict_count})...")

    # Use mock provider in mock mode, otherwise use configured reviewer
    if mock_mode:
        reviewer_spec = "mock:review"
    else:
        reviewer_spec = state.get("config_reviewer", "gemini:3-pro-preview")

    # Determine review prompt path based on workflow type
    if workflow_type == "issue":
        prompt_path = Path("docs/skills/0701c-Issue-Review-Prompt.md")
    else:
        prompt_path = Path("docs/skills/0702c-LLD-Review-Prompt.md")

    # Load review prompt
    try:
        review_prompt = load_review_prompt(prompt_path, assemblyzero_root)
    except FileNotFoundError as e:
        return {"error_message": str(e)}

    # Get reviewer provider
    try:
        reviewer = get_provider(reviewer_spec)
    except ValueError as e:
        return {"error_message": f"Invalid reviewer: {e}"}

    # System prompt for reviewing
    system_prompt = """You are a Principal Architect, Systems Engineer, and Test Plan Execution Guru.

Your role is to perform a strict gatekeeper review of design documents before implementation begins.

Key responsibilities:
- Answer any open questions in Section 1 with concrete recommendations
- Evaluate cost, safety, security, and legal concerns
- Verify test coverage meets requirements
- Provide a structured verdict: APPROVED or BLOCKED

Follow the Review Instructions exactly. Be specific about what needs to change for BLOCKED verdicts."""

    # Issue #491: Build review content with diff-aware support
    previous_draft = state.get("previous_draft", "")
    review_content = _build_review_content(
        current_draft=current_draft,
        review_prompt=review_prompt,
        previous_draft=previous_draft,
    )

    # Issue #492: Pass structured schema when reviewer is Gemini
    invoke_kwargs: dict = {
        "system_prompt": system_prompt,
        "content": review_content,
    }
    is_gemini = reviewer_spec.startswith("gemini:")
    if is_gemini and hasattr(reviewer, "invoke") and not mock_mode:
        invoke_kwargs["response_schema"] = VERDICT_SCHEMA

    # Call reviewer
    print(f"    Reviewer: {reviewer_spec}")
    result = reviewer.invoke(**invoke_kwargs)

    if not result.success:
        print(f"    ERROR: {result.error_message}")
        return {"error_message": f"Reviewer failed: {result.error_message}"}

    # Issue #476: Budget check
    cumulative = get_cumulative_cost()
    budget = state.get("cost_budget_usd", 0.0)
    if budget > 0 and cumulative > budget:
        msg = f"[BUDGET] ${cumulative:.2f} exceeds ${budget:.2f} budget. Halting."
        print(f"    {msg}")
        return {"error_message": msg}

    verdict_content = result.response or ""

    # Save to audit trail
    file_num = next_file_number(audit_dir)
    if audit_dir.exists():
        verdict_path = save_audit_file(
            audit_dir, file_num, "verdict.md", verdict_content
        )
    else:
        verdict_path = None

    # Append to verdict history
    verdict_history.append(verdict_content)

    # Issue #492: Try structured JSON parsing first, fall back to regex
    structured = parse_structured_verdict(verdict_content) if is_gemini else None
    if structured:
        lld_status = structured["verdict"]
        # Map REVISE -> BLOCKED for workflow purposes
        if lld_status == "REVISE":
            lld_status = "BLOCKED"
        print(f"    Parsed structured verdict: {structured['verdict']}")
    else:
        # Determine LLD status from verdict via regex
        lld_status = _parse_verdict_status(verdict_content)

    # Issue #248: Check open questions resolution status
    open_questions_status = _check_open_questions_status(current_draft, verdict_content)

    # Issue #257: Update draft with resolutions if APPROVED
    updated_draft = current_draft
    if lld_status == "APPROVED":
        updated_draft = _update_draft_with_verdict(current_draft, verdict_content)
        if updated_draft != current_draft:
            print("    Draft updated with resolved open questions")

    verdict_lines = len(verdict_content.splitlines()) if verdict_content else 0
    print(f"    Verdict: {lld_status} ({verdict_lines} lines)")
    print(f"    Open Questions: {open_questions_status}")
    if verdict_path:
        print(f"    Saved: {verdict_path.name}")

    return {
        "current_verdict": verdict_content,
        "current_verdict_path": str(verdict_path) if verdict_path else "",
        "verdict_count": verdict_count,
        "verdict_history": verdict_history,
        "file_counter": file_num,
        "lld_status": lld_status,
        "open_questions_status": open_questions_status,
        "current_draft": updated_draft,  # Issue #257: Return updated draft
        "error_message": "",
    }


def _build_review_content(
    current_draft: str,
    review_prompt: str,
    previous_draft: str = "",
) -> str:
    """Build review content, optionally using diff format for revisions.

    Issue #491: When previous_draft exists and changes are <20% of total,
    send diff format instead of full draft. This reduces token usage
    significantly on revision reviews.

    Args:
        current_draft: Current draft to review.
        review_prompt: Review instructions.
        previous_draft: Previous draft for diff comparison.

    Returns:
        Formatted review content string.
    """
    if not previous_draft:
        # First review — send full draft
        return f"## Document to Review\n\n{current_draft}\n\n## Review Instructions\n\n{review_prompt}"

    # Calculate diff
    prev_lines = previous_draft.splitlines(keepends=True)
    curr_lines = current_draft.splitlines(keepends=True)
    diff = list(difflib.unified_diff(prev_lines, curr_lines, n=3))

    if not diff:
        # No changes — send full draft (shouldn't happen in practice)
        return f"## Document to Review\n\n{current_draft}\n\n## Review Instructions\n\n{review_prompt}"

    # Count changed lines in current (additions only, exclude diff headers)
    changed_lines = sum(
        1 for line in diff
        if line.startswith("+")
        and not line.startswith("+++")
    )
    total_lines = max(len(curr_lines), 1)
    change_ratio = changed_lines / total_lines

    if change_ratio > 0.20:
        # Too many changes — diff won't help, send full draft
        return f"## Document to Review\n\n{current_draft}\n\n## Review Instructions\n\n{review_prompt}"

    # Send diff format with context
    diff_text = "".join(diff)
    return (
        f"## CHANGES SINCE LAST REVIEW (unified diff)\n\n"
        f"Focus your review on these changes. The rest of the document is unchanged.\n\n"
        f"```diff\n{diff_text}```\n\n"
        f"## Full Document (for reference)\n\n{current_draft}\n\n"
        f"## Review Instructions\n\n{review_prompt}"
    )


def _update_draft_with_verdict(draft: str, verdict_content: str) -> str:
    """Update draft with resolutions and suggestions from verdict.

    Issue #257: After APPROVED verdict, update the draft with:
    - Resolved open questions (mark as [x] with resolution text)
    - Tier 3 suggestions (add new section)

    Args:
        draft: Current draft content.
        verdict_content: The APPROVED verdict from reviewer.

    Returns:
        Updated draft content.
    """
    try:
        from assemblyzero.workflows.requirements.parsers.verdict_parser import parse_verdict
        from assemblyzero.workflows.requirements.parsers.draft_updater import update_draft

        verdict_result = parse_verdict(verdict_content)
        updated_draft, warnings = update_draft(draft, verdict_result)

        for warning in warnings:
            print(f"    Warning: {warning}")

        return updated_draft
    except ImportError:
        # Parsers not available (shouldn't happen in production)
        return draft
    except Exception as e:
        print(f"    Warning: Could not update draft with verdict: {e}")
        return draft


def _parse_verdict_status(verdict_content: str) -> str:
    """Parse LLD status from verdict content.

    Args:
        verdict_content: The reviewer's verdict text.

    Returns:
        One of: "APPROVED", "BLOCKED"
    """
    verdict_upper = verdict_content.upper()

    # Check for checked APPROVED checkbox
    if re.search(r"\[X\]\s*\**APPROVED\**", verdict_upper):
        return "APPROVED"
    # Check for checked REVISE checkbox (maps to BLOCKED for workflow purposes)
    elif re.search(r"\[X\]\s*\**REVISE\**", verdict_upper):
        return "BLOCKED"
    # Check for checked DISCUSS checkbox (maps to BLOCKED, needs human)
    elif re.search(r"\[X\]\s*\**DISCUSS\**", verdict_upper):
        return "BLOCKED"
    # Fallback: Look for explicit keywords (legacy/simple responses)
    elif "VERDICT: APPROVED" in verdict_upper:
        return "APPROVED"
    elif "VERDICT: BLOCKED" in verdict_upper or "VERDICT: REVISE" in verdict_upper:
        return "BLOCKED"
    else:
        # Default to BLOCKED if we can't determine status (safe choice)
        return "BLOCKED"


def _check_open_questions_status(draft_content: str, verdict_content: str) -> str:
    """Check whether open questions have been resolved.

    Issue #248: After Gemini review, check if:
    1. Questions were answered (all [x] in verdict's "Open Questions Resolved" section)
    2. Questions marked as HUMAN REQUIRED
    3. Questions remain unanswered

    Args:
        draft_content: The draft that was reviewed.
        verdict_content: Gemini's verdict.

    Returns:
        One of:
        - "RESOLVED": All open questions answered
        - "HUMAN_REQUIRED": One or more questions need human decision
        - "UNANSWERED": Questions exist but weren't answered
        - "NONE": No open questions in the draft
    """
    # Check if draft has open questions
    draft_has_questions = _draft_has_open_questions(draft_content)
    if not draft_has_questions:
        return "NONE"

    # Check for HUMAN REQUIRED in verdict
    if _verdict_has_human_required(verdict_content):
        return "HUMAN_REQUIRED"

    # Check if verdict has "Open Questions Resolved" section with answers
    if _verdict_has_resolved_questions(verdict_content):
        return "RESOLVED"

    # Questions exist but weren't answered
    return "UNANSWERED"


def _draft_has_open_questions(content: str) -> bool:
    """Check if draft has unchecked open questions.

    Args:
        content: Draft content.

    Returns:
        True if unchecked open questions exist.
    """
    if not content:
        return False

    # Extract Open Questions section
    pattern = r"(?:^##?#?\s*Open Questions\s*\n)(.*?)(?=^##|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        return False

    open_questions_section = match.group(1)

    # Check for unchecked boxes, filtering out "None" placeholders
    # Drafters write "- [ ] None" to mean "no open questions"
    unchecked_lines = re.findall(
        r"^- \[ \] ?(.*)", open_questions_section, re.MULTILINE
    )
    real_questions = [
        q
        for q in unchecked_lines
        if not re.match(r"^none\b", q.strip(), re.IGNORECASE)
    ]
    return len(real_questions) > 0


def _verdict_has_human_required(verdict_content: str) -> bool:
    """Check if verdict contains HUMAN REQUIRED marker.

    Args:
        verdict_content: The verdict text.

    Returns:
        True if HUMAN REQUIRED is present.
    """
    # Look for HUMAN REQUIRED (case insensitive) in various formats
    patterns = [
        r"HUMAN\s+REQUIRED",
        r"\*\*HUMAN\s+REQUIRED\*\*",
        r"REQUIRES?\s+HUMAN",
        r"NEEDS?\s+HUMAN\s+DECISION",
        r"ESCALATE\s+TO\s+HUMAN",
    ]
    verdict_upper = verdict_content.upper()
    for pattern in patterns:
        if re.search(pattern, verdict_upper):
            return True
    return False


def _verdict_has_resolved_questions(verdict_content: str) -> bool:
    """Check if verdict has resolved open questions.

    Looks for the "Open Questions Resolved" section and checks if
    all items are marked as [x] with RESOLVED.

    Args:
        verdict_content: The verdict text.

    Returns:
        True if questions were resolved.
    """
    # Look for "Open Questions Resolved" section
    pattern = r"(?:##\s*Open Questions Resolved\s*\n)(.*?)(?=^##|\Z)"
    match = re.search(pattern, verdict_content, re.MULTILINE | re.DOTALL)

    if not match:
        # No explicit section - check if "RESOLVED:" appears in verdict
        return "RESOLVED:" in verdict_content.upper()

    resolved_section = match.group(1)

    # Check for resolved markers: [x] followed by ~~question~~ **RESOLVED:
    resolved_count = len(re.findall(r"\[x\].*?RESOLVED:", resolved_section, re.IGNORECASE))

    # Check for any unchecked items still in the section
    unchecked_count = len(re.findall(r"^- \[ \]", resolved_section, re.MULTILINE))

    # If we have resolutions and no unchecked items, questions are resolved
    return resolved_count > 0 and unchecked_count == 0