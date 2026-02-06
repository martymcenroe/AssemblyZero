"""Integration tests for smoke test node.

Reference: Issue #172, LLD docs/LLDs/active/172-smoke-test-node.md
"""

import sys
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
def test_workflow_integration_smoke_after_green(tmp_path):
    """test_workflow_integration_smoke_after_green | Smoke test runs after green phase | RED"""
    # TDD: Arrange
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    script = tools_dir / "run_test.py"
    script.write_text("import sys\nprint('--help')\nsys.exit(0)")
    
    state: SmokeTestState = {
        "smoke_test_enabled": True,
        "smoke_test_results": [],
        "smoke_test_passed": False,
        "project_root": tmp_path,
    }
    
    # TDD: Act
    # Verify conditional edge allows smoke test to run
    should_run = should_run_smoke_test(state)
    assert should_run is True
    
    # Run smoke test node
    result = integration_smoke_test(state)
    
    # TDD: Assert
    # Verify smoke test executed and passed
    assert result["smoke_test_passed"] is True
    assert len(result["smoke_test_results"]) == 1
    assert result["smoke_test_results"][0]["success"] is True


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