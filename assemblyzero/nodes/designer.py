"""Designer node for AssemblyZero LangGraph workflows.

This module contains the Designer Node that drafts LLDs from GitHub Issues,
pausing for human editing before LLD review.

Issue: #56
LLD: docs/lld/active/56-designer-node.md

Cross-repo support (Issue #86):
- Accepts issue_title, issue_body from state (skips re-fetch)
- Accepts repo_root from state (writes to correct repo)
- Returns actual lld_content (not empty)
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from assemblyzero.core.audit import ReviewAuditLog, create_log_entry
from assemblyzero.core.config import (
    REVIEWER_MODEL,
    LLD_DRAFTS_DIR,
    LLD_GENERATOR_PROMPT_PATH,
)
from assemblyzero.core.gemini_client import CredentialPoolExhaustedException, GeminiClient
from assemblyzero.core.state import AgentState


# Default GitHub repo for issue fetching (only used if not provided in state)
DEFAULT_GITHUB_REPO = "martymcenroe/AssemblyZero"


def design_lld_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph node that drafts an LLD from a GitHub Issue.

    Process:
    1. Use issue content from state OR fetch from GitHub via `gh issue view`
    2. Load system instruction from 0705-lld-generator.md
    3. Invoke Gemini via GeminiClient (uses REVIEWER_MODEL)
    4. Write draft to repo_root/docs/llds/drafts/{issue_id}-LLD.md
    5. Print plain text prompt and block on input()
    6. Return state updates with draft path AND content

    Args:
        state: The current AgentState containing:
            - issue_id: GitHub issue number
            - issue_title (optional): Pre-fetched issue title
            - issue_body (optional): Pre-fetched issue body
            - repo_root (optional): Target repository root path
            - auto_mode (optional): Skip human edit pause

    Returns:
        dict with keys: design_status, lld_draft_path, lld_content, iteration_count

    Fail-safe: Returns FAILED if:
    - Issue not found (404)
    - Model configuration invalid
    - All credentials exhausted
    - File write fails
    """
    # Initialize audit log
    audit_log = ReviewAuditLog()

    # Increment iteration count
    iteration_count = state.get("iteration_count", 0) + 1

    # Get issue_id from state
    issue_id = state.get("issue_id", 0)

    # Get repo_root for cross-repo workflows
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else None

    # Track timing
    start_time = time.time()

    try:
        # Step 1: Get issue content from state OR fetch from GitHub
        # Cross-repo workflows pass issue_title/issue_body in state
        title = state.get("issue_title", "")
        body = state.get("issue_body", "")

        if title and body:
            # Use pre-fetched content from state (cross-repo workflow)
            print(f"    Using issue content from state: {title[:50]}...")
        else:
            # Fetch from GitHub (legacy single-repo workflow)
            try:
                title, body = _fetch_github_issue(issue_id, repo_root)
            except ValueError as e:
                # Issue not found or fetch failed
                duration_ms = int((time.time() - start_time) * 1000)
                entry = create_log_entry(
                    node="design_lld",
                    model=REVIEWER_MODEL,
                    model_verified="",
                    issue_id=issue_id,
                    verdict="FAILED",
                    critique=str(e),
                    tier_1_issues=["Issue fetch failed"],
                    raw_response="",
                    duration_ms=duration_ms,
                    credential_used="",
                    rotation_occurred=False,
                    attempts=0,
                    sequence_id=iteration_count,
                )
                audit_log.log(entry)

                return {
                    "design_status": "FAILED",
                    "lld_draft_path": "",
                    "lld_content": "",
                    "iteration_count": iteration_count,
                    "error_message": str(e),
                }

        # Step 2: Load system instruction from 0705-lld-generator.md
        try:
            system_instruction = _load_generator_instruction()
        except FileNotFoundError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            entry = create_log_entry(
                node="design_lld",
                model=REVIEWER_MODEL,
                model_verified="",
                issue_id=issue_id,
                verdict="FAILED",
                critique=str(e),
                tier_1_issues=["Generator prompt not found"],
                raw_response="",
                duration_ms=duration_ms,
                credential_used="",
                rotation_occurred=False,
                attempts=0,
                sequence_id=iteration_count,
            )
            audit_log.log(entry)

            return {
                "design_status": "FAILED",
                "lld_draft_path": "",
                "lld_content": "",
                "iteration_count": iteration_count,
                "error_message": str(e),
            }

        # Step 3: Initialize GeminiClient with REVIEWER_MODEL
        # NUCLEAR WINTER: This will raise ValueError if model is forbidden
        client = GeminiClient(model=REVIEWER_MODEL)

        # Step 4: Build prompt and invoke Gemini
        # Include feedback and previous draft if this is a revision
        user_feedback = state.get("user_feedback", "")
        previous_draft = state.get("lld_content", "")

        content = f"## Issue Number\n#{issue_id}\n\n## Issue Title\n{title}\n\n## Issue Body\n{body}"

        if user_feedback and previous_draft:
            # Revision mode: include previous draft and feedback
            content += f"\n\n## Previous LLD Draft (REVISE THIS)\n{previous_draft}"
            content += f"\n\n## Reviewer Feedback\n{user_feedback}"
            content += "\n\n## CRITICAL REVISION INSTRUCTIONS"
            content += "\n1. Address ALL issues in the NEW FEEDBACK section above"
            content += "\n2. Self-audit against PREVIOUS FEEDBACK to ensure you have not regressed on any previously-fixed issues"
            content += "\n3. If previous feedback mentioned scope confinement, observability, or safety - verify these are STILL correct"
            content += "\n4. Do NOT remove sections that were already correct"
            print("    Revision mode: incorporating reviewer feedback...")
        elif user_feedback:
            # Feedback but no draft - include feedback only
            content += f"\n\n## Reviewer Feedback\n{user_feedback}"
        result = client.invoke(
            system_instruction=system_instruction,
            content=content,
        )

        if not result.success:
            # Check if ALL credentials are exhausted - pause workflow instead of failing
            if result.pool_exhausted:
                raise CredentialPoolExhaustedException(
                    message=f"All Gemini credentials exhausted during LLD design for #{issue_id}",
                    earliest_reset=result.earliest_reset,
                    exhausted_credentials=[],  # Not easily available here
                )

            # Gemini call failed (not quota exhaustion)
            duration_ms = int((time.time() - start_time) * 1000)
            entry = create_log_entry(
                node="design_lld",
                model=REVIEWER_MODEL,
                model_verified=result.model_verified,
                issue_id=issue_id,
                verdict="FAILED",
                critique=result.error_message or "Gemini API error",
                tier_1_issues=["Gemini call failed"],
                raw_response="",
                duration_ms=duration_ms,
                credential_used=result.credential_used,
                rotation_occurred=result.rotation_occurred,
                attempts=result.attempts,
                sequence_id=iteration_count,
            )
            audit_log.log(entry)

            return {
                "design_status": "FAILED",
                "lld_draft_path": "",
                "lld_content": "",
                "iteration_count": iteration_count,
                "error_message": result.error_message or "Gemini API error",
            }

        # Step 5: Write draft to disk (use repo_root for cross-repo workflows)
        lld_content = result.response or ""
        try:
            draft_path = _write_draft(issue_id, lld_content, repo_root)
        except OSError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            entry = create_log_entry(
                node="design_lld",
                model=REVIEWER_MODEL,
                model_verified=result.model_verified,
                issue_id=issue_id,
                verdict="FAILED",
                critique=f"File write failed: {e}",
                tier_1_issues=["File write failed"],
                raw_response=result.raw_response or "",
                duration_ms=duration_ms,
                credential_used=result.credential_used,
                rotation_occurred=result.rotation_occurred,
                attempts=result.attempts,
                sequence_id=iteration_count,
            )
            audit_log.log(entry)

            return {
                "design_status": "FAILED",
                "lld_draft_path": "",
                "lld_content": "",
                "iteration_count": iteration_count,
                "error_message": f"File write failed: {e}",
            }

        # Step 6: Log success to audit trail
        duration_ms = int((time.time() - start_time) * 1000)
        entry = create_log_entry(
            node="design_lld",
            model=REVIEWER_MODEL,
            model_verified=result.model_verified,
            issue_id=issue_id,
            verdict="DRAFTED",
            critique=f"LLD draft saved to {draft_path}",
            tier_1_issues=[],
            raw_response=result.raw_response or "",
            duration_ms=duration_ms,
            credential_used=result.credential_used,
            rotation_occurred=result.rotation_occurred,
            attempts=result.attempts,
            sequence_id=iteration_count,
        )
        audit_log.log(entry)

        # Step 7: Print and block for human edit (unless auto mode)
        auto_mode = state.get("auto_mode", False)
        _human_edit_pause(draft_path, auto_mode=auto_mode)

        # Step 8: Return state updates
        # Return actual lld_content so audit trail and subsequent nodes have it
        return {
            "design_status": "DRAFTED",
            "lld_draft_path": str(draft_path),
            "lld_content": lld_content,  # Return actual content for audit trail
            "iteration_count": iteration_count,
        }

    except ValueError as e:
        # Model configuration error (NUCLEAR WINTER)
        duration_ms = int((time.time() - start_time) * 1000)
        entry = create_log_entry(
            node="design_lld",
            model=REVIEWER_MODEL,
            model_verified="",
            issue_id=issue_id,
            verdict="FAILED",
            critique=f"Model configuration error: {e}",
            tier_1_issues=["Invalid model configuration"],
            raw_response="",
            duration_ms=duration_ms,
            credential_used="",
            rotation_occurred=False,
            attempts=0,
            sequence_id=iteration_count,
        )
        audit_log.log(entry)

        return {
            "design_status": "FAILED",
            "lld_draft_path": "",
            "lld_content": "",
            "iteration_count": iteration_count,
            "error_message": f"Model configuration error: {e}",
        }

    except Exception as e:
        # Unexpected error - fail closed
        duration_ms = int((time.time() - start_time) * 1000)
        entry = create_log_entry(
            node="design_lld",
            model=REVIEWER_MODEL,
            model_verified="",
            issue_id=issue_id,
            verdict="FAILED",
            critique=f"Unexpected error: {e}",
            tier_1_issues=["Fail-safe triggered"],
            raw_response="",
            duration_ms=duration_ms,
            credential_used="",
            rotation_occurred=False,
            attempts=0,
            sequence_id=iteration_count,
        )
        audit_log.log(entry)

        return {
            "design_status": "FAILED",
            "lld_draft_path": "",
            "lld_content": "",
            "iteration_count": iteration_count,
            "error_message": f"Unexpected error: {e}",
        }


