"""N4b: Implementation Completeness Gate node for TDD Testing Workflow.

Issue #147: Implementation Completeness Gate (Anti-Stub Detection)
Related: #181 (Implementation Report), #335 (N2.5 precedent)

Two-layer validation between N4 (implement_code) and N5 (verify_green):
- Layer 1: AST-based deterministic analysis (fast, free)
- Layer 2: Gemini semantic review materials preparation (user-controlled)

Fail Mode: Fail Open — if AST analysis fails unexpectedly, proceed to N5
with a warning rather than blocking indefinitely.

Architectural Constraints:
- Cannot modify N4 or N5 node logic (only add N4b between them)
- Gemini calls go through user (not direct from node)
- Hard iteration limit of 3 prevents infinite N4<->N4b loops
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.completeness.ast_analyzer import (
    CompletenessResult,
    run_ast_analysis,
)
from assemblyzero.workflows.testing.completeness.report_generator import (
    generate_implementation_report,
    prepare_review_materials,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Issue #147, Section 2.5: Hard limit of 3 iterations before routing to end
MAX_COMPLETENESS_ITERATIONS = 3


# =============================================================================
# N4b Node Implementation
# =============================================================================


def completeness_gate(state: TestingWorkflowState) -> dict[str, Any]:
    """N4b: Verify implementation completeness before proceeding to test verification.

    Issue #147: Two-layer completeness gate that detects semantically
    incomplete implementations (stubs, dead flags, trivial assertions)
    before they reach the test verification phase.

    Layer 1 (AST analysis) runs first as a fast, deterministic check.
    If Layer 1 has BLOCK-level issues, Layer 2 is skipped (cost control).
    If Layer 1 passes, Layer 2 materials are prepared for the user
    to submit to Gemini.

    Fail Mode: If AST analysis raises an unexpected exception, the node
    proceeds with verdict="WARN" to avoid blocking the pipeline.

    Args:
        state: Current workflow state from N4_implement_code.

    Returns:
        State updates with completeness_verdict, completeness_issues,
        implementation_report_path, and review_materials.
    """
    iteration_count = state.get("iteration_count", 0)
    gate_log(f"[N4b] Completeness gate (iteration {iteration_count})...")

    # Extract required state
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    issue_number = state.get("issue_number", 0)
    lld_path_str = state.get("lld_path", "")
    implementation_files_strs = state.get("implementation_files", [])
    test_files_strs = state.get("test_files", [])
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None

    # Convert string paths to Path objects
    implementation_files = [Path(f) for f in implementation_files_strs]
    test_files = [Path(f) for f in test_files_strs]
    lld_path = Path(lld_path_str) if lld_path_str else None

    # Combine implementation and test files for analysis
    all_files = implementation_files + test_files

    if not all_files:
        print("    [WARN] No implementation files to analyze — passing through")
        return {
            "completeness_verdict": "PASS",
            "completeness_issues": [],
            "error_message": "",
        }

    print(f"    Analyzing {len(implementation_files)} implementation + {len(test_files)} test files...")

    # =========================================================================
    # Layer 1: AST Analysis
    # =========================================================================

    try:
        ast_result: CompletenessResult = run_ast_analysis(all_files)
    except Exception as e:
        # Fail Open: proceed with warning rather than blocking
        logger.warning(
            "AST analysis failed unexpectedly: %s — proceeding with WARN verdict", e
        )
        print(f"    [WARN] AST analysis failed: {e} — fail open, proceeding")
        ast_result = CompletenessResult(
            verdict="WARN",
            issues=[],
            ast_analysis_ms=0,
            gemini_review_ms=None,
        )

    verdict = ast_result["verdict"]
    issues = ast_result["issues"]
    ast_ms = ast_result["ast_analysis_ms"]

    # Log AST results
    error_count = sum(1 for i in issues if i["severity"] == "ERROR")
    warn_count = sum(1 for i in issues if i["severity"] == "WARNING")
    print(f"    Layer 1 (AST): {verdict} — {error_count} errors, {warn_count} warnings ({ast_ms}ms)")

    for issue in issues:
        severity = issue["severity"]
        category = issue["category"]
        cat_value = category.value if hasattr(category, "value") else str(category)
        print(f"      [{severity}] {cat_value}: {issue['description']}")

    # Save AST analysis to audit trail
    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        ast_audit = _format_ast_audit(ast_result)
        save_audit_file(
            audit_dir,
            file_num,
            "completeness-ast-analysis.md",
            ast_audit,
        )

    # =========================================================================
    # Layer 2: Gemini Semantic Review (preparation only)
    # =========================================================================

    review_materials = None

    if verdict != "BLOCK" and lld_path and lld_path.exists():
        # Layer 1 passed — prepare materials for user to submit to Gemini
        print("    Layer 2: Preparing review materials for Gemini...")
        try:
            review_materials = prepare_review_materials(
                issue_number=issue_number,
                lld_path=lld_path,
                implementation_files=implementation_files,
            )
            req_count = len(review_materials.get("lld_requirements", []))
            snippet_count = len(review_materials.get("code_snippets", {}))
            print(f"    Layer 2: Prepared {req_count} requirements, {snippet_count} code snippets")
        except Exception as e:
            # Fail Open: if material preparation fails, log and continue
            logger.warning(
                "Review materials preparation failed: %s — skipping Layer 2", e
            )
            print(f"    [WARN] Layer 2 preparation failed: {e} — skipping")
    elif verdict == "BLOCK":
        print("    Layer 2: Skipped (Layer 1 BLOCK)")
    else:
        print("    Layer 2: Skipped (no LLD path available)")

    # =========================================================================
    # Report Generation (side effect — does not block)
    # =========================================================================

    implementation_report_path = ""

    if lld_path and lld_path.exists():
        print("    Generating implementation report...")
        try:
            report_path = generate_implementation_report(
                issue_number=issue_number,
                lld_path=lld_path,
                implementation_files=implementation_files,
                completeness_result=ast_result,
            )
            implementation_report_path = str(report_path)
            print(f"    Report: {report_path}")
        except Exception as e:
            # Report generation is a side effect — log and continue
            logger.warning(
                "Report generation failed: %s — continuing without report", e
            )
            print(f"    [WARN] Report generation failed: {e}")
    else:
        print("    [WARN] No LLD path — skipping report generation")

    # Save report path to audit
    if audit_dir and audit_dir.exists() and implementation_report_path:
        file_num = next_file_number(audit_dir)
        save_audit_file(
            audit_dir,
            file_num,
            "completeness-report-path.txt",
            implementation_report_path,
        )

    # =========================================================================
    # Log to workflow execution audit
    # =========================================================================

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=issue_number,
        workflow_type="testing",
        event="completeness_gate",
        details={
            "verdict": verdict,
            "error_count": error_count,
            "warning_count": warn_count,
            "ast_ms": ast_ms,
            "iteration": iteration_count,
            "report_path": implementation_report_path,
            "layer2_prepared": review_materials is not None,
        },
    )

    # =========================================================================
    # Return state updates
    # =========================================================================

    # Issue #505: Store issue identities for stagnation detection
    issue_ids = [list(_completeness_issue_identity(i)) for i in issues]

    result: dict[str, Any] = {
        "completeness_verdict": verdict,
        "completeness_issues": issues,
        "previous_completeness_issues": issue_ids,
        "implementation_report_path": implementation_report_path,
        "error_message": "",
    }

    # Include review materials if prepared (for user to submit to Gemini)
    if review_materials is not None:
        result["review_materials"] = review_materials

    print(f"    Completeness gate verdict: {verdict}")
    return result


# =============================================================================
# Routing Function
# =============================================================================


def _completeness_issue_identity(issue: dict) -> tuple:
    """Extract identity tuple from a completeness issue for set comparison.

    Issue #505: Uses (file_path, line_number, category) as the identity
    for stagnation detection across completeness gate iterations.
    """
    category = issue.get("category", "")
    if hasattr(category, "value"):
        category = category.value
    return (
        issue.get("file_path", ""),
        issue.get("line_number", 0),
        str(category),
    )


def route_after_completeness_gate(
    state: TestingWorkflowState,
) -> Literal["N5_verify_green", "N4_implement_code", "end"]:
    """Route based on completeness verdict and iteration count.

    Issue #147, Requirements 7, 8, 12:
    - BLOCK verdict: route back to N4 for re-implementation (up to 3 iterations)
    - PASS/WARN verdict: route forward to N5
    - BLOCK at max iterations (3): route to end (hard stop)

    Issue #505: AST stagnation detection — identical issues across
    2 consecutive iterations routes to end immediately.

    Args:
        state: Current workflow state with completeness_verdict set.

    Returns:
        Next node name: "N5_verify_green", "N4_implement_code", or "end".
    """
    error = state.get("error_message", "")
    if error:
        return "end"

    verdict = state.get("completeness_verdict", "")
    iteration_count = state.get("iteration_count", 0)

    if verdict == "BLOCK":
        if iteration_count >= MAX_COMPLETENESS_ITERATIONS:
            print(
                f"    [N4b] BLOCK at iteration {iteration_count} "
                f"(max {MAX_COMPLETENESS_ITERATIONS}) — routing to end"
            )
            return "end"

        # Issue #505: AST stagnation detection
        current_issues = state.get("completeness_issues", [])
        previous_issue_ids = state.get("previous_completeness_issues", [])

        if current_issues and previous_issue_ids:
            current_ids = sorted(
                _completeness_issue_identity(i) for i in current_issues
            )
            prev_ids = sorted(tuple(x) for x in previous_issue_ids)
            if current_ids == prev_ids:
                print(
                    f"    [N4b] [STAGNANT] Same {len(current_ids)} completeness issues "
                    f"across 2 iterations. Halting."
                )
                return "end"

        print(
            f"    [N4b] BLOCK — routing back to N4 "
            f"(iteration {iteration_count}/{MAX_COMPLETENESS_ITERATIONS})"
        )
        return "N4_implement_code"

    # PASS or WARN — proceed to N5
    gate_log(f"    [N4b] {verdict} — routing to N5_verify_green")
    return "N5_verify_green"


# =============================================================================
# Audit Formatting
# =============================================================================


def _format_ast_audit(result: CompletenessResult) -> str:
    """Format AST analysis result as a markdown audit entry.

    Args:
        result: CompletenessResult from Layer 1 analysis.

    Returns:
        Formatted markdown string.
    """
    lines = [
        "# Completeness Gate: AST Analysis",
        "",
        f"**Verdict:** {result['verdict']}",
        f"**Analysis Time:** {result['ast_analysis_ms']}ms",
        f"**Issues Found:** {len(result['issues'])}",
        "",
    ]

    if result["issues"]:
        lines.append("## Issues")
        lines.append("")
        lines.append("| Severity | Category | File | Line | Description |")
        lines.append("|----------|----------|------|------|-------------|")

        for issue in result["issues"]:
            category = issue["category"]
            cat_value = category.value if hasattr(category, "value") else str(category)
            file_name = Path(issue["file_path"]).name
            desc = issue["description"].replace("|", "\\|")
            lines.append(
                f"| {issue['severity']} "
                f"| {cat_value} "
                f"| `{file_name}` "
                f"| {issue['line_number']} "
                f"| {desc} |"
            )
        lines.append("")
    else:
        lines.append("*No issues detected.*")
        lines.append("")

    return "\n".join(lines)