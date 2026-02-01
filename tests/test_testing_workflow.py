"""Tests for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
"""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agentos.workflows.testing import TestingWorkflowState, build_testing_workflow
from agentos.workflows.testing.audit import (
    create_testing_audit_dir,
    next_file_number,
    parse_pytest_output,
    save_audit_file,
)
from agentos.workflows.testing.knowledge.patterns import (
    detect_test_types,
    get_mock_guidance,
    get_required_tools,
)
from agentos.workflows.testing.nodes.load_lld import (
    extract_coverage_target,
    extract_requirements,
    extract_test_plan_section,
    parse_test_scenarios,
)
from agentos.workflows.testing.nodes.scaffold_tests import (
    generate_test_file_content,
)
from agentos.workflows.testing.state import TestScenario


class TestAuditUtilities:
    """Tests for audit trail utilities."""

    def test_next_file_number_empty_dir(self, tmp_path):
        """next_file_number returns 1 for empty directory."""
        result = next_file_number(tmp_path)
        assert result == 1

    def test_next_file_number_with_files(self, tmp_path):
        """next_file_number returns max + 1."""
        (tmp_path / "001-test.md").write_text("test")
        (tmp_path / "002-test.md").write_text("test")
        (tmp_path / "003-test.md").write_text("test")

        result = next_file_number(tmp_path)
        assert result == 4

    def test_save_audit_file(self, tmp_path):
        """save_audit_file creates file with correct name."""
        path = save_audit_file(tmp_path, 5, "verdict.md", "content")

        assert path.exists()
        assert path.name == "005-verdict.md"
        assert path.read_text() == "content"

    def test_parse_pytest_output_passed(self):
        """parse_pytest_output extracts pass count."""
        output = "5 passed in 1.23s"
        result = parse_pytest_output(output)

        assert result["passed"] == 5
        assert result["failed"] == 0

    def test_parse_pytest_output_mixed(self):
        """parse_pytest_output extracts mixed results."""
        output = "3 passed, 2 failed, 1 error in 2.34s"
        result = parse_pytest_output(output)

        assert result["passed"] == 3
        assert result["failed"] == 2
        assert result["errors"] == 1

    def test_parse_pytest_output_coverage(self):
        """parse_pytest_output extracts coverage."""
        output = """
TOTAL                        100     15    85%
============================== 3 passed in 1.23s ===============================
"""
        result = parse_pytest_output(output)

        assert result["coverage"] == 85.0


class TestTestTypeDetection:
    """Tests for test type knowledge base."""

    def test_detect_unit_tests(self):
        """detect_test_types finds unit test patterns."""
        content = "This function validates input data."
        result = detect_test_types(content)

        assert "unit" in result

    def test_detect_integration_tests(self):
        """detect_test_types finds integration patterns."""
        content = "This integrates with the database API."
        result = detect_test_types(content)

        assert "integration" in result

    def test_detect_browser_tests(self):
        """detect_test_types finds browser patterns."""
        content = "The web UI has a button that triggers a form submission."
        result = detect_test_types(content)

        assert "browser" in result

    def test_detect_security_tests(self):
        """detect_test_types finds security patterns."""
        content = "Users must authenticate with a password token."
        result = detect_test_types(content)

        assert "security" in result

    def test_default_to_unit(self):
        """detect_test_types defaults to unit for unknown content."""
        content = "This does something."
        result = detect_test_types(content)

        assert "unit" in result

    def test_get_required_tools(self):
        """get_required_tools returns tools for types."""
        result = get_required_tools(["unit", "browser"])

        assert "pytest" in result
        assert "playwright" in result or "selenium" in result


