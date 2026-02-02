"""Tests for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
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
from agentos.workflows.testing.nodes.review_test_plan import (
    check_requirement_coverage,
    extract_covered_requirements,
    extract_requirement_ids,
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


class TestMechanicalCoverageCheck:
    """Tests for mechanical requirement coverage check (ADR 0207)."""

    def test_extract_requirement_ids_standard(self):
        """extract_requirement_ids extracts REQ-X patterns."""
        requirements = [
            "REQ-1: User login",
            "REQ-2: Input validation",
            "REQ-3.1: Session management",
        ]
        result = extract_requirement_ids(requirements)

        assert result == {"REQ-1", "REQ-2", "REQ-3.1"}

    def test_extract_requirement_ids_numbered_list(self):
        """extract_requirement_ids handles numbered lists."""
        requirements = [
            "1. User login",
            "2. Input validation",
            "3. Session management",
        ]
        result = extract_requirement_ids(requirements)

        assert result == {"REQ-1", "REQ-2", "REQ-3"}

    def test_extract_requirement_ids_case_insensitive(self):
        """extract_requirement_ids normalizes to uppercase."""
        requirements = [
            "req-1: User login",
            "Req-2: Input validation",
        ]
        result = extract_requirement_ids(requirements)

        assert result == {"REQ-1", "REQ-2"}

    def test_extract_covered_requirements_standard(self):
        """extract_covered_requirements extracts from test scenarios."""
        scenarios = [
            {"name": "test_login", "requirement_ref": "REQ-1"},
            {"name": "test_validate", "requirement_ref": "REQ-2"},
        ]
        result = extract_covered_requirements(scenarios)

        assert result == {"REQ-1", "REQ-2"}

    def test_extract_covered_requirements_normalizes_case(self):
        """extract_covered_requirements normalizes case."""
        scenarios = [
            {"name": "test_a", "requirement_ref": "req-1"},
            {"name": "test_b", "requirement_ref": "Req-2"},
        ]
        result = extract_covered_requirements(scenarios)

        assert result == {"REQ-1", "REQ-2"}

    def test_extract_covered_requirements_handles_missing(self):
        """extract_covered_requirements handles missing refs."""
        scenarios = [
            {"name": "test_a", "requirement_ref": "REQ-1"},
            {"name": "test_b"},  # No requirement_ref
            {"name": "test_c", "requirement_ref": ""},  # Empty ref
        ]
        result = extract_covered_requirements(scenarios)

        assert result == {"REQ-1"}

    def test_check_requirement_coverage_full_coverage(self):
        """check_requirement_coverage returns passed=True for 100% coverage."""
        requirements = ["REQ-1: Login", "REQ-2: Validate"]
        scenarios = [
            {"name": "test_login", "requirement_ref": "REQ-1"},
            {"name": "test_validate", "requirement_ref": "REQ-2"},
        ]

        result = check_requirement_coverage(requirements, scenarios)

        assert result["passed"] is True
        assert result["total"] == 2
        assert result["covered"] == 2
        assert result["coverage_pct"] == 100.0
        assert result["missing"] == []

    def test_check_requirement_coverage_partial_coverage(self):
        """check_requirement_coverage returns passed=False for <100% coverage."""
        requirements = ["REQ-1: Login", "REQ-2: Validate", "REQ-3: Logout"]
        scenarios = [
            {"name": "test_login", "requirement_ref": "REQ-1"},
            {"name": "test_validate", "requirement_ref": "REQ-2"},
        ]

        result = check_requirement_coverage(requirements, scenarios)

        assert result["passed"] is False
        assert result["total"] == 3
        assert result["covered"] == 2
        assert result["coverage_pct"] == pytest.approx(66.67, rel=0.1)
        assert result["missing"] == ["REQ-3"]

    def test_check_requirement_coverage_no_scenarios(self):
        """check_requirement_coverage handles empty scenarios."""
        requirements = ["REQ-1: Login"]
        scenarios = []

        result = check_requirement_coverage(requirements, scenarios)

        assert result["passed"] is False
        assert result["total"] == 1
        assert result["covered"] == 0
        assert result["missing"] == ["REQ-1"]

    def test_check_requirement_coverage_no_requirements(self):
        """check_requirement_coverage handles empty requirements."""
        requirements = []
        scenarios = [{"name": "test_login", "requirement_ref": "REQ-1"}]

        result = check_requirement_coverage(requirements, scenarios)

        # No requirements = 0% coverage, not passed
        assert result["passed"] is False
        assert result["total"] == 0
        assert result["coverage_pct"] == 0.0

    def test_check_requirement_coverage_extra_tests(self):
        """check_requirement_coverage ignores tests for non-existent requirements."""
        requirements = ["REQ-1: Login"]
        scenarios = [
            {"name": "test_login", "requirement_ref": "REQ-1"},
            {"name": "test_extra", "requirement_ref": "REQ-99"},  # Not in requirements
        ]

        result = check_requirement_coverage(requirements, scenarios)

        assert result["passed"] is True
        assert result["total"] == 1
        assert result["covered"] == 1
        # REQ-99 is in covered_ids but not in all_ids, so not counted as missing


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
        assert "N8_document" in nodes

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

    def test_review_test_plan_mock_mode_full_coverage(self, tmp_path):
        """review_test_plan returns APPROVED with 100% coverage in mock mode."""
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

        # With 100% coverage, mock mode should APPROVE (mechanical check passes)
        assert result.get("test_plan_status") == "APPROVED"
        assert result.get("error_message") == ""

    def test_review_test_plan_mock_mode_partial_coverage(self, tmp_path):
        """review_test_plan returns BLOCKED with <100% coverage in mock mode."""
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
            # Two requirements but only one test - 50% coverage
            "requirements": ["REQ-1: Example", "REQ-2: Missing test"],
            "detected_test_types": ["unit"],
            "coverage_target": 90,
        }

        result = review_test_plan(state)

        # With <100% coverage, mock mode should BLOCK (mechanical check fails)
        assert result.get("test_plan_status") == "BLOCKED"
        assert "REQ-2" in result.get("gemini_feedback", "")

    def test_review_test_plan_auto_mode_skips_review(self, tmp_path):
        """review_test_plan auto-approves in auto mode without calling Gemini."""
        from agentos.workflows.testing.nodes.review_test_plan import review_test_plan

        # Create lineage directory
        lineage_dir = tmp_path / "docs" / "lineage" / "active" / "42-testing"
        lineage_dir.mkdir(parents=True)

        state: TestingWorkflowState = {
            "issue_number": 42,
            "repo_root": str(tmp_path),
            "auto_mode": True,  # Auto mode - should skip review
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

        # Auto mode should always APPROVE without calling Gemini
        assert result.get("test_plan_status") == "APPROVED"
        assert "AUTO" in result.get("test_plan_verdict", "")

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


class TestDocumentNode:
    """Tests for N8 document node."""

    def test_detect_doc_scope_explicit_full(self):
        """detect_doc_scope returns full for explicit marker."""
        from agentos.workflows.testing.nodes.document import detect_doc_scope

        lld = "<!-- doc-scope: full -->\nSome content"
        assert detect_doc_scope(lld) == "full"

    def test_detect_doc_scope_explicit_none(self):
        """detect_doc_scope returns none for explicit marker."""
        from agentos.workflows.testing.nodes.document import detect_doc_scope

        lld = "<!-- doc-scope: none -->\nSome content"
        assert detect_doc_scope(lld) == "none"

    def test_detect_doc_scope_bugfix(self):
        """detect_doc_scope returns minimal for bugfix."""
        from agentos.workflows.testing.nodes.document import detect_doc_scope

        lld = "This is a bugfix for issue #123"
        assert detect_doc_scope(lld) == "minimal"

    def test_detect_doc_scope_new_feature(self):
        """detect_doc_scope returns full for new feature."""
        from agentos.workflows.testing.nodes.document import detect_doc_scope

        lld = "Implement new feature for workflow management"
        assert detect_doc_scope(lld) == "full"

    def test_detect_doc_scope_workflow(self):
        """detect_doc_scope returns full for workflow."""
        from agentos.workflows.testing.nodes.document import detect_doc_scope

        lld = "This workflow handles state machine transitions"
        assert detect_doc_scope(lld) == "full"

    def test_should_generate_wiki_feature(self):
        """should_generate_wiki returns True for feature with architecture."""
        from agentos.workflows.testing.nodes.document import should_generate_wiki

        state: TestingWorkflowState = {
            "lld_content": "This new feature includes architecture changes",
        }
        assert should_generate_wiki(state) is True

    def test_should_generate_wiki_bugfix(self):
        """should_generate_wiki returns False for bugfix."""
        from agentos.workflows.testing.nodes.document import should_generate_wiki

        state: TestingWorkflowState = {
            "lld_content": "This is a bugfix for an edge case",
        }
        assert should_generate_wiki(state) is False

    def test_is_operational_feature_workflow(self):
        """is_operational_feature returns True for workflow."""
        from agentos.workflows.testing.nodes.document import is_operational_feature

        state: TestingWorkflowState = {
            "lld_content": "This workflow manages state transitions",
            "implementation_files": ["agentos/workflows/test/graph.py"],
        }
        assert is_operational_feature(state) is True

    def test_is_operational_feature_cli_tool(self):
        """is_operational_feature returns True for CLI tool."""
        from agentos.workflows.testing.nodes.document import is_operational_feature

        state: TestingWorkflowState = {
            "lld_content": "Some content",
            "implementation_files": ["tools/run_feature.py"],
        }
        assert is_operational_feature(state) is True

    def test_is_cli_tool_tools_dir(self):
        """is_cli_tool returns True for tools/ directory."""
        from agentos.workflows.testing.nodes.document import is_cli_tool

        state: TestingWorkflowState = {
            "implementation_files": ["tools/new_tool.py"],
        }
        assert is_cli_tool(state) is True

    def test_is_cli_tool_cli_file(self):
        """is_cli_tool returns True for cli in filename."""
        from agentos.workflows.testing.nodes.document import is_cli_tool

        state: TestingWorkflowState = {
            "implementation_files": ["src/feature_cli.py"],
        }
        assert is_cli_tool(state) is True

    def test_is_cli_tool_not_cli(self):
        """is_cli_tool returns False for non-CLI file."""
        from agentos.workflows.testing.nodes.document import is_cli_tool

        state: TestingWorkflowState = {
            "implementation_files": ["src/feature.py", "tests/test_feature.py"],
        }
        assert is_cli_tool(state) is False

    def test_extract_feature_name_from_title(self):
        """extract_feature_name extracts from LLD title."""
        from agentos.workflows.testing.nodes.document import extract_feature_name

        state: TestingWorkflowState = {
            "issue_number": 42,
            "lld_content": "# 42 - N8 Documentation Node\n\nContent here",
        }
        assert "Documentation Node" in extract_feature_name(state)

    def test_extract_feature_name_fallback(self):
        """extract_feature_name falls back to issue number."""
        from agentos.workflows.testing.nodes.document import extract_feature_name

        state: TestingWorkflowState = {
            "issue_number": 42,
            "lld_content": "Some content without a clear title",
        }
        assert "42" in extract_feature_name(state)

    def test_document_generates_lessons_learned(self, tmp_path):
        """document node always generates lessons learned."""
        from agentos.workflows.testing.nodes.document import document

        # Setup directories
        audit_dir = tmp_path / "docs" / "lineage" / "active" / "42-testing"
        audit_dir.mkdir(parents=True)

        state: TestingWorkflowState = {
            "issue_number": 42,
            "repo_root": str(tmp_path),
            "lld_content": "# Simple feature\n\nBugfix content",
            "audit_dir": str(audit_dir),
            "implementation_files": [],
            "test_files": [],
            "iteration_count": 1,
            "coverage_achieved": 95.0,
            "coverage_target": 90,
            "doc_scope": "auto",
        }

        result = document(state)

        assert result.get("doc_lessons_path") != ""
        lessons_path = Path(result["doc_lessons_path"])
        assert lessons_path.exists()
        content = lessons_path.read_text()
        assert "Lessons Learned" in content
        assert "Issue #42" in content

    def test_document_skips_with_none_scope(self, tmp_path):
        """document node respects doc_scope: none."""
        from agentos.workflows.testing.nodes.document import document

        # Setup directories
        audit_dir = tmp_path / "docs" / "lineage" / "active" / "42-testing"
        audit_dir.mkdir(parents=True)

        state: TestingWorkflowState = {
            "issue_number": 42,
            "repo_root": str(tmp_path),
            "lld_content": "<!-- doc-scope: none -->\nSimple content",
            "audit_dir": str(audit_dir),
            "implementation_files": [],
            "test_files": [],
            "iteration_count": 1,
            "coverage_achieved": 95.0,
            "coverage_target": 90,
            "doc_scope": "auto",
        }

        result = document(state)

        # Lessons learned still generated
        assert result.get("doc_lessons_path") != ""
        # But no wiki, runbook, or c/p docs
        assert result.get("doc_wiki_path") == ""
        assert result.get("doc_runbook_path") == ""
        assert result.get("doc_cp_paths") == []


class TestDocumentTemplates:
    """Tests for documentation templates."""

    def test_generate_wiki_page(self, tmp_path):
        """generate_wiki_page creates wiki file."""
        from agentos.workflows.testing.templates.wiki_page import generate_wiki_page

        lld_content = """# Test Feature

