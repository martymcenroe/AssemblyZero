"""N3 and N5: Verify Red/Green Phase nodes for TDD Testing Workflow.

N3 (verify_red_phase): Verify all tests fail before implementation
N5 (verify_green_phase): Verify all tests pass with coverage target

Issue #292: Added pytest exit code routing. Exit codes 4/5 (syntax/collection
errors) route back to N2_scaffold_tests instead of endlessly looping through
N4_implement_code. Exit codes 2/3 (interrupt/internal error) stop the workflow.
"""

from assemblyzero.utils.shell import run_command
import re
import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    parse_pytest_output,
    save_audit_file,
)
from assemblyzero.workflows.testing.circuit_breaker import check_circuit_breaker
from assemblyzero.workflows.testing.nodes.e2e_validation import _extract_failed_test_names
from assemblyzero.workflows.testing.exit_code_router import (
    EXIT_INTERRUPTED,
    EXIT_INTERNALERROR,
    EXIT_USAGEERROR,
    EXIT_NOTESTSCOLLECTED,
    describe_exit_code,
    route_by_exit_code,
)
from assemblyzero.workflows.testing.framework_detector import CoverageType, TestFramework
from assemblyzero.workflows.testing.runner_registry import get_runner
from assemblyzero.workflows.testing.state import TestingWorkflowState


# Timeout for pytest execution
PYTEST_TIMEOUT_SECONDS = 300

# Issue #498: Max chars for failure summary fed back to N4
MAX_FAILURE_SUMMARY_CHARS = 2000

# Issue #562: Critical skip keywords (aligned with tools/test-gate.py)
_CRITICAL_SKIP_KEYWORDS = ["security", "auth", "payment", "critical"]

# Regex for verbose pytest skip lines: "test_name SKIPPED"
_SKIP_PATTERN = re.compile(r"([\w/\\.\-]+::[\w\[\]\-]+)\s+SKIPPED")


def _validate_skip_audit(output: str) -> dict[str, Any]:
    """Post-run validation of skipped tests (Issue #562).

    Parses pytest verbose output for SKIPPED tests, checks for critical
    keywords. Returns audit info for state tracking and logging.

    Args:
        output: Combined stdout+stderr from pytest.

    Returns:
        Dict with skip_count, critical_count, critical_tests, gate_passed.
    """
    skipped_names = _SKIP_PATTERN.findall(output)
    if not skipped_names:
        return {
            "skip_count": 0,
            "critical_count": 0,
            "critical_tests": [],
            "gate_passed": True,
        }

    critical = []
    for name in skipped_names:
        name_lower = name.lower()
        if any(kw in name_lower for kw in _CRITICAL_SKIP_KEYWORDS):
            critical.append(name)

    return {
        "skip_count": len(skipped_names),
        "critical_count": len(critical),
        "critical_tests": critical,
        "gate_passed": len(critical) == 0,
    }


def _build_failure_summary(output: str) -> str:
    """Extract a concise failure summary from pytest output.

    Issue #498: Instead of feeding N4 the entire pytest output, extract
    only the "short test summary info" section which contains test names
    and one-line error messages. This tells N4 exactly what to fix.

    Args:
        output: Combined stdout + stderr from pytest.

    Returns:
        Concise failure summary, truncated to MAX_FAILURE_SUMMARY_CHARS.
        Empty string if no failures found.
    """
    import re

    lines = output.split("\n")
    summary_lines: list[str] = []

    # Extract "short test summary info" section
    in_summary = False
    for line in lines:
        if "short test summary info" in line:
            in_summary = True
            continue
        if in_summary:
            # Section ends at the next separator line (====)
            if line.startswith("=" * 10):
                # Capture the final summary (e.g., "2 failed, 1 passed in 0.15s")
                summary_lines.append(line.strip("= \n"))
                break
            if line.strip():
                summary_lines.append(line.strip())

    if not summary_lines:
        # Fallback: extract FAILED lines from anywhere in output
        for line in lines:
            if re.match(r"FAILED\s+", line):
                summary_lines.append(line.strip())

    if not summary_lines:
        return ""

    result = "\n".join(summary_lines)
    if len(result) > MAX_FAILURE_SUMMARY_CHARS:
        result = result[:MAX_FAILURE_SUMMARY_CHARS] + "\n... (truncated)"
    return result


