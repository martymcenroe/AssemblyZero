"""Unified state definition for Requirements Workflow.

Issue #101: Unified Requirements Workflow
Issue #248: Added open_questions_status field
Issue #334: Added is_directory flag to FileChange TypedDict

This TypedDict merges IssueWorkflowState and LLDWorkflowState to support
both workflow types through a single graph. Fields are organized by:
- Configuration (type, paths, modes)
- Input (workflow-type specific)
- Workflow tracking (common)
- Current artifacts (common)
- Routing (common)
- Output (workflow-type specific)
- Error handling (common)
"""

from enum import Enum
from typing import Literal, TypedDict


class WorkflowType(str, Enum):
    """Type of requirements workflow."""

    ISSUE = "issue"
    LLD = "lld"


class HumanDecision(str, Enum):
    """User choices at human gate nodes.

    Draft gate (after generation):
    - SEND: Send to Gemini review
    - REVISE: Return to drafter with feedback
    - MANUAL: Exit for manual handling

    Verdict gate (after review):
    - APPROVE: Accept verdict and finalize
    - REVISE: Return to drafter with feedback
    - WRITE_FEEDBACK: Re-read verdict + prompt for comments
    - MANUAL: Exit for manual handling
    """

    SEND = "S"
    APPROVE = "A"
    REVISE = "R"
    WRITE_FEEDBACK = "W"
    MANUAL = "M"


class SlugCollisionChoice(str, Enum):
    """User choices when slug collision detected (Issue workflow)."""

    RESUME = "R"
    NEW_NAME = "N"
    CLEAN = "C"
    ABORT = "A"


class FileChange(TypedDict, total=False):
    """A file change entry from LLD Section 2.1.

    Issue #334: Added is_directory flag for directory entries.

    Attributes:
        path: File or directory path.
        change_type: Normalized change type ("add", "modify", "delete").
        description: Brief description of the change.
        is_directory: True if path represents a directory (e.g., from "Add (Directory)").
    """

    path: str
    change_type: str
    description: str
    is_directory: bool


class RequirementsWorkflowState(TypedDict, total=False):
    """Unified state for both Issue and LLD requirements workflows.

    CRITICAL PATH RULES (from LLD #101):
    - agentos_root: ALWAYS set, NEVER empty. Where templates live.
    - target_repo: ALWAYS set, NEVER empty. Where outputs go.
    - Never use "" (empty string) for paths - it's falsy and causes auto-detection bugs.

    Attributes:
        # Configuration
        workflow_type: Either "issue" or "lld".
        agentos_root: Path to AgentOS installation (for templates/prompts).
        target_repo: Path to target repository (for outputs/context).
        config_drafter: LLM provider spec for drafter.
        config_reviewer: LLM provider spec for reviewer.
        config_gates_draft: Whether draft gate is enabled.
        config_gates_verdict: Whether verdict gate is enabled.
        config_auto_mode: If True, skip VS Code and auto-progress.
        config_mock_mode: If True, use mock providers.

        # Input - Issue workflow
        brief_file: Path to user's ideation notes file.
        brief_content: Loaded brief text content.
        slug: Derived from brief filename, used for audit directory.
        source_idea: Path to original idea in ideas/active/ (for cleanup).

        # Input - LLD workflow
        issue_number: GitHub issue number to create LLD for.
        issue_title: Issue title from GitHub.
        issue_body: Issue body content from GitHub.
        context_files: Paths to additional context files.
        context_content: Assembled context from context_files.

        # Workflow tracking (common)
        audit_dir: Path to docs/lineage/active/{slug|issue#-lld}/.
        file_counter: Sequential number for audit files (001, 002, ...).
        iteration_count: Total loop iterations (displayed to user).
        draft_count: Number of drafts generated.
        verdict_count: Number of Gemini verdicts received.
        max_iterations: Maximum allowed iterations.

        # Current artifacts (common)
        current_draft_path: Path to latest draft file.
        current_draft: Latest draft content.
        current_verdict_path: Path to latest verdict file.
        current_verdict: Latest Gemini verdict content.
        verdict_history: List of all verdicts (cumulative, sent to drafter).
        user_feedback: Feedback when user selects Revise.

        # Open questions tracking (Issue #248)
        open_questions_status: Status of open questions after review.
            - "NONE": No open questions in draft
            - "RESOLVED": All questions answered by Gemini
            - "HUMAN_REQUIRED": Questions need human decision
            - "UNANSWERED": Questions exist but weren't answered

        # Routing (common)
        next_node: Routing decision from human nodes.

        # Output - Issue workflow
        issue_url: GitHub URL of the created issue.
        filed_issue_number: Issue number assigned by GitHub.

        # Output - LLD workflow
        final_lld_path: Path to approved LLD in docs/lld/active/.
        lld_status: Current LLD status (PENDING, APPROVED, BLOCKED).

        # Error handling (common)
        error_message: Last error message if any.

        # Git commit tracking (Issue #162)
        created_files: List of files created by workflow for commit.
        commit_sha: SHA of commit if successfully pushed.
        commit_error: Error message if commit/push failed.

        # Lineage tracking (Issue #334)
        lineage_path: Path to lineage folder for audit trail.
        draft_number: Current draft iteration number.
    """

    # Configuration
    workflow_type: Literal["issue", "lld"]
    agentos_root: str  # ALWAYS set, NEVER empty
    target_repo: str  # ALWAYS set, NEVER empty
    config_drafter: str
    config_reviewer: str
    config_gates_draft: bool
    config_gates_verdict: bool
    config_auto_mode: bool
    config_mock_mode: bool

    # Input - Issue workflow
    brief_file: str
    brief_content: str
    slug: str
    source_idea: str

    # Input - LLD workflow
    issue_number: int
    issue_title: str
    issue_body: str
    context_files: list[str]
    context_content: str

    # Workflow tracking
    audit_dir: str
    file_counter: int
    iteration_count: int
    draft_count: int
    verdict_count: int
    max_iterations: int

    # Current artifacts
    current_draft_path: str
    current_draft: str
    current_verdict_path: str
    current_verdict: str
    verdict_history: list[str]
    user_feedback: str

    # Open questions tracking (Issue #248)
    open_questions_status: Literal["NONE", "RESOLVED", "HUMAN_REQUIRED", "UNANSWERED"]

    # Routing
    next_node: str

    # Output - Issue workflow
    issue_url: str
    filed_issue_number: int

    # Output - LLD workflow
    final_lld_path: str
    lld_status: Literal["PENDING", "APPROVED", "BLOCKED"]

    # Error handling
    error_message: str

    # Mechanical validation (Issue #277)
    validation_errors: list[str]
    validation_warnings: list[str]

    # Git commit tracking (Issue #162)
    created_files: list[str]
    commit_sha: str
    commit_error: str

    # Lineage tracking (Issue #334)
    lineage_path: str
    draft_number: int