class TestLLDExtraction:
    """Tests for LLD content extraction."""

    def test_extract_test_plan_section(self):
        """extract_test_plan_section finds Section 10."""
        lld = """# LLD

## 1. Context

Some context.

## 10. Test Plan

### test_login
Test the login flow.

### test_logout
Test the logout flow.

## 11. Appendix
"""
        result = extract_test_plan_section(lld)

        assert "test_login" in result
        assert "test_logout" in result
        assert "Appendix" not in result

    def test_extract_test_plan_section_missing(self):
        """extract_test_plan_section returns empty for missing section."""
        lld = "# LLD\n\n## 1. Context\n\nNo test plan here."
        result = extract_test_plan_section(lld)

        assert result == ""

    def test_extract_requirements(self):
        """extract_requirements finds requirement patterns."""
        lld = """
## 3. Requirements

1. Users must be able to log in
2. Passwords must be encrypted
3. Sessions must expire after 24 hours

### REQ-1.1: Login Requirement
Users need valid credentials.
"""
        result = extract_requirements(lld)

        assert len(result) >= 3
        assert any("REQ-1.1" in r for r in result)

    def test_extract_coverage_target_explicit(self):
        """extract_coverage_target finds explicit target."""
        lld = "Target coverage: 85%"
        result = extract_coverage_target(lld)

        assert result == 85

    def test_extract_coverage_target_default(self):
        """extract_coverage_target defaults to 95 (ADR 0207)."""
        lld = "No coverage mentioned."
        result = extract_coverage_target(lld)

        assert result == 95

    def test_parse_test_scenarios_headings(self):
        """parse_test_scenarios extracts from headings."""
        test_plan = """
### test_login_success
Verify that valid credentials result in successful login.
Requirement: REQ-1

### test_login_failure
Verify that invalid credentials return error.
Mock: authentication service
"""
        result = parse_test_scenarios(test_plan)

        assert len(result) == 2
        assert result[0]["name"] == "test_login_success"
        assert result[1]["name"] == "test_login_failure"
        assert result[1]["mock_needed"] is True


class TestTestScaffolding:
    """Tests for test file generation."""

    def test_generate_test_file_content_basic(self):
        """generate_test_file_content creates valid Python."""
        scenarios: list[TestScenario] = [
            {
                "name": "test_example",
                "description": "Test example functionality",
                "requirement_ref": "REQ-1",
                "test_type": "unit",
                "mock_needed": False,
                "assertions": ["returns true"],
            }
        ]

        content = generate_test_file_content(scenarios, "example", 42)

        assert "def test_example(" in content
        assert "assert False" in content
        assert "TDD: Implementation pending" in content
        assert "import pytest" in content

    def test_generate_test_file_content_with_mock(self):
        """generate_test_file_content includes mock fixture."""
        scenarios: list[TestScenario] = [
            {
                "name": "test_with_mock",
                "description": "Test with mocking",
                "requirement_ref": "REQ-1",
                "test_type": "unit",
                "mock_needed": True,
                "assertions": [],
            }
        ]

        content = generate_test_file_content(scenarios, "example", 42)

        assert "mock_external_service" in content
        assert "@pytest.fixture" in content

    def test_generate_test_file_content_multiple_types(self):
        """generate_test_file_content groups by type."""
        scenarios: list[TestScenario] = [
            {
                "name": "test_unit",
                "description": "Unit test",
                "requirement_ref": "REQ-1",
                "test_type": "unit",
                "mock_needed": False,
                "assertions": [],
            },
            {
                "name": "test_integration",
                "description": "Integration test",
                "requirement_ref": "REQ-2",
                "test_type": "integration",
                "mock_needed": False,
                "assertions": [],
            },
        ]

        content = generate_test_file_content(scenarios, "example", 42)

        assert "# Unit Tests" in content
        assert "# Integration Tests" in content


