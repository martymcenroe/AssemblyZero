"""N3 and N5: Verify Red/Green Phase nodes for TDD Testing Workflow.

N3 (verify_red_phase): Verify all tests fail before implementation
N5 (verify_green_phase): Verify all tests pass with coverage target

Issue #292: Added pytest exit code routing. Exit codes 4/5 (syntax/collection
errors) route back to N2_scaffold_tests instead of endlessly looping through
N4_implement_code. Exit codes 2/3 (interrupt/internal error) stop the workflow.
"""

import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import (
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    parse_pytest_output,
    save_audit_file,
)
from assemblyzero.workflows.testing.exit_code_router import (
    EXIT_INTERRUPTED,
    EXIT_INTERNALERROR,
    EXIT_USAGEERROR,
    EXIT_NOTESTSCOLLECTED,
    describe_exit_code,
    route_by_exit_code,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState


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
    # Issue #268: Use poetry run to ensure correct virtualenv with dependencies
    cmd = ["poetry", "run", "pytest", "-v", "--tb=short"]
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
    exit_code = result["returncode"]
    output = result["stdout"] + "\n" + result["stderr"]
    parsed = result["parsed"]

    print(f"    Results: {parsed.get('passed', 0)} passed, {parsed.get('failed', 0)} failed")
    print(f"    Exit code: {exit_code} ({describe_exit_code(exit_code)})")

    # Save output to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "red-phase.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Issue #292: Check exit code FIRST for routing decisions
    # Exit codes 4 (syntax/collection error) and 5 (no tests collected) mean
    # the scaffold itself is broken — route back to N2 to regenerate.
    # Exit codes 2 (interrupted) and 3 (internal error) stop the workflow.
    if exit_code in (EXIT_USAGEERROR, EXIT_NOTESTSCOLLECTED):
        reason = describe_exit_code(exit_code)
        print(f"    [EXIT CODE {exit_code}] {reason} — routing to re-scaffold")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="red_phase_scaffold_error",
            details={"exit_code": exit_code, "reason": reason},
        )

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "next_node": "N2_scaffold_tests",
            "error_message": "",
        }

    if exit_code in (EXIT_INTERRUPTED, EXIT_INTERNALERROR):
        reason = describe_exit_code(exit_code)
        print(f"    [EXIT CODE {exit_code}] {reason} — stopping workflow")

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "next_node": "end",
            "error_message": f"Red phase stopped: pytest {reason} (exit code {exit_code})",
        }

    # Analyze pass/fail counts (exit codes 0 and 1)
    passed_count = parsed.get("passed", 0)
    failed_count = parsed.get("failed", 0)
    error_count = parsed.get("errors", 0)

    # Issue #263: Import errors are valid RED phase behavior
    # With import-based TDD scaffolding, ImportError means "module doesn't exist"
    # which is exactly what RED phase should catch.
    total_red = failed_count + error_count

    # Red phase success = ALL tests fail or error (none pass)
    if passed_count > 0:
        print(f"    [GUARD] WARNING: {passed_count} tests passed unexpectedly!")
        print("    This may indicate pre-existing implementation.")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="red_phase_unexpected_pass",
            details={"passed": passed_count, "failed": failed_count, "errors": error_count},
        )

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "error_message": f"Red phase failed: {passed_count} tests passed unexpectedly. "
                           "Tests should fail before implementation.",
            "next_node": "END",
        }

    if total_red == 0:
        print("    [GUARD] WARNING: No tests ran!")

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "error_message": "Red phase failed: No tests were collected/run",
            "next_node": "END",
        }

    # Success: all tests failed or errored as expected
    # Note: errors include ImportError which is valid TDD RED behavior
    if error_count > 0:
        print(f"    Red phase PASSED: {error_count} import errors (module doesn't exist yet)")
    else:
        print(f"    Red phase PASSED: {failed_count} tests failed as expected")

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="red_phase_complete",
        details={"failed": failed_count, "errors": error_count, "exit_code": exit_code},
    )

    return {
        "red_phase_output": output,
        "file_counter": file_num,
        "pytest_exit_code": exit_code,
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

    # Determine coverage module from implementation files
    # Filter out test files - we want to measure coverage of implementation, not tests
    impl_files = state.get("implementation_files", [])
    coverage_module = None

    # Debug: Show what implementation files were received
    print(f"    DEBUG: implementation_files = {impl_files}")

    if impl_files:
        # Find first non-test, non-init implementation file for coverage
        for impl_path in impl_files:
            print(f"    DEBUG: Checking impl_path = {impl_path}")
            # Skip test files (in tests/ directory)
            path_parts = Path(impl_path).parts
            print(f"    DEBUG: path_parts = {path_parts}")
            if any(part.lower() in ("tests", "test") for part in path_parts):
                print(f"    DEBUG: Skipping (test path)")
                continue
            # Issue #265: Skip __init__.py - pytest-cov doesn't work with it
            if impl_path.endswith("__init__.py"):
                print(f"    DEBUG: Skipping __init__.py")
                continue
            rel_path = Path(impl_path).relative_to(repo_root) if repo_root else Path(impl_path)
            print(f"    DEBUG: rel_path = {rel_path}")
            # Convert file path to module format for pytest-cov
            # e.g., assemblyzero/workflows/testing/nodes/finalize.py -> assemblyzero.workflows.testing.nodes.finalize
            rel_path_str = str(rel_path)
            if rel_path_str.endswith(".py"):
                rel_path_str = rel_path_str[:-3]  # Remove .py extension
            coverage_module = rel_path_str.replace("/", ".").replace("\\", ".")
            print(f"    DEBUG: coverage_module (after conversion) = {coverage_module}")
            break

    # Default to assemblyzero if no implementation files
    if not coverage_module:
        coverage_module = "assemblyzero"

    print(f"    Coverage module: {coverage_module}")

    result = run_pytest(
        test_files,
        coverage_module=coverage_module,
        coverage_target=coverage_target,
        repo_root=repo_root,
    )
    exit_code = result["returncode"]
    output = result["stdout"] + "\n" + result["stderr"]
    parsed = result["parsed"]

    print(f"    Results: {parsed.get('passed', 0)} passed, {parsed.get('failed', 0)} failed")
    print(f"    Coverage: {parsed.get('coverage', 0):.1f}%")
    print(f"    Exit code: {exit_code} ({describe_exit_code(exit_code)})")

    # Save output to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "green-phase.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Issue #292: Check exit code FIRST for routing decisions
    # Exit codes 4/5 mean scaffold is broken — not an implementation problem.
    # Route back to N2 to regenerate tests instead of looping through N4.
    if exit_code in (EXIT_USAGEERROR, EXIT_NOTESTSCOLLECTED):
        reason = describe_exit_code(exit_code)
        print(f"    [EXIT CODE {exit_code}] {reason} — routing to re-scaffold")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="green_phase_scaffold_error",
            details={"exit_code": exit_code, "reason": reason, "iteration": iteration_count},
        )

        return {
            "green_phase_output": output,
            "coverage_achieved": 0,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "iteration_count": iteration_count + 1,
            "next_node": "N2_scaffold_tests",
            "error_message": "",
        }

    if exit_code in (EXIT_INTERRUPTED, EXIT_INTERNALERROR):
        reason = describe_exit_code(exit_code)
        print(f"    [EXIT CODE {exit_code}] {reason} — stopping workflow")

        return {
            "green_phase_output": output,
            "coverage_achieved": 0,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "iteration_count": iteration_count,
            "next_node": "end",
            "error_message": f"Green phase stopped: pytest {reason} (exit code {exit_code})",
        }

    # Analyze results (exit codes 0 and 1)
    passed_count = parsed.get("passed", 0)
    failed_count = parsed.get("failed", 0)
    error_count = parsed.get("errors", 0)
    coverage_achieved = parsed.get("coverage", 0)

    # Check for failures
    print(f"    DEBUG: failed_count={failed_count}, error_count={error_count}, iteration_count={iteration_count}")
    if failed_count > 0 or error_count > 0:
        # Check if we've exhausted iterations
        max_iterations = state.get("max_iterations", 10)
        print(f"    DEBUG: max_iterations={max_iterations}, check={iteration_count + 1} >= {max_iterations}")
        if iteration_count + 1 >= max_iterations:
            print(f"    [ERROR] Max iterations ({max_iterations}) reached with {failed_count} failures")
            error_msg = f"Green phase failed after {max_iterations} iterations: {failed_count} tests still failing"
            print(f"    DEBUG: Returning error_message='{error_msg}'")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": error_msg,
            }

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
            "pytest_exit_code": exit_code,
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
        }

    # Check coverage
    if coverage_achieved < coverage_target:
        # Check if we've exhausted iterations
        max_iterations = state.get("max_iterations", 10)
        if iteration_count + 1 >= max_iterations:
            print(f"    [ERROR] Max iterations ({max_iterations}) reached with {coverage_achieved:.1f}% coverage")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": f"Green phase failed after {max_iterations} iterations: coverage {coverage_achieved:.1f}% < target {coverage_target}%",
            }

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
            "pytest_exit_code": exit_code,
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
        }

    # Success: all tests pass and coverage meets target
    print(f"    DEBUG: SUCCESS PATH - failed_count={failed_count}, coverage_achieved={coverage_achieved}, coverage_target={coverage_target}")
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
            "pytest_exit_code": exit_code,
            "next_node": "N7_finalize",  # Skip E2E
            "error_message": "",
        }

    return {
        "green_phase_output": output,
        "coverage_achieved": coverage_achieved,
        "file_counter": file_num,
        "pytest_exit_code": exit_code,
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
assemblyzero/__init__.py          10      0   100%
assemblyzero/module.py            50      5    90%
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
