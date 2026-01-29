"""Node implementations for LLD Governance workflow.

Issue #86: LLD Creation & Governance Review Workflow
LLD: docs/LLDs/active/LLD-086-lld-governance-workflow.md

Nodes:
- N0: fetch_issue - Fetch issue from GitHub, assemble context
- N1: design - Generate LLD draft using designer node
- N2: human_edit - Human review gate
- N3: review - Gemini governance review
- N4: finalize - Save approved LLD
"""

import json
import subprocess
from pathlib import Path

from agentos.workflows.lld.audit import (
    assemble_context,
    create_lld_audit_dir,
    embed_review_evidence,
    get_repo_root,
    next_file_number,
    save_approved_metadata,
    save_audit_file,
    save_final_lld,
    update_lld_status,
)
from agentos.workflows.lld.state import HumanDecision, LLDWorkflowState

# Configuration constants
GH_CLI_TIMEOUT_SECONDS = 30

# Maximum iterations before forcing exit
MAX_ITERATIONS = 5


# ---------------------------------------------------------------------------
# Shared audit helpers (used by both production and mock implementations)
# ---------------------------------------------------------------------------


def _save_draft_to_audit(
    audit_dir: Path,
    lld_content: str,
    state: LLDWorkflowState,
) -> tuple[int, int]:
    """Save LLD draft to audit trail.

    Args:
        audit_dir: Path to audit directory.
        lld_content: LLD content to save.
        state: Current workflow state.

    Returns:
        Tuple of (file_num, draft_count).
    """
    draft_count = state.get("draft_count", 0) + 1
    file_num = state.get("file_counter", 0)

    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "draft.md", lld_content)
        print(f"    Draft saved to audit: {file_num:03d}-draft.md")

    return file_num, draft_count


def _save_verdict_to_audit(
    audit_dir: Path,
    lld_status: str,
    critique: str,
    state: LLDWorkflowState,
) -> tuple[int, int]:
    """Save governance verdict to audit trail.

    Args:
        audit_dir: Path to audit directory.
        lld_status: APPROVED or BLOCKED.
        critique: Gemini critique text.
        state: Current workflow state.

    Returns:
        Tuple of (file_num, verdict_count).
    """
    verdict_count = state.get("verdict_count", 0) + 1
    file_num = state.get("file_counter", 0)

    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        verdict_content = f"# Governance Verdict: {lld_status}\n\n{critique}"
        save_audit_file(audit_dir, file_num, "verdict.md", verdict_content)
        print(f"    Verdict saved to audit: {file_num:03d}-verdict.md")

    return file_num, verdict_count


def fetch_issue(state: LLDWorkflowState) -> dict:
    """N0: Fetch issue from GitHub and assemble context.

    - Validates issue_number exists
    - Fetches issue title and body via gh CLI
    - Reads context_files and assembles context_content
    - Creates audit directory
    - Saves 001-issue.md to audit trail

    Args:
        state: Current workflow state.

    Returns:
        State updates with issue content and audit_dir.
    """
    issue_number = state.get("issue_number", 0)

    if not issue_number:
        return {"error_message": "No issue number provided"}

    print(f"\n[N0] Fetching issue #{issue_number}...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_fetch_issue(state)

    try:
        # Fetch issue via gh CLI
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "title,body"],
            capture_output=True,
            text=True,
            timeout=GH_CLI_TIMEOUT_SECONDS,
        )

        if result.returncode != 0:
            return {
                "error_message": f"Issue #{issue_number} not found: {result.stderr.strip()}"
            }

        issue_data = json.loads(result.stdout)
        issue_title = issue_data.get("title", "")
        issue_body = issue_data.get("body", "")

        print(f"    Title: {issue_title}")

    except subprocess.TimeoutExpired:
        return {"error_message": f"Timeout fetching issue #{issue_number}"}
    except json.JSONDecodeError as e:
        return {"error_message": f"Failed to parse issue data: {e}"}

    # Assemble context from context_files
    context_files = state.get("context_files", [])
    context_content = ""
    if context_files:
        print(f"    Loading {len(context_files)} context file(s)...")
        context_content = assemble_context(context_files)

    # Create audit directory
    audit_dir = create_lld_audit_dir(issue_number)
    print(f"    Audit dir: {audit_dir}")

    # Save issue to audit trail
    issue_content = f"# Issue #{issue_number}: {issue_title}\n\n{issue_body}"
    if context_content:
        issue_content += f"\n\n---\n\n# Context Files\n\n{context_content}"

    file_num = next_file_number(audit_dir)
    save_audit_file(audit_dir, file_num, "issue.md", issue_content)

    return {
        "issue_id": issue_number,  # Alias for existing nodes
        "issue_title": issue_title,
        "issue_body": issue_body,
        "context_content": context_content,
        "audit_dir": str(audit_dir),
        "file_counter": file_num,
        "iteration_count": 0,
        "error_message": "",
    }