def _fetch_github_issue(issue_id: int, repo_root: Path | None = None) -> tuple[str, str]:
    """
    Fetch issue content from GitHub.

    Args:
        issue_id: The GitHub issue number.
        repo_root: Optional path to run gh from (for cross-repo workflows).
                   If provided, gh will infer repo from git remote.
                   If not provided, uses DEFAULT_GITHUB_REPO.

    Returns:
        Tuple of (title, body).

    Raises:
        ValueError: If issue not found or fetch fails.
    """
    # Validate issue_id is a positive integer (security: prevent command injection)
    if not isinstance(issue_id, int) or issue_id <= 0:
        raise ValueError(f"Invalid issue ID: {issue_id}")

    # Build gh command
    # If repo_root provided, run gh in that directory (infers repo from git)
    # Otherwise, use explicit --repo flag with default
    if repo_root and repo_root.exists():
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_id),
            "--json",
            "title,body",
        ]
        cwd = str(repo_root)
    else:
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_id),
            "--repo",
            DEFAULT_GITHUB_REPO,
            "--json",
            "title,body",
        ]
        cwd = None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        raise ValueError(f"Timeout fetching issue #{issue_id}")
    except FileNotFoundError:
        raise ValueError(
            "gh CLI not installed. Install from https://cli.github.com/ "
            "and run `gh auth login`"
        )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "Could not resolve" in stderr or "not found" in stderr.lower():
            raise ValueError(f"Issue #{issue_id} not found")
        raise ValueError(f"Failed to fetch issue #{issue_id}: {stderr}")

    # Parse JSON response
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response from gh: {e}")

    title = data.get("title", "")
    body = data.get("body", "")

    if not title:
        raise ValueError(f"Issue #{issue_id} has no title")

    return title, body