## 1. Overview

This is a test feature for documentation.

## 3. Requirements

- User can do X
- System handles Y

```mermaid
graph TD
    A[Start] --> B[End]
```
"""
        wiki_path = generate_wiki_page(
            feature_name="Test Feature",
            lld_content=lld_content,
            issue_number=42,
            repo_root=tmp_path,
        )

        assert wiki_path.exists()
        content = wiki_path.read_text()
        assert "Test Feature" in content
        assert "Overview" in content
        assert "mermaid" in content

    def test_generate_runbook(self, tmp_path):
        """generate_runbook creates runbook file."""
        from agentos.workflows.testing.templates.runbook import generate_runbook

        lld_content = """# Workflow Feature

## Prerequisites

- Python 3.11+
- Poetry installed

## Implementation

1. Load configuration
2. Execute workflow
3. Save results
"""
        runbook_path = generate_runbook(
            feature_name="Workflow Feature",
            lld_content=lld_content,
            issue_number=42,
            repo_root=tmp_path,
            implementation_files=["tools/run_workflow.py"],
        )

        assert runbook_path.exists()
        content = runbook_path.read_text()
        assert "Workflow Feature" in content
        assert "Procedure" in content
        assert "Verification" in content

    def test_generate_lessons_learned(self, tmp_path):
        """generate_lessons_learned creates lessons file."""
        from agentos.workflows.testing.templates.lessons import generate_lessons_learned

        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()

        state = {
            "iteration_count": 3,
            "coverage_achieved": 87.5,
            "coverage_target": 90,
            "test_files": ["tests/test_feature.py"],
            "implementation_files": ["src/feature.py"],
            "red_phase_output": "mock fixture used",
            "green_phase_output": "5 passed",
            "test_plan_status": "APPROVED",
            "e2e_output": "",
            "skip_e2e": True,
        }

        lessons_path = generate_lessons_learned(
            issue_number=42,
            audit_dir=audit_dir,
            state=state,
            repo_root=tmp_path,
        )

        assert lessons_path.exists()
        content = lessons_path.read_text()
        assert "Issue #42" in content
        assert "87.5%" in content
        assert "3" in content  # iteration count

    def test_generate_cli_doc(self, tmp_path):
        """generate_cli_doc creates CLI documentation."""
        from agentos.workflows.testing.templates.cp_docs import generate_cli_doc

        lld_content = """# CLI Tool

