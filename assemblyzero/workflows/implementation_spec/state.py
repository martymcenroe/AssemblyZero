"""TypedDict state definitions for Implementation Spec workflow.

Issue #304: Implementation Readiness Review Workflow (LLD → Implementation Spec)

Defines the state schema used by the LangGraph workflow:
- ImplementationSpecState: Main workflow state
- FileToModify: Parsed file entry from LLD Section 2.1
- PatternRef: Reference to similar implementation patterns
- CompletenessCheck: Result of a mechanical completeness check
"""

from __future__ import annotations

from typing import Literal, TypedDict


class FileToModify(TypedDict):
    """A file entry parsed from LLD Section 2.1.

    Attributes:
        path: File path from LLD (relative to repo root).
        change_type: Whether the file is being added, modified, or deleted.
        description: Description of the change from LLD.
        current_content: Loaded file content for Modify/Delete types.
            None for Add types or before N1 loads content.
    """

    path: str
    change_type: Literal["Add", "Modify", "Delete"]
    description: str
    current_content: str | None


class PatternRef(TypedDict):
    """Reference to a similar implementation pattern in the codebase.

    Used by N1 (analyze_codebase) to find existing patterns that inform
    the spec generation in N2.

    Attributes:
        file_path: Path to the file containing the pattern.
        start_line: Starting line number of the pattern.
        end_line: Ending line number of the pattern.
        pattern_type: Category of pattern (e.g., "node implementation",
            "state definition", "graph construction").
        relevance: Explanation of why this pattern is relevant.
    """

    file_path: str
    start_line: int
    end_line: int
    pattern_type: str
    relevance: str


class CompletenessCheck(TypedDict):
    """Result of a single mechanical completeness check in N3.

    Attributes:
        check_name: Identifier for the check (e.g.,
            "modify_files_have_excerpts").
        passed: Whether the check passed.
        details: Explanation of result, especially if failed.
    """

    check_name: str
    passed: bool
    details: str


class ImplementationSpecState(TypedDict, total=False):
    """Main workflow state for the Implementation Spec generation workflow.

    This TypedDict defines all state fields used across nodes N0-N6.
    Fields use total=False so nodes can return partial updates.

    Input fields (set before workflow starts):
        issue_number: GitHub issue number being implemented.
        lld_path: Path to the approved LLD file.

    Loaded content (set by N0):
        lld_content: Raw LLD markdown content.
        files_to_modify: Parsed file entries from LLD Section 2.1.

    Codebase analysis (set by N1):
        current_state_snapshots: Mapping of file_path to code excerpt.
        pattern_references: Similar patterns found in the codebase.

    Generated spec (set by N2):
        spec_draft: Generated Implementation Spec markdown.
        spec_path: Output path for the final spec file.

    Validation (set by N3):
        completeness_issues: List of issues found during validation.
        validation_passed: Whether N3 validation passed.

    Review (set by N5):
        review_verdict: Gemini review result.
        review_feedback: Gemini review comments.
        review_iteration: Current review/generation round.

    Workflow control:
        max_iterations: Maximum retry iterations (default 3).
        human_gate_enabled: Whether N4 human gate is active.
        error_message: Error message if workflow encounters a failure.
        next_node: Used by N4 human gate to signal routing decision.
    """

    # Input
    issue_number: int
    lld_path: str

    # Issue #392: Paths that must survive between nodes
    repo_root: str
    assemblyzero_root: str
    audit_dir: str

    # Configuration (set by CLI runner)
    config_mock_mode: bool
    config_drafter: str
    config_reviewer: str

    # Loaded content (N0)
    lld_content: str
    files_to_modify: list[FileToModify]

    # Codebase analysis (N1)
    current_state_snapshots: dict[str, str]
    pattern_references: list[PatternRef]

    # Generated spec (N2)
    spec_draft: str
    spec_path: str

    # Validation (N3)
    completeness_issues: list[str]
    validation_passed: bool

    # Review (N5)
    review_verdict: Literal["APPROVED", "REVISE", "BLOCKED"]
    review_feedback: str
    review_iteration: int

    # Workflow control
    max_iterations: int
    human_gate_enabled: bool
    error_message: str
    next_node: str