def _path_to_cov_target(rel_path: str | Path, repo_root: Path | None) -> str:
    """Convert a relative file path to the correct --cov target.

    For Python packages (top-level dir has __init__.py), returns dotted
    module format (e.g., ``assemblyzero.utils.file_type``).
    For standalone scripts (no __init__.py, e.g., ``tools/``), returns
    the file path so pytest-cov measures the right file.
    """
    rel = Path(rel_path)
    top_level = rel.parts[0] if rel.parts else None
    is_package = (
        top_level
        and repo_root
        and (repo_root / top_level / "__init__.py").exists()
    )

    rel_str = str(rel)
    if rel_str.endswith(".py"):
        rel_str = rel_str[:-3]

    if is_package:
        module = rel_str.replace("/", ".").replace("\\", ".")
        # Issue #387: Strip src. prefix for src-layout projects
        if module.startswith("src."):
            module = module[4:]
        return module
    else:
        # Return as a file path — pytest-cov accepts paths for non-package code
        return str(rel).replace("\\", "/")


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

    # Issue #789: Only add --cov flags if pytest-cov is installed.
    # Without it, pytest returns exit code 4 ("unrecognized arguments")
    # which the workflow misclassifies as "collection/syntax error" and loops.
    if coverage_module:
        try:
            import pytest_cov  # noqa: F401
            cmd.extend([f"--cov={coverage_module}", "--cov-report=term-missing"])
            if coverage_target:
                cmd.append(f"--cov-fail-under={coverage_target}")
        except ImportError:
            print("    [WARN] pytest-cov not installed — skipping coverage measurement")

    try:
        result = run_command(
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
    gate_log("[N3] Verifying red phase (all tests should fail)...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_verify_red_phase(state)

    # Issue #381: Framework-aware red phase
    framework_config = state.get("framework_config")
    if framework_config:
        fw_enum = _resolve_framework_enum(framework_config)
        if fw_enum and fw_enum != TestFramework.PYTEST:
            return _verify_red_non_pytest(state, framework_config, fw_enum)

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
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    if audit_dir and audit_dir.exists():
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
    gate_log("[N5] Verifying green phase (all tests should pass)...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_verify_green_phase(state)

    # Issue #381: Framework-aware green phase
    framework_config = state.get("framework_config")
    if framework_config:
        fw_enum = _resolve_framework_enum(framework_config)
        if fw_enum and fw_enum != TestFramework.PYTEST:
            return _verify_green_non_pytest(state, framework_config, fw_enum)

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

    if impl_files:
        # Find first non-test, non-init, Python implementation file for coverage
        for impl_path in impl_files:
            # Skip test files (in tests/ directory)
            path_parts = Path(impl_path).parts
            if any(part.lower() in ("tests", "test") for part in path_parts):
                continue
            # Issue #265: Skip __init__.py - pytest-cov doesn't work with it
            if impl_path.endswith("__init__.py"):
                continue
            # Skip non-Python files (.gitkeep, .json, .yml, etc.)
            if not impl_path.endswith(".py"):
                print(f"    [N5] Skipping non-Python file for coverage: {impl_path}")
                continue
            rel_path = Path(impl_path).relative_to(repo_root) if repo_root else Path(impl_path)
            # Issue #474: Use helper that handles both packages and standalone scripts
            coverage_module = _path_to_cov_target(rel_path, repo_root)
            break

    # Issue #462: When all impl files are test files (test-only issues),
    # fall back to files_to_modify from LLD to find the source module
    if not coverage_module:
        files_to_modify = state.get("files_to_modify", [])
        for file_info in files_to_modify:
            fpath = file_info.get("path", "")
            if "test" in fpath.lower():
                continue
            if fpath.endswith("__init__.py"):
                continue
            if not fpath.endswith(".py"):
                continue
            # Issue #474: Use helper that handles both packages and standalone scripts
            coverage_module = _path_to_cov_target(fpath, repo_root)
            print(f"    [N5] Derived coverage module from LLD files_to_modify: {coverage_module}")
            break

    # Issue #462 fallback 2: reverse-map test file name to source module
    # e.g., tests/unit/test_circuit_breaker.py → find circuit_breaker.py in repo
    if not coverage_module and test_files:
        for tf in test_files:
            tf_name = Path(tf).name  # e.g., test_circuit_breaker.py
            if tf_name.startswith("test_"):
                src_name = tf_name[5:]  # e.g., circuit_breaker.py
                # Search for matching source file in repo
                matches = list(repo_root.rglob(src_name)) if repo_root else []
                # Filter to .py files not in tests/ directories
                for match in matches:
                    match_parts = match.relative_to(repo_root).parts
                    if any(p.lower() in ("tests", "test") for p in match_parts):
                        continue
                    # Issue #474: Use helper that handles both packages and standalone scripts
                    rel_path = match.relative_to(repo_root)
                    coverage_module = _path_to_cov_target(rel_path, repo_root)
                    print(f"    [N5] Derived coverage module from test filename: {coverage_module}")
                    break
                if coverage_module:
                    break

    # Issue #474: Last resort — infer from any available file paths before
    # falling back to a hardcoded default.  Previous versions always fell
    # back to "assemblyzero", which measured 0% for tools/ targets.
    if not coverage_module:
        # Try ALL files (including non-.py) to at least get the right directory
        all_candidate_paths = [
            p for p in impl_files
            if not any(part.lower() in ("tests", "test") for part in Path(p).parts)
        ]
        if not all_candidate_paths:
            all_candidate_paths = [
                fi.get("path", "")
                for fi in state.get("files_to_modify", [])
                if fi.get("path") and "test" not in fi["path"].lower()
            ]
        if all_candidate_paths:
            rel = Path(all_candidate_paths[0])
            if repo_root:
                try:
                    rel = rel.relative_to(repo_root)
                except ValueError:
                    pass
            # Use the top-level directory as coverage scope
            coverage_module = str(rel.parts[0]).replace("\\", "/") if rel.parts else "assemblyzero"
            print(f"    [N5] Fallback: inferred coverage scope from file paths: {coverage_module}")
        else:
            coverage_module = "assemblyzero"
            print(f"    [N5] Fallback: no file paths available, defaulting to: {coverage_module}")

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

    print(f"    [N5] Results: {parsed.get('passed', 0)} passed, {parsed.get('failed', 0)} failed | "
          f"Coverage: {parsed.get('coverage', 0):.1f}% | Exit: {exit_code} ({describe_exit_code(exit_code)})")

    # Save output to audit trail
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    if audit_dir and audit_dir.exists():
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

    # Stagnation detection: coverage must improve by >=1% each iteration
    previous_coverage = state.get("previous_coverage", -1.0)
    max_iterations = state.get("max_iterations", 5)

    # Issue #498: Build concise failure summary for N4 feedback
    failure_summary = _build_failure_summary(output)

    # Issue #501: Extract failed test names for identity-based stagnation
    current_green_failures = _extract_failed_test_names(output)

    # Check for failures
    if failed_count > 0 or error_count > 0:
        # Check if we've exhausted iterations
        if iteration_count + 1 >= max_iterations:
            print(f"    [ERROR] Max iterations ({max_iterations}) reached with {failed_count} failures")
            error_msg = f"Green phase failed after {max_iterations} iterations: {failed_count} tests still failing"
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": error_msg,
            }

        # Stagnation check: if passed count unchanged from previous iteration, halt.
        # Catches 0/N->0/N loops (e.g., circular imports, total import failures).
        previous_passed = state.get("previous_passed", -1)
        if previous_passed >= 0 and passed_count == previous_passed:
            stagnant_msg = (
                f"Test count stagnant: {passed_count}/{passed_count + failed_count} passed "
                f"(unchanged from previous iteration). Halting to prevent token waste."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Issue #501: Identity-based stagnation — same tests failing across iterations.
        # Catches cases where pass count fluctuates but the SAME tests keep failing.
        previous_green_failures = state.get("previous_green_failures", [])
        identity_stagnant = (
            bool(current_green_failures)
            and bool(previous_green_failures)
            and current_green_failures == sorted(previous_green_failures)
        )
        if identity_stagnant:
            stagnant_msg = (
                f"Test identity stagnant: same {len(current_green_failures)} test(s) failing "
                f"across iterations. Halting to prevent token waste."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Stagnation check: if coverage didn't improve by at least 1%, halt.
        # Skip when passed_count == 0: coverage is vacuously 100% with no passing
        # tests, so the metric is meaningless. The test-count check above handles that case.
        if passed_count > 0 and previous_coverage >= 0 and coverage_achieved <= previous_coverage + 1.0:
            stagnant_msg = (
                f"Coverage stagnant: {previous_coverage:.1f}% -> {coverage_achieved:.1f}% "
                f"(< 1% improvement). Halting to prevent token waste."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Circuit breaker check before looping
        should_trip, trip_reason = check_circuit_breaker(state)
        if should_trip:
            print(f"    {trip_reason}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": trip_reason,
            }

        print(f"    [N5] Iteration {iteration_count + 1}/{max_iterations} | "
              f"Tests: {passed_count}/{passed_count + failed_count} passed | "
              f"Coverage: {coverage_achieved:.1f}% (was {previous_coverage:.1f}%) | "
              f"Target: {coverage_target}%")

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

        # Loop back to implementation with failure feedback
        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed_count,
            "previous_green_failures": current_green_failures,
            "test_failure_summary": failure_summary,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
        }

    # Check coverage
    if coverage_achieved < coverage_target:
        # Check if we've exhausted iterations
        if iteration_count + 1 >= max_iterations:
            print(f"    [ERROR] Max iterations ({max_iterations}) reached with {coverage_achieved:.1f}% coverage")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": f"Green phase failed after {max_iterations} iterations: coverage {coverage_achieved:.1f}% < target {coverage_target}%",
            }

        # Stagnation check: if coverage didn't improve by at least 1%, halt
        if previous_coverage >= 0 and coverage_achieved <= previous_coverage + 1.0:
            stagnant_msg = (
                f"Coverage stagnant: {previous_coverage:.1f}% -> {coverage_achieved:.1f}% "
                f"(< 1% improvement). Halting to prevent token waste."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Circuit breaker check before looping
        should_trip, trip_reason = check_circuit_breaker(state)
        if should_trip:
            print(f"    {trip_reason}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": trip_reason,
            }

        print(f"    [N5] Iteration {iteration_count + 1}/{max_iterations} | "
              f"Tests: {passed_count}/{passed_count + failed_count} passed | "
              f"Coverage: {coverage_achieved:.1f}% (was {previous_coverage:.1f}%) | "
              f"Target: {coverage_target}%")

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
            "previous_coverage": coverage_achieved,
            "previous_passed": passed_count,
            "previous_green_failures": current_green_failures,
            "test_failure_summary": failure_summary,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
        }

    # Success: all tests pass and coverage meets target
    print(f"    [N5] Green phase PASSED: {passed_count} tests, {coverage_achieved:.1f}% coverage")

    # --------------------------------------------------------------------------
    # Issue #562: Skip audit gate — validate skipped tests post-run
    # --------------------------------------------------------------------------
    skipped_count = parsed.get("skipped", 0)
    skip_audit = _validate_skip_audit(output)
    if skip_audit["skip_count"] > 0:
        if skip_audit["critical_count"] > 0:
            print(f"    [SKIP-GATE] WARNING: {skip_audit['critical_count']} critical skipped test(s): "
                  f"{', '.join(skip_audit['critical_tests'])}")
        else:
            print(f"    [SKIP-GATE] {skip_audit['skip_count']} skipped test(s) (none critical)")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="skip_audit",
            details={
                "skip_count": skip_audit["skip_count"],
                "critical_count": skip_audit["critical_count"],
                "critical_tests": skip_audit["critical_tests"],
                "gate_passed": skip_audit["gate_passed"],
            },
        )
    # --------------------------------------------------------------------------

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="green_phase_complete",
        details={
            "passed": passed_count,
            "coverage": coverage_achieved,
            "iterations": iteration_count,
            "skipped": skipped_count,
        },
    )

    # Check if E2E should be skipped
    if state.get("skip_e2e"):
        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed_count,
            "previous_green_failures": [],
            "test_failure_summary": "",
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "skip_audit": skip_audit,
            "next_node": "N7_finalize",  # Skip E2E
            "error_message": "",
        }

    return {
        "green_phase_output": output,
        "coverage_achieved": coverage_achieved,
        "previous_coverage": coverage_achieved,
        "previous_passed": passed_count,
        "previous_green_failures": [],
        "test_failure_summary": "",
        "file_counter": file_num,
        "pytest_exit_code": exit_code,
        "skip_audit": skip_audit,
        "next_node": "N6_e2e_validation",
        "error_message": "",
    }


