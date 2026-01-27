"""State definition for Issue creation workflow.

Issue #62: Governance Workflow StateGraph

This TypedDict travels through nodes N0-N6, accumulating audit trail files
and tracking iteration counts for user visibility.
"""

from enum import Enum
from typing import TypedDict


class HumanDecision(str, Enum):
    """User choices at human gate nodes (N3, N5)."""

    SEND = "S"  # Send to Gemini (N3 only)
    APPROVE = "A"  # Approve and file (N5 only)
    REVISE = "R"  # Revise draft (N3 or N5)
    MANUAL = "M"  # Exit for manual handling


class SlugCollisionChoice(str, Enum):
    """User choices when slug already exists in active/."""

    RESUME = "R"  # Resume existing workflow from checkpoint
    NEW_NAME = "N"  # Enter a new slug name
    ABORT = "A"  # Exit cleanly


class ErrorRecovery(str, Enum):
    """User choices when GitHub rejects the issue at N6."""

    RETRY = "R"  # Retry gh issue create
    EDIT = "E"  # Reopen VS Code, return to N5
    ABORT = "A"  # Exit with error


class IssueWorkflowState(TypedDict, total=False):
    """State for the issue creation workflow.

    Attributes:
        # Input
        brief_file: Path to user's ideation notes file.
        brief_content: Loaded brief text content.
        slug: Derived from brief filename, used for audit directory.

        # Workflow tracking
        audit_dir: Path to docs/audit/active/{slug}/.
        file_counter: Sequential number for audit files (001, 002, ...).
        iteration_count: Total loop iterations (displayed to user).
        draft_count: Number of drafts generated.
        verdict_count: Number of Gemini verdicts received.

        # Current artifacts
        current_draft_path: Path to latest draft file.
        current_draft: Latest draft content.
        current_verdict_path: Path to latest verdict file.
        current_verdict: Latest Gemini verdict content.
        user_feedback: Feedback when user selects Revise.

        # Routing
        next_node: Routing decision from human nodes.

        # Output
        issue_number: Assigned at N6 when gh creates the issue.
        issue_url: GitHub URL of the created issue.

        # Error handling
        error_message: Last error message if any.
    """

    # Input
    brief_file: str
    brief_content: str
    slug: str

    # Workflow tracking
    audit_dir: str
    file_counter: int
    iteration_count: int
    draft_count: int
    verdict_count: int

    # Current artifacts
    current_draft_path: str
    current_draft: str
    current_verdict_path: str
    current_verdict: str
    user_feedback: str

    # Routing
    next_node: str

    # Output
    issue_number: int
    issue_url: str

    # Error handling
    error_message: str
