# File: agentos/workflows/requirements/nodes/generate_draft.py

```python
"""N1: Generate draft node for Requirements Workflow.

Issue #101: Unified Requirements Workflow
Issue #248: Remove pre-review validation gate - Gemini answers open questions

Uses the configured drafter LLM to generate a draft based on:
- Issue workflow: brief content + template
- LLD workflow: issue content + context + template

Supports revision mode with cumulative verdict history.
"""

import re
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

    Note (Issue #248): Pre-review validation gate removed.
    Open questions now proceed to review where Gemini can answer them.

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

    draft_count = state.get("draft_count", 0) + 1
    is_revision = bool(state.get("current_draft") and state.get("verdict_history"))

    if is_revision:
        print(f"\n[N1] Generating revision (draft #{draft_count})...")
    else:
        print(f"\n[N1] Generating initial draft...")

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
    print(f"    Drafter: {drafter_spec}")

    result = drafter.invoke(system_prompt=system_prompt, content=prompt)

    if not result.success:
        print(f"    ERROR: {result.error_message}")
        return {"error_message": f"Drafter failed: {result.error_message}"}

    draft_content = result.response or ""

    # Save to audit trail
    iteration_count = state.get("iteration_count", 0) + 1
    file_num = next_file_number(audit_dir)
    if audit_dir.exists():
        draft_path = save_audit_file(audit_dir, file_num, "draft.md", draft_content)
    else:
        draft_path = None

    draft_lines = len(draft_content.splitlines()) if draft_content else 0
    print(f"    Generated {draft_lines} lines")
    if draft_path:
        print(f"    Saved: {draft_path.name}")

    # Issue #248: Pre-review validation gate REMOVED
    # Open questions now proceed to review where Gemini can answer them.
    # The post-review check in review.py handles the loop-back logic.

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
        issue_number = state.get("issue_number", 0)
        issue_title = state.get("issue_title", "")
        issue_body = state.get("issue_body", "")
        context_content = state.get("context_content", "")

        # CRITICAL: Explicitly include issue number to prevent LLM confusion
        input_content = f"# Issue #{issue_number}: {issue_title}\n\n{issue_body}"
        if context_content:
            input_content += f"\n\n## Context\n\n{context_content}"
        input_content += f"\n\n**CRITICAL: This LLD is for GitHub Issue #{issue_number}. Use this exact issue number in all references.**"
        input_label = f"GitHub Issue #{issue_number}"

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


def validate_draft_structure(content: str) -> str | None:
    """Check for unresolved open questions in draft.

    Issue #235: Mechanical validation gate to catch structural issues
    before Gemini review.

    Issue #245: Only checks the 'Open Questions' section, ignoring Definition
    of Done and other sections that legitimately have unchecked checkboxes.

    Issue #248: This function is kept for backward compatibility but is NO LONGER
    called in the main generate_draft flow. Open questions now proceed to review
    where Gemini can answer them.

    Args:
        content: Draft content to validate.

    Returns:
        Error message if validation fails, None if passes.
    """
    if not content:
        return None

    # Extract only the Open Questions section
    # Pattern: from "### Open Questions" or "## Open Questions"
    # until the next "##" header or end of document
    pattern = r"(?:^##?#?\s*Open Questions\s*\n)(.*?)(?=^##|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        # No Open Questions section found - that's fine
        return None

    open_questions_section = match.group(1)

    # Count unchecked boxes only in this section
    unchecked = re.findall(r"^- \[ \]", open_questions_section, re.MULTILINE)
    if unchecked:
        return f"BLOCKED: {len(unchecked)} unresolved open questions - resolve before review"

    return None
```