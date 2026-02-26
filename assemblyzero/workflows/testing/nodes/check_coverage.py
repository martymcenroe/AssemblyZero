"""CheckCoverage node for TDD Testing Workflow.

Issue #381: Framework-aware coverage checking that dispatches on
coverage_type (LINE, SCENARIO, NONE).
"""

import logging
from typing import Any

from assemblyzero.workflows.testing.audit import gate_log, log_workflow_execution
from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import (
    get_framework_config,
    get_runner,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState

logger = logging.getLogger(__name__)


def check_coverage(state: TestingWorkflowState) -> dict[str, Any]:
    """Evaluate coverage against framework-appropriate target.

    Dispatches on coverage_type:
    - LINE: compare result.coverage_percent against coverage_target
    - SCENARIO: compute passed/total_scenarios against coverage_target
    - NONE: skip coverage gate, only check pass/fail

    Args:
        state: Workflow state containing test_run_result and framework_config.

    Returns:
        Dict with 'green' (bool) and 'iterate_reason' (str).
    """
    issue_number = state.get("issue_number", 0)
    test_run_result = state.get("test_run_result")
    framework_config = state.get("framework_config")

    gate_log(f"[CheckCoverage] Evaluating results for issue #{issue_number}")

    if not test_run_result:
        return {
            "green": False,
            "iterate_reason": "No test results available",
        }

    # Fallback to pytest config if not set
    if not framework_config:
        framework_config = get_framework_config(TestFramework.PYTEST)

    coverage_type = framework_config["coverage_type"]
    coverage_target = framework_config["coverage_target"]

    # Step 1: Check for test failures (applies to all frameworks)
    if test_run_result["failed"] > 0:
        reason = f"{test_run_result['failed']} tests failed"
        gate_log(f"[CheckCoverage] NOT GREEN: {reason}")
        return {
            "green": False,
            "iterate_reason": reason,
        }

    if test_run_result["errors"] > 0:
        reason = f"{test_run_result['errors']} test errors"
        gate_log(f"[CheckCoverage] NOT GREEN: {reason}")
        return {
            "green": False,
            "iterate_reason": reason,
        }

    # Step 2: Coverage check based on type
    repo_root = str(state.get("repo_root", "."))

    if coverage_type == CoverageType.SCENARIO:
        total_scenarios = state.get("total_scenarios", 0)

        if total_scenarios == 0:
            # Try to use test total as fallback
            total_scenarios = test_run_result.get("total", 0)

        if total_scenarios == 0:
            gate_log("[CheckCoverage] WARNING: No scenarios to measure coverage against")
            return {
                "green": False,
                "iterate_reason": "No scenarios defined for coverage measurement",
            }

        runner = get_runner(framework_config["framework"])
        coverage = runner.compute_scenario_coverage(test_run_result, total_scenarios)

        if coverage < coverage_target:
            reason = (
                f"Scenario coverage {coverage:.1%} < target {coverage_target:.1%}"
            )
            gate_log(f"[CheckCoverage] NOT GREEN: {reason}")
            return {
                "green": False,
                "iterate_reason": reason,
            }

        gate_log(f"[CheckCoverage] GREEN: Scenario coverage {coverage:.1%} >= {coverage_target:.1%}")
        log_workflow_execution(
            target_repo=repo_root,
            issue_number=issue_number,
            workflow_type="testing",
            event="coverage_checked",
            details={
                "coverage_type": "scenario",
                "coverage": coverage,
                "target": coverage_target,
                "green": True,
            },
        )
        return {"green": True, "iterate_reason": ""}

    elif coverage_type == CoverageType.LINE:
        coverage_percent = test_run_result.get("coverage_percent", 0.0)
        target_percent = coverage_target * 100  # Convert 0.95 to 95.0

        if coverage_percent < target_percent:
            reason = (
                f"Line coverage {coverage_percent:.1f}% < target {target_percent:.1f}%"
            )
            gate_log(f"[CheckCoverage] NOT GREEN: {reason}")
            return {
                "green": False,
                "iterate_reason": reason,
            }

        gate_log(
            f"[CheckCoverage] GREEN: Line coverage {coverage_percent:.1f}% >= {target_percent:.1f}%"
        )
        log_workflow_execution(
            target_repo=repo_root,
            issue_number=issue_number,
            workflow_type="testing",
            event="coverage_checked",
            details={
                "coverage_type": "line",
                "coverage_percent": coverage_percent,
                "target_percent": target_percent,
                "green": True,
            },
        )
        return {"green": True, "iterate_reason": ""}

    elif coverage_type == CoverageType.NONE:
        gate_log("[CheckCoverage] GREEN: Coverage type is NONE, pass/fail check only")
        log_workflow_execution(
            target_repo=repo_root,
            issue_number=issue_number,
            workflow_type="testing",
            event="coverage_checked",
            details={
                "coverage_type": "none",
                "green": True,
            },
        )
        return {"green": True, "iterate_reason": ""}

    else:
        logger.warning("Unknown coverage type: %s", coverage_type)
        return {
            "green": False,
            "iterate_reason": f"Unknown coverage type: {coverage_type}",
        }