```bash
poetry run python tools/run_tool.py --help
poetry run python tools/run_tool.py --issue 42
```
"""
        cli_path = generate_cli_doc(
            tool_name="Test Tool",
            lld_content=lld_content,
            issue_number=42,
            repo_root=tmp_path,
        )

        assert cli_path.exists()
        assert "cli.md" in cli_path.name
        content = cli_path.read_text()
        assert "Test Tool" in content
        assert "Quick Reference" in content

    def test_generate_prompt_doc(self, tmp_path):
        """generate_prompt_doc creates Prompt documentation."""
        from agentos.workflows.testing.templates.cp_docs import generate_prompt_doc

        lld_content = """# CLI Tool

## Usage

- Run the tool for issue 42
- Check the output
"""
        prompt_path = generate_prompt_doc(
            tool_name="Test Tool",
            lld_content=lld_content,
            issue_number=42,
            repo_root=tmp_path,
        )

        assert prompt_path.exists()
        assert "prompt.md" in prompt_path.name
        content = prompt_path.read_text()
        assert "Test Tool" in content
        assert "Example Prompts" in content

    def test_update_wiki_sidebar_adds_link(self, tmp_path):
        """update_wiki_sidebar adds link to sidebar."""
        from agentos.workflows.testing.templates.wiki_page import update_wiki_sidebar

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        # Create sidebar
        sidebar_path = wiki_dir / "_Sidebar.md"
        sidebar_path.write_text("""# Wiki

### Reference

- [Home](Home)
""")

        # Create wiki page
        wiki_page = wiki_dir / "New-Feature.md"
        wiki_page.write_text("# New Feature")

        result = update_wiki_sidebar(wiki_page, section="Reference")

        assert result is True
        content = sidebar_path.read_text()
        assert "New Feature" in content

    def test_update_wiki_sidebar_skips_duplicate(self, tmp_path):
        """update_wiki_sidebar skips existing link."""
        from agentos.workflows.testing.templates.wiki_page import update_wiki_sidebar

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        # Create sidebar with existing link
        sidebar_path = wiki_dir / "_Sidebar.md"
        sidebar_path.write_text("""# Wiki

### Reference

- [Home](Home)
- [New-Feature](New-Feature)
""")

        # Create wiki page
        wiki_page = wiki_dir / "New-Feature.md"
        wiki_page.write_text("# New Feature")

        result = update_wiki_sidebar(wiki_page, section="Reference")

        assert result is False  # No update needed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
