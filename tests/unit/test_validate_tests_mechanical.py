"""Tests for Issue #335: Mechanical validation of generated tests.

Real TDD tests - NOT stubs. Tests the validation node that catches
stub tests and other structural issues before the green phase.
"""

import pytest


# =============================================================================
# Test: validate_tests_mechanical_node()
# =============================================================================


class TestValidateMechanicalNode:
    """Tests for the validation LangGraph node."""

    def test_node_returns_valid_for_good_tests(self):
        """Validation node passes for well-structured tests."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_tests_mechanical_node,
        )

        state = {
            "generated_tests": '''
import pytest
from mymodule import add

def test_add():
    """Test addition. Requirement: R010"""
    result = add(2, 3)
    assert result == 5
''',
            "parsed_scenarios": {
                "scenarios": [
                    {"test_id": "T010", "test_name": "test_add"}
                ]
            },
            "scaffold_attempts": 0,
        }

        result = validate_tests_mechanical_node(state)

        assert result.get("validation_result", {}).get("is_valid", False) is True

    def test_node_returns_invalid_for_stubs(self):
        """Validation node fails for stub tests."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_tests_mechanical_node,
        )

        state = {
            "generated_tests": '''
import pytest

def test_example():
    assert False, "TDD RED: not implemented"
''',
            "parsed_scenarios": {
                "scenarios": [
                    {"test_id": "T010", "test_name": "test_example"}
                ]
            },
            "scaffold_attempts": 0,
        }

        result = validate_tests_mechanical_node(state)

        validation = result.get("validation_result", {})
        assert validation.get("is_valid") is False
        assert validation.get("stub_count", 0) > 0

    def test_node_increments_attempts(self):
        """Validation node increments scaffold_attempts on failure."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_tests_mechanical_node,
        )

        state = {
            "generated_tests": '''
def test_example():
    assert False, "stub"
''',
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 1,
        }

        result = validate_tests_mechanical_node(state)

        assert result.get("scaffold_attempts", 0) == 2


# =============================================================================
# Test: Graph routing - should_regenerate()
# =============================================================================


class TestShouldRegenerate:
    """Tests for conditional edge routing."""

    def test_regenerate_on_validation_failure(self):
        """Routes to regenerate when validation fails and attempts < 3."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            should_regenerate,
        )

        state = {
            "validation_result": {
                "is_valid": False,
                "errors": ["Stub detected"],
            },
            "scaffold_attempts": 1,
        }

        result = should_regenerate(state)

        assert result == "regenerate"

    def test_continue_on_validation_success(self):
        """Routes to continue when validation passes."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            should_regenerate,
        )

        state = {
            "validation_result": {
                "is_valid": True,
                "errors": [],
            },
            "scaffold_attempts": 1,
        }

        result = should_regenerate(state)

        assert result == "continue"

    def test_escalate_after_max_attempts(self):
        """Routes to escalate after 3 failed attempts."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            should_regenerate,
        )

        state = {
            "validation_result": {
                "is_valid": False,
                "errors": ["Still failing"],
            },
            "scaffold_attempts": 3,
        }

        result = should_regenerate(state)

        assert result == "escalate"


# =============================================================================
# Test: Full validation flow
# =============================================================================


class TestValidationFlow:
    """Integration tests for the validation flow."""

    def test_validation_catches_common_stub_patterns(self):
        """Validates all common stub patterns are detected."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            detect_stub_patterns,
        )

        stub_examples = [
            'assert False, "TDD: Implementation pending"',
            'assert False, "TDD RED: not implemented"',
            "assert False  # TODO: Implement",
            'raise NotImplementedError("Test not implemented")',
            "pass  # stub",
        ]

        for stub in stub_examples:
            test_content = f'''
def test_example():
    {stub}
'''
            errors = detect_stub_patterns(test_content)
            assert len(errors) > 0, f"Should detect stub pattern: {stub}"

    def test_validation_accepts_various_assertion_styles(self):
        """Accepts different valid assertion styles."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            detect_stub_patterns,
            validate_test_structure,
        )

        valid_tests = [
            '''
def test_equality():
    assert result == 5
''',
            '''
def test_truth():
    assert is_valid
''',
            '''
def test_in():
    assert "foo" in result
''',
            '''
def test_raises():
    with pytest.raises(ValueError):
        bad_function()
''',
        ]

        for test_content in valid_tests:
            # Add import for completeness
            full_content = "import pytest\n" + test_content
            errors = detect_stub_patterns(full_content)
            assert len(errors) == 0, f"Should accept: {test_content[:50]}..."
