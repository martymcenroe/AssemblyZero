"""N1: Generate draft node for Requirements Workflow.

Issue #101: Unified Requirements Workflow

Uses the configured drafter LLM to generate a draft based on:
- Issue workflow: brief content + template
- LLD workflow: issue content + context + template

Supports revision mode with cumulative verdict history.
"""

from pathlib import Path
from typing import Any

from agentos.core.llm_provider import get_provider
from agentos.workflows.requirements.audit import (
    load_template,
    next_file_number,
    save_audit_file,
)
from agentos.workflows.requirements.state import RequirementsWorkflowState


def generate_draft(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N1: Generate draft using configured drafter.

    Steps:
    1. Load template from agentos_root
    2. Build prompt (initial or revision)
    3. Call drafter LLM
    4. Save draft to audit trail
    5. Increment draft_count

    Args:
        state: Current workflow state.

    Returns:
        State updates with current_draft, draft_count.
    """
    workflow_type = state.get("workflow_type", "lld")
    agentos_root = Path(state.get("agentos_root", ""))
    target_repo = Path(state.get("target_repo", ""))
    mock_mode = state.get("config_mock_mode", False)
    audit_dir = Path(state.get("audit_dir", ""))

    # Use mock provider in mock mode, otherwise use configured drafter
    if mock_mode:
        drafter_spec = "mock:draft"
    else:
        drafter_spec = state.get("config_drafter", "claude:opus-4.5")

    # Determine template path based on workflow type
    if workflow_type == "issue":
        template_path = Path("docs/templates/0101-issue-template.md")
    else:
        template_path = Path("docs/templates/0102-feature-lld-template.md")

    # Load template
    try:
        template = load_template(template_path, agentos_root)
    except FileNotFoundError as e:
        return {"error_message": str(e)}

    # Build prompt
    prompt = _build_prompt(state, template, workflow_type)

    # Get drafter provider
    try:
        drafter = get_provider(drafter_spec)
    except ValueError as e:
        return {"error_message": f"Invalid drafter: {e}"}

    # System prompt for drafting
    if workflow_type == "issue":
        system_prompt = """You are a technical writer creating a GitHub issue.

CRITICAL FORMATTING RULES:
- Start DIRECTLY with the issue title (# heading)
- Do NOT include any preamble, explanation, or meta-commentary
- Output ONLY the raw markdown content that will be pasted into GitHub
- First line MUST be the issue title starting with #

Use the template structure provided. Fill in all sections. Be specific and actionable."""
    else:
        system_prompt = """You are a technical architect creating a Low-Level Design document.

CRITICAL FORMATTING RULES:
- Start DIRECTLY with the document title (# heading)
- Do NOT include any preamble, explanation, or meta-commentary
- Output ONLY the raw markdown content
- First line MUST be the title starting with #

Use the template structure provided. Include all sections. Be specific about:
- Files to be created/modified
- Function signatures
- Data structures
- Error handling approach"""

    # Call drafter
    result = drafter.invoke(system_prompt=system_prompt, content=prompt)

    if not result.success:
        return {"error_message": f"Drafter failed: {result.error_message}"}

    draft_content = result.response or ""

    # Save to audit trail
    draft_count = state.get("draft_count", 0) + 1
    iteration_count = state.get("iteration_count", 0) + 1
    file_num = next_file_number(audit_dir)
    if audit_dir.exists():
        draft_path = save_audit_file(audit_dir, file_num, "draft.md", draft_content)
    else:
        draft_path = None

    return {
        "current_draft": draft_content,
        "current_draft_path": str(draft_path) if draft_path else "",
        "draft_count": draft_count,
        "iteration_count": iteration_count,
        "file_counter": file_num,
        "user_feedback": "",  # Clear feedback after use
        "error_message": "",
    }


def _build_prompt(
    state: RequirementsWorkflowState,
    template: str,
    workflow_type: str,
) -> str:
    """Build prompt for drafter based on workflow type and revision state.

    Args:
        state: Current workflow state.
        template: Template content.
        workflow_type: Either "issue" or "lld".

    Returns:
        Complete prompt string.
    """
    current_draft = state.get("current_draft", "")
    verdict_history = state.get("verdict_history", [])
    user_feedback = state.get("user_feedback", "")

    if workflow_type == "issue":
        input_content = state.get("brief_content", "")
        input_label = "Brief (user's ideation notes)"
    else:
        issue_title = state.get("issue_title", "")
        issue_body = state.get("issue_body", "")
        context_content = state.get("context_content", "")

        input_content = f"# {issue_title}\n\n{issue_body}"
        if context_content:
            input_content += f"\n\n## Context\n\n{context_content}"
        input_label = "GitHub Issue"

    # Check if this is a revision
    if current_draft and verdict_history:
        # Revision mode
        revision_context = ""

        if verdict_history:
            revision_context += "## ALL Gemini Review Feedback (CUMULATIVE)\n\n"
            for i, verdict in enumerate(verdict_history, 1):
                revision_context += f"### Gemini Review #{i}\n\n{verdict}\n\n"

        if user_feedback:
            revision_context += f"## Additional Human Feedback\n\n{user_feedback}\n\n"

        prompt = f"""IMPORTANT: Output ONLY the markdown content. Start with # title. No preamble.

{revision_context}## Current Draft (to revise)
{current_draft}

## Original {input_label}
{input_content}

## Template (REQUIRED STRUCTURE)
{template}

CRITICAL REVISION INSTRUCTIONS:
1. Implement EVERY change requested by Gemini feedback
2. PRESERVE sections that Gemini didn't flag
3. ONLY modify sections Gemini specifically mentioned
4. Keep ALL template sections intact

Revise the draft to address ALL feedback above.
START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE."""

    else:
        # Initial draft mode
        prompt = f"""IMPORTANT: Output ONLY the markdown content. Start with # title. No preamble.

## {input_label}
{input_content}

## Template (follow this structure)
{template}

Create a complete document following the template structure.
START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE."""

    return prompt