def _resolve_framework_enum(framework_config: dict) -> TestFramework | None:
    """Extract TestFramework enum from framework_config dict.

    The framework field may be a TestFramework enum or its string value
    (after serialization through LangGraph state).
    """
    fw = framework_config.get("framework")
    if isinstance(fw, TestFramework):
        return fw
    if isinstance(fw, str):
        try:
            return TestFramework(fw)
        except ValueError:
            return None
    return None


def _verify_red_non_pytest(
    state: TestingWorkflowState,
    framework_config: dict,
    framework: TestFramework,
) -> dict[str, Any]:
    """Red phase verification for non-pytest frameworks (Playwright/Jest/Vitest).

    Issue #381: Uses the runner registry to execute tests. In red phase,
    ALL tests should fail (none should pass).
    """
    test_files = state.get("test_files", [])
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    if not test_files:
        print("    [GUARD] BLOCKED: No test files to run")
        return {"error_message": "GUARD: No test files generated"}

    print(f"    Running {framework.value} on {len(test_files)} test file(s)...")

    try:
        runner = get_runner(framework, str(repo_root))
    except (ValueError, EnvironmentError) as e:
        return {"error_message": f"Runner unavailable for {framework.value}: {e}"}

    result = runner.run_tests(test_paths=test_files)

    output = result["raw_output"]
    passed = result["passed"]
    failed = result["failed"]
    errors = result["errors"]
    exit_code = result["exit_code"]

    print(f"    Results: {passed} passed, {failed} failed, {errors} errors")
    print(f"    Exit code: {exit_code}")

    # Save output to audit trail
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "red-phase.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Red phase: ALL tests must fail
    if passed > 0:
        print(f"    [GUARD] WARNING: {passed} tests passed unexpectedly!")
        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "test_run_result": dict(result),
            "error_message": f"Red phase failed: {passed} tests passed unexpectedly.",
            "next_node": "END",
        }

    total_red = failed + errors
    if total_red == 0:
        print("    [GUARD] WARNING: No tests ran!")
        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "test_run_result": dict(result),
            "error_message": "Red phase failed: No tests were collected/run",
            "next_node": "END",
        }

    print(f"    Red phase PASSED: {total_red} tests failed as expected ({framework.value})")

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="red_phase_complete",
        details={
            "failed": failed,
            "errors": errors,
            "exit_code": exit_code,
            "framework": framework.value,
        },
    )

    return {
        "red_phase_output": output,
        "file_counter": file_num,
        "test_run_result": dict(result),
        "next_node": "N4_implement_code",
        "error_message": "",
    }


