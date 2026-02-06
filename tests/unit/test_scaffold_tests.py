"""Tests for Issue #335: Scaffold real tests from LLD Section 10.0.

Real TDD tests - NOT stubs. Tests the scaffold improvements to generate
actual executable tests instead of `assert False` placeholders.
"""

import pytest
from pathlib import Path


# =============================================================================
# Test: parse_lld_test_section()
# =============================================================================


class TestParseLLDTestSection:
    """Tests for extracting test scenarios from LLD Section 10.0."""

    def test_parse_basic_test_table(self):
        """Extract scenarios from valid Section 10.0 table."""
        from assemblyzero.workflows.testing.nodes.scaffold_tests import (
            parse_lld_test_section,
        )

        lld_content = """
## 10. Verification & Testing

### 10.0 Test Plan (TDD - Complete Before Implementation)

| Test ID | Test Description | Expected Behavior | Req ID | Status |
|---------|------------------|-------------------|--------|--------|
| T010 | test_add_numbers | Returns sum of two numbers | R010 | RED |
| T020 | test_subtract_numbers | Returns difference of two numbers | R020 | RED |
"""

        result = parse_lld_test_section(lld_content)

        assert len(result["scenarios"]) == 2
        assert result["scenarios"][0]["test_id"] == "T010"
        assert result["scenarios"][0]["test_name"] == "test_add_numbers"
        assert "sum" in result["scenarios"][0]["expected_behavior"].lower()

    def test_parse_missing_section_10(self):
        """Returns empty list for LLD without Section 10.0."""
        from assemblyzero.workflows.testing.nodes.scaffold_tests import (
            parse_lld_test_section,
        )

        lld_content = """
## 1. Context & Goal

Some content without a test section.

## 2. Proposed Changes

More content.
"""

        result = parse_lld_test_section(lld_content)

        assert result["scenarios"] == []

    def test_parse_extracts_input_output(self):
        """Extracts input/output patterns from description."""
        from assemblyzero.workflows.testing.nodes.scaffold_tests import (
            parse_lld_test_section,
        )

        lld_content = """
### 10.0 Test Plan

| Test ID | Test Description | Expected Behavior | Req ID | Status |
|---------|------------------|-------------------|--------|--------|
| T010 | test_normalize_type | "Add (Directory)" -> ("add", True) | R010 | RED |
"""

        result = parse_lld_test_section(lld_content)

        scenario = result["scenarios"][0]
        # Should extract the input/output pattern
        assert "Add (Directory)" in scenario.get("expected_behavior", "")


# =============================================================================
# Test: infer_module_path()
# =============================================================================


class TestInferModulePath:
    """Tests for determining target module from LLD Section 2.1."""

    def test_infer_from_section_2_1(self):
        """Extracts module from Section 2.1 Files Changed."""
        from assemblyzero.workflows.testing.nodes.scaffold_tests import (
            infer_module_path,
        )

        lld_content = """
### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py` | Modify | Fix scaffold |
| `tests/unit/test_scaffold.py` | Add | Unit tests |
"""

        result = infer_module_path(lld_content)

        # Should return the non-test Python module
        assert result == "assemblyzero.workflows.testing.nodes.scaffold_tests"

    def test_infer_skips_test_files(self):
        """Skips test files when inferring module."""
        from assemblyzero.workflows.testing.nodes.scaffold_tests import (
            infer_module_path,
        )

        lld_content = """
### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/test_foo.py` | Add | Tests |
| `assemblyzero/foo.py` | Add | Implementation |
"""

        result = infer_module_path(lld_content)

        # Should return foo.py, not test_foo.py
        assert "test" not in result.lower()
        assert "assemblyzero.foo" == result


# =============================================================================
# Test: generate_test_code()
# =============================================================================


class TestGenerateTestCode:
    """Tests for generating real pytest code."""

    def test_generates_real_assertion(self):
        """Generated test has real assertion, not assert False."""
        from assemblyzero.workflows.testing.nodes.scaffold_tests import (
            generate_test_code,
        )

        scenarios = {
            "module_path": "assemblyzero.mymodule",
            "scenarios": [
                {
                    "test_id": "T010",
                    "test_name": "test_add_numbers",
                    "expected_behavior": "add(2, 3) returns 5",
                    "requirement_id": "R010",
                }
            ],
            "imports_needed": ["add"],
        }

        code = generate_test_code(scenarios)

        # Should NOT contain stub patterns
        assert "assert False" not in code
        # Should have a real assertion
        assert "assert" in code
        # Should reference the function
        assert "add" in code

    def test_includes_proper_imports(self):
        """Generated test imports target module."""
        from assemblyzero.workflows.testing.nodes.scaffold_tests import (
            generate_test_code,
        )

        scenarios = {
            "module_path": "assemblyzero.workflows.testing.nodes.scaffold_tests",
            "scenarios": [
                {
                    "test_id": "T010",
                    "test_name": "test_scaffold",
                    "expected_behavior": "scaffold_tests returns dict",
                    "requirement_id": "R010",
                }
            ],
            "imports_needed": ["scaffold_tests"],
        }

        code = generate_test_code(scenarios)

        assert "from assemblyzero.workflows.testing.nodes.scaffold_tests import" in code

    def test_includes_requirement_docstring(self):
        """Generated test has requirement ID in docstring."""
        from assemblyzero.workflows.testing.nodes.scaffold_tests import (
            generate_test_code,
        )

        scenarios = {
            "module_path": "mymodule",
            "scenarios": [
                {
                    "test_id": "T010",
                    "test_name": "test_foo",
                    "expected_behavior": "foo() returns bar",
                    "requirement_id": "R010",
                }
            ],
            "imports_needed": [],
        }

        code = generate_test_code(scenarios)

        assert "R010" in code


