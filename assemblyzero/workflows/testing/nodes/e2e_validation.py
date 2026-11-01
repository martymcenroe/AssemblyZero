"""N6: E2E Validation node for TDD Testing Workflow.

Runs E2E tests in a sandbox environment:
- Uses dedicated sandbox repos (mcwiz/assemblyzero-e2e-tools, mcwiz/assemblyzero-e2e-target)
- Has safety limits (max 5 issues, max 3 PRs per run)
- Auto-cleanup after each E2E run

#3585 (ADR 0236): every failure here halts with its cause, through
`_halt_e2e_error` or the node's own returns, which `route_after_e2e` sends to
HALT, which alerts. The sandbox safety check and cleanup are not implemented,
and say so by raising rather than reporting "safe" and "cleaned", so a run
pointed at a sandbox stops before any test runs.
"""

from assemblyzero.core.gate_registry import advised
from assemblyzero.utils.shell import run_command
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from assemblyzero.workflows.target_env import (
    TargetEnvironmentError,
    hook_environment,
    require_pytest,
)
from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.circuit_breaker import check_circuit_breaker
from assemblyzero.workflows.testing.state import TestingWorkflowState


# Safety limits for E2E testing
DEFAULT_E2E_MAX_ISSUES = 5
DEFAULT_E2E_MAX_PRS = 3
DEFAULT_E2E_MAX_ITERATIONS = 5
E2E_TIMEOUT_SECONDS = 600  # 10 minutes


class E2ERunFailed(RuntimeError):
    """The E2E pytest run did not complete: it timed out, or could not start."""


def _halt_e2e_error(reason: str) -> dict[str, Any]:
    """N6's halt for an E2E run that could not be made or judged (#3585).

    Said at ERROR on stderr; routed to HALT by `route_after_e2e`, which alerts.
    """
    print(f"ERROR [N6] E2E validation error: {reason}", file=sys.stderr)
    return {"error_message": f"E2E validation error: {reason}"}


#: How much of pytest's output an error message carries (#3585).
_OUTPUT_TAIL_CHARS = 1500


def _tail(output: str) -> str:
    text = output.strip()
    return text if len(text) <= _OUTPUT_TAIL_CHARS else "..." + text[-_OUTPUT_TAIL_CHARS:]


def _e2e_files(test_files: list[str], repo_root: Path) -> list[str]:
    """The run's test files that are E2E or integration files by name.

    Judged on the path inside the repository (#3585). The whole absolute path
    used to be searched, so a checkout whose own directory name held "e2e" or
    "integration" made every test file an E2E file; with N6 now halting when
    E2E files collect nothing, that would stop every run in such a checkout.
    A file outside the repository is judged by its name alone.
    """
    root = Path(repo_root)
    named: list[str] = []
    for f in test_files:
        path = Path(f)
        if not path.is_absolute():
            inside = path
        elif path.is_relative_to(root):
            inside = path.relative_to(root)
        else:
            inside = Path(path.name)
        text = inside.as_posix().lower()
        if "e2e" in text or "integration" in text:
            named.append(f)
    return named


def _parse_e2e_passed(output: str) -> int:
    """Parse passed test count from pytest output.

    0 when no count is printed: the count feeds the advisory stagnation line
    only, never a verdict, so an unparseable count is a quiet answer.

    Args:
        output: Combined stdout + stderr from pytest.

    Returns:
        Number of passed tests, or 0 if not parseable.
    """
    # Match patterns like "3 passed", "1 passed, 2 failed"
    match = re.search(r"(\d+)\s+passed", output)
    return int(match.group(1)) if match else 0


