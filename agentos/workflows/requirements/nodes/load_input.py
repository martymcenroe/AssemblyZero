"""N0: Load input node for Requirements Workflow.

Issue #101: Unified Requirements Workflow

Handles loading input for both workflow types:
- Issue workflow: Load brief file content
- LLD workflow: Fetch GitHub issue via gh CLI

Creates audit directory and saves initial input to audit trail.
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from agentos.workflows.requirements.audit import (
    assemble_context,
    create_audit_dir,
    generate_slug,
    next_file_number,
    save_audit_file,
)
from agentos.workflows.requirements.state import RequirementsWorkflowState


# Timeout for gh CLI commands
GH_CLI_TIMEOUT_SECONDS = 30

# Retry configuration for gh CLI
GH_MAX_RETRIES = 3
GH_BACKOFF_BASE_SECONDS = 1.0
GH_BACKOFF_MAX_SECONDS = 10.0


def load_input(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N0: Load input based on workflow type.

    For issue workflow:
    - Loads brief file content
    - Generates slug from filename
    - Creates audit directory
    - Saves brief to audit trail

    For LLD workflow:
    - Fetches issue from GitHub via gh CLI
    - Assembles context from context_files
    - Creates audit directory
    - Saves issue content to audit trail

    Args:
        state: Current workflow state.

    Returns:
        State updates with input content and audit_dir.
    """
    workflow_type = state.get("workflow_type", "lld")

    if workflow_type == "issue":
        return _load_brief(state)
    else:
        return _load_issue(state)


def _load_brief(state: RequirementsWorkflowState) -> dict[str, Any]:
    """Load brief file for issue workflow.

    Args:
        state: Current workflow state.

    Returns:
        State updates with brief_content, slug, and audit_dir.
    """
    brief_file = state.get("brief_file", "")
    target_repo = Path(state.get("target_repo", ""))

    if not brief_file:
        return {"error_message": "No brief file specified"}

    brief_path = Path(brief_file)
    if not brief_path.is_absolute():
        brief_path = target_repo / brief_path

    if not brief_path.exists():
        return {"error_message": f"Brief file not found: {brief_path}"}

    # Load content
    try:
        brief_content = brief_path.read_text(encoding="utf-8")
    except OSError as e:
        return {"error_message": f"Failed to read brief: {e}"}

    # Generate slug
    slug = generate_slug(str(brief_file))

    # Create audit directory
    audit_dir = create_audit_dir(
        workflow_type="issue",
        slug=slug,
        target_repo=target_repo,
    )

    # Save brief to audit trail
    file_num = next_file_number(audit_dir)
    save_audit_file(audit_dir, file_num, "brief.md", brief_content)

    return {
        "brief_content": brief_content,
        "slug": slug,
        "audit_dir": str(audit_dir),
        "file_counter": file_num,
        "error_message": "",
    }


def _load_issue(state: RequirementsWorkflowState) -> dict[str, Any]:
    """Load GitHub issue for LLD workflow.

    Args:
        state: Current workflow state.

    Returns:
        State updates with issue content and audit_dir.
    """
    issue_number = state.get("issue_number", 0)
    target_repo = Path(state.get("target_repo", ""))
    context_files = state.get("context_files", [])

    if not issue_number:
        return {"error_message": "No issue number specified"}

    # Check for mock mode
    if state.get("config_mock_mode"):
        return _mock_load_issue(state)

    # Fetch issue via gh CLI with exponential backoff retry
    issue_data = None
    last_error = ""

    for attempt in range(1, GH_MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                ["gh", "issue", "view", str(issue_number), "--json", "title,body"],
                capture_output=True,
                text=True,
                timeout=GH_CLI_TIMEOUT_SECONDS,
                cwd=str(target_repo),
            )

            if result.returncode != 0:
                last_error = f"Issue #{issue_number} not found: {result.stderr.strip()}"
                # Non-zero return code is likely a permanent error (issue doesn't exist)
                break

            if not result.stdout:
                last_error = f"Empty response from gh issue view #{issue_number} (attempt {attempt}/{GH_MAX_RETRIES})"
                # Empty response is transient - retry with backoff
                if attempt < GH_MAX_RETRIES:
                    delay = min(
                        GH_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)),
                        GH_BACKOFF_MAX_SECONDS,
                    )
                    time.sleep(delay)
                    continue
                break

            issue_data = json.loads(result.stdout)
            break  # Success - exit retry loop

        except subprocess.TimeoutExpired:
            last_error = f"Timeout fetching issue #{issue_number} (attempt {attempt}/{GH_MAX_RETRIES})"
            if attempt < GH_MAX_RETRIES:
                delay = min(
                    GH_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)),
                    GH_BACKOFF_MAX_SECONDS,
                )
                time.sleep(delay)
                continue
            break
        except json.JSONDecodeError as e:
            last_error = f"Failed to parse issue data: {e}"
            # JSON parse error on non-empty response is likely permanent
            break

    if issue_data is None:
        return {"error_message": last_error}

    issue_title = issue_data.get("title", "")
    issue_body = issue_data.get("body", "")

    # Assemble context
    context_content = ""
    if context_files:
        context_content = assemble_context(context_files, target_repo)

    # Create audit directory
    audit_dir = create_audit_dir(
        workflow_type="lld",
        issue_number=issue_number,
        target_repo=target_repo,
    )

    # Save issue to audit trail
    issue_content = f"# Issue #{issue_number}: {issue_title}\n\n{issue_body}"
    if context_content:
        issue_content += f"\n\n---\n\n# Context Files\n\n{context_content}"

    file_num = next_file_number(audit_dir)
    save_audit_file(audit_dir, file_num, "issue.md", issue_content)

    return {
        "issue_title": issue_title,
        "issue_body": issue_body,
        "context_content": context_content,
        "audit_dir": str(audit_dir),
        "file_counter": file_num,
        "error_message": "",
    }


def _mock_load_issue(state: RequirementsWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    issue_number = state.get("issue_number", 42)
    target_repo = Path(state.get("target_repo", ""))

    mock_title = f"Mock Issue #{issue_number}"
    mock_body = """## Requirements

This is a mock issue for testing.

## Acceptance Criteria

- [ ] Feature implemented
- [ ] Tests passing
"""

    # Create audit directory
    audit_dir = create_audit_dir(
        workflow_type="lld",
        issue_number=issue_number,
        target_repo=target_repo,
    )

    # Save to audit
    file_num = next_file_number(audit_dir)
    save_audit_file(
        audit_dir, file_num, "issue.md",
        f"# Issue #{issue_number}: {mock_title}\n\n{mock_body}"
    )

    return {
        "issue_title": mock_title,
        "issue_body": mock_body,
        "context_content": "",
        "audit_dir": str(audit_dir),
        "file_counter": file_num,
        "error_message": "",
    }