def _verify_green_non_pytest(
    state: TestingWorkflowState,
    framework_config: dict,
    framework: TestFramework,
) -> dict[str, Any]:
    """Green phase verification for non-pytest frameworks (Playwright/Jest/Vitest).

    Issue #381: Uses the runner registry to execute tests. Handles both
    line-based coverage (Jest/Vitest) and scenario-based coverage (Playwright).
    Preserves stagnation detection and circuit breaker logic.
    """
    test_files = state.get("test_files", [])
    coverage_target = state.get("coverage_target", 90)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 5)
    total_scenarios = state.get("total_scenarios", 0)

    print(f"    Running {framework.value} with coverage target: {coverage_target}%")

    try:
        runner = get_runner(framework, str(repo_root))
    except (ValueError, EnvironmentError) as e:
        return {"error_message": f"Runner unavailable for {framework.value}: {e}"}

    result = runner.run_tests(test_paths=test_files)

    output = result["raw_output"]
    passed = result["passed"]
    failed = result["failed"]
    errors = result["errors"]
    exit_code = result["exit_code"]

    # Compute coverage based on coverage_type
    coverage_type = framework_config.get("coverage_type")
    if isinstance(coverage_type, str):
        try:
            coverage_type = CoverageType(coverage_type)
        except ValueError:
            coverage_type = CoverageType.LINE

    if coverage_type == CoverageType.SCENARIO:
        # Playwright: coverage = passed / total_scenarios
        coverage_achieved = runner.compute_scenario_coverage(result, total_scenarios) * 100.0
    else:
        # Jest/Vitest: line coverage from runner output
        coverage_achieved = result.get("coverage_percent", 0.0)

    print(f"    [N5] Results: {passed} passed, {failed} failed | "
          f"Coverage: {coverage_achieved:.1f}% | Exit: {exit_code} ({framework.value})")

    # Save output to audit trail
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "green-phase.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Stagnation detection
    previous_coverage = state.get("previous_coverage", -1.0)
    previous_passed = state.get("previous_passed", -1)

    if failed > 0 or errors > 0:
        if iteration_count + 1 >= max_iterations:
            error_msg = (
                f"Green phase failed after {max_iterations} iterations: "
                f"{failed} tests still failing ({framework.value})"
            )
            print(f"    [ERROR] {error_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": error_msg,
            }

        # Stagnation: passed count unchanged
        if previous_passed >= 0 and passed == previous_passed:
            stagnant_msg = (
                f"Test count stagnant: {passed}/{passed + failed} passed "
                f"(unchanged from previous iteration). Halting."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Circuit breaker
        should_trip, trip_reason = check_circuit_breaker(state)
        if should_trip:
            print(f"    {trip_reason}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": trip_reason,
            }

        print(f"    [N5] Iteration {iteration_count + 1}/{max_iterations} | "
              f"Tests: {passed}/{passed + failed} passed | "
              f"Coverage: {coverage_achieved:.1f}% | Target: {coverage_target}%")

        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed,
            "file_counter": file_num,
            "test_run_result": dict(result),
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
        }

    # All tests pass — check coverage
    if coverage_achieved < coverage_target:
        if iteration_count + 1 >= max_iterations:
            error_msg = (
                f"Green phase failed after {max_iterations} iterations: "
                f"coverage {coverage_achieved:.1f}% < target {coverage_target}%"
            )
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": error_msg,
            }

        # Stagnation on coverage
        if previous_coverage >= 0 and coverage_achieved <= previous_coverage + 1.0:
            stagnant_msg = (
                f"Coverage stagnant: {previous_coverage:.1f}% -> {coverage_achieved:.1f}% "
                f"(< 1% improvement). Halting."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Circuit breaker
        should_trip, trip_reason = check_circuit_breaker(state)
        if should_trip:
            print(f"    {trip_reason}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": trip_reason,
            }

        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed,
            "file_counter": file_num,
            "test_run_result": dict(result),
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
        }

    # Success
    print(f"    [N5] Green phase PASSED: {passed} tests, "
          f"{coverage_achieved:.1f}% coverage ({framework.value})")

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="green_phase_complete",
        details={
            "passed": passed,
            "coverage": coverage_achieved,
            "iterations": iteration_count,
            "framework": framework.value,
        },
    )

    if state.get("skip_e2e"):
        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed,
            "file_counter": file_num,
            "test_run_result": dict(result),
            "next_node": "N7_finalize",
            "error_message": "",
        }

    return {
        "green_phase_output": output,
        "coverage_achieved": coverage_achieved,
        "previous_coverage": coverage_achieved,
        "previous_passed": passed,
        "file_counter": file_num,
        "test_run_result": dict(result),
        "next_node": "N6_e2e_validation",
        "error_message": "",
    }


def _mock_verify_red_phase(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None

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

    if audit_dir and audit_dir.exists():
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
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
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

    if audit_dir and audit_dir.exists():
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
