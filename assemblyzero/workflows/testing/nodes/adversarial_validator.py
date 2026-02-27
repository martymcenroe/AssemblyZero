"""Validates generated adversarial test files.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

Performs:
1. Syntax check (compile each file)
2. No-mock enforcement (AST scan)
3. No duplicate test function names
4. Each test has at least one assert statement
"""

import ast
import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class ValidationResult(TypedDict):
    """Result of adversarial test validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]
    mock_violations: list[str]


def validate_adversarial_tests(test_files: dict[str, str]) -> ValidationResult:
    """Validate generated adversarial test files.

    Checks:
    1. Syntax check (compile each file).
    2. No-mock enforcement (scan for unittest.mock, MagicMock, patch, monkeypatch).
    3. No duplicate test function names across files.
    4. Each test has at least one assert statement.

    Args:
        test_files: Dictionary of filepath -> file content.

    Returns:
        ValidationResult with detailed error/warning/violation lists.
    """
    all_errors: list[str] = []
    all_warnings: list[str] = []
    all_mock_violations: list[str] = []
    seen_test_names: dict[str, str] = {}  # test_name -> filepath

    for filepath, source_code in test_files.items():
        # 1. Syntax check
        syntax_errors = _check_syntax(source_code, filepath)
        all_errors.extend(syntax_errors)

        if syntax_errors:
            # Can't do AST analysis on syntactically invalid code
            continue

        # 2. No-mock enforcement
        mock_violations = _check_no_mocks(source_code, filepath)
        all_mock_violations.extend(mock_violations)

        # 3. Assertion check
        assertion_warnings = _check_assertions(source_code, filepath)
        all_warnings.extend(assertion_warnings)

        # 4. Duplicate function name check
        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith(
                    "test_"
                ):
                    if node.name in seen_test_names:
                        all_warnings.append(
                            f"{filepath}: Duplicate test function '{node.name}' "
                            f"(also in {seen_test_names[node.name]})"
                        )
                    else:
                        seen_test_names[node.name] = filepath
        except SyntaxError:
            pass  # Already caught above

    is_valid = len(all_errors) == 0 and len(all_mock_violations) == 0

    return ValidationResult(
        valid=is_valid,
        errors=all_errors,
        warnings=all_warnings,
        mock_violations=all_mock_violations,
    )


def _check_no_mocks(source_code: str, filepath: str) -> list[str]:
    """AST-scan source code for mock usage. Returns list of violations.

    Detects:
    - import unittest.mock
    - from unittest.mock import *
    - from unittest import mock
    - @patch / @mock.patch decorators
    - MagicMock(), Mock(), AsyncMock() instantiation
    - monkeypatch fixture usage

    Args:
        source_code: Python source code string.
        filepath: File path for error reporting.

    Returns:
        List of violation descriptions.
    """
    violations: list[str] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return violations  # Syntax errors handled separately

    mock_import_names = {"unittest.mock", "mock"}
    mock_class_names = {"MagicMock", "Mock", "AsyncMock"}
    mock_decorator_names = {"patch", "mock.patch"}

    for node in ast.walk(tree):
        # Check: import unittest.mock / import mock
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in mock_import_names or alias.name.startswith(
                    "unittest.mock"
                ):
                    violations.append(
                        f"{filepath}:{node.lineno}: Mock import detected: "
                        f"'import {alias.name}'"
                    )

        # Check: from unittest.mock import ... / from unittest import mock
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "unittest.mock" or module == "unittest":
                for alias in node.names:
                    if module == "unittest" and alias.name == "mock":
                        violations.append(
                            f"{filepath}:{node.lineno}: Mock import detected: "
                            f"'from unittest import mock'"
                        )
                    elif module == "unittest.mock":
                        import_names = ", ".join(
                            a.name for a in node.names
                        )
                        violations.append(
                            f"{filepath}:{node.lineno}: Mock import detected: "
                            f"'from unittest.mock import {import_names}'"
                        )
                        break  # Report once per import statement

        # Check: @patch / @mock.patch decorators
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                decorator_name = _get_decorator_name(decorator)
                if decorator_name and any(
                    mock_name in decorator_name for mock_name in mock_decorator_names
                ):
                    violations.append(
                        f"{filepath}:{decorator.lineno}: Mock decorator detected: "
                        f"'@{decorator_name}'"
                    )

            # Check: monkeypatch fixture usage
            for arg in node.args.args:
                if arg.arg == "monkeypatch":
                    violations.append(
                        f"{filepath}:{node.lineno}: Monkeypatch fixture detected: "
                        f"'def {node.name}(monkeypatch)'"
                    )

        # Check: MagicMock() / Mock() / AsyncMock() instantiation
        elif isinstance(node, ast.Call):
            call_name = _get_call_name(node)
            if call_name in mock_class_names:
                violations.append(
                    f"{filepath}:{node.lineno}: Mock instantiation detected: "
                    f"'{call_name}()'"
                )

    return violations


def _get_decorator_name(node: ast.expr) -> str | None:
    """Extract decorator name from AST node.

    Handles:
    - Simple names: @patch → "patch"
    - Attribute access: @mock.patch → "mock.patch"
    - Calls: @patch('module.func') → "patch"
    """
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        value_name = _get_decorator_name(node.value)
        if value_name:
            return f"{value_name}.{node.attr}"
        return node.attr
    elif isinstance(node, ast.Call):
        return _get_decorator_name(node.func)
    return None


def _get_call_name(node: ast.Call) -> str:
    """Extract function/class name from a Call AST node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    elif isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _check_syntax(source_code: str, filepath: str) -> list[str]:
    """Attempt to compile source code. Returns list of syntax errors.

    Args:
        source_code: Python source code string.
        filepath: File path for error reporting.

    Returns:
        List of syntax error descriptions.
    """
    errors: list[str] = []
    try:
        compile(source_code, filepath, "exec")
    except SyntaxError as e:
        errors.append(
            f"{filepath}: SyntaxError: {e.msg} (line {e.lineno})"
        )
    return errors


def _check_assertions(source_code: str, filepath: str) -> list[str]:
    """AST-scan for assert statements in each test function.

    Returns warnings for test functions with zero assertions.
    Also checks for pytest.raises as an assertion equivalent.

    Args:
        source_code: Python source code string.
        filepath: File path for error reporting.

    Returns:
        List of warning descriptions for test functions without assertions.
    """
    warnings: list[str] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return warnings  # Syntax errors handled separately

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            has_assertion = False

            for child in ast.walk(node):
                # Direct assert statement
                if isinstance(child, ast.Assert):
                    has_assertion = True
                    break

                # pytest.raises context manager
                if isinstance(child, ast.With):
                    for item in child.items:
                        ctx = item.context_expr
                        if isinstance(ctx, ast.Call):
                            call_name = _get_call_name(ctx)
                            if call_name == "raises":
                                has_assertion = True
                                break
                    if has_assertion:
                        break

            if not has_assertion:
                warnings.append(
                    f"{filepath}: {node.name} has no assertions"
                )

    return warnings