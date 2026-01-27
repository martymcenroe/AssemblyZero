"""N4: Review node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Calls Gemini API with hard-coded 0701c prompt + draft.
The 0701c path is hard-coded and cannot be changed by the agent.
"""

from pathlib import Path
from typing import Any

from agentos.core.config import GOVERNANCE_MODEL
from agentos.core.gemini_client import GeminiClient
from agentos.workflows.issue.audit import (
    get_repo_root,
    next_file_number,
    save_audit_file,
)
from agentos.workflows.issue.state import IssueWorkflowState

# HARD-CODED path to issue review prompt - cannot be changed
ISSUE_REVIEW_PROMPT_PATH = Path("docs/skills/0701c-Issue-Review-Prompt.md")


def load_review_prompt(repo_root: Path | None = None) -> str:
    """Load the 0701c issue review prompt.

    This path is HARD-CODED and cannot be overridden.

    Args:
        repo_root: Repository root path. Auto-detected if None.

    Returns:
        Review prompt content.

    Raises:
        FileNotFoundError: If prompt doesn't exist.
    """
    root = repo_root or get_repo_root()
    prompt_path = root / ISSUE_REVIEW_PROMPT_PATH

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Issue review prompt not found: {prompt_path}\n"
            f"Expected: {ISSUE_REVIEW_PROMPT_PATH}"
        )

    return prompt_path.read_text(encoding="utf-8")


def review(state: IssueWorkflowState) -> dict[str, Any]:
    """N4: Gemini review with 0701c prompt.

    Steps:
    1. Increment file_counter
    2. Load 0701c review prompt (HARD-CODED path)
    3. Combine: 0701c + current_draft
    4. Call Gemini API via GeminiClient
    5. Save raw response to NNN-verdict.md
    6. Increment verdict_count

    Args:
        state: Current workflow state.

    Returns:
        dict with: current_verdict, current_verdict_path, file_counter,
                   verdict_count
    """
    audit_dir = Path(state.get("audit_dir", ""))
    current_draft = state.get("current_draft", "")
    file_counter = state.get("file_counter", 0)
    verdict_count = state.get("verdict_count", 0)

    if not audit_dir or not audit_dir.exists():
        return {"error_message": "Audit directory not set or doesn't exist"}

    if not current_draft:
        return {"error_message": "No draft content to review"}

    # Increment file counter
    file_counter = next_file_number(audit_dir)

    try:
        # Load review prompt (HARD-CODED path)
        review_prompt = load_review_prompt()
    except FileNotFoundError as e:
        return {"error_message": str(e)}

    # Build content for Gemini
    content = f"""{review_prompt}

---

## Issue Draft for Review

{current_draft}
"""

    try:
        # Call Gemini API
        client = GeminiClient(model=GOVERNANCE_MODEL)
        result = client.invoke(
            system_instruction="You are reviewing a GitHub issue draft for quality and completeness.",
            content=content,
        )

        if not result.success:
            return {
                "error_message": f"Gemini API error: {result.error_message}",
            }

        verdict_content = result.response or ""

        # Verify Pro-tier model was used
        if result.model_verified and "pro" not in result.model_verified.lower():
            verdict_content = (
                f"WARNING: Model verification failed - {result.model_verified} is not Pro-tier.\n\n"
                + verdict_content
            )

    except Exception as e:
        return {"error_message": f"Gemini API error: {e}"}

    # Save verdict to audit trail
    verdict_path = save_audit_file(
        audit_dir, file_counter, "verdict.md", verdict_content
    )

    # Increment verdict count
    verdict_count += 1

    return {
        "current_verdict": verdict_content,
        "current_verdict_path": str(verdict_path),
        "file_counter": file_counter,
        "verdict_count": verdict_count,
        "error_message": "",
    }
