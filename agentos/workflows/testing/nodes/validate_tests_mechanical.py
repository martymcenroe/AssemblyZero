"""Mechanical validation of generated tests.

Issue #335: Validates that generated tests are real executable tests,
not stubs with `assert False` placeholders.

This node runs after scaffold_tests and before verify_red to catch
stub tests early and route back for regeneration.
"""

import ast
import logging
import re
from typing import Any, Literal

logger = logging.getLogger(__name__)


# =============================================================================
# Stub Pattern Detection
# =============================================================================

# Patterns that indicate a stub test
STUB_PATTERNS = [
    re.compile(r'assert\s+False', re.IGNORECASE),
    re.compile(r'raise\s+NotImplementedError', re.IGNORECASE),
    re.compile(r'TDD\s*(?:RED|:)', re.IGNORECASE),
    re.compile(r'Implementation\s+pending', re.IGNORECASE),
    re.compile(r'not\s+implemented', re.IGNORECASE),
    re.compile(r'#\s*TODO:\s*implement', re.IGNORECASE),
    re.compile(r'#\s*stub', re.IGNORECASE),
]


def detect_stub_patterns(test_content: str) -> list[str]:
    """Find stub test patterns that indicate placeholder tests.

    Issue #335: Detects common stub patterns like `assert False`,
    `raise NotImplementedError`, "TDD RED", etc.

    Args:
        test_content: The generated test file content.

    Returns:
        List of error messages describing detected stub patterns.
    """
    errors = []

    lines = test_content.split('\n')
    for i, line in enumerate(lines, 1):
        for pattern in STUB_PATTERNS:
            if pattern.search(line):
                # Get a clean snippet of the line
                snippet = line.strip()[:60]
                errors.append(
                    f"Line {i}: Stub pattern detected: '{snippet}'"
                )
                break  # Only report first pattern match per line

    return errors


# =============================================================================
# AST Validation
# =============================================================================


def validate_test_structure(
    test_content: str,
    scenarios: list[dict],
) -> list[str]:
    """AST validation: verify imports, calls, and assertions exist.

    Issue #335: Uses Python AST to verify that tests have proper structure:
    - At least one import statement
    - Each test function has at least one real assertion
    - Assertions aren't just `assert False`

    Args:
        test_content: The generated test file content.
        scenarios: List of test scenario dicts with test_id and test_name.

    Returns:
        List of error messages for structural issues.
    """
    errors = []

    try:
        tree = ast.parse(test_content)
    except SyntaxError as e:
        errors.append(f"Syntax error in generated tests: {e}")
        return errors

    # Check for imports
    has_import = any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        for node in ast.walk(tree)
    )

    if not has_import:
        errors.append("No import statements found - tests need imports")

    # Check each test function
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
            # Check for assertions in this function
            has_real_assertion = False

            for child in ast.walk(node):
                if isinstance(child, ast.Assert):
                    # Check if it's a real assertion (not assert False)
                    if isinstance(child.test, ast.Constant):
                        if child.test.value is False:
                            continue  # Skip assert False
                    has_real_assertion = True
                    break

                # Also accept pytest.raises as valid
                if isinstance(child, ast.With):
                    for item in child.items:
                        if isinstance(item.context_expr, ast.Call):
                            call = item.context_expr
                            if isinstance(call.func, ast.Attribute):
                                if call.func.attr == 'raises':
                                    has_real_assertion = True
                                    break

            if not has_real_assertion:
                # Check if function only has pass
                func_has_only_pass = (
                    len(node.body) == 1 and
                    isinstance(node.body[0], (ast.Pass, ast.Expr)) and
                    (isinstance(node.body[0], ast.Pass) or
                     (isinstance(node.body[0], ast.Expr) and
                      isinstance(node.body[0].value, ast.Constant)))
                )

                if func_has_only_pass:
                    errors.append(
                        f"Function '{node.name}' has no assertions - only pass/docstring"
                    )
                else:
                    # Check if any assert exists (even assert False)
                    any_assert = any(
                        isinstance(child, ast.Assert)
                        for child in ast.walk(node)
                    )
                    if not any_assert:
                        errors.append(
                            f"Function '{node.name}' has no assertion statements"
                        )

    return errors