def _load_generator_instruction() -> str:
    """
    Load LLD generator prompt from docs/skills/0705-lld-generator.md.

    Returns:
        The system instruction text.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    # Try relative path first (for testing)
    if LLD_GENERATOR_PROMPT_PATH.exists():
        prompt_path = LLD_GENERATOR_PROMPT_PATH
    else:
        # Try from project root
        project_root = Path(__file__).parent.parent.parent
        prompt_path = project_root / LLD_GENERATOR_PROMPT_PATH

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"LLD generator prompt not found at: {prompt_path}\n"
            f"Expected path: {LLD_GENERATOR_PROMPT_PATH}"
        )

    return prompt_path.read_text(encoding="utf-8")


def _write_draft(issue_id: int, content: str, repo_root: Path | None = None) -> Path:
    """
    Write LLD draft to disk.

    Args:
        issue_id: The GitHub issue number.
        content: The generated LLD content.
        repo_root: Optional target repository root (for cross-repo workflows).
                   If provided, writes to repo_root/docs/llds/drafts/.
                   If not provided, uses relative LLD_DRAFTS_DIR.

    Returns:
        Path to the written file.

    Raises:
        OSError: If file write fails.

    Creates docs/llds/drafts/ directory if it doesn't exist.
    """
    # Determine output path based on repo_root
    if repo_root and repo_root.exists():
        # Cross-repo workflow: write to target repo
        output_dir = repo_root / "docs" / "llds" / "drafts"
    elif LLD_DRAFTS_DIR.exists() or LLD_DRAFTS_DIR.parent.exists():
        # Relative path exists
        output_dir = LLD_DRAFTS_DIR
    else:
        # Fall back to AssemblyZero project root
        project_root = Path(__file__).parent.parent.parent
        output_dir = project_root / LLD_DRAFTS_DIR

    # Create directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write file
    output_path = output_dir / f"{issue_id}-LLD.md"
    output_path.write_text(content, encoding="utf-8")

    return output_path


def _human_edit_pause(draft_path: Path, auto_mode: bool = False) -> None:
    """
    Print prompt and block until user presses Enter.

    Args:
        draft_path: Path to the draft file (shown in prompt).
        auto_mode: If True, skip the blocking input() call.

    Output:
        Draft saved: docs/llds/drafts/56-LLD.md
        Edit the file, then press Enter to continue...
    """
    print(f"Draft saved: {draft_path}")
    if not auto_mode:
        input("Edit the file, then press Enter to continue...")