def _extract_failed_test_names(output: str) -> list[str]:
    """Extract failed test names from pytest output.

    Issue #504: Parse FAILED lines from pytest summary to get test identities.

    Args:
        output: Combined stdout + stderr from pytest.

    Returns:
        Sorted list of failed test names (e.g., ["test_a", "test_b"]).
    """
    # Match patterns like "FAILED tests/test_foo.py::test_bar - AssertionError"
    # or "FAILED tests/test_foo.py::TestClass::test_bar"
    #
    # #2345: anchored to line start. run_pytest passes -v, so pytest reports
    # each failure TWICE in different shapes:
    #
    #   tests/test_x.py::test_a FAILED                              [ 96%]
    #   FAILED tests/test_x.py::test_a - pathlib.UnsupportedOperation
    #
    # The unanchored pattern matched both, and on the progress line the token
    # after FAILED is the progress bracket -- so one real failure was counted
    # as two, one of them named "[". run-issue7-231606 printed "1 failed" and
    # "same 2 test(s) failing again" in adjacent lines from that.
    #
    # The `::` requirement is the second guard: a captured token that is not a
    # test id is not a test, whatever produced it.
    failures = re.findall(r"^FAILED\s+(\S+)", output, re.MULTILINE)
    return sorted({f for f in failures if "::" in f})


# Issue #498: Max chars for E2E failure summary
MAX_E2E_FAILURE_SUMMARY_CHARS = 2000