def validate_scenario_coverage(
    test_content: str,
    scenarios: list[dict],
) -> list[str]:
    """Ensure all LLD scenarios have corresponding test functions.

    Issue #335: Verifies that every test scenario from the LLD
    has a corresponding test function in the generated code.

    Args:
        test_content: The generated test file content.
        scenarios: List of test scenario dicts with test_id and test_name.

    Returns:
        List of error messages for missing test functions.
    """
    errors = []

    # Extract function names from test content
    try:
        tree = ast.parse(test_content)
    except SyntaxError:
        return []  # Don't add coverage errors if file doesn't parse

    test_functions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
            test_functions.add(node.name.lower())

    # Check each scenario
    for scenario in scenarios:
        test_name = scenario.get("test_name", "").lower()
        test_id = scenario.get("test_id", "")

        if not test_name:
            continue

        # Normalize test name
        if not test_name.startswith("test_"):
            test_name = f"test_{test_name}"

        if test_name not in test_functions:
            errors.append(
                f"Missing test function for scenario {test_id}: {scenario.get('test_name')}"
            )

    return errors


# =============================================================================
# LangGraph Node
# =============================================================================


def validate_tests_mechanical_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: Mechanical validation of generated tests.

    Issue #335: Validates generated tests to catch stubs before
    the green phase. Routes back to scaffold for regeneration if
    stubs are detected.

    Args:
        state: Workflow state with generated_tests and parsed_scenarios.

    Returns:
        State updates with validation_result and scaffold_attempts.
    """
    print("\n[N2.5] Validating generated tests (mechanical)...")

    generated_tests = state.get("generated_tests", "")
    parsed_scenarios = state.get("parsed_scenarios", {})
    scenarios = parsed_scenarios.get("scenarios", [])
    scaffold_attempts = state.get("scaffold_attempts", 0)

    all_errors = []
    stub_count = 0

    # Step 1: Detect stub patterns
    stub_errors = detect_stub_patterns(generated_tests)
    if stub_errors:
        stub_count = len(stub_errors)
        all_errors.extend(stub_errors)
        print(f"    Found {stub_count} stub patterns")

    # Step 2: Validate structure with AST
    structure_errors = validate_test_structure(generated_tests, scenarios)
    all_errors.extend(structure_errors)

    # Step 3: Validate scenario coverage
    coverage_errors = validate_scenario_coverage(generated_tests, scenarios)
    all_errors.extend(coverage_errors)

    # Build validation result
    is_valid = len(all_errors) == 0

    # Count real tests (functions without stub patterns)
    try:
        tree = ast.parse(generated_tests)
        total_tests = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')
        )
        real_test_count = total_tests - stub_count
    except SyntaxError:
        total_tests = 0
        real_test_count = 0

    validation_result = {
        "is_valid": is_valid,
        "errors": all_errors,
        "warnings": [],
        "stub_count": stub_count,
        "real_test_count": max(0, real_test_count),
    }

    if is_valid:
        print(f"    Validation PASSED: {real_test_count} real tests")
    else:
        print(f"    Validation FAILED: {len(all_errors)} errors")
        for error in all_errors[:5]:
            print(f"      - {error}")
        if len(all_errors) > 5:
            print(f"      ... and {len(all_errors) - 5} more")

    # Increment attempts if validation failed
    new_attempts = scaffold_attempts + 1 if not is_valid else scaffold_attempts

    return {
        "validation_result": validation_result,
        "scaffold_attempts": new_attempts,
    }


# =============================================================================
# Routing Function
# =============================================================================


def should_regenerate(state: dict[str, Any]) -> Literal["regenerate", "continue", "escalate"]:
    """Conditional edge: return routing decision based on validation.

    Issue #335: Routes the workflow based on validation results:
    - "regenerate": Validation failed, attempts < 3, retry scaffold
    - "continue": Validation passed, proceed to verify_red
    - "escalate": Validation failed, attempts >= 3, use Claude

    Args:
        state: Workflow state with validation_result and scaffold_attempts.

    Returns:
        Routing decision string.
    """
    validation_result = state.get("validation_result", {})
    is_valid = validation_result.get("is_valid", False)
    scaffold_attempts = state.get("scaffold_attempts", 0)

    if is_valid:
        return "continue"

    # Max 3 attempts before escalation
    if scaffold_attempts >= 3:
        print(f"    [ESCALATE] Max attempts ({scaffold_attempts}) reached, escalating to Claude")
        return "escalate"

    print(f"    [REGENERATE] Attempt {scaffold_attempts}/3, returning to scaffold")
    return "regenerate"