def design(state: LLDWorkflowState) -> dict:
    """N1: Generate LLD draft using designer node.

    - Builds prompt from issue + context + LLD template
    - Calls existing designer.py
    - Saves draft to audit trail
    - Opens in VS Code (unless --auto mode)

    Args:
        state: Current workflow state.

    Returns:
        State updates with lld_content and lld_draft_path.
    """
    print("\n[N1] Generating LLD draft...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_design(state)

    # Import designer node (reuse existing)
    from agentos.nodes.designer import design_lld_node

    # Call existing designer node
    # It expects: issue_id, iteration_count
    # It returns: design_status, lld_draft_path, lld_content, iteration_count
    designer_state = {
        "issue_id": state.get("issue_id", state.get("issue_number")),
        "iteration_count": state.get("iteration_count", 0),
    }

    result = design_lld_node(designer_state)

    design_status = result.get("design_status", "FAILED")
    lld_content = result.get("lld_content", "")
    lld_draft_path = result.get("lld_draft_path", "")

    if design_status == "FAILED":
        return {
            "error_message": "Designer node failed",
            "design_status": "FAILED",
        }

    # Save draft to audit trail using shared helper
    audit_dir = Path(state.get("audit_dir", ""))
    file_num, draft_count = _save_draft_to_audit(audit_dir, lld_content, state)

    print(f"    Design status: {design_status}")
    print(f"    Draft path: {lld_draft_path}")

    return {
        "design_status": design_status,
        "lld_content": lld_content,
        "lld_draft_path": lld_draft_path,
        "draft_count": draft_count,
        "file_counter": file_num if audit_dir.exists() else state.get("file_counter", 0),
        "error_message": "",
    }


def human_edit(state: LLDWorkflowState) -> dict:
    """N2: Human review gate - wait for user decision.

    - Displays current iteration count
    - Shows governance critique if available
    - Prompts: [S]end to review, [R]evise with feedback, [M]anual exit
    - Reads updated LLD from disk
    - Returns updated state with next_node routing

    Args:
        state: Current workflow state.

    Returns:
        State updates with next_node and possibly user_feedback.
    """
    iteration = state.get("iteration_count", 0) + 1
    print(f"\n[N2] Human Edit Gate (Iteration {iteration}/{MAX_ITERATIONS})")

    # Auto mode: skip prompt, auto-send
    if state.get("auto_mode"):
        print("    Auto mode: sending to review...")
        return {
            "iteration_count": iteration,
            "next_node": "N3_review",
            "user_feedback": "",
        }

    # Show critique if available
    critique = state.get("gemini_critique", "")
    if critique:
        print("\n--- Gemini Critique ---")
        print(critique)
        print("-----------------------\n")

    # Show draft location
    lld_draft_path = state.get("lld_draft_path", "")
    if lld_draft_path:
        print(f"    Draft location: {lld_draft_path}")

    # Prompt user
    print("\n    [S] Send to Gemini review")
    print("    [R] Revise (return to designer with feedback)")
    print("    [M] Manual exit")

    while True:
        try:
            choice = input("\n    Choice: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            choice = "M"

        if choice == "S":
            # Read LLD from disk (may have been edited)
            if lld_draft_path and Path(lld_draft_path).exists():
                lld_content = Path(lld_draft_path).read_text(encoding="utf-8")
            else:
                lld_content = state.get("lld_content", "")

            return {
                "iteration_count": iteration,
                "next_node": "N3_review",
                "lld_content": lld_content,
                "user_feedback": "",
            }

        elif choice == "R":
            feedback = input("    Enter feedback for revision: ").strip()
            return {
                "iteration_count": iteration,
                "next_node": "N1_design",
                "user_feedback": feedback,
            }

        elif choice == "M":
            return {
                "iteration_count": iteration,
                "next_node": "END",
                "error_message": "MANUAL: User chose manual exit",
            }

        else:
            print("    Invalid choice. Enter S, R, or M.")


def review(state: LLDWorkflowState) -> dict:
    """N3: Submit LLD to Gemini governance review.

    - Calls existing governance.py
    - Parses verdict: APPROVED, BLOCKED
    - Saves verdict to audit trail
    - Checks iteration count vs max

    Args:
        state: Current workflow state.

    Returns:
        State updates with lld_status and gemini_critique.
    """
    print("\n[N3] Submitting to Gemini governance review...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_review(state)

    # Import governance node (reuse existing)
    from agentos.nodes.governance import review_lld_node

    # Call existing governance node
    # It expects: lld_content or lld_draft_path, issue_id, iteration_count
    # It returns: lld_status, gemini_critique, iteration_count
    governance_state = {
        "issue_id": state.get("issue_id", state.get("issue_number")),
        "lld_content": state.get("lld_content", ""),
        "lld_draft_path": state.get("lld_draft_path", ""),
        "iteration_count": state.get("iteration_count", 0),
    }

    result = review_lld_node(governance_state)

    lld_status = result.get("lld_status", "BLOCKED")
    gemini_critique = result.get("gemini_critique", "")

    # Save verdict to audit trail using shared helper
    audit_dir = Path(state.get("audit_dir", ""))
    file_num, verdict_count = _save_verdict_to_audit(
        audit_dir, lld_status, gemini_critique, state
    )

    print(f"    Status: {lld_status}")

    # Check max iterations
    iteration = state.get("iteration_count", 0)
    if lld_status != "APPROVED" and iteration >= MAX_ITERATIONS:
        return {
            "lld_status": lld_status,
            "gemini_critique": gemini_critique,
            "verdict_count": verdict_count,
            "file_counter": file_num if audit_dir.exists() else state.get("file_counter", 0),
            "error_message": f"Max iterations ({MAX_ITERATIONS}) reached. Please review manually.",
            "next_node": "END",
        }

    # Route based on verdict
    if lld_status == "APPROVED":
        next_node = "N4_finalize"
    else:
        next_node = "N2_human_edit"

    return {
        "lld_status": lld_status,
        "gemini_critique": gemini_critique,
        "verdict_count": verdict_count,
        "file_counter": file_num if audit_dir.exists() else state.get("file_counter", 0),
        "next_node": next_node,
        "error_message": "",
    }


def finalize(state: LLDWorkflowState) -> dict:
    """N4: Save approved LLD to final location.

    - Embeds review evidence in LLD content
    - Copies LLD to docs/lld/active/LLD-{issue_number}.md
    - Updates lld-status.json tracking cache
    - Saves approved.json metadata
    - Logs success message

    Args:
        state: Current workflow state.

    Returns:
        State updates with final_lld_path.
    """
    from datetime import datetime

    print("\n[N4] Finalizing approved LLD...")

    issue_number = state.get("issue_id", state.get("issue_number", 0))
    issue_title = state.get("issue_title", "")
    lld_content = state.get("lld_content", "")
    verdict_count = state.get("verdict_count", 1)

    # Embed review evidence in LLD content before saving
    review_date = datetime.now().strftime("%Y-%m-%d")
    lld_content = embed_review_evidence(
        lld_content,
        verdict="APPROVED",
        review_date=review_date,
        review_count=verdict_count,
    )
    print(f"    Embedded review evidence (Gemini #{verdict_count}, {review_date})")

    # Save final LLD
    final_path = save_final_lld(issue_number, lld_content)
    print(f"    Saved to: {final_path}")

    # Update tracking cache
    update_lld_status(
        issue_number=issue_number,
        lld_path=str(final_path),
        review_info={
            "has_gemini_review": True,
            "final_verdict": "APPROVED",
            "last_review_date": review_date,
            "review_count": verdict_count,
        },
    )
    print(f"    Updated lld-status.json tracking")

    # Save approved metadata to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_approved_metadata(
            audit_dir=audit_dir,
            number=file_num,
            issue_number=issue_number,
            issue_title=issue_title,
            final_lld_path=str(final_path),
            total_iterations=state.get("iteration_count", 0),
            draft_count=state.get("draft_count", 0),
            verdict_count=verdict_count,
        )
        print(f"    Metadata saved: {file_num:03d}-approved.json")

    print(f"\n    LLD #{issue_number} APPROVED and saved!")

    return {
        "final_lld_path": str(final_path),
        "error_message": "",
    }


# ---------------------------------------------------------------------------
# Mock implementations for testing
# ---------------------------------------------------------------------------


def _mock_fetch_issue(state: LLDWorkflowState) -> dict:
    """Mock implementation of fetch_issue for testing."""
    issue_number = state.get("issue_number", 42)

    # Create audit directory even in mock mode
    audit_dir = create_lld_audit_dir(issue_number)

    mock_title = f"Mock Issue #{issue_number}"
    mock_body = """## Requirements

This is a mock issue for testing the LLD workflow.

## Acceptance Criteria

- [ ] LLD is generated
- [ ] LLD passes governance review
"""

    # Save to audit trail
    file_num = next_file_number(audit_dir)
    issue_content = f"# Issue #{issue_number}: {mock_title}\n\n{mock_body}"
    save_audit_file(audit_dir, file_num, "issue.md", issue_content)

    print(f"    [MOCK] Loaded mock issue #{issue_number}")

    return {
        "issue_id": issue_number,
        "issue_title": mock_title,
        "issue_body": mock_body,
        "context_content": "",
        "audit_dir": str(audit_dir),
        "file_counter": file_num,
        "iteration_count": 0,
        "error_message": "",
    }


def _mock_design(state: LLDWorkflowState) -> dict:
    """Mock implementation of design for testing."""
    issue_number = state.get("issue_id", state.get("issue_number", 42))
    audit_dir = Path(state.get("audit_dir", ""))

    mock_lld = f"""# 1{issue_number:02d} - Feature: Mock LLD

## 1. Context & Goal

* **Issue:** #{issue_number}
* **Objective:** This is a mock LLD for testing.
* **Status:** Draft

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `mock/file.py` | Add | Mock file |

## 3. Requirements

1. Mock requirement 1
2. Mock requirement 2
"""

    # Save to audit trail using shared helper
    file_num, draft_count = _save_draft_to_audit(audit_dir, mock_lld, state)

    # Save to drafts directory for VS Code to open
    repo_root = get_repo_root()
    drafts_dir = repo_root / "docs" / "LLDs" / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    draft_path = drafts_dir / f"{issue_number}-LLD.md"
    draft_path.write_text(mock_lld, encoding="utf-8")

    print(f"    [MOCK] Generated mock LLD draft")

    return {
        "design_status": "DRAFTED",
        "lld_content": mock_lld,
        "lld_draft_path": str(draft_path),
        "draft_count": draft_count,
        "file_counter": file_num,
        "error_message": "",
    }


def _mock_review(state: LLDWorkflowState) -> dict:
    """Mock implementation of review for testing.

    Returns BLOCKED on first iteration, APPROVED on second.
    At max iterations, stays BLOCKED and returns error.
    """
    iteration = state.get("iteration_count", 0)
    audit_dir = Path(state.get("audit_dir", ""))

    # Check max iterations first - don't auto-approve at max
    if iteration >= MAX_ITERATIONS:
        lld_status = "BLOCKED"
        critique = """## Max Iterations Reached

The maximum number of iterations has been reached.
Please review the LLD manually.

## Verdict
[x] **BLOCKED** - Max iterations exceeded
"""
    # First iteration: reject
    elif iteration <= 1:
        lld_status = "BLOCKED"
        critique = """## Pre-Flight Gate: PASSED

## Tier 1: BLOCKING Issues

### Safety
- [ ] **Mock issue:** This is a mock rejection for testing purposes.

## Verdict
[x] **REVISE** - Fix Tier 1 issues first
"""
    # Second+ iteration (before max): approve
    else:
        lld_status = "APPROVED"
        critique = """## Pre-Flight Gate: PASSED

## Review Summary
The LLD meets all requirements.

## Tier 1: BLOCKING Issues
No blocking issues found.

## Verdict
[x] **APPROVED** - Ready for implementation
"""

    # Save verdict to audit trail using shared helper
    file_num, verdict_count = _save_verdict_to_audit(
        audit_dir, lld_status, critique, state
    )

    print(f"    [MOCK] Verdict: {lld_status}")

    # Determine next node
    if lld_status == "APPROVED":
        next_node = "N4_finalize"
    elif iteration >= MAX_ITERATIONS:
        next_node = "END"
    else:
        next_node = "N2_human_edit"

    return {
        "lld_status": lld_status,
        "gemini_critique": critique,
        "verdict_count": verdict_count,
        "file_counter": file_num,
        "next_node": next_node,
        "error_message": "" if iteration < MAX_ITERATIONS else f"Max iterations ({MAX_ITERATIONS}) reached",
    }
