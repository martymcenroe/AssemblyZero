"""State definition for LLD Governance workflow.

Issue #86: LLD Creation & Governance Review Workflow
LLD: docs/LLDs/active/LLD-086-lld-governance-workflow.md

This TypedDict travels through nodes N0-N4, tracking the LLD
through design, human edit, and governance review cycles.
"""

from enum import Enum
from typing import Literal, TypedDict


class HumanDecision(str, Enum):
    """User choices at human edit node (N2)."""

    SEND = "S"  # Send to Gemini review
    REVISE = "R"  # Return to designer with feedback
    MANUAL = "M"  # Exit for manual handling


class LLDWorkflowState(TypedDict, total=False):
    """State for the LLD governance workflow.

    Attributes:
        # Input
        issue_number: GitHub issue number to create LLD for.
        context_files: Paths to additional context files (--context flag).

        # Issue content (populated by N0)
        issue_id: Same as issue_number (for compatibility with existing nodes).
        issue_title: Issue title from GitHub.
        issue_body: Issue body content from GitHub.
        context_content: Assembled context from context_files.

        # Workflow tracking
        audit_dir: Path to docs/audit/active/{issue_number}-lld/.
        file_counter: Sequential number for audit files (001, 002, ...).
        iteration_count: Total loop iterations (max 5).

        # Current artifacts (compatible with existing nodes)
        lld_draft_path: Path to current draft file.
        lld_content: Current LLD content.
        design_status: Designer node outcome.
        lld_status: Governance review outcome.
        gemini_critique: Feedback from Gemini review.
        user_feedback: Feedback when user selects Revise.

        # Routing
        next_node: Routing decision from human node.

        # Output
        final_lld_path: Path to approved LLD in docs/LLDs/active/.

        # Error handling
        error_message: Last error message if any.

        # Mode flags (from CLI)
        auto_mode: If True, skip VS Code and auto-send to review.
        mock_mode: If True, use fixtures instead of real APIs.
    """

    # Input
    issue_number: int
    context_files: list[str]

    # Issue content
    issue_id: int  # Alias for compatibility with designer.py/governance.py
    issue_title: str
    issue_body: str
    context_content: str

    # Workflow tracking
    audit_dir: str
    file_counter: int
    iteration_count: int

    # Current artifacts (compatible with existing nodes)
    lld_draft_path: str
    lld_content: str
    design_status: Literal["PENDING", "DRAFTED", "FAILED"]
    lld_status: Literal["PENDING", "APPROVED", "BLOCKED"]
    gemini_critique: str
    user_feedback: str

    # Routing
    next_node: str

    # Output
    final_lld_path: str

    # Error handling
    error_message: str

    # Mode flags
    auto_mode: bool
    mock_mode: bool
