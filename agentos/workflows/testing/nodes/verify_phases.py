"""N3 and N5: Verify Red/Green Phase nodes for TDD Testing Workflow.

N3 (verify_red_phase): Verify all tests fail before implementation
N5 (verify_green_phase): Verify all tests pass with coverage target
"""

import subprocess
from pathlib import Path
from typing import Any

from agentos.workflows.testing.audit import (
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    parse_pytest_output,
    save_audit_file,
)
from agentos.workflows.testing.state import TestingWorkflowState


# Timeout for pytest execution
PYTEST_TIMEOUT_SECONDS = 300


def run_pytest(
    test_files: list[str],
    coverage_module: str | None = None,
    coverage_target: int | None = None,
    repo_root: Path | None = None,
) -> dict:
    """Run pytest on the specified test files.

    Args:
        test_files: List of test file paths.
        coverage_module: Module to measure coverage for.
        coverage_target: Coverage threshold percentage.
        repo_root: Repository root for running pytest.

    Returns:
        Dict with returncode, stdout, stderr, and parsed results.
    """
    cmd = ["pytest", "-v", "--tb=short"]
    cmd.extend(test_files)

    if coverage_module:
        cmd.extend([f"--cov={coverage_module}", "--cov-report=term-missing"])
        if coverage_target:
            cmd.append(f"--cov-fail-under={coverage_target}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PYTEST_TIMEOUT_SECONDS,
            cwd=str(repo_root) if repo_root else None,
        )

        parsed = parse_pytest_output(result.stdout + result.stderr)

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "parsed": parsed,
        }

    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "Pytest execution timed out",
            "parsed": {"passed": 0, "failed": 0, "errors": 1, "coverage": 0},
        }
    except FileNotFoundError:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "pytest not found. Is it installed?",
            "parsed": {"passed": 0, "failed": 0, "errors": 1, "coverage": 0},
        }


def verify_red_phase(state: TestingWorkflowState) -> dict[str, Any]:
    """N3: Verify all tests fail (TDD red phase).

    The red phase confirms that:
    1. All tests are syntactically valid and runnable
    2. All tests fail (no pre-existing implementation)
    3. Failures are the expected "TDD: Implementation pending" assertions

    Args:
        state: Current workflow state.

    Returns:
        State updates with red phase results.
    """
    print("\n[N3] Verifying red phase (all tests should fail)...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_verify_red_phase(state)

    # Get data from state
    test_files = state.get("test_files", [])
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    # --------------------------------------------------------------------------
    # GUARD: Validate test files exist
    # --------------------------------------------------------------------------
    if not test_files:
        print("    [GUARD] BLOCKED: No test files to run")
        return {"error_message": "GUARD: No test files generated"}

    for tf in test_files:
        if not Path(tf).exists():
            print(f"    [GUARD] BLOCKED: Test file not found: {tf}")
            return {"error_message": f"GUARD: Test file not found: {tf}"}
    # --------------------------------------------------------------------------

    print(f"    Running pytest on {len(test_files)} test file(s)...")

    # Run pytest
    result = run_pytest(test_files, repo_root=repo_root)
    output = result["stdout"] + "\n" + result["stderr"]
    parsed = result["parsed"]

    print(f"    Results: {parsed.get('passed', 0)} passed, {parsed.get('failed', 0)} failed")

    # Save output to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "red-phase.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Analyze results
    passed_count = parsed.get("passed", 0)
    failed_count = parsed.get("failed", 0)
    error_count = parsed.get("errors", 0)

    # Red phase success = ALL tests fail (none pass)
    if passed_count > 0:
        print(f"    [GUARD] WARNING: {passed_count} tests passed unexpectedly!")
        print("    This may indicate pre-existing implementation.")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="red_phase_unexpected_pass",
            details={"passed": passed_count, "failed": failed_count},
        )

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "error_message": f"Red phase failed: {passed_count} tests passed unexpectedly. "
                           "Tests should fail before implementation.",
            "next_node": "END",
        }

    if error_count > 0:
        print(f"    [ERROR] {error_count} tests had errors (not assertion failures)")

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "error_message": f"Red phase error: {error_count} tests had syntax/import errors",
            "next_node": "END",
        }

    if failed_count == 0:
        print("    [GUARD] WARNING: No tests ran!")

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "error_message": "Red phase failed: No tests were collected/run",
            "next_node": "END",
        }

    # Success: all tests failed as expected
    print(f"    Red phase PASSED: {failed_count} tests failed as expected")

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="red_phase_complete",
        details={"failed": failed_count},
    )

    return {
        "red_phase_output": output,
        "file_counter": file_num,
        "next_node": "N4_implement_code",
        "error_message": "",
    }