# =============================================================================
# Test: detect_stub_patterns() - Validation
# =============================================================================


class TestDetectStubPatterns:
    """Tests for detecting stub test patterns."""

    def test_detects_assert_false(self):
        """Detects `assert False` pattern."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            detect_stub_patterns,
        )

        test_content = '''
def test_example():
    assert False, "stub"
'''

        errors = detect_stub_patterns(test_content)

        assert len(errors) > 0
        assert any("assert False" in e.lower() or "stub" in e.lower() for e in errors)

    def test_detects_tdd_red_message(self):
        """Detects 'TDD RED' in assertion message."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            detect_stub_patterns,
        )

        test_content = '''
def test_example():
    assert False, "TDD RED: not implemented"
'''

        errors = detect_stub_patterns(test_content)

        assert len(errors) > 0

    def test_no_error_for_real_assertion(self):
        """No error for tests with real assertions."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            detect_stub_patterns,
        )

        test_content = '''
def test_example():
    result = add(2, 3)
    assert result == 5
'''

        errors = detect_stub_patterns(test_content)

        assert len(errors) == 0


# =============================================================================
# Test: validate_test_structure() - AST Validation
# =============================================================================


class TestValidateTestStructure:
    """Tests for AST-based test validation."""

    def test_rejects_missing_imports(self):
        """Rejects tests without proper imports."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_test_structure,
        )

        # Test with no imports at all
        test_content = '''
def test_example():
    result = mysterious_function()
    assert result == 42
'''

        scenarios = [{"test_id": "T010", "test_name": "test_example"}]
        errors = validate_test_structure(test_content, scenarios)

        # Should warn about missing imports for the function being tested
        assert len(errors) > 0

    def test_rejects_no_real_assertion(self):
        """Rejects tests with only pass statement."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_test_structure,
        )

        test_content = '''
import pytest

def test_example():
    pass
'''

        scenarios = [{"test_id": "T010", "test_name": "test_example"}]
        errors = validate_test_structure(test_content, scenarios)

        assert len(errors) > 0
        assert any("assertion" in e.lower() for e in errors)

    def test_accepts_valid_test(self):
        """Accepts test with import and real assertion."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_test_structure,
        )

        test_content = '''
import pytest
from mymodule import add

def test_add():
    result = add(2, 3)
    assert result == 5
'''

        scenarios = [{"test_id": "T010", "test_name": "test_add"}]
        errors = validate_test_structure(test_content, scenarios)

        assert len(errors) == 0


# =============================================================================
# Test: validate_scenario_coverage()
# =============================================================================


class TestValidateScenarioCoverage:
    """Tests for verifying all scenarios have test functions."""

    def test_all_scenarios_covered(self):
        """Passes when all scenarios have tests."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_scenario_coverage,
        )

        test_content = '''
def test_add():
    pass

def test_subtract():
    pass
'''

        scenarios = [
            {"test_id": "T010", "test_name": "test_add"},
            {"test_id": "T020", "test_name": "test_subtract"},
        ]
        errors = validate_scenario_coverage(test_content, scenarios)

        assert len(errors) == 0

    def test_missing_scenario(self):
        """Fails when scenario is missing test function."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_scenario_coverage,
        )

        test_content = '''
def test_add():
    pass
'''

        scenarios = [
            {"test_id": "T010", "test_name": "test_add"},
            {"test_id": "T020", "test_name": "test_subtract"},  # Missing!
        ]
        errors = validate_scenario_coverage(test_content, scenarios)

        assert len(errors) > 0
        assert any("T020" in e or "test_subtract" in e for e in errors)


# =============================================================================
# Test: Integration - scaffold_tests_node
# =============================================================================


class TestScaffoldIntegration:
    """Integration tests for the full scaffold node."""

    def test_scaffold_produces_runnable_tests(self, tmp_path):
        """Full scaffold produces syntactically valid Python."""
        from assemblyzero.workflows.testing.nodes.scaffold_tests import scaffold_tests
        import ast

        # Create minimal state with test scenarios
        state = {
            "issue_number": 999,
            "test_scenarios": [
                {
                    "name": "test_example",
                    "description": "Example test",
                    "requirement_ref": "R001",
                    "test_type": "unit",
                    "mock_needed": False,
                    "assertions": ["result equals expected"],
                }
            ],
            "files_to_modify": [
                {"path": "mymodule.py", "change_type": "Add"}
            ],
            "repo_root": str(tmp_path),
            "audit_dir": str(tmp_path / "audit"),
        }
        (tmp_path / "audit").mkdir()

        result = scaffold_tests(state)

        # Should produce test file
        assert result.get("test_files")
        test_file = Path(result["test_files"][0])
        assert test_file.exists()

        # Content should be valid Python
        content = test_file.read_text()
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"Generated test is not valid Python: {e}")
