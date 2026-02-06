"""N1: Sandbox node for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

Performs pre-flight checks:
1. Verify VS Code CLI ('code') exists in PATH
2. Verify gh CLI is authenticated
3. (Future: Create worktree sandbox, strip permissions)
"""

import shutil
import subprocess
from typing import Any

from assemblyzero.workflows.issue.state import IssueWorkflowState


def check_vscode_available() -> tuple[bool, str]:
    """Verify 'code' binary exists in PATH (VS Code CLI).

    Returns:
        Tuple of (available, error_message).
        If available is True, error_message is empty.

    Note: If productized, expand to check_editor_available(cmd: str)
    supporting --editor flag for other editors.
    """
    # Check if 'code' is in PATH
    code_path = shutil.which("code")
    if code_path is None:
        return (
            False,
            "VS Code CLI not found. Install VS Code and ensure 'code' is in PATH.\n"
            "See: https://code.visualstudio.com/docs/setup/setup-overview",
        )
    return (True, "")


def check_gh_authenticated() -> tuple[bool, str]:
    """Verify gh CLI is authenticated.

    Returns:
        Tuple of (authenticated, error_message).
        If authenticated is True, error_message is empty.
    """
    # Check if gh is in PATH
    gh_path = shutil.which("gh")
    if gh_path is None:
        return (
            False,
            "GitHub CLI (gh) not found. Install gh and authenticate.\n"
            "See: https://cli.github.com/",
        )

    # Check authentication status
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return (
                False,
                f"GitHub CLI not authenticated. Run 'gh auth login'.\n{result.stderr}",
            )
        return (True, "")
    except subprocess.TimeoutExpired:
        return (False, "gh auth status timed out")
    except Exception as e:
        return (False, f"Error checking gh auth: {e}")


def sandbox(state: IssueWorkflowState) -> dict[str, Any]:
    """N1: Pre-flight checks and sandbox setup.

    Steps:
    1. Check VS Code CLI ('code') exists in PATH
    2. Check gh CLI is authenticated
    3. (Future: Create worktree, strip agent permissions)

    Args:
        state: Current workflow state.

    Returns:
        dict with error_message if checks fail, empty dict otherwise.
    """
    # Check VS Code
    vscode_ok, vscode_error = check_vscode_available()
    if not vscode_ok:
        return {"error_message": vscode_error}

    # Check gh CLI
    gh_ok, gh_error = check_gh_authenticated()
    if not gh_ok:
        return {"error_message": gh_error}

    # All checks passed
    # Note: Worktree creation and permission stripping are handled
    # externally by the CLI runner, not in this node. The agent
    # executing inside the workflow never has gh access.

    return {"error_message": ""}