class TestWorkflowIntegration:
    """Integration tests for the full workflow."""

    def test_build_workflow_creates_graph(self):
        """build_testing_workflow creates valid graph."""
        workflow = build_testing_workflow()

        assert workflow is not None
        # Check nodes are registered
        nodes = workflow.nodes
        assert "N0_load_lld" in nodes
        assert "N1_review_test_plan" in nodes
        assert "N2_scaffold_tests" in nodes
        assert "N3_verify_red" in nodes
        assert "N4_implement_code" in nodes
        assert "N5_verify_green" in nodes
        assert "N6_e2e_validation" in nodes
        assert "N7_finalize" in nodes

    def test_workflow_mock_mode_completes(self, tmp_path):
        """Workflow completes in mock mode."""
        # Create minimal LLD file
        lld_dir = tmp_path / "docs" / "lld" / "active"
        lld_dir.mkdir(parents=True)

        lld_content = """# LLD-042: Mock Feature

## 1. Context
* **Status:** Approved (Gemini Review, 2026-01-30)

## 3. Requirements
1. REQ-1: User login
2. REQ-2: Input validation

## 10. Test Plan

### test_login
Verify login works.
Requirement: REQ-1

**Final Status:** APPROVED
"""
        (lld_dir / "LLD-042.md").write_text(lld_content)

        # Create tests directory
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        # Create lineage directory
        lineage_dir = tmp_path / "docs" / "lineage" / "active"
        lineage_dir.mkdir(parents=True)

        # Build workflow
        workflow = build_testing_workflow()
        app = workflow.compile()

        # Create initial state
        initial_state: TestingWorkflowState = {
            "issue_number": 42,
            "repo_root": str(tmp_path),
            "mock_mode": True,
            "skip_e2e": True,
            "auto_mode": True,
        }

        # Run workflow (without checkpointing for test)
        config = {"recursion_limit": 50}

        final_state = None
        for event in app.stream(initial_state, config):
            for node_name, output in event.items():
                if node_name != "__end__":
                    final_state = output

        # Verify workflow completed
        assert final_state is not None


class TestNodeFunctions:
    """Unit tests for individual node functions."""

    def test_load_lld_mock_mode(self, tmp_path):
        """load_lld works in mock mode."""
        from agentos.workflows.testing.nodes.load_lld import load_lld

        # Create lineage directory
        lineage_dir = tmp_path / "docs" / "lineage" / "active"
        lineage_dir.mkdir(parents=True)

        state: TestingWorkflowState = {
            "issue_number": 42,
            "repo_root": str(tmp_path),
            "mock_mode": True,
        }

        result = load_lld(state)

        assert result.get("error_message") == ""
        assert result.get("lld_content") is not None
        assert len(result.get("test_scenarios", [])) > 0

    def test_review_test_plan_mock_mode(self, tmp_path):
        """review_test_plan works in mock mode."""
        from agentos.workflows.testing.nodes.review_test_plan import review_test_plan

        # Create lineage directory
        lineage_dir = tmp_path / "docs" / "lineage" / "active" / "42-testing"
        lineage_dir.mkdir(parents=True)

        state: TestingWorkflowState = {
            "issue_number": 42,
            "repo_root": str(tmp_path),
            "mock_mode": True,
            "audit_dir": str(lineage_dir),
            "file_counter": 1,
            "iteration_count": 0,
            "test_scenarios": [
                {
                    "name": "test_example",
                    "description": "Test",
                    "requirement_ref": "REQ-1",
                    "test_type": "unit",
                    "mock_needed": False,
                    "assertions": [],
                }
            ],
            "requirements": ["REQ-1: Example"],
            "detected_test_types": ["unit"],
            "coverage_target": 90,
        }

        result = review_test_plan(state)

        # First iteration should be BLOCKED in mock mode
        assert result.get("test_plan_status") == "BLOCKED"

        # Second iteration should be APPROVED
        state["iteration_count"] = 2
        result = review_test_plan(state)
        assert result.get("test_plan_status") == "APPROVED"

    def test_scaffold_tests_creates_files(self, tmp_path):
        """scaffold_tests creates test files."""
        from agentos.workflows.testing.nodes.scaffold_tests import scaffold_tests

        # Create directories
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        lineage_dir = tmp_path / "docs" / "lineage" / "active" / "42-testing"
        lineage_dir.mkdir(parents=True)

        state: TestingWorkflowState = {
            "issue_number": 42,
            "repo_root": str(tmp_path),
            "mock_mode": False,
            "audit_dir": str(lineage_dir),
            "file_counter": 1,
            "test_scenarios": [
                {
                    "name": "test_example",
                    "description": "Test example",
                    "requirement_ref": "REQ-1",
                    "test_type": "unit",
                    "mock_needed": False,
                    "assertions": ["returns true"],
                }
            ],
        }

        result = scaffold_tests(state)

        assert result.get("error_message") == ""
        assert len(result.get("test_files", [])) > 0

        # Verify file was created
        test_file = Path(result["test_files"][0])
        assert test_file.exists()
        content = test_file.read_text()
        assert "def test_example" in content
        assert "assert False" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
