"""RunTests node for TDD Testing Workflow.

Issue #381: Framework-aware test execution that delegates to the
appropriate runner from the runner registry.
"""

import logging
from typing import Any

from assemblyzero.workflows.testing.audit import gate_log, log_workflow_execution
from assemblyzero.workflows.testing.framework_detector import (
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runner_registry import (
    get_framework_config,
    get_runner,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState

logger = logging.getLogger(__name__)


def run_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """Execute tests using the framework-appropriate runner.

    Reads framework_config from state, validates test files,
    runs tests, and stores unified TestRunResult in state.

    Args:
        state: Workflow state containing framework_config, test_files, etc.

    Returns:
        Dict with test_run_result, validation_errors, and error_message.
    """
    issue_number = state.get("issue_number", 0)
    framework_config = state.get("framework_config")
    test_files: list[str] = state.get("test_files", [])
    repo_root: str = str(state.get("repo_root", "."))

    gate_log(f"[RunTests] Starting test execution for issue #{issue_number}")

    # Fallback to pytest if no framework config
    if not framework_config:
        logger.info("No framework_config in state; defaulting to pytest")
        framework_config = get_framework_config(TestFramework.PYTEST)

    framework = framework_config["framework"]
    gate_log(f"[RunTests] Framework: {framework.value}")

    if not test_files:
        return {
            "test_run_result": None,
            "validation_errors": [],
            "error_message": "No test files to run",
        }

    # Get the runner
    try:
        runner = get_runner(framework, project_root=repo_root)
    except EnvironmentError as e:
        gate_log(f"[RunTests] Environment error: {e}")
        return {
            "test_run_result": None,
            "validation_errors": [],
            "error_message": str(e),
        }

    # Validate each test file
    all_validation_errors: list[str] = []
    for file_path in test_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            errors = runner.validate_test_file(file_path, content)
            all_validation_errors.extend(errors)
        except (OSError, IOError) as e:
            all_validation_errors.append(f"Cannot read test file {file_path}: {e}")

    if all_validation_errors:
        gate_log(
            f"[RunTests] Validation errors found: {len(all_validation_errors)}"
        )
        for err in all_validation_errors:
            gate_log(f"[RunTests]   - {err}")
        return {
            "test_run_result": None,
            "validation_errors": all_validation_errors,
            "error_message": f"Test file validation failed: {len(all_validation_errors)} error(s)",
        }

    # Run the tests
    gate_log(f"[RunTests] Executing {len(test_files)} test file(s)")
    try:
        result: TestRunResult = runner.run_tests(test_paths=test_files)
    except Exception as e:
        logger.error("Test execution failed: %s", e)
        return {
            "test_run_result": None,
            "validation_errors": [],
            "error_message": f"Test execution failed: {e}",
        }

    gate_log(
        f"[RunTests] Results: {result['passed']} passed, "
        f"{result['failed']} failed, {result['skipped']} skipped, "
        f"{result['errors']} errors (exit code: {result['exit_code']})"
    )

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=issue_number,
        workflow_type="testing",
        event="tests_executed",
        details={
            "total": result["total"],
            "passed": result["passed"],
            "failed": result["failed"],
            "framework": result["framework"].value,
        },
    )

    return {
        "test_run_result": result,
        "validation_errors": [],
        "error_message": "",
    }