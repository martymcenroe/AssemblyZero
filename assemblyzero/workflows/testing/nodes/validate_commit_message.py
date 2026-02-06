"""Validate commit message node for TDD Testing Workflow.

Issue #190: Validates that commit messages contain 'fixes #N' or equivalent
to ensure issues are auto-closed when PRs are merged.
"""

from typing import Any

from assemblyzero.workflows.testing.state import TestingWorkflowState


def validate_commit_message(state: TestingWorkflowState) -> dict[str, Any]:
    """Validate commit message contains issue-closing keyword.

    Checks that the commit message contains one of:
    - fixes #N
    - closes #N
    - resolves #N

    Where N matches state["issue_number"].

    Args:
        state: Current workflow state with issue_number and commit_message.

    Returns:
        State updates. Empty error_message if valid, BLOCKED message if invalid.
    """
    issue_number = state.get("issue_number", 0)
    commit_message = state.get("commit_message", "")

    if not commit_message:
        return {
            "error_message": f"BLOCKED: Empty commit message. Must contain 'fixes #{issue_number}' to auto-close the issue.",
        }

    # Check for valid patterns (case-insensitive)
    patterns = [
        f"fixes #{issue_number}",
        f"closes #{issue_number}",
        f"resolves #{issue_number}",
    ]

    message_lower = commit_message.lower()
    if any(pattern in message_lower for pattern in patterns):
        return {"error_message": ""}

    return {
        "error_message": (
            f"BLOCKED: Commit message must contain 'fixes #{issue_number}' "
            f"(or 'closes #{issue_number}' or 'resolves #{issue_number}') "
            f"to auto-close the issue when the PR is merged."
        ),
    }
