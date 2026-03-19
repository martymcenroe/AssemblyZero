"""State definition for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #335: Scaffold validation fields
Issue #147: Completeness gate fields (completeness_verdict, completeness_issues, review_materials)
Issue #292: pytest_exit_code for exit code routing
Issue #180: N9 Cleanup node fields (pr_url, pr_merged, learning_summary_path, cleanup_skipped_reason)
Issue #381: Multi-framework TDD support (framework_config, test_run_result, total_scenarios)

This TypedDict travels through nodes N0-N8, tracking the testing workflow
from LLD loading through test generation, implementation, E2E validation,
documentation generation, and post-implementation cleanup.
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
        test_plan_verdict: Extracted verdict summary (not raw prose). Full response in audit trail.
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

        # Issue #180: N9 Cleanup node
        pr_url: GitHub PR URL.
        pr_merged: Set by N9 after checking PR merge status.
        learning_summary_path: Absolute path to generated learning summary.
        cleanup_skipped_reason: Reason cleanup was skipped.
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
    previous_coverage: float  # Previous iteration coverage for stagnation detection
    previous_passed: int  # Previous iteration pass count for stagnation detection
    e2e_output: str
    previous_e2e_passed: int  # Previous E2E pass count for stagnation detection
    previous_e2e_failures: list[str]  # Issue #504: Previous E2E failed test names for identity comparison
    previous_green_failures: list[str]  # Issue #501: Previous green phase failed test names for identity comparison
    test_failure_summary: str  # Issue #498: Structured test failure feedback for N4
    e2e_failure_summary: str  # Issue #498: Structured E2E failure feedback for N4
    full_suite_validated: bool  # Issue #842: True after full test suite passes regression check
    full_suite_regressions: list[str]  # Issue #842: Failed test names from last full suite run (for stagnation)

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
    config_reviewer: str  # Issue #773: Reviewer LLM spec (e.g., "claude:opus")
    config_effort: str  # Issue #779: Effort level for Claude reviewer
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
    scaffold_validation_errors: list[str]  # Issue #500: errors from last validation
    previous_scaffold_hash: str  # Issue #502: SHA-256 of last scaffold output

    # Issue #147: Completeness gate (N4b) - Anti-stub detection
    completeness_verdict: Literal["PASS", "WARN", "BLOCK", ""]
    completeness_issues: list[dict]  # List of CompletenessIssue dicts
    previous_completeness_issues: list[list]  # Issue #505: Previous issue IDs for stagnation detection
    review_materials: dict | None  # ReviewMaterials for Gemini Layer 2

    # Issue #292: Pytest exit code routing
    pytest_exit_code: int  # Last pytest return code (0-5, -1 for timeout)

    # Circuit breaker / token budget
    token_budget: int  # Max estimated tokens (0 = unlimited)
    estimated_tokens_used: int  # Running estimate of tokens consumed

    # Issue #476: API cost budget
    cost_budget_usd: float

    # Issue #381: Multi-framework TDD support
    framework_config: dict | None   # FrameworkConfig from runner_registry (None = pytest default)
    test_run_result: dict | None    # TestRunResult from runner (non-pytest frameworks)
    total_scenarios: int            # For scenario-based coverage (Playwright)

    # === N9: Cleanup (Issue #180) ===
    pr_url: str                    # GitHub PR URL (e.g., "https://github.com/org/repo/pull/42")
    pr_merged: bool                # Set by N9 after checking PR merge status
    learning_summary_path: str     # Absolute path to generated learning summary
    cleanup_skipped_reason: str    # Reason cleanup was skipped (e.g., "PR not merged")

    # Issue #486: Halt-and-Plan
    recovery_plan_path: str
    state_snapshot_path: str

    # Issue #511: Per-node LLM cost tracking
    node_costs: dict[str, float]  # node_name -> cumulative cost_usd
    node_tokens: dict[str, dict[str, int]]  # node_name -> {"input": N, "output": N}