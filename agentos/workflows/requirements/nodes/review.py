"""N3: Review node for Requirements Workflow.

Issue #101: Unified Requirements Workflow

Uses the configured reviewer LLM to review the current draft.
Saves verdict to audit trail and updates verdict history.
"""

from pathlib import Path
from typing import Any

from agentos.core.llm_provider import get_provider
from agentos.workflows.requirements.audit import (
    load_review_prompt,
    next_file_number,
    save_audit_file,
)
from agentos.workflows.requirements.state import RequirementsWorkflowState


def review(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N3: Review draft using configured reviewer.

    Steps:
    1. Load review prompt from agentos_root
    2. Build review content (draft + context)
    3. Call reviewer LLM
    4. Save verdict to audit trail
    5. Update verdict_count and verdict_history
    6. Determine lld_status from verdict

    Args:
        state: Current workflow state.

    Returns:
        State updates with current_verdict, verdict_count, verdict_history.
    """
    workflow_type = state.get("workflow_type", "lld")
    agentos_root = Path(state.get("agentos_root", ""))
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
        review_prompt = load_review_prompt(prompt_path, agentos_root)
    except FileNotFoundError as e:
        return {"error_message": str(e)}

    # Get reviewer provider
    try:
        reviewer = get_provider(reviewer_spec)
    except ValueError as e:
        return {"error_message": f"Invalid reviewer: {e}"}

    # System prompt for reviewing
    system_prompt = """You are a technical reviewer evaluating a document.

Provide a structured verdict:
- APPROVED if the document meets all requirements
- BLOCKED if there are issues that must be addressed

Be specific about what needs to change for BLOCKED verdicts."""

    # Build review content
    review_content = f"""## Document to Review

{current_draft}

## Review Instructions

{review_prompt}"""

    # Call reviewer
    print(f"    Reviewer: {reviewer_spec}")
    result = reviewer.invoke(system_prompt=system_prompt, content=review_content)

    if not result.success:
        print(f"    ERROR: {result.error_message}")
        return {"error_message": f"Reviewer failed: {result.error_message}"}

    verdict_content = result.response or ""

    # Save to audit trail
    file_num = next_file_number(audit_dir)
    if audit_dir.exists():
        verdict_path = save_audit_file(
            audit_dir, file_num, "verdict", verdict_content
        )
    else:
        verdict_path = None

    # Append to verdict history
    verdict_history.append(verdict_content)

    # Determine LLD status from verdict
    # Look for the checked verdict checkbox: [x] **APPROVED** or [X] **APPROVED**
    # The review prompt outputs checkboxes like:
    # [ ] **APPROVED** - Ready for implementation
    # [x] **REVISE** - Fix issues first
    import re
    verdict_upper = verdict_content.upper()

    # Check for checked APPROVED checkbox
    if re.search(r"\[X\]\s*\**APPROVED\**", verdict_upper):
        lld_status = "APPROVED"
    # Check for checked REVISE checkbox (maps to BLOCKED for workflow purposes)
    elif re.search(r"\[X\]\s*\**REVISE\**", verdict_upper):
        lld_status = "BLOCKED"
    # Check for checked DISCUSS checkbox (maps to BLOCKED, needs human)
    elif re.search(r"\[X\]\s*\**DISCUSS\**", verdict_upper):
        lld_status = "BLOCKED"
    # Fallback: Look for explicit keywords (legacy/simple responses)
    elif "VERDICT: APPROVED" in verdict_upper:
        lld_status = "APPROVED"
    elif "VERDICT: BLOCKED" in verdict_upper or "VERDICT: REVISE" in verdict_upper:
        lld_status = "BLOCKED"
    else:
        # Default to BLOCKED if we can't determine status (safe choice)
        lld_status = "BLOCKED"

    verdict_lines = len(verdict_content.splitlines()) if verdict_content else 0
    print(f"    Verdict: {lld_status} ({verdict_lines} lines)")
    if verdict_path:
        print(f"    Saved: {verdict_path.name}")

    return {
        "current_verdict": verdict_content,
        "current_verdict_path": str(verdict_path) if verdict_path else "",
        "verdict_count": verdict_count,
        "verdict_history": verdict_history,
        "file_counter": file_num,
        "lld_status": lld_status,
        "error_message": "",
    }
