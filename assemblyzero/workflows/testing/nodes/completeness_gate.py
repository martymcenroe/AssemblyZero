"""N4b: Implementation Completeness Gate node for TDD Testing Workflow.

Issue #147: Implementation Completeness Gate (Anti-Stub Detection)
Related: #181 (Implementation Report), #335 (N2.5 precedent)

Two-layer validation between N4 (implement_code) and N5 (verify_green):
- Layer 1: AST-based deterministic analysis (fast, free)
- Layer 2: Gemini semantic review materials preparation (user-controlled)

Failure (ADR 0236, #3811): a gate that cannot check stops the run. A file it
cannot read or parse, an LLD with no requirements, a report it cannot write,
and a BLOCK that survives the iteration cap or stagnates all set
error_message, which routes to HALT, and HALT alerts the operator.

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
    CompletenessGateError,
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

# Issue #147, Section 2.5: hard limit of 3 iterations; a BLOCK at it halts (#3811)
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

    Failure (#3811): when the gate cannot check, or a BLOCK reaches the
    iteration cap or repeats unchanged, the node returns verdict BLOCK with
    an error_message, which routes to HALT.

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
    # #2024: prefer the canonical LLD. `lld_path` is a legacy name that in this
    # workflow holds the SPEC, whose Section 3 is "Current State" -- so the
    # requirement extractor found nothing, said so in a log warning, and the
    # gate reviewed the implementation against ZERO requirements and returned a
    # verdict anyway. Falls back to lld_path when no LLD was resolved.
    lld_path_str = state.get("original_lld_path", "") or state.get("lld_path", "")
    implementation_files_strs = state.get("implementation_files", [])
    test_files_strs = state.get("test_files", [])
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None

    # Convert string paths to Path objects
    implementation_files = [Path(f) for f in implementation_files_strs]
    test_files = [Path(f) for f in test_files_strs]
    lld_path = Path(lld_path_str) if lld_path_str else None
    # #3811: mock mode records the LLD relative to the target repository. Read
    # against the process's working directory it never existed, and Layer 2
    # and the report were skipped without a word.
    if lld_path is not None and not lld_path.is_absolute():
        lld_path = repo_root / lld_path

    # Combine implementation and test files for analysis
    all_files = implementation_files + test_files

    # =========================================================================
    # #2552: a zero needs a denominator here too. This gate's verdict comes
    # entirely from Layer 1's AST analysis of the implementation files; the
    # requirement set only ever fed Layer 2's PREPARATION — so with zero
    # requirements the gate reviewed the implementation against nothing and
    # returned the same PASS five requirements would earn (#2024 repaired
    # the path resolution that caused one such run; the requirement-
    # blindness itself survived it). Certifying completeness against an
    # empty set is not a verdict, it is the absence of one: refuse, naming
    # load_lld's recorded reason so the halt says whether the set was
    # declared empty or unreadable and where it looked.
    # =========================================================================
    requirements = state.get("requirements", [])
    if not requirements:
        reason = state.get("requirements_empty_reason", "") or (
            "no requirement set in state and no recorded reason -- "
            "load_lld did not run, or ran before this field existed"
        )
        message = (
            f"Completeness gate: cannot certify an implementation against "
            f"zero requirements -- {reason} (#2552)"
        )
        print(f"    [N4b] {message}")
        log_workflow_execution(
            target_repo=repo_root,
            issue_number=issue_number,
            workflow_type="testing",
            event="completeness_zero_requirements",
            details={"reason": reason},
        )
        return {
            "completeness_verdict": "BLOCK",
            "completeness_issues": [],
            "error_message": message,
        }

    where = f"issue #{issue_number} in {repo_root}"
    if not all_files:
        # #3811: a gate with nothing to analyse has certified nothing.
        return _cannot_check(f"no implementation or test files to analyse for {where}")
    if lld_path is None or not lld_path.exists():
        # #3811: the review materials and the report both need the LLD.
        return _cannot_check(f"the LLD {lld_path_str or '(none in state)'} for {where} does not exist")

    print(f"    Analyzing {len(implementation_files)} implementation + {len(test_files)} test files...")

    # =========================================================================
    # Layer 1: AST Analysis
    # =========================================================================

    try:
        ast_result: CompletenessResult = run_ast_analysis(all_files)
    except CompletenessGateError as exc:
        return _cannot_check(f"Layer 1 AST analysis for {where}: {exc}")

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

    if verdict != "BLOCK":
        # Layer 1 passed — prepare materials for user to submit to Gemini
        print("    Layer 2: Preparing review materials for Gemini...")
        try:
            review_materials = prepare_review_materials(
                issue_number=issue_number,
                lld_path=lld_path,
                implementation_files=implementation_files,
            )
        except CompletenessGateError as exc:
            return _cannot_check(f"Layer 2 review materials for {where}: {exc}")
        req_count = len(review_materials.get("lld_requirements", []))
        snippet_count = len(review_materials.get("code_snippets", {}))
        print(f"    Layer 2: Prepared {req_count} requirements, {snippet_count} code snippets")
    else:
        print("    Layer 2: Skipped (Layer 1 BLOCK)")

    # =========================================================================
    # Report Generation
    # =========================================================================

    print("    Generating implementation report...")
    try:
        report_path = generate_implementation_report(
            issue_number=issue_number,
            lld_path=lld_path,
            implementation_files=implementation_files,
            completeness_result=ast_result,
            repo_root=repo_root,
        )
    except CompletenessGateError as exc:
        return _cannot_check(f"the implementation report for {where}: {exc}")
    implementation_report_path = str(report_path)
    print(f"    Report: {report_path}")

    # Save report path to audit
    if audit_dir and audit_dir.exists():
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
        "error_message": _block_stop_reason(
            verdict, issue_ids, state.get("previous_completeness_issues", []),
            iteration_count, where,
        ),
    }

    # Include review materials if prepared (for user to submit to Gemini)
    if review_materials is not None:
        result["review_materials"] = review_materials

    print(f"    Completeness gate verdict: {verdict}")
    return result


def _cannot_check(reason: str) -> dict[str, Any]:
    """The gate could not check: BLOCK, with an error that routes to HALT (#3811)."""
    message = f"Completeness gate could not check: {reason} (#3811)"
    logger.error(message)
    return {
        "completeness_verdict": "BLOCK",
        "completeness_issues": [],
        "error_message": message,
    }


def _block_stop_reason(
    verdict: str,
    issue_ids: list[list],
    previous_issue_ids: list[list],
    iteration_count: int,
    where: str,
) -> str:
    """Why a BLOCK stops the run instead of going back to N4, or "" when it does not.

    Issue #147: a BLOCK at the iteration cap stops. Issue #505: so does one
    whose issues are those of the previous iteration. #3852: the previous
    iteration's identities are read from state before this update replaces
    them; the router used to compare this update with itself, so every first
    BLOCK looked stagnant. #3811: the stop is an error_message, so it reaches
    HALT and the operator is alerted, where it used to end the graph silently.
    """
    if verdict != "BLOCK":
        return ""
    if iteration_count >= MAX_COMPLETENESS_ITERATIONS:
        message = (
            f"Completeness gate still BLOCK at iteration {iteration_count} "
            f"(max {MAX_COMPLETENESS_ITERATIONS}) for {where}; see the implementation report"
        )
    elif issue_ids and sorted(map(tuple, issue_ids)) == sorted(map(tuple, previous_issue_ids)):
        message = (
            f"Completeness gate stagnant for {where}: the same {len(issue_ids)} issue(s) "
            f"two iterations running"
        )
    else:
        return ""
    logger.error(message)
    return message


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
) -> Literal["N4_5_mechanical_hooks", "N4_implement_code", "HALT"]:
    """Route based on the node's error and verdict.

    Issue #147, Requirements 7, 8, 12:
    - BLOCK verdict: route back to N4 for re-implementation
    - PASS/WARN verdict: route forward to N5

    #2756, #3811: every stop is an error_message the node set, and routes to
    HALT. That includes a BLOCK at the iteration cap and a stagnant BLOCK
    (#505), which the node decides; they used to route to END with no reason
    recorded and no alert.

    Args:
        state: Current workflow state with completeness_verdict set.

    Returns:
        Next node name: "N4_5_mechanical_hooks", "N4_implement_code" or "HALT".
    """
    if state.get("error_message", ""):
        return "HALT"

    verdict = state.get("completeness_verdict", "")
    if verdict == "BLOCK":
        print(
            f"    [N4b] BLOCK — routing back to N4 "
            f"(iteration {state.get('iteration_count', 0)}/{MAX_COMPLETENESS_ITERATIONS})"
        )
        return "N4_implement_code"

    # PASS or WARN — proceed to N5
    gate_log(f"    [N4b] {verdict} — routing to N5_verify_green")
    return "N4_5_mechanical_hooks"


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