"""N4: Review node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Calls Gemini API with hard-coded 0701c prompt + draft.
The 0701c path is hard-coded and cannot be changed by the agent.
"""

from pathlib import Path
from typing import Any

from agentos.core.config import REVIEWER_MODEL
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
    7. Append verdict to verdict_history

    Args:
        state: Current workflow state.

    Returns:
        dict with: current_verdict, current_verdict_path, file_counter,
                   verdict_count, verdict_history
    """
    audit_dir = Path(state.get("audit_dir", ""))
    current_draft = state.get("current_draft", "")
    file_counter = state.get("file_counter", 0)
    verdict_count = state.get("verdict_count", 0)
    verdict_history = state.get("verdict_history", [])

    if not audit_dir or not audit_dir.exists():
        return {"error_message": "Audit directory not set or doesn't exist"}

    if not current_draft:
        return {"error_message": "No draft content to review"}

    # --------------------------------------------------------------------------
    # GUARD: Pre-LLM content validation (Issue #101)
    # --------------------------------------------------------------------------
    if not current_draft.strip():
        print("    [GUARD] BLOCKED: Draft is empty - cannot send to reviewer")
        return {"error_message": "GUARD: Draft is empty - cannot send to reviewer"}

    content_len = len(current_draft)
    if content_len < 100:
        print(f"    [GUARD] WARNING: Draft suspiciously short ({content_len} chars)")

    if content_len > 100000:
        print(f"    [GUARD] BLOCKED: Draft too large ({content_len} chars)")
        return {"error_message": f"GUARD: Draft too large ({content_len} chars)"}
    # --------------------------------------------------------------------------

    # Increment file counter
    file_counter = next_file_number(audit_dir)

    try:
        # Load review prompt from AgentOS (NOT target repo - prompts are part of AgentOS)
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
        import datetime
        import time
        import sys

        # Progress indicator for Gemini call
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] Calling Gemini for review...", flush=True)
        start_time = time.time()

        # Call Gemini API
        client = GeminiClient(model=REVIEWER_MODEL)
        result = client.invoke(
            system_instruction="You are reviewing a GitHub issue draft for quality and completeness.",
            content=content,
        )

        elapsed = int(time.time() - start_time)
        end_timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{end_timestamp}] Gemini response received ({elapsed}s)", flush=True)

        if not result.success:
            return {
                "error_message": f"Gemini API error: {result.error_message}",
            }

        verdict_content = result.response or ""

        # --------------------------------------------------------------------------
        # GUARD: Post-LLM response validation (Issue #101)
        # --------------------------------------------------------------------------
        if not verdict_content or not verdict_content.strip():
            print("    [GUARD] WARNING: Reviewer returned empty response")
            # Don't fail, but log warning - empty response is unusual

        # Check for valid verdict markers
        verdict_upper = verdict_content.upper() if verdict_content else ""
        if "APPROVED" not in verdict_upper and "BLOCKED" not in verdict_upper:
            if "REVISE" not in verdict_upper:  # Also accept REVISE as a valid verdict
                print("    [GUARD] WARNING: Verdict missing APPROVED/BLOCKED markers")
        # --------------------------------------------------------------------------

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

    # Print verdict summary
    print(f"\n{'=' * 60}")
    print("Gemini Verdict")
    print(f"{'=' * 60}")
    # Print first 500 chars or full verdict if shorter
    preview = verdict_content[:500] if len(verdict_content) > 500 else verdict_content
    print(preview)
    if len(verdict_content) > 500:
        print(f"\n... ({len(verdict_content) - 500} more characters)")
    print(f"\n{'=' * 60}")
    print(f"Full verdict saved to: {verdict_path}")
    print(f"{'=' * 60}\n")

    # Increment verdict count
    verdict_count += 1

    # Append to verdict history (cumulative)
    verdict_history = verdict_history + [verdict_content]

    return {
        "current_verdict": verdict_content,
        "current_verdict_path": str(verdict_path),
        "verdict_history": verdict_history,
        "file_counter": file_counter,
        "verdict_count": verdict_count,
        "error_message": "",
    }
