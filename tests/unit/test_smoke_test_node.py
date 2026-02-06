"""Unit tests for smoke test functionality.

Reference: Issue #172, LLD docs/LLDs/active/172-smoke-test-node.md
"""

import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.nodes.smoke_test_node import (
    SmokeTestResult,
    SmokeTestState,
    discover_entry_points,
    integration_smoke_test,
    parse_import_error,
    run_smoke_test,
    should_run_smoke_test,
)


# Unit Tests
# -----------

def test_discover_entry_points_finds_run_scripts(tmp_path):
    """test_discover_entry_points_finds_run_scripts | Returns list of tools/run_*.py paths | RED"""
    # TDD: Arrange
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "run_foo.py").touch()
    (tools_dir / "run_bar.py").touch()
    (tools_dir / "not_run.py").touch()
    
    # TDD: Act
    result = discover_entry_points(tmp_path)
    
    # TDD: Assert
    assert len(result) == 2
    assert all(p.name.startswith("run_") for p in result)
    assert all(p.suffix == ".py" for p in result)


def test_discover_entry_points_excludes_pycache(tmp_path):
    """test_discover_entry_points_excludes_pycache | Excludes __pycache__ directories | RED"""
    # TDD: Arrange
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "run_foo.py").touch()
    pycache_dir = tools_dir / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "run_cached.py").touch()
    
    # TDD: Act
    result = discover_entry_points(tmp_path)
    
    # TDD: Assert
    assert len(result) == 1
    assert "__pycache__" not in str(result[0])


def test_discover_entry_points_excludes_hidden_dirs(tmp_path):
    """test_discover_entry_points_excludes_hidden_dirs | Excludes hidden directories | RED"""
    # TDD: Arrange
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "run_foo.py").touch()
    hidden_dir = tools_dir / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "run_secret.py").touch()
    
    # TDD: Act
    result = discover_entry_points(tmp_path)
    
    # TDD: Assert
    assert len(result) == 1
    assert ".hidden" not in str(result[0])


def test_run_smoke_test_success(tmp_path):
    """test_run_smoke_test_success | Returns success=True for valid script | RED"""
    # TDD: Arrange
    script = tmp_path / "valid.py"
    script.write_text("import sys\nprint('--help')\nsys.exit(0)")
    
    # TDD: Act
    result = run_smoke_test(script, timeout_seconds=5)
    
    # TDD: Assert
    assert result["success"] is True
    assert result["error_type"] is None
    assert result["error_message"] is None
    assert result["execution_time_ms"] > 0


def test_run_smoke_test_import_error(tmp_path):
    """test_run_smoke_test_import_error | Returns success=False with error details for ImportError | RED"""
    # TDD: Arrange
    script = tmp_path / "broken.py"
    script.write_text("import nonexistent_module\nprint('--help')")
    
    # TDD: Act
    result = run_smoke_test(script, timeout_seconds=5)
    
    # TDD: Assert
    assert result["success"] is False
    assert result["error_type"] in ["ImportError", "ModuleNotFoundError"]
    assert result["error_message"] is not None
    assert "nonexistent_module" in result["error_message"]


def test_run_smoke_test_module_not_found(tmp_path):
    """test_run_smoke_test_module_not_found | Returns success=False with error details for ModuleNotFoundError | RED"""
    # TDD: Arrange
    script = tmp_path / "missing.py"
    script.write_text("from missing_package import foo\nprint('--help')")
    
    # TDD: Act
    result = run_smoke_test(script, timeout_seconds=5)
    
    # TDD: Assert
    assert result["success"] is False
    assert result["error_type"] in ["ImportError", "ModuleNotFoundError"]
    assert result["error_message"] is not None


def test_run_smoke_test_timeout(tmp_path):
    """test_run_smoke_test_timeout | Returns failure after timeout | RED"""
    # TDD: Arrange
    script = tmp_path / "slow.py"
    script.write_text("import time\ntime.sleep(60)\nprint('--help')")

    # TDD: Act
    result = run_smoke_test(script, timeout_seconds=1)

    # TDD: Assert
    assert result["success"] is False
    assert result["error_type"] == "TimeoutError"
    assert "timed out" in result["error_message"].lower()


def test_parse_import_error_extracts_module():
    """test_parse_import_error_extracts_module | Parses ModuleNotFoundError correctly | RED"""
    # TDD: Arrange
    stderr = "ModuleNotFoundError: No module named 'foo'"
    
    # TDD: Act
    error_type, module_name = parse_import_error(stderr)
    
    # TDD: Assert
    assert error_type == "ModuleNotFoundError"
    assert module_name == "foo"


