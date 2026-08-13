"""Mechanical validation of generated tests.

Issue #335: Validates that generated tests are real executable tests,
not stubs with `assert False` placeholders.

Issue #502: Hash-based stagnation detection for scaffold loop.

This node runs after scaffold_tests and before verify_red to catch
stub tests early and route back for regeneration.
"""

import ast
import hashlib
import logging
import re
from typing import Any, Literal

from assemblyzero.workflows.testing.audit import gate_log
from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.runner_registry import get_runner

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


def count_stub_tests(test_content: str) -> tuple[int, int, list[str]]:
    """Count test functions whose BODY can never pass. (#2317)

    Returns (total_tests, stub_tests, stub_names).

    A stub here is a test whose body does nothing but fail: an unconditional
    `assert False`, a bare `raise NotImplementedError`, or nothing at all
    beyond a docstring, comments and `pass`. Such a function is not a weak
    test -- it is a test no implementation can satisfy, so a suite made
    entirely of them cannot converge no matter what the coder writes.

    Decided on the AST rather than by regex, because the line-based
    STUB_PATTERNS above cannot tell a placeholder body from a genuine test
    that merely mentions one of those strings (a test asserting on the text
    "not implemented", for instance). That imprecision is part of why the
    detection was blanket-disabled by #386 rather than made accurate.
    """
    try:
        tree = ast.parse(test_content)
    except SyntaxError:
        return 0, 0, []

    total = 0
    stub_names: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        total += 1

        meaningful = []
        for stmt in node.body:
            # Docstrings and bare constants carry no behaviour.
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue
            if isinstance(stmt, ast.Pass):
                continue
            meaningful.append(stmt)

        if not meaningful:
            stub_names.append(node.name)
            continue

        def _is_dead_end(stmt: ast.stmt) -> bool:
            if isinstance(stmt, ast.Assert):
                test = stmt.test
                return isinstance(test, ast.Constant) and not test.value
            if isinstance(stmt, ast.Raise) and stmt.exc is not None:
                exc = stmt.exc
                name = exc.func if isinstance(exc, ast.Call) else exc
                return isinstance(name, ast.Name) and name.id == "NotImplementedError"
            return False

        if all(_is_dead_end(stmt) for stmt in meaningful):
            stub_names.append(node.name)

    return total, len(stub_names), stub_names


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
                    # Issue #386: Accept `assert False, 'TDD RED: ...'` as valid
                    # TDD scaffold intentionally generates failing assertions.
                    # Only reject bare `assert False` without a message.
                    if isinstance(child.test, ast.Constant):
                        if child.test.value is False and child.msg is None:
                            continue  # Skip bare assert False (no message)
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
    gate_log("[N2.5] Validating generated tests (mechanical)...")

    generated_tests = state.get("generated_tests", "")
    parsed_scenarios = state.get("parsed_scenarios", {})
    scenarios = parsed_scenarios.get("scenarios", [])
    scaffold_attempts = state.get("scaffold_attempts", 0)

    # Issue #381: Framework-aware validation branch
    framework_config = state.get("framework_config")
    if framework_config:
        fw_enum = framework_config.get("framework")
        # Normalize: could be a TestFramework enum or its string value
        if isinstance(fw_enum, str):
            try:
                fw_enum = TestFramework(fw_enum)
            except ValueError:
                fw_enum = None
        if fw_enum and fw_enum != TestFramework.PYTEST:
            return _validate_non_pytest(
                state, generated_tests, fw_enum, scaffold_attempts
            )

    all_errors = []

    # Issue #386 exempted `assert False, 'TDD RED: ...'` from stub detection,
    # because the TDD scaffold emits such placeholders on purpose and flagging
    # them created a scaffold -> validate -> reject -> scaffold loop.
    #
    # #2317: that exemption was total, so this node could no longer tell a few
    # placeholders among real tests from a suite that is ENTIRELY placeholders.
    # It blessed the second case as "36 real tests" on boostgauge #7, and the
    # implementation stage then spent two iterations against a suite no code
    # could satisfy.
    #
    # The distinction restored here is proportional, not a revert. Individual
    # placeholders remain acceptable -- that is #386's case and it still
    # passes. A wholly hollow suite is always NAMED, and is rejected only when
    # rejecting can actually help.
    #
    # That condition is deliberate. `should_regenerate` escalates a
    # deterministic scaffolder on its hash check, and "escalate" routes to
    # N4_implement_code (graph.py) -- so for a spec that supplies no test
    # bodies, failing here reaches implementation anyway, just with the red
    # phase skipped as well. Rejecting is worth it precisely when regeneration
    # can produce something better, which since #2316 means: the spec ships
    # executable Section 10 test functions and the scaffold ignored them.
    # Where it cannot help, the suite is reported loudly instead of being
    # bounced around a loop that ends in the same place.
    total_tests, stub_count, stub_names = count_stub_tests(generated_tests)
    hollow = total_tests > 0 and stub_count == total_tests
    spec_has_bodies = bool(
        (state.get("spec_test_suite") or {}).get("functions")
    )
    if hollow:
        shown = ", ".join(stub_names[:3])
        more = f" (and {stub_count - 3} more)" if stub_count > 3 else ""
        # ASCII only: this string is printed, and per #1493 a non-ASCII
        # character raises UnicodeEncodeError mid-stream on Windows cp1252.
        description = (
            f"all {total_tests} generated test(s) fail unconditionally "
            f"({shown}{more}) -- no implementation can make this suite green"
        )
        if spec_has_bodies:
            all_errors.append(
                f"{description}. The spec supplies executable Section 10 test "
                f"functions that were not used; regenerate from those."
            )
        else:
            print(f"    [HOLLOW SCAFFOLD] {description}")
            print(
                "    The spec supplies no executable test bodies, so "
                "re-scaffolding cannot improve on this. Proceeding, but the "
                "implementation loop cannot converge against these tests."
            )

    # Step 2: Validate structure with AST (imports, test functions exist)
    structure_errors = validate_test_structure(generated_tests, scenarios)
    all_errors.extend(structure_errors)

    # Step 3: Validate scenario coverage
    coverage_errors = validate_scenario_coverage(generated_tests, scenarios)
    all_errors.extend(coverage_errors)

    # Build validation result
    is_valid = len(all_errors) == 0

    # #2317: `real` now excludes placeholders. It previously could not --
    # stub_count was pinned at 0, so every stub was reported as a real test
    # and the number the operator reads was the opposite of the truth.
    real_test_count = total_tests - stub_count

    validation_result = {
        "is_valid": is_valid,
        "errors": all_errors,
        "warnings": [],
        "stub_count": stub_count,
        "real_test_count": max(0, real_test_count),
    }

    if is_valid:
        # #2317: name the placeholders when there are any. A bare count of
        # "real tests" that silently included every stub is what let the
        # hollow suite through looking healthy.
        if stub_count:
            print(
                f"    Validation PASSED: {real_test_count} real tests "
                f"({stub_count} placeholder(s) among {total_tests})"
            )
        else:
            print(f"    Validation PASSED: {real_test_count} real tests")
    else:
        print(f"    Validation FAILED: {len(all_errors)} errors")
        for error in all_errors[:5]:
            print(f"      - {error}")
        if len(all_errors) > 5:
            print(f"      ... and {len(all_errors) - 5} more")

    # Increment attempts if validation failed
    new_attempts = scaffold_attempts + 1 if not is_valid else scaffold_attempts

    # Issue #500: Pass validation errors back so scaffold node can use them
    result_dict: dict[str, Any] = {
        "validation_result": validation_result,
        "scaffold_attempts": new_attempts,
    }
    if not is_valid:
        result_dict["scaffold_validation_errors"] = all_errors
    else:
        result_dict["scaffold_validation_errors"] = []  # Clear on success

    # Issue #502: Store hash for stagnation detection
    if generated_tests:
        result_dict["previous_scaffold_hash"] = hashlib.sha256(
            generated_tests.encode()
        ).hexdigest()

    return result_dict