def create_initial_state(
    workflow_type: Literal["issue", "lld"],
    agentos_root: str,
    target_repo: str,
    drafter: str = "claude:opus-4.5",
    reviewer: str = "gemini:3-pro-preview",
    gates_draft: bool = True,
    gates_verdict: bool = True,
    auto_mode: bool = False,
    mock_mode: bool = False,
    max_iterations: int = 20,
    # Issue-specific
    brief_file: str = "",
    source_idea: str = "",
    # LLD-specific
    issue_number: int = 0,
    context_files: list[str] | None = None,
    # Lineage tracking (Issue #334)
    lineage_path: str = "",
) -> RequirementsWorkflowState:
    """Create initial state for requirements workflow.

    Args:
        workflow_type: Either "issue" or "lld".
        agentos_root: Path to AgentOS installation.
        target_repo: Path to target repository.
        drafter: LLM provider spec for drafter.
        reviewer: LLM provider spec for reviewer.
        gates_draft: Whether draft gate is enabled.
        gates_verdict: Whether verdict gate is enabled.
        auto_mode: Skip VS Code, auto-progress.
        mock_mode: Use mock providers.
        max_iterations: Maximum revision cycles.
        brief_file: Path to brief (issue workflow).
        source_idea: Path to source idea (issue workflow).
        issue_number: GitHub issue number (LLD workflow).
        context_files: Context file paths (LLD workflow).
        lineage_path: Path to lineage folder for audit trail (Issue #334).

    Returns:
        Initialized RequirementsWorkflowState.

    Raises:
        ValueError: If agentos_root or target_repo is empty.
    """
    # CRITICAL: Never allow empty paths
    if not agentos_root or not agentos_root.strip():
        raise ValueError("agentos_root must be set and non-empty")
    if not target_repo or not target_repo.strip():
        raise ValueError("target_repo must be set and non-empty")

    state: RequirementsWorkflowState = {
        # Configuration
        "workflow_type": workflow_type,
        "agentos_root": agentos_root,
        "target_repo": target_repo,
        "config_drafter": drafter,
        "config_reviewer": reviewer,
        "config_gates_draft": gates_draft,
        "config_gates_verdict": gates_verdict,
        "config_auto_mode": auto_mode,
        "config_mock_mode": mock_mode,
        # Workflow tracking
        "audit_dir": "",
        "file_counter": 0,
        "iteration_count": 0,
        "draft_count": 0,
        "verdict_count": 0,
        "max_iterations": max_iterations,
        # Current artifacts
        "current_draft_path": "",
        "current_draft": "",
        "current_verdict_path": "",
        "current_verdict": "",
        "verdict_history": [],
        "user_feedback": "",
        # Open questions tracking (Issue #248)
        "open_questions_status": "NONE",
        # Routing
        "next_node": "",
        # Error handling
        "error_message": "",
        # Mechanical validation (Issue #277)
        "validation_errors": [],
        "validation_warnings": [],
        # Git commit tracking (Issue #162)
        "created_files": [],
        "commit_sha": "",
        "commit_error": "",
        # Lineage tracking (Issue #334)
        "lineage_path": lineage_path,
        "draft_number": 1,
    }

    # Add workflow-type specific fields
    if workflow_type == "issue":
        state.update(
            {
                "brief_file": brief_file,
                "brief_content": "",
                "slug": "",
                "source_idea": source_idea,
                "issue_url": "",
                "filed_issue_number": 0,
            }
        )
    else:  # lld
        state.update(
            {
                "issue_number": issue_number,
                "issue_title": "",
                "issue_body": "",
                "context_files": context_files or [],
                "context_content": "",
                "final_lld_path": "",
                "lld_status": "PENDING",
            }
        )

    return state


def validate_state(state: RequirementsWorkflowState) -> list[str]:
    """Validate workflow state and return list of errors.

    Args:
        state: State to validate.

    Returns:
        List of error messages. Empty if valid.
    """
    errors = []

    # Check required paths are set
    if not state.get("agentos_root"):
        errors.append("agentos_root must be set")
    if not state.get("target_repo"):
        errors.append("target_repo must be set")

    # Check workflow type is valid
    workflow_type = state.get("workflow_type")
    if workflow_type not in ("issue", "lld"):
        errors.append(f"Invalid workflow_type: {workflow_type}")

    # Type-specific validation
    if workflow_type == "issue":
        if not state.get("brief_file"):
            errors.append("brief_file must be set for issue workflow")
    elif workflow_type == "lld":
        if not state.get("issue_number"):
            errors.append("issue_number must be set for LLD workflow")

    return errors