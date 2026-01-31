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
    log_workflow_execution,
    next_file_number,
    save_approved_metadata,
    save_audit_file,
    save_final_lld,
    update_lld_status,
)
from agentos.workflows.lld.state import HumanDecision, LLDWorkflowState

# Configuration constants
GH_CLI_TIMEOUT_SECONDS = 30

# Default maximum iterations (can be overridden via state["max_iterations"])
DEFAULT_MAX_ITERATIONS = 20


def open_vscode_folder(folder_path: str) -> tuple[bool, str]:
    """Open a folder in VS Code for review.

    Args:
        folder_path: Path to the folder to open.

    Returns:
        Tuple of (success, error_message).
    """
    import os
    from datetime import datetime

    # Test mode: skip VS Code launch
    if os.environ.get("AGENTOS_TEST_MODE") == "1":
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] TEST MODE: Skipping VS Code launch for folder {folder_path}")
        return True, ""

    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Launching VS Code: code {folder_path}")
        result = subprocess.run(
            ["code", folder_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            error = f"VS Code exited with code {result.returncode}"
            if result.stderr:
                error += f": {result.stderr.strip()}"
            return False, error
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "VS Code launch timed out"
    except FileNotFoundError:
        return False, "'code' command not found. Is VS Code installed and in PATH?"
    except Exception as e:
        return False, f"Unexpected error launching VS Code: {type(e).__name__}: {e}"


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

    Note:
        Logs a warning if audit_dir doesn't exist (Part 4.2 fix).
    """
    draft_count = state.get("draft_count", 0) + 1
    file_num = state.get("file_counter", 0)

    if not audit_dir.exists():
        # Part 4.2 fix: Log warning instead of silent failure
        print(f"    [WARN] Audit directory does not exist: {audit_dir}")
        print(f"    [WARN] Draft NOT saved to audit trail!")
        return file_num, draft_count

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

    Note:
        Logs a warning if audit_dir doesn't exist (Part 4.2 fix).
    """
    verdict_count = state.get("verdict_count", 0) + 1
    file_num = state.get("file_counter", 0)

    if not audit_dir.exists():
        # Part 4.2 fix: Log warning instead of silent failure
        print(f"    [WARN] Audit directory does not exist: {audit_dir}")
        print(f"    [WARN] Verdict NOT saved to audit trail!")
        return file_num, verdict_count

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

    # Get repo_root from state for cross-repo workflows
    repo_root_str = state.get("repo_root", "")
    repo_root = repo_root_str if repo_root_str else None

    try:
        # --------------------------------------------------------------------------
        # GUARD: Cross-repo verification - log which repo we're operating on (Issue #101)
        # --------------------------------------------------------------------------
        try:
            repo_check = subprocess.run(
                ["gh", "repo", "view", "--json", "nameWithOwner"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GH_CLI_TIMEOUT_SECONDS,
                cwd=repo_root,
            )
            if repo_check.returncode == 0 and repo_check.stdout:
                repo_data = json.loads(repo_check.stdout)
                actual_repo = repo_data.get("nameWithOwner", "unknown")
                print(f"    [GUARD] Operating on repo: {actual_repo}")
        except Exception as e:
            print(f"    [GUARD] WARNING: Could not verify repo identity: {e}")
        # --------------------------------------------------------------------------

        # Fetch issue via gh CLI (use cwd for cross-repo workflows)
        # Use encoding='utf-8' to handle Unicode characters in issue bodies
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "title,body"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # Replace undecodable chars instead of crashing
            timeout=GH_CLI_TIMEOUT_SECONDS,
            cwd=repo_root,
        )

        if result.returncode != 0:
            return {
                "error_message": f"Issue #{issue_number} not found: {result.stderr.strip()}"
            }

        if not result.stdout:
            return {
                "error_message": f"Issue #{issue_number} returned empty response"
            }

        issue_data = json.loads(result.stdout)
        issue_title = issue_data.get("title", "")
        issue_body = issue_data.get("body", "")

        # --------------------------------------------------------------------------
        # GUARD: Input validation - check issue content (Issue #101)
        # --------------------------------------------------------------------------
        if not issue_body or not issue_body.strip():
            print(f"    [GUARD] WARNING: Issue #{issue_number} has empty body")

        if issue_title and len(issue_title) < 5:
            print(f"    [GUARD] WARNING: Issue #{issue_number} has very short title")
        # --------------------------------------------------------------------------

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

    # Create audit directory (use repo_root for cross-repo workflows)
    repo_root_path = Path(repo_root) if repo_root else None
    audit_dir = create_lld_audit_dir(issue_number, repo_root_path)
    print(f"    Audit dir: {audit_dir}")

    # Save issue to audit trail
    issue_content = f"# Issue #{issue_number}: {issue_title}\n\n{issue_body}"
    if context_content:
        issue_content += f"\n\n---\n\n# Context Files\n\n{context_content}"

    file_num = next_file_number(audit_dir)
    save_audit_file(audit_dir, file_num, "issue.md", issue_content)

    # Log workflow start to audit trail
    repo_root_for_audit = Path(repo_root) if repo_root else get_repo_root()
    log_workflow_execution(
        target_repo=repo_root_for_audit,
        issue_number=issue_number,
        workflow_type="lld",
        event="start",
        details={"issue_title": issue_title},
    )

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
    # Pass issue content from state to avoid re-fetching (cross-repo support)
    # Pass repo_root so draft is written to correct location
    # Pass user_feedback and lld_content for revision mode
    designer_state = {
        "issue_id": state.get("issue_id", state.get("issue_number")),
        "issue_title": state.get("issue_title", ""),
        "issue_body": state.get("issue_body", ""),
        "repo_root": state.get("repo_root", ""),
        "iteration_count": state.get("iteration_count", 0),
        "auto_mode": state.get("auto_mode", False),
        "user_feedback": state.get("user_feedback", ""),
        "lld_content": state.get("lld_content", ""),  # Previous draft for revision
    }

    result = design_lld_node(designer_state)

    design_status = result.get("design_status", "FAILED")
    lld_content = result.get("lld_content", "")
    lld_draft_path = result.get("lld_draft_path", "")

    if design_status == "FAILED":
        error_msg = result.get("error_message", "Unknown error")
        print(f"    [ERROR] Designer failed: {error_msg}")
        # Log error to audit trail (Part 2.1 fix)
        repo_root_str = state.get("repo_root", "")
        repo_root_path = Path(repo_root_str) if repo_root_str else get_repo_root()
        log_workflow_execution(
            target_repo=repo_root_path,
            issue_number=state.get("issue_id", state.get("issue_number", 0)),
            workflow_type="lld",
            event="error",
            details={"node": "N1_design", "error": error_msg},
        )
        return {
            "error_message": f"Designer node failed: {error_msg}",
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
        "gemini_critique": "",  # Clear critique after generating new draft
        "user_feedback": "",  # Clear feedback after it's been used
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
    max_iterations = state.get("max_iterations", DEFAULT_MAX_ITERATIONS)
    print(f"\n[N2] Human Edit Gate (Iteration {iteration}/{max_iterations})")

    # Auto mode: decide based on whether we have critique feedback
    if state.get("auto_mode"):
        gemini_critique = state.get("gemini_critique", "")

        if gemini_critique:
            # Previous review was BLOCKED - go back to design with critique as feedback
            print("    Auto mode: revision needed, returning to designer...")
            return {
                "iteration_count": iteration,
                "next_node": "N1_design",
                "user_feedback": f"Gemini review feedback:\n{gemini_critique}",
                # Preserve counters on loop-back (Part 1.1 fix)
                "draft_count": state.get("draft_count", 0),
                "verdict_count": state.get("verdict_count", 0),
                "file_counter": state.get("file_counter", 0),
            }
        else:
            # First iteration or just created - send to review
            print("    Auto mode: sending to review...")
            # Read LLD from disk (same as manual mode)
            lld_draft_path = state.get("lld_draft_path", "")
            if lld_draft_path and Path(lld_draft_path).exists():
                lld_content = Path(lld_draft_path).read_text(encoding="utf-8")
            else:
                lld_content = state.get("lld_content", "")
            return {
                "iteration_count": iteration,
                "next_node": "N3_review",
                "lld_content": lld_content,
                "user_feedback": "",
                # Preserve counters through transitions (Part 1.1 fix)
                "draft_count": state.get("draft_count", 0),
                "verdict_count": state.get("verdict_count", 0),
                "file_counter": state.get("file_counter", 0),
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
                # Preserve counters through transitions (Part 1.1 fix)
                "draft_count": state.get("draft_count", 0),
                "verdict_count": state.get("verdict_count", 0),
                "file_counter": state.get("file_counter", 0),
            }

        elif choice == "R":
            feedback = input("    Enter feedback for revision: ").strip()
            return {
                "iteration_count": iteration,
                "next_node": "N1_design",
                "user_feedback": feedback,
                # Preserve counters on loop-back (Part 1.1 fix)
                "draft_count": state.get("draft_count", 0),
                "verdict_count": state.get("verdict_count", 0),
                "file_counter": state.get("file_counter", 0),
            }

        elif choice == "M":
            # Log manual exit to audit trail (Part 2.1 fix)
            repo_root_str = state.get("repo_root", "")
            repo_root_path = Path(repo_root_str) if repo_root_str else get_repo_root()
            log_workflow_execution(
                target_repo=repo_root_path,
                issue_number=state.get("issue_id", state.get("issue_number", 0)),
                workflow_type="lld",
                event="manual_exit",
                details={"iteration_count": iteration},
            )
            return {
                "iteration_count": iteration,
                "next_node": "END",
                "error_message": "MANUAL: User chose manual exit",
                # Preserve counters even on exit (for checkpoint/resume)
                "draft_count": state.get("draft_count", 0),
                "verdict_count": state.get("verdict_count", 0),
                "file_counter": state.get("file_counter", 0),
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

    # --------------------------------------------------------------------------
    # GUARD: Pre-LLM content validation (Issue #101)
    # --------------------------------------------------------------------------
    lld_content = state.get("lld_content", "")
    lld_draft_path = state.get("lld_draft_path", "")

    # If content empty, try reading from draft file
    if not lld_content and lld_draft_path and Path(lld_draft_path).exists():
        lld_content = Path(lld_draft_path).read_text(encoding="utf-8")

    if not lld_content or not lld_content.strip():
        print("    [GUARD] BLOCKED: Draft is empty - cannot send to reviewer")
        # Log guard block to audit trail (Part 2.1 fix)
        repo_root_str = state.get("repo_root", "")
        repo_root_path = Path(repo_root_str) if repo_root_str else get_repo_root()
        log_workflow_execution(
            target_repo=repo_root_path,
            issue_number=state.get("issue_id", state.get("issue_number", 0)),
            workflow_type="lld",
            event="guard_block",
            details={"reason": "empty_draft", "node": "N3_review"},
        )
        return {"error_message": "GUARD: Draft is empty - cannot send to reviewer"}

    content_len = len(lld_content)
    if content_len < 100:
        print(f"    [GUARD] WARNING: Draft suspiciously short ({content_len} chars)")

    if content_len > 100000:
        print(f"    [GUARD] BLOCKED: Draft too large ({content_len} chars)")
        # Log guard block to audit trail (Part 2.1 fix)
        repo_root_str = state.get("repo_root", "")
        repo_root_path = Path(repo_root_str) if repo_root_str else get_repo_root()
        log_workflow_execution(
            target_repo=repo_root_path,
            issue_number=state.get("issue_id", state.get("issue_number", 0)),
            workflow_type="lld",
            event="guard_block",
            details={"reason": "draft_too_large", "chars": content_len, "node": "N3_review"},
        )
        return {"error_message": f"GUARD: Draft too large ({content_len} chars)"}
    # --------------------------------------------------------------------------

    # Import governance node (reuse existing)
    from agentos.nodes.governance import review_lld_node

    # Call existing governance node
    # It expects: lld_content or lld_draft_path, issue_id, iteration_count
    # It returns: lld_status, gemini_critique, iteration_count
    governance_state = {
        "issue_id": state.get("issue_id", state.get("issue_number")),
        "lld_content": lld_content,  # Use validated content
        "lld_draft_path": lld_draft_path,
        "iteration_count": state.get("iteration_count", 0),
    }

    result = review_lld_node(governance_state)

    lld_status = result.get("lld_status", "BLOCKED")
    gemini_critique = result.get("gemini_critique", "")

    # --------------------------------------------------------------------------
    # GUARD: Post-LLM response validation (Issue #101)
    # --------------------------------------------------------------------------
    if not gemini_critique or not gemini_critique.strip():
        print("    [GUARD] WARNING: Reviewer returned empty response")
        # Don't fail, but log warning - empty critique is unusual but not fatal

    # Check for valid verdict markers
    critique_upper = gemini_critique.upper() if gemini_critique else ""
    if "APPROVED" not in critique_upper and "BLOCKED" not in critique_upper:
        if "REVISE" not in critique_upper:  # Also accept REVISE as a valid verdict
            print("    [GUARD] WARNING: Verdict missing APPROVED/BLOCKED markers")
    # --------------------------------------------------------------------------

    # Save verdict to audit trail using shared helper
    audit_dir = Path(state.get("audit_dir", ""))
    file_num, verdict_count = _save_verdict_to_audit(
        audit_dir, lld_status, gemini_critique, state
    )

    print(f"    Status: {lld_status}")

    # Check max iterations
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", DEFAULT_MAX_ITERATIONS)
    if lld_status != "APPROVED" and iteration >= max_iterations:
        # Log max iterations to audit trail (Part 2.1 fix)
        repo_root_str = state.get("repo_root", "")
        repo_root_path = Path(repo_root_str) if repo_root_str else get_repo_root()
        log_workflow_execution(
            target_repo=repo_root_path,
            issue_number=state.get("issue_id", state.get("issue_number", 0)),
            workflow_type="lld",
            event="max_iterations",
            details={
                "iteration_count": iteration,
                "max_iterations": max_iterations,
                "last_status": lld_status,
            },
        )
        return {
            "lld_status": lld_status,
            "gemini_critique": gemini_critique,
            "verdict_count": verdict_count,
            "file_counter": file_num if audit_dir.exists() else state.get("file_counter", 0),
            "error_message": f"MAX_ITERATIONS_REACHED:{max_iterations}",
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
    lld_draft_path = state.get("lld_draft_path", "")
    verdict_count = state.get("verdict_count", 1)

    # Get repo_root from state for cross-repo workflows (moved earlier for error logging)
    repo_root_str = state.get("repo_root", "")
    repo_root_path = Path(repo_root_str) if repo_root_str else None

    # Safety: if lld_content is empty, read from draft path
    if not lld_content and lld_draft_path and Path(lld_draft_path).exists():
        print(f"    Reading LLD from disk: {lld_draft_path}")
        lld_content = Path(lld_draft_path).read_text(encoding="utf-8")

    if not lld_content:
        # Log error to audit trail (Part 2.1 fix)
        log_workflow_execution(
            target_repo=repo_root_path or get_repo_root(),
            issue_number=issue_number,
            workflow_type="lld",
            event="error",
            details={"node": "N4_finalize", "error": "empty_lld_content"},
        )
        return {"error_message": "No LLD content to save - lld_content is empty and no draft file found"}

    # Embed review evidence in LLD content before saving
    review_date = datetime.now().strftime("%Y-%m-%d")
    lld_content = embed_review_evidence(
        lld_content,
        verdict="APPROVED",
        review_date=review_date,
        review_count=verdict_count,
    )
    print(f"    Embedded review evidence (Gemini #{verdict_count}, {review_date})")

    # Save final LLD (use repo_root for cross-repo workflows)
    final_path = save_final_lld(issue_number, lld_content, repo_root_path)
    print(f"    Saved to: {final_path}")

    # --------------------------------------------------------------------------
    # GUARD: Output verification - verify file was written correctly (Issue #101)
    # --------------------------------------------------------------------------
    if not final_path.exists():
        print(f"    [GUARD] ERROR: LLD file not created at {final_path}")
        # Log guard error to audit trail (Part 2.1 fix)
        log_workflow_execution(
            target_repo=repo_root_path or get_repo_root(),
            issue_number=issue_number,
            workflow_type="lld",
            event="guard_error",
            details={"node": "N4_finalize", "error": "file_not_created", "path": str(final_path)},
        )
        return {"error_message": f"GUARD: LLD file not created at {final_path}"}

    saved_content = final_path.read_text(encoding="utf-8")
    saved_len = len(saved_content)
    if saved_len < 200:
        print(f"    [GUARD] WARNING: Saved LLD suspiciously small ({saved_len} chars)")

    if saved_len == 0:
        print(f"    [GUARD] ERROR: Saved LLD is empty!")
        # Log guard error to audit trail (Part 2.1 fix)
        log_workflow_execution(
            target_repo=repo_root_path or get_repo_root(),
            issue_number=issue_number,
            workflow_type="lld",
            event="guard_error",
            details={"node": "N4_finalize", "error": "saved_file_empty", "path": str(final_path)},
        )
        return {"error_message": f"GUARD: Saved LLD is empty at {final_path}"}
    # --------------------------------------------------------------------------

    # Update tracking cache (use repo_root for cross-repo workflows)
    update_lld_status(
        issue_number=issue_number,
        lld_path=str(final_path),
        review_info={
            "has_gemini_review": True,
            "final_verdict": "APPROVED",
            "last_review_date": review_date,
            "review_count": verdict_count,
        },
        repo_root=repo_root_path,
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

    # Log workflow completion to audit trail
    log_workflow_execution(
        target_repo=repo_root_path or get_repo_root(),
        issue_number=issue_number,
        workflow_type="lld",
        event="complete",
        details={
            "final_lld_path": str(final_path),
            "verdict_count": verdict_count,
            "iteration_count": state.get("iteration_count", 0),
        },
    )

    # Auto mode: open audit trail folder for review (since we skipped VS Code during workflow)
    import os
    if os.environ.get("AGENTOS_AUTO_MODE") == "1" and audit_dir.exists():
        print(f"\n>>> Opening audit trail for review...")
        success, error = open_vscode_folder(str(audit_dir))
        if not success:
            print(f"Warning: Failed to open VS Code: {error}")

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

    # Create audit directory even in mock mode (use repo_root for cross-repo)
    repo_root_str = state.get("repo_root", "")
    repo_root_path = Path(repo_root_str) if repo_root_str else None
    audit_dir = create_lld_audit_dir(issue_number, repo_root_path)

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

    # Save to drafts directory for VS Code to open (use repo_root from state for cross-repo)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
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
        "gemini_critique": "",  # Clear critique after generating new draft
        "user_feedback": "",  # Clear feedback after it's been used
        "error_message": "",
    }


def _mock_review(state: LLDWorkflowState) -> dict:
    """Mock implementation of review for testing.

    Returns BLOCKED on first iteration, APPROVED on second.
    At max iterations, stays BLOCKED and returns error.
    """
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", DEFAULT_MAX_ITERATIONS)
    audit_dir = Path(state.get("audit_dir", ""))

    # Check max iterations first - don't auto-approve at max
    if iteration >= max_iterations:
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
    elif iteration >= max_iterations:
        next_node = "END"
    else:
        next_node = "N2_human_edit"

    return {
        "lld_status": lld_status,
        "gemini_critique": critique,
        "verdict_count": verdict_count,
        "file_counter": file_num,
        "next_node": next_node,
        "error_message": "" if iteration < max_iterations else f"MAX_ITERATIONS_REACHED:{max_iterations}",
    }