def test_parse_import_error_extracts_import_error():
    """test_parse_import_error_extracts_import_error | Parses ImportError correctly | RED"""
    # TDD: Arrange
    stderr = "ImportError: cannot import name 'bar' from 'foo'"

    # TDD: Act
    error_type, error_detail = parse_import_error(stderr)

    # TDD: Assert
    assert error_type == "ImportError"
    assert "bar" in error_detail  # Error detail contains the full message


def test_parse_import_error_generic_import_error():
    """test_parse_import_error_generic_import_error | Handles generic ImportError | RED"""
    # TDD: Arrange
    stderr = "ImportError: something went wrong"

    # TDD: Act
    error_type, error_detail = parse_import_error(stderr)

    # TDD: Assert
    assert error_type == "ImportError"
    assert error_detail == "something went wrong"  # Captures error details


def test_parse_import_error_no_error():
    """test_parse_import_error_no_error | Returns None for non-import errors | RED"""
    # TDD: Arrange
    stderr = "SyntaxError: invalid syntax"
    
    # TDD: Act
    error_type, module_name = parse_import_error(stderr)
    
    # TDD: Assert
    assert error_type is None
    assert module_name is None


def test_smoke_test_skipped_when_disabled():
    """test_smoke_test_skipped_when_disabled | Smoke test skipped when smoke_test_enabled=False | RED"""
    # TDD: Arrange
    state: SmokeTestState = {
        "smoke_test_enabled": False,
        "smoke_test_results": [],
        "smoke_test_passed": True,
        "project_root": Path.cwd(),
    }
    
    # TDD: Act
    result = should_run_smoke_test(state)
    
    # TDD: Assert
    assert result is False


def test_should_run_smoke_test_enabled():
    """test_should_run_smoke_test_enabled | Returns True when smoke_test_enabled=True | RED"""
    # TDD: Arrange
    state: SmokeTestState = {
        "smoke_test_enabled": True,
        "smoke_test_results": [],
        "smoke_test_passed": True,
        "project_root": Path.cwd(),
    }
    
    # TDD: Act
    result = should_run_smoke_test(state)
    
    # TDD: Assert
    assert result is True


def test_should_run_smoke_test_default():
    """test_should_run_smoke_test_default | Defaults to True when flag not present | RED"""
    # TDD: Arrange
    state: SmokeTestState = {
        "smoke_test_results": [],
        "smoke_test_passed": True,
        "project_root": Path.cwd(),
    }
    
    # TDD: Act
    result = should_run_smoke_test(state)
    
    # TDD: Assert
    assert result is True


# Integration Tests
# -----------------

@pytest.mark.integration
def test_integration_smoke_test_all_pass(tmp_path):
    """test_integration_smoke_test_all_pass | Updates state with passed=True | RED"""
    # TDD: Arrange
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    script1 = tools_dir / "run_foo.py"
    script1.write_text("import sys\nprint('--help')\nsys.exit(0)")
    script2 = tools_dir / "run_bar.py"
    script2.write_text("import sys\nprint('--help')\nsys.exit(0)")
    
    state: SmokeTestState = {
        "smoke_test_enabled": True,
        "smoke_test_results": [],
        "smoke_test_passed": False,
        "project_root": tmp_path,
    }
    
    # TDD: Act
    result = integration_smoke_test(state)
    
    # TDD: Assert
    assert result["smoke_test_passed"] is True
    assert len(result["smoke_test_results"]) == 2
    assert all(r["success"] for r in result["smoke_test_results"])


@pytest.mark.integration
def test_integration_smoke_test_one_fails(tmp_path):
    """test_integration_smoke_test_one_fails | Updates state with passed=False | RED"""
    # TDD: Arrange
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    script1 = tools_dir / "run_foo.py"
    script1.write_text("import sys\nprint('--help')\nsys.exit(0)")
    script2 = tools_dir / "run_bar.py"
    script2.write_text("import nonexistent_module\nprint('--help')")
    
    state: SmokeTestState = {
        "smoke_test_enabled": True,
        "smoke_test_results": [],
        "smoke_test_passed": True,
        "project_root": tmp_path,
    }
    
    # TDD: Act
    result = integration_smoke_test(state)
    
    # TDD: Assert
    assert result["smoke_test_passed"] is False
    assert len(result["smoke_test_results"]) == 2
    assert any(not r["success"] for r in result["smoke_test_results"])


@pytest.mark.integration
def test_integration_smoke_test_no_entry_points(tmp_path):
    """test_integration_smoke_test_no_entry_points | Passes when no entry points found | RED"""
    # TDD: Arrange
    state: SmokeTestState = {
        "smoke_test_enabled": True,
        "smoke_test_results": [],
        "smoke_test_passed": False,
        "project_root": tmp_path,
    }
    
    # TDD: Act
    result = integration_smoke_test(state)
    
    # TDD: Assert
    assert result["smoke_test_passed"] is True
    assert len(result["smoke_test_results"]) == 0