def _validate_non_pytest(
    state: dict[str, Any],
    generated_tests: str,
    framework: TestFramework,
    scaffold_attempts: int,
) -> dict[str, Any]:
    """Validate non-pytest test files using framework-specific runner validators.

    Issue #381: Playwright/Jest/Vitest files can't be validated with Python AST.
    Instead, use the runner's validate_test_file() method which checks for
    framework-specific patterns (imports, test blocks, etc.).
    """
    repo_root = state.get("repo_root", ".")
    test_files = state.get("test_files", [])

    all_errors: list[str] = []

    try:
        runner = get_runner(framework, repo_root)
    except (ValueError, EnvironmentError) as e:
        # If runner can't be created (e.g., npx not installed), skip validation
        print(f"    [N2.5] Runner unavailable for {framework.value}: {e}")
        print("    [N2.5] Skipping mechanical validation (runner unavailable)")
        return {
            "validation_result": {
                "is_valid": True,
                "errors": [],
                "warnings": [f"Runner unavailable: {e}"],
                "stub_count": 0,
                "real_test_count": 0,
            },
            "scaffold_attempts": scaffold_attempts,
        }

    # Validate each test file using the runner
    if test_files:
        for tf in test_files:
            errors = runner.validate_test_file(tf, generated_tests)
            all_errors.extend(errors)
    else:
        # If no test_files list, validate the generated content directly
        errors = runner.validate_test_file("<generated>", generated_tests)
        all_errors.extend(errors)

    is_valid = len(all_errors) == 0

    if is_valid:
        print(f"    [N2.5] {framework.value} validation PASSED")
    else:
        print(f"    [N2.5] {framework.value} validation FAILED: {len(all_errors)} errors")
        for error in all_errors[:5]:
            print(f"      - {error}")

    new_attempts = scaffold_attempts + 1 if not is_valid else scaffold_attempts

    return {
        "validation_result": {
            "is_valid": is_valid,
            "errors": all_errors,
            "warnings": [],
            "stub_count": 0,
            "real_test_count": 0,
        },
        "scaffold_attempts": new_attempts,
        "scaffold_validation_errors": all_errors if not is_valid else [],  # Issue #500
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

    Issue #502: Hash-based stagnation detection. If scaffold output is
    identical to the previous attempt, escalate immediately instead of
    wasting another generation cycle.

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

    # Issue #502: Hash-based stagnation detection
    generated_tests = state.get("generated_tests", "")
    if generated_tests:
        current_hash = hashlib.sha256(generated_tests.encode()).hexdigest()
        previous_hash = state.get("previous_scaffold_hash", "")
        if previous_hash and current_hash == previous_hash:
            print("    [STAGNANT] Scaffold produced identical output. Escalating immediately.")
            return "escalate"

    # Max 3 attempts before escalation
    if scaffold_attempts >= 3:
        print(f"    [ESCALATE] Max attempts ({scaffold_attempts}) reached, escalating to Claude")
        return "escalate"

    print(f"    [REGENERATE] Attempt {scaffold_attempts}/3, returning to scaffold")
    return "regenerate"
