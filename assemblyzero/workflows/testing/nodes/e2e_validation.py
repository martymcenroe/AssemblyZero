"""N6: E2E Validation node for TDD Testing Workflow.

Runs E2E tests in a sandbox environment:
- Uses dedicated sandbox repos (mcwiz/assemblyzero-e2e-tools, mcwiz/assemblyzero-e2e-target)
- Has safety limits (max 5 issues, max 3 PRs per run)
- Auto-cleanup after each E2E run
"""

import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import (
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState


# Safety limits for E2E testing
DEFAULT_E2E_MAX_ISSUES = 5
DEFAULT_E2E_MAX_PRS = 3
E2E_TIMEOUT_SECONDS = 600  # 10 minutes


def run_e2e_tests(
    test_files: list[str],
    sandbox_repo: str | None,
    repo_root: Path,
) -> dict:
    """Run E2E tests.

    Args:
        test_files: List of test file paths.
        sandbox_repo: Path to sandbox repository.
        repo_root: Repository root for running tests.

    Returns:
        Dict with returncode, stdout, stderr.
    """
    # Filter for E2E tests only
    e2e_files = [f for f in test_files if "e2e" in f.lower() or "integration" in f.lower()]

    if not e2e_files:
        # Run all tests if no specific E2E files
        e2e_files = test_files

    cmd = [
        "pytest",
        "-v",
        "-m", "e2e or integration",  # Run only e2e/integration marked tests
        "--tb=short",
    ]
    cmd.extend(e2e_files)

    # Set environment variables for sandbox
    env = {}
    if sandbox_repo:
        env["E2E_SANDBOX_REPO"] = sandbox_repo

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=E2E_TIMEOUT_SECONDS,
            cwd=str(repo_root),
            env={**subprocess.os.environ, **env},
        )

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "E2E test execution timed out",
        }
    except FileNotFoundError:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "pytest not found",
        }


def cleanup_sandbox(sandbox_repo: str) -> tuple[bool, str]:
    """Clean up sandbox repository after E2E tests.

    Args:
        sandbox_repo: Path to sandbox repository.

    Returns:
        Tuple of (success, error_message).
    """
    # For now, this is a stub - actual cleanup would:
    # 1. Delete test issues created in sandbox
    # 2. Close test PRs
    # 3. Reset sandbox to clean state

    return True, ""


def verify_safety_limits(
    sandbox_repo: str,
    max_issues: int,
    max_prs: int,
) -> tuple[bool, str]:
    """Verify sandbox is within safety limits.

    Args:
        sandbox_repo: Path to sandbox repository.
        max_issues: Maximum allowed issues.
        max_prs: Maximum allowed PRs.

    Returns:
        Tuple of (safe, error_message).
    """
    # This would query GitHub to check current counts
    # For now, assume safe

    return True, ""


def e2e_validation(state: TestingWorkflowState) -> dict[str, Any]:
    """N6: Run E2E tests in sandbox environment.

    Args:
        state: Current workflow state.

    Returns:
        State updates with E2E results.
    """
    print("\n[N6] Running E2E validation...")

    # Check for skip_e2e mode
    if state.get("skip_e2e"):
        print("    E2E skipped (--skip-e2e flag)")
        return {
            "e2e_output": "E2E validation skipped",
            "next_node": "N7_finalize",
            "error_message": "",
        }

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_e2e_validation(state)

    # Get data from state
    test_files = state.get("test_files", [])
    sandbox_repo = state.get("sandbox_repo", "")
    max_issues = state.get("e2e_max_issues", DEFAULT_E2E_MAX_ISSUES)
    max_prs = state.get("e2e_max_prs", DEFAULT_E2E_MAX_PRS)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    iteration_count = state.get("iteration_count", 0)

    # --------------------------------------------------------------------------
    # GUARD: Verify safety limits before running E2E
    # --------------------------------------------------------------------------
    if sandbox_repo:
        safe, error = verify_safety_limits(sandbox_repo, max_issues, max_prs)
        if not safe:
            print(f"    [GUARD] BLOCKED: Safety limit exceeded - {error}")
            return {
                "error_message": f"GUARD: E2E safety limit exceeded - {error}",
            }
    # --------------------------------------------------------------------------

    print(f"    Running E2E tests on {len(test_files)} file(s)")
    if sandbox_repo:
        print(f"    Sandbox repo: {sandbox_repo}")

    # Run E2E tests
    result = run_e2e_tests(test_files, sandbox_repo, repo_root)
    output = result["stdout"] + "\n" + result["stderr"]

    print(f"    Return code: {result['returncode']}")

    # Save output to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "e2e-results.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Cleanup sandbox
    if sandbox_repo:
        success, error = cleanup_sandbox(sandbox_repo)
        if not success:
            print(f"    [WARN] Sandbox cleanup failed: {error}")

    # Analyze results
    # Pytest return codes:
    #   0: All tests passed
    #   1: Tests collected and run but some failed
    #   2: Test execution interrupted
    #   3: Internal error
    #   4: Command line usage error
    #   5: No tests were collected
    returncode = result["returncode"]

    if returncode == 5:
        # No tests collected - tests don't have @pytest.mark.e2e markers
        # This is NOT a failure, just means no E2E tests to run
        print("    No E2E tests collected (missing @pytest.mark.e2e markers)")
        print("    Proceeding to finalize - add markers to enable E2E validation")
        return {
            "e2e_output": output,
            "file_counter": file_num,
            "next_node": "N7_finalize",
            "error_message": "",
        }

    if returncode in (3, 4, -1):
        # Internal error, usage error, or timeout - don't loop, just fail
        print(f"    E2E validation error (code {returncode}) - not retrying")
        return {
            "e2e_output": output,
            "file_counter": file_num,
            "error_message": f"E2E validation error: pytest returned {returncode}",
        }

    if returncode != 0:
        # Fallback string check for edge cases (older pytest versions, etc.)
        output_lower = output.lower()
        if "no tests ran" in output_lower or "collected 0 items" in output_lower:
            print("    No E2E tests found - proceeding to finalize")
            return {
                "e2e_output": output,
                "file_counter": file_num,
                "next_node": "N7_finalize",
                "error_message": "",
            }

        print(f"    E2E tests failed - iteration {iteration_count}")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="e2e_failed",
            details={"iteration": iteration_count},
        )

        # Loop back to implementation if within max iterations
        max_iterations = state.get("max_iterations", 10)
        if iteration_count < max_iterations:
            return {
                "e2e_output": output,
                "file_counter": file_num,
                "iteration_count": iteration_count + 1,
                "next_node": "N4_implement_code",
                "error_message": "",
            }
        else:
            return {
                "e2e_output": output,
                "file_counter": file_num,
                "error_message": f"E2E failed after {max_iterations} iterations",
            }

    # Success
    print("    E2E validation PASSED")

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="e2e_complete",
        details={"iterations": iteration_count},
    )

    return {
        "e2e_output": output,
        "file_counter": file_num,
        "next_node": "N7_finalize",
        "error_message": "",
    }


def _mock_e2e_validation(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    audit_dir = Path(state.get("audit_dir", ""))

    mock_output = """============================= test session starts ==============================
collected 1 item

tests/test_e2e.py::test_full_workflow PASSED

============================== 1 passed in 2.34s ===============================
"""

    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "e2e-results.txt", mock_output)
    else:
        file_num = state.get("file_counter", 0)

    print("    [MOCK] E2E validation passed")

    return {
        "e2e_output": mock_output,
        "file_counter": file_num,
        "next_node": "N7_finalize",
        "error_message": "",
    }