def verify_green_phase(state: TestingWorkflowState) -> dict[str, Any]:
    """N5: Verify all tests pass with coverage target.

    The green phase confirms that:
    1. All tests pass
    2. Coverage meets target (default 90%)

    Args:
        state: Current workflow state.

    Returns:
        State updates with green phase results.
    """
    print("\n[N5] Verifying green phase (all tests should pass)...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_verify_green_phase(state)

    # Get data from state
    test_files = state.get("test_files", [])
    coverage_target = state.get("coverage_target", 90)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    iteration_count = state.get("iteration_count", 0)

    print(f"    Running pytest with coverage target: {coverage_target}%")

    # Run pytest with coverage
    # For now, use "agentos" as the coverage module - this should be configurable
    result = run_pytest(
        test_files,
        coverage_module="agentos",
        coverage_target=coverage_target,
        repo_root=repo_root,
    )
    output = result["stdout"] + "\n" + result["stderr"]
    parsed = result["parsed"]

    print(f"    Results: {parsed.get('passed', 0)} passed, {parsed.get('failed', 0)} failed")
    print(f"    Coverage: {parsed.get('coverage', 0):.1f}%")

    # Save output to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "green-phase.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Analyze results
    passed_count = parsed.get("passed", 0)
    failed_count = parsed.get("failed", 0)
    error_count = parsed.get("errors", 0)
    coverage_achieved = parsed.get("coverage", 0)

    # Check for failures
    if failed_count > 0 or error_count > 0:
        print(f"    [ITERATE] {failed_count} failures, {error_count} errors - needs revision")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="green_phase_failed",
            details={
                "passed": passed_count,
                "failed": failed_count,
                "errors": error_count,
                "iteration": iteration_count,
            },
        )

        # Loop back to implementation
        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "file_counter": file_num,
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
        }

    # Check coverage
    if coverage_achieved < coverage_target:
        print(f"    [ITERATE] Coverage {coverage_achieved:.1f}% < target {coverage_target}%")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="green_phase_low_coverage",
            details={
                "coverage": coverage_achieved,
                "target": coverage_target,
                "iteration": iteration_count,
            },
        )

        # Loop back to implementation for more coverage
        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "file_counter": file_num,
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
        }

    # Success: all tests pass and coverage meets target
    print(f"    Green phase PASSED: {passed_count} tests, {coverage_achieved:.1f}% coverage")

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="green_phase_complete",
        details={
            "passed": passed_count,
            "coverage": coverage_achieved,
            "iterations": iteration_count,
        },
    )

    # Check if E2E should be skipped
    if state.get("skip_e2e"):
        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "file_counter": file_num,
            "next_node": "N7_finalize",  # Skip E2E
            "error_message": "",
        }

    return {
        "green_phase_output": output,
        "coverage_achieved": coverage_achieved,
        "file_counter": file_num,
        "next_node": "N6_e2e_validation",
        "error_message": "",
    }


def _mock_verify_red_phase(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    audit_dir = Path(state.get("audit_dir", ""))

    mock_output = """============================= test session starts ==============================
collected 3 items

tests/test_issue_42.py::test_login_success FAILED
tests/test_issue_42.py::test_login_failure FAILED
tests/test_issue_42.py::test_input_validation FAILED

=========================== short test summary info ============================
FAILED tests/test_issue_42.py::test_login_success - AssertionError: TDD: Implementation pending
FAILED tests/test_issue_42.py::test_login_failure - AssertionError: TDD: Implementation pending
FAILED tests/test_issue_42.py::test_input_validation - AssertionError: TDD: Implementation pending
============================== 3 failed in 0.12s ===============================
"""

    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "red-phase.txt", mock_output)
    else:
        file_num = state.get("file_counter", 0)

    print("    [MOCK] Red phase: 3 tests failed as expected")

    return {
        "red_phase_output": mock_output,
        "file_counter": file_num,
        "next_node": "N4_implement_code",
        "error_message": "",
    }


def _mock_verify_green_phase(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    audit_dir = Path(state.get("audit_dir", ""))
    iteration_count = state.get("iteration_count", 0)
    coverage_target = state.get("coverage_target", 90)

    # First iteration: fail, second: pass
    if iteration_count <= 1:
        mock_output = """============================= test session starts ==============================
collected 3 items

tests/test_issue_42.py::test_login_success PASSED
tests/test_issue_42.py::test_login_failure FAILED
tests/test_issue_42.py::test_input_validation PASSED

=========================== short test summary info ============================
FAILED tests/test_issue_42.py::test_login_failure - AssertionError
============================== 1 failed, 2 passed in 0.15s =====================
"""
        coverage_achieved = 75.0
        next_node = "N4_implement_code"
    else:
        mock_output = f"""============================= test session starts ==============================
collected 3 items

tests/test_issue_42.py::test_login_success PASSED
tests/test_issue_42.py::test_login_failure PASSED
tests/test_issue_42.py::test_input_validation PASSED

---------- coverage: platform linux, python 3.11.0 ----------
Name                      Stmts   Miss  Cover
---------------------------------------------
agentos/__init__.py          10      0   100%
agentos/module.py            50      5    90%
---------------------------------------------
TOTAL                        60      5    92%

============================== 3 passed in 0.18s ===============================
"""
        coverage_achieved = 92.0
        next_node = "N7_finalize" if state.get("skip_e2e") else "N6_e2e_validation"

    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "green-phase.txt", mock_output)
    else:
        file_num = state.get("file_counter", 0)

    print(f"    [MOCK] Green phase: coverage {coverage_achieved}%")

    return {
        "green_phase_output": mock_output,
        "coverage_achieved": coverage_achieved,
        "file_counter": file_num,
        "iteration_count": iteration_count + 1 if next_node == "N4_implement_code" else iteration_count,
        "next_node": next_node,
        "error_message": "",
    }
