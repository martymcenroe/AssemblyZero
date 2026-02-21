"""State definition for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #335: Scaffold validation fields
Issue #147: Completeness gate fields (completeness_verdict, completeness_issues, review_materials)
Issue #292: pytest_exit_code for exit code routing

This TypedDict travels through nodes N0-N8, tracking the testing workflow
from LLD loading through test generation, implementation, E2E validation,
and documentation generation.
"""

from enum import Enum
from typing import Literal, TypedDict


class HumanDecision(str, Enum):
    """User choices at human gate nodes."""

    APPROVE = "A"  # Approve and proceed
    REVISE = "R"  # Return to previous step with feedback
    SKIP = "S"  # Skip E2E (for fast mode)
    MANUAL = "M"  # Exit for manual handling


class TestScenario(TypedDict):
    __test__ = False
    """A single test scenario extracted from the LLD."""

    name: str  # Test name (e.g., "test_login_success")
    description: str  # What the test verifies
    requirement_ref: str  # Reference to LLD requirement (e.g., "REQ-1.1")
    test_type: str  # unit, integration, e2e, etc.
    mock_needed: bool  # Whether mocking is required
    assertions: list[str]  # Expected assertions


class TestingWorkflowState(TypedDict, total=False):
    __test__ = False
    """State for the TDD testing workflow.

    Attributes:
        # Input
        issue_number: GitHub issue number (links to LLD).
        lld_path: Path to the approved LLD file.
        repo_root: Target repository root path (for cross-repo workflows).
        worktree_path: Path to git worktree (if created for this workflow).
        original_repo_root: Original repository root before worktree switch.

        # LLD content (populated by N0)
        lld_content: Full LLD content.
        test_plan_section: Extracted Section 10 (Test Plan).
        test_scenarios: Parsed test scenarios from test plan.
        detected_test_types: Types of tests detected (unit, integration, etc.).
        coverage_target: Target code coverage percentage.
        requirements: List of requirements from LLD.

        # Workflow tracking
        audit_dir: Path to docs/lineage/active/{issue}-testing/.
        file_counter: Sequential number for audit files (001, 002, ...).
        iteration_count: Total loop iterations.
        max_iterations: Maximum allowed iterations (default 10).

        # Test artifacts
        test_files: List of generated test file paths.
        implementation_files: List of generated implementation file paths.
        completed_files: List of (filepath, content) tuples for context accumulation (#272).
        red_phase_output: Pytest output from red phase verification.
        green_phase_output: Pytest output from green phase verification.
        coverage_achieved: Actual coverage percentage achieved.
        e2e_output: E2E test output.

        # Review artifacts
        test_plan_review_prompt: Prompt sent to Gemini for test plan review.
        test_plan_verdict: Gemini's verdict on test plan.
        test_plan_status: APPROVED or BLOCKED.
        gemini_feedback: Feedback from Gemini if BLOCKED.

        # Routing
        next_node: Routing decision from nodes.

        # Output
        test_report_path: Path to generated test report.
        implementation_report_path: Path to implementation report.

        # Error handling
        error_message: Last error message if any.

        # Context injection (Issue #288)
        context_files: List of context file paths from --context flag.
        context_content: Concatenated content from validated context files.

        # Mode flags (from CLI)
        auto_mode: If True, skip human gates and auto-approve.
        mock_mode: If True, use fixtures instead of real APIs.
        skip_e2e: If True, skip E2E validation (fast mode).
        scaffold_only: If True, stop after scaffolding tests.
        green_only: If True, only run green phase verification.

        # E2E configuration
        sandbox_repo: Path to sandbox repository for E2E tests.
        e2e_max_issues: Maximum issues to create in E2E (safety limit).
        e2e_max_prs: Maximum PRs to create in E2E (safety limit).

        # Documentation outputs (N8)
        doc_wiki_path: Path to generated wiki page.
        doc_runbook_path: Path to generated runbook.
        doc_lessons_path: Path to lessons learned file.
        doc_readme_updated: Whether README was updated.
        doc_cp_paths: Paths to c/p documentation files.

        # Documentation control
        skip_docs: CLI flag to skip documentation generation.
        doc_scope: Documentation scope ("full", "minimal", "auto", "none").

        # Issue #147: Completeness gate (N4b)
        completeness_verdict: Result of completeness analysis ("PASS", "WARN", "BLOCK", or "").
        completeness_issues: List of completeness issues detected by AST analysis.
        review_materials: Materials prepared for Gemini Layer 2 semantic review.
    """

    # Input
    issue_number: int
    lld_path: str
    repo_root: str

    # Worktree isolation (for multi-branch safety)
    worktree_path: str  # Path to worktree if created
    original_repo_root: str  # Original repo root (for reference)

    # LLD content
    lld_content: str
    test_plan_section: str
    test_scenarios: list[TestScenario]
    detected_test_types: list[str]
    coverage_target: int
    requirements: list[str]
    files_to_modify: list[dict]  # Files from LLD Section 2.1

    # Workflow tracking
    audit_dir: str
    file_counter: int
    iteration_count: int
    max_iterations: int

    # Test artifacts
    test_files: list[str]
    implementation_files: list[str]
    completed_files: list[tuple[str, str]]  # Issue #272: (filepath, content) for context accumulation
    coverage_module: str  # Module path for coverage measurement (e.g., "assemblyzero.workflows.scout")
    red_phase_output: str
    green_phase_output: str
    coverage_achieved: float
    e2e_output: str

    # Review artifacts
    test_plan_review_prompt: str
    test_plan_verdict: str
    test_plan_status: Literal["PENDING", "APPROVED", "BLOCKED"]
    gemini_feedback: str

    # Routing
    next_node: str
    implementation_exists: bool

    # Output
    test_report_path: str
    implementation_report_path: str

    # Error handling
    error_message: str

    # Context injection (Issue #288)
    context_files: list[str]
    context_content: str

    # Mode flags
    auto_mode: bool
    mock_mode: bool
    skip_e2e: bool
    scaffold_only: bool
    green_only: bool
    issue_only: bool  # Issue #287: Use issue body as spec, skip LLD search

    # E2E configuration
    sandbox_repo: str
    e2e_max_issues: int
    e2e_max_prs: int

    # Documentation outputs (N8)
    doc_wiki_path: str
    doc_runbook_path: str
    doc_lessons_path: str
    doc_readme_updated: bool
    doc_cp_paths: list[str]

    # Documentation control
    skip_docs: bool
    doc_scope: Literal["full", "minimal", "auto", "none"]

    # Issue #335: Scaffold validation
    generated_tests: str  # Generated test file content
    parsed_scenarios: dict  # ParsedLLDTests from Section 10.0
    validation_result: dict  # TestValidationResult from mechanical validation
    scaffold_attempts: int  # Number of scaffold regeneration attempts

    # Issue #147: Completeness gate (N4b) - Anti-stub detection
    completeness_verdict: Literal["PASS", "WARN", "BLOCK", ""]
    completeness_issues: list[dict]  # List of CompletenessIssue dicts
    review_materials: dict | None  # ReviewMaterials for Gemini Layer 2

    # Issue #292: Pytest exit code routing
    pytest_exit_code: int  # Last pytest return code (0-5, -1 for timeout)