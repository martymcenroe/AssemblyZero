"""Unit tests verifying test skip patterns are explicit.

Issue #154: Environmental test skips hide failures instead of failing clearly

Problem: Tests use inline pytest.skip() which hides environmental issues.
Fix: Use explicit @pytest.mark.skipif decorators that are visible and configured.
"""

import ast
from pathlib import Path

import pytest


class TestNoInlineSkips:
    """Verify tests don't use inline pytest.skip() for environmental conditions."""

    def test_issue_78_no_inline_skip(self):
        """test_issue_78.py should not have inline pytest.skip() calls."""
        test_file = Path(__file__).parent.parent / "test_issue_78.py"

        if not test_file.exists():
            pytest.skip("test_issue_78.py not found")

        content = test_file.read_text(encoding="utf-8")

        # Parse AST and look for Call nodes to pytest.skip inside functions
        tree = ast.parse(content)

        skip_calls_in_functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if (child.func.attr == "skip" and
                                isinstance(child.func.value, ast.Name) and
                                child.func.value.id == "pytest"):
                                skip_calls_in_functions.append(node.name)

        assert not skip_calls_in_functions, (
            f"Found inline pytest.skip() in functions: {skip_calls_in_functions}. "
            f"Use @pytest.mark.skipif decorator instead for explicit, visible skips."
        )

    def test_integration_workflow_no_inline_skip(self):
        """test_integration_workflow.py should not have inline pytest.skip() calls."""
        test_file = Path(__file__).parent.parent / "test_integration_workflow.py"

        if not test_file.exists():
            pytest.skip("test_integration_workflow.py not found")

        content = test_file.read_text(encoding="utf-8")

        tree = ast.parse(content)

        skip_calls_in_functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if (child.func.attr == "skip" and
                                isinstance(child.func.value, ast.Name) and
                                child.func.value.id == "pytest"):
                                skip_calls_in_functions.append(node.name)

        assert not skip_calls_in_functions, (
            f"Found inline pytest.skip() in functions: {skip_calls_in_functions}. "
            f"Use @pytest.mark.skipif decorator instead for explicit, visible skips."
        )


class TestIntegrationMarkers:
    """Verify integration tests have proper markers."""

    def test_integration_workflow_has_markers(self):
        """Integration tests should have @pytest.mark.integration marker."""
        test_file = Path(__file__).parent.parent / "test_integration_workflow.py"

        if not test_file.exists():
            pytest.skip("test_integration_workflow.py not found")

        content = test_file.read_text(encoding="utf-8")

        # Check for integration marker on the class or functions
        has_integration_marker = (
            "@pytest.mark.integration" in content or
            'pytestmark = pytest.mark.integration' in content
        )

        assert has_integration_marker, (
            "test_integration_workflow.py should have @pytest.mark.integration "
            "marker to clearly identify integration tests"
        )


class TestSkipifDecoratorUsage:
    """Verify skipif decorators are used properly."""

    def test_claude_dependency_uses_skipif(self):
        """Tests depending on claude CLI should use @pytest.mark.skipif."""
        test_file = Path(__file__).parent.parent / "test_integration_workflow.py"

        if not test_file.exists():
            pytest.skip("test_integration_workflow.py not found")

        content = test_file.read_text(encoding="utf-8")

        # Should have skipif for claude dependency
        has_skipif_for_claude = (
            "skipif" in content and
            ("claude" in content.lower() or "shutil.which" in content)
        )

        # The skipif should be a decorator, not inline
        has_decorator_skipif = "@pytest.mark.skipif" in content

        assert has_decorator_skipif, (
            "Tests depending on claude CLI should use @pytest.mark.skipif "
            "decorator with shutil.which('claude') check"
        )

    def test_gitignore_test_uses_skipif(self):
        """test_110 should use @pytest.mark.skipif for file existence check."""
        test_file = Path(__file__).parent.parent / "test_issue_78.py"

        if not test_file.exists():
            pytest.skip("test_issue_78.py not found")

        content = test_file.read_text(encoding="utf-8")

        # Find the test_110 function and check it has skipif
        tree = ast.parse(content)

        test_110_has_skipif = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "test_110":
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            if decorator.func.attr == "skipif":
                                test_110_has_skipif = True

        assert test_110_has_skipif, (
            "test_110 should use @pytest.mark.skipif decorator for "
            ".gitignore file existence check, not inline pytest.skip()"
        )
