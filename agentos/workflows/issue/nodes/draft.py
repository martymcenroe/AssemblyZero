"""N2: Draft node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Calls Claude API with brief + template to generate structured issue draft.
Saves draft to audit trail with sequential numbering.
"""

from pathlib import Path
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from agentos.workflows.issue.audit import (
    get_repo_root,
    next_file_number,
    save_audit_file,
)
from agentos.workflows.issue.state import IssueWorkflowState

# Path to issue template (relative to repo root)
ISSUE_TEMPLATE_PATH = Path("docs/templates/0101-issue-template.md")

# Claude model for drafting
DRAFT_MODEL = "claude-sonnet-4-20250514"


def load_issue_template(repo_root: Path | None = None) -> str:
    """Load the 0101 issue template.

    Args:
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Template content.

    Raises:
        FileNotFoundError: If template doesn't exist.
    """
    root = repo_root or get_repo_root()
    template_path = root / ISSUE_TEMPLATE_PATH

    if not template_path.exists():
        raise FileNotFoundError(f"Issue template not found: {template_path}")

    return template_path.read_text(encoding="utf-8")


def draft(state: IssueWorkflowState) -> dict[str, Any]:
    """N2: Generate issue draft using Claude.

    Steps:
    1. Increment file_counter
    2. Load issue template (0101)
    3. Combine brief + template (+ feedback if revising)
    4. Call Claude API
    5. Save response to NNN-draft.md
    6. Increment draft_count

    Args:
        state: Current workflow state.

    Returns:
        dict with: current_draft, current_draft_path, file_counter,
                   draft_count, user_feedback (cleared)
    """
    audit_dir = Path(state.get("audit_dir", ""))
    brief_content = state.get("brief_content", "")
    user_feedback = state.get("user_feedback", "")
    current_draft = state.get("current_draft", "")
    file_counter = state.get("file_counter", 0)
    draft_count = state.get("draft_count", 0)

    if not audit_dir or not audit_dir.exists():
        return {"error_message": "Audit directory not set or doesn't exist"}

    # Increment file counter
    file_counter = next_file_number(audit_dir)

    try:
        # Load template
        template = load_issue_template()
    except FileNotFoundError as e:
        return {"error_message": str(e)}

    # Build prompt
    system_prompt = """You are a technical writer creating a GitHub issue.
Use the template structure provided. Fill in all sections based on the brief.
Include Mermaid diagrams where helpful. Be specific and actionable.
Output ONLY the issue content in markdown format, ready to file."""

    if user_feedback and current_draft:
        # Revision mode: include feedback and current draft
        user_content = f"""## User Feedback for Revision
{user_feedback}

## Current Draft (to revise)
{current_draft}

## Original Brief
{brief_content}

## Issue Template (follow this structure)
{template}

Please revise the draft based on the feedback while maintaining the template structure."""
    else:
        # Initial draft mode
        user_content = f"""## Brief (user's ideation notes)
{brief_content}

## Issue Template (follow this structure)
{template}

Create a complete GitHub issue following the template structure."""

    try:
        # Call Claude API
        llm = ChatAnthropic(model=DRAFT_MODEL, temperature=0.3)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
        response = llm.invoke(messages)
        draft_content = response.content

        if isinstance(draft_content, list):
            # Handle case where content is a list of content blocks
            draft_content = "\n".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in draft_content
            )

    except Exception as e:
        return {"error_message": f"Claude API error: {e}"}

    # Save draft to audit trail
    draft_path = save_audit_file(audit_dir, file_counter, "draft.md", draft_content)

    # Increment draft count
    draft_count += 1

    return {
        "current_draft": draft_content,
        "current_draft_path": str(draft_path),
        "file_counter": file_counter,
        "draft_count": draft_count,
        "user_feedback": "",  # Clear feedback after use
        "error_message": "",
    }
