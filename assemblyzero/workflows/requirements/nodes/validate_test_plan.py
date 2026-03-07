"""N1b: Mechanical test plan validation node for Requirements Workflow.

Issue #166: Validates test plan coverage, assertions, and delegation
before sending to Gemini review. Uses shared validator from
assemblyzero.core.validation to ensure consistency with testing workflow.

Routes:
- PASS → N2 (human gate) or N3 (Gemini review)
- FAIL → N1 (draft) with structured feedback
- MAX_ATTEMPTS → END (prevent infinite loops)
"""

from typing import Any

from assemblyzero.core.validation.test_plan_validator import (
    MAX_VALIDATION_ATTEMPTS,
    validate_test_plan,
)
from assemblyzero.workflows.requirements.state import RequirementsWorkflowState


def validate_test_plan_node(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N1b: Mechanical test plan validation.

    Runs deterministic validation checks on the LLD's test plan
    before sending to Gemini review. If validation fails, routes
    back to N1 (draft) with specific feedback.

    Args:
        state: Current workflow state.

    Returns:
        State updates with validation results.
    """
    print("\n[N1b] Running mechanical test plan validation...")

    # Check max attempts to prevent infinite loops
    attempts = state.get("test_plan_validation_attempts", 0)
    if attempts >= MAX_VALIDATION_ATTEMPTS:
        print(f"    [ESCALATE] Max validation attempts ({MAX_VALIDATION_ATTEMPTS}) reached")
        return {
            "error_message": f"Test plan validation failed after {MAX_VALIDATION_ATTEMPTS} attempts — escalating",
            "test_plan_validation_attempts": attempts,
        }

    # Get LLD content
    lld_content = state.get("current_draft", "")
    if not lld_content:
        print("    [ERROR] No draft content available")
        return {
            "error_message": "No draft content for test plan validation",
        }

    # Issue #656: Mechanical format check — call actual parsers and report
    # diagnostics before running the full validation. This catches format
    # mismatches early with clear error messages.
    from assemblyzero.core.validation.test_plan_validator import (
        extract_requirements as _extract_reqs,
        extract_test_scenarios as _extract_tests,
    )
    _reqs = _extract_reqs(lld_content)
    _tests = _extract_tests(lld_content)
    if not _reqs:
        print("    [DIAG] extract_requirements() returned 0 items — "
              "Section 3 heading may be missing or format mismatch")
    else:
        print(f"    [DIAG] extract_requirements() found {len(_reqs)} items")
    if not _tests:
        print("    [DIAG] extract_test_scenarios() returned 0 items — "
              "Section 10/10.1 heading may be missing or no table rows parsed")
    else:
        print(f"    [DIAG] extract_test_scenarios() found {len(_tests)} items")

    # Run validation
    result = validate_test_plan(lld_content)

    print(f"    Coverage: {result['coverage_percentage']}% "
          f"({result['mapped_count']}/{result['requirements_count']} requirements)")
    print(f"    Tests: {result['tests_count']}")
    print(f"    Violations: {len(result['violations'])} "
          f"({sum(1 for v in result['violations'] if v['severity'] == 'error')} errors, "
          f"{sum(1 for v in result['violations'] if v['severity'] == 'warning')} warnings)")
    print(f"    Time: {result['execution_time_ms']:.1f}ms")
    print(f"    Result: {'PASSED' if result['passed'] else 'FAILED'}")

    new_attempts = attempts + 1

    if result["passed"]:
        return {
            "test_plan_validation_result": result,
            "test_plan_validation_attempts": new_attempts,
            "iteration_count": state.get("iteration_count", 0) + 1,
            "error_message": "",
        }

    # Build feedback for drafter
    feedback = _build_validation_feedback(result)
    print(f"    Feedback:\n{feedback}")

    return {
        "test_plan_validation_result": result,
        "test_plan_validation_attempts": new_attempts,
        "user_feedback": feedback,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "lld_status": "BLOCKED",
        "error_message": "",
    }


def _build_validation_feedback(result: dict) -> str:
    """Build structured feedback from validation violations.

    Args:
        result: ValidationResult dict.

    Returns:
        Markdown-formatted feedback string.
    """
    lines = [
        "## Mechanical Test Plan Validation Failed",
        "",
        f"**Coverage:** {result['coverage_percentage']}% "
        f"({result['mapped_count']}/{result['requirements_count']} requirements mapped)",
        "",
    ]

    errors = [v for v in result["violations"] if v["severity"] == "error"]
    warnings = [v for v in result["violations"] if v["severity"] == "warning"]

    if errors:
        lines.append("### Errors (must fix)")
        lines.append("")
        for v in errors:
            lines.append(f"- **{v['check_type']}**: {v['message']}")
        lines.append("")

    if warnings:
        lines.append("### Warnings (consider fixing)")
        lines.append("")
        for v in warnings:
            lines.append(f"- **{v['check_type']}**: {v['message']}")
        lines.append("")

    lines.append("Please revise the LLD to address the errors above.")
    lines.append("")
    lines.append("### Format Requirements (CRITICAL)")
    lines.append("")
    lines.append("**Section 3 (Requirements):** MUST use numbered list format:")
    lines.append("```")
    lines.append("1. First requirement text")
    lines.append("2. Second requirement text")
    lines.append("```")
    lines.append("Do NOT use tables, bullet points, or REQ-ID prefixes in Section 3.")
    lines.append("")
    lines.append("**Section 10.1 (Test Scenarios):** Each test scenario MUST reference "
                 "its requirement in the Scenario column using `(REQ-N)` suffix:")
    lines.append("```")
    lines.append("| 010 | Create logger with defaults (REQ-1) | Auto | ... |")
    lines.append("| 020 | Log directory auto-created (REQ-2) | Auto | ... |")
    lines.append("```")

    return "\n".join(lines)
