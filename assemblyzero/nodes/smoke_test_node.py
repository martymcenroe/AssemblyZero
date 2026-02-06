"""Smoke test node for LangGraph TDD workflow.

This module provides smoke testing functionality that runs after the GREEN phase
to catch integration breaks that unit tests with mocks might miss.

Ref: Issue #172, LLD: docs/LLDs/active/172-smoke-test-node.md
"""

import re
import subprocess
import time
from pathlib import Path
from typing import Optional, TypedDict

from langgraph.graph import StateGraph


class SmokeTestResult(TypedDict):
    """Result from running a single smoke test."""
    success: bool
    entry_point: str
    error_type: Optional[str]
    error_message: Optional[str]
    execution_time_ms: int


class SmokeTestState(TypedDict):
    """State for smoke test node in LangGraph."""
    smoke_test_enabled: bool
    smoke_test_results: list[SmokeTestResult]
    smoke_test_passed: bool
    project_root: Path


def discover_entry_points(project_root: Path) -> list[Path]:
    """Find all tools/run_*.py entry points in the project.
    
    Excludes __pycache__ and hidden directories (.*) from discovery.
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        List of absolute paths to entry point scripts
    """
    tools_dir = project_root / "tools"
    if not tools_dir.exists():
        return []
    
    entry_points = []
    for path in tools_dir.rglob("run_*.py"):
        # Exclude __pycache__ and hidden directories
        if "__pycache__" in path.parts:
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        entry_points.append(path)
    
    return sorted(entry_points)


def parse_import_error(stderr: str) -> tuple[Optional[str], Optional[str]]:
    """Extract error type and module from import error output.
    
    Args:
        stderr: Standard error output from the subprocess
        
    Returns:
        Tuple of (error_type, module_name) or (None, None) if not an import error
    """
    # Match ModuleNotFoundError: No module named 'foo'
    module_not_found = re.search(r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]", stderr)
    if module_not_found:
        return ("ModuleNotFoundError", module_not_found.group(1))
    
    # Match ImportError: cannot import name 'foo' from 'bar'
    import_error = re.search(r"ImportError: (.+)", stderr)
    if import_error:
        return ("ImportError", import_error.group(1))
    
    return (None, None)


def run_smoke_test(entry_point: Path, timeout_seconds: int = 30) -> SmokeTestResult:
    """Execute a single entry point with --help and capture results.
    
    Uses subprocess.run with shell=False to prevent shell injection.
    
    Args:
        entry_point: Path to the entry point script
        timeout_seconds: Maximum time to wait for the process
        
    Returns:
        SmokeTestResult with success/failure and error details
    """
    start_time = time.perf_counter()
    
    try:
        # Run with shell=False for security
        result = subprocess.run(
            ["python", str(entry_point), "--help"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
        
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        
        if result.returncode == 0:
            return SmokeTestResult(
                success=True,
                entry_point=str(entry_point),
                error_type=None,
                error_message=None,
                execution_time_ms=execution_time_ms,
            )
        else:
            error_type, error_detail = parse_import_error(result.stderr)
            return SmokeTestResult(
                success=False,
                entry_point=str(entry_point),
                error_type=error_type or "UnknownError",
                error_message=result.stderr.strip() or result.stdout.strip(),
                execution_time_ms=execution_time_ms,
            )
    
    except subprocess.TimeoutExpired:
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        return SmokeTestResult(
            success=False,
            entry_point=str(entry_point),
            error_type="TimeoutError",
            error_message=f"Process timed out after {timeout_seconds} seconds",
            execution_time_ms=execution_time_ms,
        )
    
    except Exception as e:
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        return SmokeTestResult(
            success=False,
            entry_point=str(entry_point),
            error_type=type(e).__name__,
            error_message=str(e),
            execution_time_ms=execution_time_ms,
        )


def integration_smoke_test(state: SmokeTestState) -> dict:
    """LangGraph node: Run smoke tests on all entry points after green phase.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with smoke test results
    """
    project_root = state.get("project_root")
    if not project_root:
        return {
            "smoke_test_passed": False,
            "smoke_test_results": [
                SmokeTestResult(
                    success=False,
                    entry_point="N/A",
                    error_type="ConfigurationError",
                    error_message="project_root not set in state",
                    execution_time_ms=0,
                )
            ],
        }
    
    entry_points = discover_entry_points(project_root)
    
    if not entry_points:
        # No entry points found - consider this a pass
        return {
            "smoke_test_passed": True,
            "smoke_test_results": [],
        }
    
    results = []
    for entry_point in entry_points:
        result = run_smoke_test(entry_point)
        results.append(result)
    
    all_passed = all(result["success"] for result in results)
    
    return {
        "smoke_test_passed": all_passed,
        "smoke_test_results": results,
    }


def should_run_smoke_test(state: SmokeTestState) -> bool:
    """Conditional edge: Determine if smoke test should run based on smoke_test_enabled flag.
    
    Args:
        state: Current workflow state
        
    Returns:
        True if smoke test should run, False to bypass
    """
    return state.get("smoke_test_enabled", True)