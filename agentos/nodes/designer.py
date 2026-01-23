"""Designer node for AgentOS LangGraph workflows.

This module contains the Designer Node that drafts LLDs from GitHub Issues,
pausing for human editing before Governance review.

Issue: #56
LLD: docs/LLDs/active/56-designer-node.md
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from agentos.core.audit import GovernanceAuditLog, create_log_entry
from agentos.core.config import (
    GOVERNANCE_MODEL,
    LLD_DRAFTS_DIR,
    LLD_GENERATOR_PROMPT_PATH,
)
from agentos.core.gemini_client import GeminiClient
from agentos.core.state import AgentState


# GitHub repo for issue fetching
GITHUB_REPO = "martymcenroe/AgentOS"


def design_lld_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph node that drafts an LLD from a GitHub Issue.

    Process:
    1. Fetch issue content from GitHub via `gh issue view`
    2. Load system instruction from 0705-lld-generator.md
    3. Invoke Gemini via GeminiClient (uses GOVERNANCE_MODEL)
    4. Write draft to docs/llds/drafts/{issue_id}-LLD.md
    5. Print plain text prompt and block on input()
    6. Return state updates with draft path

    Args:
        state: The current AgentState containing issue_id.

    Returns:
        dict with keys: design_status, lld_draft_path, lld_content, iteration_count

    Fail-safe: Returns FAILED if:
    - Issue not found (404)
    - Model configuration invalid
    - All credentials exhausted
    - File write fails
    """
    # Initialize audit log
    audit_log = GovernanceAuditLog()

    # Increment iteration count
    iteration_count = state.get("iteration_count", 0) + 1

    # Get issue_id from state
    issue_id = state.get("issue_id", 0)

    # Track timing
    start_time = time.time()

    try:
        # Step 1: Fetch issue from GitHub
        try:
            title, body = _fetch_github_issue(issue_id)
        except ValueError as e:
            # Issue not found or fetch failed
            duration_ms = int((time.time() - start_time) * 1000)
            entry = create_log_entry(
                node="design_lld",
                model=GOVERNANCE_MODEL,
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
            }

        # Step 2: Load system instruction from 0705-lld-generator.md
        try:
            system_instruction = _load_generator_instruction()
        except FileNotFoundError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            entry = create_log_entry(
                node="design_lld",
                model=GOVERNANCE_MODEL,
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
            }

        # Step 3: Initialize GeminiClient with GOVERNANCE_MODEL
        # NUCLEAR WINTER: This will raise ValueError if model is forbidden
        client = GeminiClient(model=GOVERNANCE_MODEL)

        # Step 4: Build prompt and invoke Gemini
        content = f"## Issue Title\n{title}\n\n## Issue Body\n{body}"
        result = client.invoke(
            system_instruction=system_instruction,
            content=content,
        )

        if not result.success:
            # Gemini call failed
            duration_ms = int((time.time() - start_time) * 1000)
            entry = create_log_entry(
                node="design_lld",
                model=GOVERNANCE_MODEL,
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
            }

        # Step 5: Write draft to disk
        lld_content = result.response or ""
        try:
            draft_path = _write_draft(issue_id, lld_content)
        except OSError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            entry = create_log_entry(
                node="design_lld",
                model=GOVERNANCE_MODEL,
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
            }

        # Step 6: Log success to audit trail
        duration_ms = int((time.time() - start_time) * 1000)
        entry = create_log_entry(
            node="design_lld",
            model=GOVERNANCE_MODEL,
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

        # Step 7: Print and block for human edit
        _human_edit_pause(draft_path)

        # Step 8: Return state updates
        # lld_content is empty - Governance will read from disk
        return {
            "design_status": "DRAFTED",
            "lld_draft_path": str(draft_path),
            "lld_content": "",  # Empty - governance will read from disk
            "iteration_count": iteration_count,
        }

    except ValueError as e:
        # Model configuration error (NUCLEAR WINTER)
        duration_ms = int((time.time() - start_time) * 1000)
        entry = create_log_entry(
            node="design_lld",
            model=GOVERNANCE_MODEL,
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
        }

    except Exception as e:
        # Unexpected error - fail closed
        duration_ms = int((time.time() - start_time) * 1000)
        entry = create_log_entry(
            node="design_lld",
            model=GOVERNANCE_MODEL,
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
        }


def _fetch_github_issue(issue_id: int) -> tuple[str, str]:
    """
    Fetch issue content from GitHub.

    Args:
        issue_id: The GitHub issue number.

    Returns:
        Tuple of (title, body).

    Raises:
        ValueError: If issue not found or fetch fails.
    """
    # Validate issue_id is a positive integer (security: prevent command injection)
    if not isinstance(issue_id, int) or issue_id <= 0:
        raise ValueError(f"Invalid issue ID: {issue_id}")

    # Run gh issue view
    cmd = [
        "gh",
        "issue",
        "view",
        str(issue_id),
        "--repo",
        GITHUB_REPO,
        "--json",
        "title,body",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
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


def _write_draft(issue_id: int, content: str) -> Path:
    """
    Write LLD draft to disk.

    Args:
        issue_id: The GitHub issue number.
        content: The generated LLD content.

    Returns:
        Path to the written file.

    Raises:
        OSError: If file write fails.

    Creates docs/llds/drafts/ directory if it doesn't exist.
    """
    # Determine output path
    # Try relative path first, fall back to project root
    if LLD_DRAFTS_DIR.exists() or LLD_DRAFTS_DIR.parent.exists():
        output_dir = LLD_DRAFTS_DIR
    else:
        project_root = Path(__file__).parent.parent.parent
        output_dir = project_root / LLD_DRAFTS_DIR

    # Create directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write file
    output_path = output_dir / f"{issue_id}-LLD.md"
    output_path.write_text(content, encoding="utf-8")

    return output_path


def _human_edit_pause(draft_path: Path) -> None:
    """
    Print prompt and block until user presses Enter.

    Args:
        draft_path: Path to the draft file (shown in prompt).

    Output:
        Draft saved: docs/llds/drafts/56-LLD.md
        Edit the file, then press Enter to continue...
    """
    print(f"Draft saved: {draft_path}")
    input("Edit the file, then press Enter to continue...")
