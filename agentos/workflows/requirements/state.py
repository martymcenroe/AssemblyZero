"""State management for requirements workflows."""

from typing import TypedDict, Literal, Optional


class WorkflowState(TypedDict, total=False):
    """Type definition for workflow state dictionary."""
    workflow_type: Literal["lld", "issue"]
    agentos_root: str
    target_repo: str
    issue_number: Optional[int]
    slug: Optional[str]
    audit_dir: str
    current_draft: str
    lld_status: str
    created_files: list[str]


# Alias for backwards compatibility
RequirementsState = WorkflowState


def create_initial_state(
    workflow_type: Literal["lld", "issue"],
    agentos_root: str,
    target_repo: str,
    issue_number: Optional[int] = None,
    slug: Optional[str] = None,
) -> WorkflowState:
    """Create initial workflow state.

    Args:
        workflow_type: Type of workflow ("lld" or "issue")
        agentos_root: Path to AgentOS root directory
        target_repo: Path to target repository
        issue_number: Issue number for LLD workflows
        slug: Slug for issue workflows

    Returns:
        Initial workflow state dictionary
    """
    state: WorkflowState = {
        "workflow_type": workflow_type,
        "agentos_root": agentos_root,
        "target_repo": target_repo,
        "created_files": [],
    }

    if issue_number is not None:
        state["issue_number"] = issue_number

    if slug is not None:
        state["slug"] = slug

    return state