def _build_e2e_failure_summary(output: str) -> str:
    """Extract a concise failure summary from E2E pytest output.

    Issue #498: Mirrors _build_failure_summary from verify_phases.py
    but for E2E test output. Feeds N4 targeted error context.

    Args:
        output: Combined stdout + stderr from E2E pytest run.

    Returns:
        Concise failure summary, truncated to MAX_E2E_FAILURE_SUMMARY_CHARS.
        Empty string if no failures found.
    """
    lines = output.split("\n")
    summary_lines: list[str] = []

    # Extract "short test summary info" section
    in_summary = False
    for line in lines:
        if "short test summary info" in line:
            in_summary = True
            continue
        if in_summary:
            if line.startswith("=" * 10):
                summary_lines.append(line.strip("= \n"))
                break
            if line.strip():
                summary_lines.append(line.strip())

    if not summary_lines:
        # Fallback: extract FAILED lines from anywhere
        for line in lines:
            if re.match(r"FAILED\s+", line):
                summary_lines.append(line.strip())

    if not summary_lines:
        return ""

    result = "\n".join(summary_lines)
    if len(result) > MAX_E2E_FAILURE_SUMMARY_CHARS:
        result = result[:MAX_E2E_FAILURE_SUMMARY_CHARS] + "\n... (truncated)"
    return result


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

    Raises:
        E2ERunFailed: #3585 (ledger 0908, e2e_validation.py:182, :188) when
            the run times out or cannot start, naming the command, the
            ceiling or the cause. Both used to return code -1 with a fixed
            string, and the halt that followed said neither. Also when the
            target's own environment cannot run pytest (#4490).
    """
    try:
        require_pytest(repo_root)
    except TargetEnvironmentError as err:
        raise E2ERunFailed(f"the E2E run could not start: {err}") from err

    # Filter for E2E tests only
    e2e_files = _e2e_files(test_files, repo_root)

    if not e2e_files:
        # Run all tests if no specific E2E files
        e2e_files = test_files

    # #1904: through the target repo's env, matching verify_phases — bare
    # pytest ran in AssemblyZero's venv.
    cmd = [
        "poetry", "run", "pytest",
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
        result = run_command(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=E2E_TIMEOUT_SECONDS,
            cwd=str(repo_root),
            env={**hook_environment(), **env},
        )

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    except subprocess.TimeoutExpired as err:
        raise E2ERunFailed(
            f"the E2E run timed out after {E2E_TIMEOUT_SECONDS}s: "
            f"{' '.join(cmd)} (cwd {repo_root})"
        ) from err
    except FileNotFoundError as err:
        raise E2ERunFailed(
            f"the E2E run could not start: {err} ({' '.join(cmd)}, cwd {repo_root})"
        ) from err


def cleanup_sandbox(sandbox_repo: str) -> tuple[bool, str]:
    """Clean up sandbox repository after E2E tests.

    Cleanup would delete the test issues created in the sandbox, close the
    test PRs and reset the sandbox. None of it is implemented.

    #3585 (ledger 0908, e2e_validation.py:210): this stub returned success
    without doing anything. It raises instead, so nothing reads a sandbox as
    clean that was never touched.

    Args:
        sandbox_repo: Path to sandbox repository.

    Returns:
        Tuple of (success, error_message), once implemented.

    Raises:
        NotImplementedError: always, until the cleanup exists.
    """
    raise NotImplementedError(
        f"E2E sandbox cleanup of {sandbox_repo} is not implemented: nothing "
        f"deletes the test issues or closes the test PRs it would leave"
    )


def verify_safety_limits(
    sandbox_repo: str,
    max_issues: int,
    max_prs: int,
) -> tuple[bool, str]:
    """Verify sandbox is within safety limits.

    It would query GitHub for the sandbox's open issue and PR counts. That
    query is not implemented.

    #3585 (ledger 0908, e2e_validation.py:231): this stub reported "safe"
    without checking. It raises instead: a safety gate that cannot run is a
    gate that failed.

    Args:
        sandbox_repo: Path to sandbox repository.
        max_issues: Maximum allowed issues.
        max_prs: Maximum allowed PRs.

    Returns:
        Tuple of (safe, error_message), once implemented.

    Raises:
        NotImplementedError: always, until the check exists.
    """
    raise NotImplementedError(
        f"the E2E sandbox safety check for {sandbox_repo} is not implemented: "
        f"nothing counts its open issues (limit {max_issues}) or PRs "
        f"(limit {max_prs})"
    )


def e2e_validation(state: TestingWorkflowState) -> dict[str, Any]:
    """N6: Run E2E tests in sandbox environment.

    Args:
        state: Current workflow state.

    Returns:
        State updates with E2E results.
    """
    gate_log("[N6] Running E2E validation...")

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
    issue = state.get("issue_number", 0)

    # #3585 (ledger 0908, e2e_validation.py:291): the results are saved to the
    # audit dir, and an unset one read as "." and wrote them into the working
    # directory, while a missing one skipped the save silently. Checked
    # before anything runs.
    audit_dir_str = state.get("audit_dir", "") or ""
    audit_dir = Path(audit_dir_str)
    if not audit_dir_str or not audit_dir.is_dir():
        return _halt_e2e_error(
            f"the audit directory {audit_dir_str!r} for issue #{issue} is not a "
            f"directory, so the E2E results would not be kept"
        )

    # --------------------------------------------------------------------------
    # GUARD: Verify safety limits before running E2E
    # --------------------------------------------------------------------------
    if sandbox_repo:
        try:
            safe, error = verify_safety_limits(sandbox_repo, max_issues, max_prs)
        except NotImplementedError as err:
            # #3585 (ledger 0908, e2e_validation.py:231)
            return _halt_e2e_error(
                f"{err}; issue #{issue} cannot run E2E against the sandbox"
            )
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
    try:
        result = run_e2e_tests(test_files, sandbox_repo, repo_root)
    except E2ERunFailed as err:
        # #3585 (ledger 0908, e2e_validation.py:182, :188)
        return _halt_e2e_error(f"{err}; issue #{issue}")
    output = result["stdout"] + "\n" + result["stderr"]

    print(f"    Return code: {result['returncode']}")

    # Save output to audit trail
    file_num = next_file_number(audit_dir)
    save_audit_file(audit_dir, file_num, "e2e-results.txt", output)

    # Cleanup sandbox
    if sandbox_repo:
        try:
            success, error = cleanup_sandbox(sandbox_repo)
        except NotImplementedError as err:
            # #3585 (ledger 0908, e2e_validation.py:210); unreachable while the
            # safety check above also raises.
            return _halt_e2e_error(f"{err}; issue #{issue}")
        if not success:
            # #3585 (ledger 0908, e2e_validation.py:300): it was a WARN.
            return _halt_e2e_error(
                f"sandbox cleanup of {sandbox_repo} failed for issue #{issue}: "
                f"{error}"
            )

    # Analyze results
    # Pytest return codes:
    #   0: All tests passed
    #   1: Tests collected and run but some failed
    #   2: Test execution interrupted
    #   3: Internal error
    #   4: Command line usage error
    #   5: No tests were collected
    returncode = result["returncode"]

    # Nothing collected. Exit 5, or the older pytest's wording on another code.
    output_lower = output.lower()
    if returncode == 5 or (
        returncode != 0
        and ("no tests ran" in output_lower or "collected 0 items" in output_lower)
    ):
        # #3585 (ledger 0908, e2e_validation.py:313, :337): E2E or
        # integration files that collect nothing marked e2e or integration
        # are a check that could not run, and halt. A run with no such file
        # and no marked test has nothing to validate, the way N4.5 treats a
        # target with no build hook; it goes on to finalize.
        named = _e2e_files(test_files, repo_root)
        if named:
            return _halt_e2e_error(
                f"pytest (exit {returncode}) collected no test marked e2e or "
                f"integration from the E2E/integration file(s) of issue "
                f"#{issue}: {', '.join(named)}. Mark their tests, or run with "
                f"--skip-e2e"
            )
        print(
            "    No E2E tests in this run: no E2E or integration test file, "
            "and no test marked e2e or integration -- nothing to validate"
        )
        return {
            "e2e_output": output,
            "file_counter": file_num,
            "next_node": "N7_finalize",
            "error_message": "",
        }

    if returncode not in (0, 1):
        # #3585 (ledger 0908, e2e_validation.py:331, :334): only exit 1 is a
        # test failure. Exit 2 (interrupted) and any code pytest does not
        # document used to loop to N4 as failures; 3 and 4 halted without
        # the issue or the output.
        meaning = {
            2: "interrupted", 3: "internal error", 4: "usage error",
        }.get(returncode, "not a pytest exit code")
        print(
            f"ERROR [N6] E2E validation error: pytest exited {returncode} "
            f"({meaning}) for issue #{issue}",
            file=sys.stderr,
        )
        return {
            "e2e_output": output,
            "file_counter": file_num,
            "error_message": (
                f"E2E validation error: pytest exited {returncode} ({meaning}) "
                f"for issue #{issue}, which is not a test failure; output: "
                f"{_tail(output)}"
            ),
        }

    if returncode != 0:
        e2e_passed = _parse_e2e_passed(output)
        previous_e2e_passed = state.get("previous_e2e_passed", -1)
        current_failures = _extract_failed_test_names(output)
        previous_failures = state.get("previous_e2e_failures", [])

        # Issue #498: Build concise failure summary for N4 feedback
        e2e_failure_summary = _build_e2e_failure_summary(output)

        print(f"    E2E tests failed - iteration {iteration_count} | passed: {e2e_passed}")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="e2e_failed",
            details={"iteration": iteration_count, "passed": e2e_passed},
        )

        # E2E stagnation detection (Issue #504):
        # 1. Count-based: pass count didn't improve
        count_stagnant = previous_e2e_passed >= 0 and e2e_passed <= previous_e2e_passed
        # 2. Identity-based: same tests still failing even if count changed
        identity_stagnant = (
            bool(current_failures)
            and bool(previous_failures)
            and current_failures == sorted(previous_failures)
        )

        if count_stagnant or identity_stagnant:
            reason = "same failures persisting" if identity_stagnant else "no improvement"
            # #2723: advisory. The circuit breaker below and the e2e cap are
            # budgets and remain the only things that end this loop.
            print("    [STAGNANT] " + advised(
                "impl.stagnation.e2e",
                f"E2E stagnant: {previous_e2e_passed} -> {e2e_passed} passed "
                f"({reason}).",
            ))

        # Circuit breaker check before looping
        should_trip, trip_reason = check_circuit_breaker(state)
        if should_trip:
            print(f"    {trip_reason}")
            return {
                "e2e_output": output,
                "file_counter": file_num,
                "previous_e2e_passed": e2e_passed,
                "previous_e2e_failures": current_failures,
                "e2e_failure_summary": e2e_failure_summary,
                "error_message": trip_reason,
            }

        # Loop back to implementation if within max iterations
        max_iterations = state.get("max_iterations", DEFAULT_E2E_MAX_ITERATIONS)
        if iteration_count < max_iterations:
            return {
                "e2e_output": output,
                "file_counter": file_num,
                "previous_e2e_passed": e2e_passed,
                "previous_e2e_failures": current_failures,
                "e2e_failure_summary": e2e_failure_summary,
                "iteration_count": iteration_count + 1,
                "next_node": "N4_implement_code",
                "error_message": "",
            }
        else:
            return {
                "e2e_output": output,
                "file_counter": file_num,
                "previous_e2e_passed": e2e_passed,
                "previous_e2e_failures": current_failures,
                "e2e_failure_summary": e2e_failure_summary,
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
