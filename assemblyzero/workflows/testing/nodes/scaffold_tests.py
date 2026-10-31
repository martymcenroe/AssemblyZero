"""N2: Scaffold Tests node for TDD Testing Workflow.

Issue #335: Updated to generate real executable tests from LLD Section 10.0,
not just stubs with `assert False`.

Issue #381: Extended with multi-framework scaffolding support for
Playwright, Jest, and Vitest in addition to pytest.

Generates executable tests from the approved test plan:
- Parses Section 10.0 Test Plan table for test scenarios
- Generates real assertions based on expected behavior
- Tests are syntactically valid and RUNNABLE
- Uses pytest conventions and fixtures (Python)
- Uses Playwright/Jest/Vitest conventions (TypeScript)

Previous behavior (stubs) caused infinite loops in the TDD workflow
because stub tests always fail regardless of implementation.
"""

import ast
import builtins
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, TypedDict

from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState, TestScenario

from assemblyzero.workflows.testing.framework_detector import (
    TestFramework,
    FrameworkConfig,
)
from assemblyzero.workflows.testing.framework_ownership import (
    RunFramework,
    TestFileOwnershipError,
    framework_label,
    owner_of,
    run_frameworks,
)
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import DETERMINISTIC_FAILURE
from assemblyzero.workflows.testing.runner_registry import get_runner, resolve_framework


# =============================================================================
# Issue #335: Data Structures for Parsed LLD Tests
# =============================================================================


class ParsedTestScenario(TypedDict):
    """A test scenario parsed from LLD Section 10.0."""

    test_id: str  # e.g., "T010"
    test_name: str  # e.g., "test_add_numbers"
    description: str  # Full description
    expected_behavior: str  # Expected result
    requirement_id: str  # e.g., "R010"


class ParsedLLDTests(TypedDict):
    """Parsed test information from LLD."""

    module_path: str  # Target module being tested
    scenarios: list[ParsedTestScenario]
    imports_needed: list[str]  # Detected imports


# =============================================================================
# Issue #335: LLD Section 10.0 Parsing Functions
# =============================================================================


def parse_lld_test_section(lld_content: str) -> ParsedLLDTests:
    """Extract test scenarios from LLD Section 10.0 Test Plan table.

    Issue #335: Parses the Test Plan table to extract structured test
    scenarios that can be used to generate real tests.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        ParsedLLDTests with scenarios and module info.

    Raises:
        ValueError: the LLD has no Section 10 test plan any pattern matches,
            naming the patterns (ledger 0908, line 105). It used to return
            no scenarios, which reads the same as a plan with an empty table.
    """
    result: ParsedLLDTests = {
        "module_path": "",
        "scenarios": [],
        "imports_needed": [],
    }

    # Find Section 10 test plan — search 10.0, 10.1, or the parent Section 10
    # Issue #656: unified patterns to match all known LLD section formats
    section_patterns = [
        r"###?\s*10\.0[^\n]*Test\s*Plan[^\n]*\n(.*?)(?=###?\s*\d|##\s*\d|\Z)",
        r"###?\s*10\.1[^\n]*Test\s*Scenario[^\n]*\n(.*?)(?=###?\s*10\.\d|##\s*\d|\Z)",
        r"##\s*10\.?\s*(?:Verification|Test|Testing)\b[^\n]*\n(.*?)(?=##\s*(?:11|[A-Z])|\Z)",
    ]

    section_content = None
    for pattern in section_patterns:
        match = re.search(pattern, lld_content, re.DOTALL | re.IGNORECASE)
        if match:
            section_content = match.group(1)
            break

    if section_content is None:
        raise ValueError(
            "the LLD has no Section 10 test plan to scaffold from: no heading "
            "matched '### 10.0 ... Test Plan', '### 10.1 ... Test Scenarios' or "
            "'## 10 Verification / Test / Testing' (the patterns: "
            + "; ".join(section_patterns) + ")"
        )

    # Parse the test table
    # Format: | Test ID | Test Description | Expected Behavior | Req ID | Status |
    # Also supports: | Test ID | Description | Expected | Req | Status |
    table_pattern = re.compile(
        r"\|\s*(T\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*(R?\d*)\s*\|\s*([^|]*)\s*\|",
        re.MULTILINE,
    )

    for match in table_pattern.finditer(section_content):
        test_id = match.group(1).strip()
        test_name = match.group(2).strip()
        expected_behavior = match.group(3).strip()
        requirement_id = match.group(4).strip()

        # Skip header rows
        if test_name.lower() in ("test description", "description", "---", "-"):
            continue

        # Normalize test name
        if not test_name.startswith("test_"):
            # Convert description to function name if needed
            clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", test_name.lower())
            clean_name = re.sub(r"_+", "_", clean_name).strip("_")
            if not clean_name.startswith("test_"):
                clean_name = f"test_{clean_name}"
            test_name = clean_name

        scenario: ParsedTestScenario = {
            "test_id": test_id,
            "test_name": test_name,
            "description": f"{test_id}: {match.group(2).strip()}",
            "expected_behavior": expected_behavior,
            "requirement_id": requirement_id if requirement_id else "",
        }
        result["scenarios"].append(scenario)

    return result


def infer_module_path(lld_content: str) -> str:
    """Determine target module from LLD Section 2.1 Files Changed.

    Issue #335: Extracts the Python module path from the Files Changed
    table, skipping test files.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        Python module path (e.g., "assemblyzero.workflows.testing.nodes.scaffold_tests")
        or empty string if not found.
    """
    # Find Section 2.1
    # Note: [^\n]*? is non-greedy to not consume "Files Changed"
    section_match = re.search(
        r"###?\s*2\.1[^\n]*?\n(.*?)(?=###?\s*\d|##\s*\d|\Z)",
        lld_content,
        re.DOTALL | re.IGNORECASE,
    )

    if not section_match:
        return ""

    section_content = section_match.group(1)

    # Parse table rows: | `path` | Type | Description |
    table_pattern = re.compile(
        r"\|\s*`?([^`|]+?)`?\s*\|\s*([^|]+)\s*\|\s*([^|]*)\s*\|",
        re.MULTILINE,
    )

    for match in table_pattern.finditer(section_content):
        path = match.group(1).strip()
        change_type = match.group(2).strip().lower()

        # Skip header rows
        if path.lower() in ("file", "---", "-"):
            continue
        if change_type in ("change type", "type", "---", "-"):
            continue

        # Skip test files (but not "testing" directories)
        path_lower = path.lower()
        filename = path_lower.split("/")[-1].split("\\")[-1]
        if (
            filename.startswith("test_") or
            filename.endswith("_test.py") or
            path_lower.startswith("tests/") or
            "/tests/" in path_lower or
            "\\tests\\" in path_lower
        ):
            continue

        # Skip non-Python files
        if not path.endswith(".py"):
            continue

        # Skip __init__.py
        if path.endswith("__init__.py"):
            continue

        # Convert path to module
        module = path.replace("/", ".").replace("\\", ".")
        if module.endswith(".py"):
            module = module[:-3]
        if module.startswith("src."):
            module = module[4:]

        return module

    return ""


def generate_test_code(scenarios: ParsedLLDTests) -> str:
    """Generate executable pytest code from parsed scenarios.

    Issue #335: Generates real test code with actual assertions
    instead of `assert False` stubs.

    Args:
        scenarios: ParsedLLDTests with module_path and scenarios.

    Returns:
        Python test file content as string.
    """
    module_path = scenarios.get("module_path", "")
    test_scenarios = scenarios.get("scenarios", [])
    imports_needed = scenarios.get("imports_needed", [])

    lines = [
        '"""Auto-generated tests from LLD Section 10.0.',
        "",
        "Issue #335: Real executable tests, not stubs.",
        '"""',
        "",
        "import pytest",
        "",
    ]

    # Add module import
    if module_path:
        lines.append(f"from {module_path} import (")
        # Add specific imports if known
        if imports_needed:
            for imp in imports_needed:
                lines.append(f"    {imp},")
        else:
            # Extract function names from expected_behavior
            for scenario in test_scenarios:
                expected = scenario.get("expected_behavior", "")
                # Look for function calls like "add(2, 3)"
                func_match = re.search(r"(\w+)\s*\(", expected)
                if func_match:
                    func_name = func_match.group(1)
                    if func_name not in ("assert", "print", "len", "str", "int", "float"):
                        lines.append(f"    {func_name},")
        lines.append(")")
        lines.append("")

    lines.append("")

    # Generate test functions
    for scenario in test_scenarios:
        test_id = scenario.get("test_id", "")
        test_name = scenario.get("test_name", "test_unnamed")
        description = scenario.get("description", "")
        expected = scenario.get("expected_behavior", "")
        req_id = scenario.get("requirement_id", "")

        lines.append(f"def {test_name}():")
        lines.append('    """')
        lines.append(f"    {description}")
        if req_id:
            lines.append("")
            lines.append(f"    Requirement: {req_id}")
        lines.append('    """')

        # Try to generate real assertion from expected behavior
        assertion = _generate_assertion_from_expected(expected)

        lines.append("    # Arrange")
        lines.append("    # (setup done in assertion)")
        lines.append("")
        lines.append("    # Act & Assert")
        lines.append(f"    {assertion}")
        lines.append("")
        lines.append("")

    return "\n".join(lines)


def _generate_assertion_from_expected(expected: str) -> str:
    """Generate assertion code from expected behavior string.

    Issue #335: Parses expected behavior like '"Add (Directory)" -> ("add", True)'
    and generates appropriate assertion code.

    Args:
        expected: Expected behavior string from LLD.

    Returns:
        Python assertion statement. When no assertion can be derived, a
        failing one that names the expected behaviour (ledger 0908, lines 325
        and 342): it used to be `assert True`, a test that passes with no
        implementation at all, so a scaffold no one replaced read as green.
    """
    # Pattern: input -> output (arrow notation)
    arrow_match = re.search(r'["\']?([^"\']+)["\']?\s*->\s*(.+)', expected)
    if arrow_match:
        input_val = arrow_match.group(1).strip()
        output_val = arrow_match.group(2).strip()

        # Try to find function name
        # Look for patterns like "func(x) returns y" before the arrow
        func_match = re.search(r'(\w+)\s*\([^)]*\)', expected)
        if func_match:
            func_name = func_match.group(1)
            return f'assert {func_name}("{input_val}") == {output_val}'

        # No function to call: the comparison cannot be written.
        return (
            f'# Input: "{input_val}" Expected: {output_val}\n'
            f"    {_underived_assertion(expected)}"
        )

    # Pattern: func(args) returns/equals value
    returns_match = re.search(
        r'(\w+)\s*\(([^)]*)\)\s*(?:returns?|equals?|==|is)\s*(.+)',
        expected,
        re.IGNORECASE,
    )
    if returns_match:
        func_name = returns_match.group(1)
        args = returns_match.group(2).strip()
        result = returns_match.group(3).strip()
        return f"assert {func_name}({args}) == {result}"

    # Pattern: simple description. No assertion can be derived from it.
    return f"# Expected: {expected}\n    {_underived_assertion(expected)}"


def _underived_assertion(expected: str) -> str:
    """A placeholder that fails until a real assertion replaces it, naming
    the expected behaviour no assertion could be derived from (ledger 0908,
    lines 325 and 342), as the TDD scaffold's `assert False, 'TDD RED: ...'`
    does."""
    reason = f"TDD RED: no assertion could be derived from the expected behaviour: {expected}"
    return f"assert False, {reason!r}"


def _path_to_module(path: str) -> str:
    """Convert a plan file path to its Python module path."""
    module = path.replace("/", ".").replace("\\", ".")
    if module.endswith(".py"):
        module = module[:-3]
    # Remove src/ prefix if present
    if module.startswith("src."):
        module = module[4:]
    # Skip __init__.py - import the package instead
    if module.endswith(".__init__"):
        module = module[:-9]
    return module


def _extract_impl_module(files_to_modify: list[dict] | None) -> str | None:
    """Extract Python module path from files_to_modify.

    Prioritizes NEW files (change_type="Add") over existing files (change_type="Modify")
    because new files won't exist yet, causing the import to fail (TDD RED phase).

    Issue #261: Previously picked the first file regardless of change type,
    which could be an existing "Modify" file that imports successfully.

    Args:
        files_to_modify: List of file dicts from LLD Section 2.1.

    Returns:
        Python module path (e.g., 'assemblyzero.workflows.testing.nodes.foo')
        or None if no Python files found.
    """
    if not files_to_modify:
        return None

    # First pass: look for NEW files (Add) - these won't exist yet
    for file_info in files_to_modify:
        path = file_info.get("path", "")
        change_type = file_info.get("change_type", "").lower()

        # Skip test files and __init__.py
        if "test" in path.lower():
            continue
        if path.endswith("__init__.py"):
            continue

        # Prioritize "Add" files - they don't exist yet
        if path.endswith(".py") and change_type == "add":
            return _path_to_module(path)

    # Second pass: fall back to "Modify" files if no "Add" found
    for file_info in files_to_modify:
        path = file_info.get("path", "")
        change_type = file_info.get("change_type", "").lower()

        if "test" in path.lower():
            continue
        if path.endswith("__init__.py"):
            continue

        if path.endswith(".py") and change_type == "modify":
            return _path_to_module(path)

    return None


# =============================================================================
# Issue #381: TypeScript Test File Generation
# =============================================================================


def generate_ts_test_file_content(
    scenarios: list[TestScenario],
    framework_config: FrameworkConfig,
    issue_number: int,
) -> str:
    """Generate TypeScript test file content for Playwright or Jest/Vitest.

    Issue #381: Generates .spec.ts or .test.ts files with framework-appropriate
    imports and test structure.

    Args:
        scenarios: Test scenarios from LLD Section 10.0
        framework_config: Framework configuration from runner_registry
        issue_number: Issue number for file naming
    """
    framework = framework_config["framework"]

    if framework == TestFramework.PLAYWRIGHT:
        return _generate_playwright_content(scenarios, issue_number)
    elif framework in (TestFramework.JEST, TestFramework.VITEST):
        return _generate_jest_content(scenarios, framework_config, issue_number)
    else:
        raise ValueError(f"Cannot generate TS content for framework: {framework}")


#: The body of every TypeScript placeholder test (#3067; ledger 0908,
#: `scaffold_tests.py:457` and `:489`). It fails until a real test replaces
#: it, as the Python scaffold's `assert False, 'TDD RED: ...'` does. The
#: placeholders were `expect(true).toBe(true)` and
#: `await expect(page).toBeTruthy()`, which pass with no implementation at
#: all, so a fresh TypeScript scaffold could never fail its red phase and a
#: scaffold no one replaced read as green.
TS_RED_PLACEHOLDER = "expect(false).toBe(true);"


def _ts_string(text: object) -> str:
    """`text` as a TypeScript string literal. JSON's escaping is valid
    TypeScript, so a description holding an apostrophe or a newline no longer
    ends the literal early (`it('Replays a user's session` did)."""
    return json.dumps(str(text))


def _ts_comment(text: object) -> str:
    """`text` on one line, safe to follow `//`."""
    return " ".join(str(text).split())


def _generate_playwright_content(
    scenarios: list[TestScenario],
    issue_number: int,
) -> str:
    """Generate Playwright .spec.ts test content: one placeholder per
    scenario, each failing until a real test replaces it (#3067)."""
    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"// Issue #{issue_number} - Auto-scaffolded Playwright tests",
        "",
    ]

    for scenario in scenarios:
        test_name = scenario.get("description", scenario.get("id", "unnamed"))
        expected = scenario.get("expected_behavior", "no expected behaviour given")
        lines.extend([
            f"test({_ts_string(test_name)}, async ({{ page }}) => {{",
            f"  // Expected: {_ts_comment(expected)}",
            "  // TDD RED: a placeholder; it fails until a real test replaces it",
            f"  {TS_RED_PLACEHOLDER}",
            "});",
            "",
        ])

    return "\n".join(lines)


def _generate_jest_content(
    scenarios: list[TestScenario],
    framework_config: FrameworkConfig,
    issue_number: int,
) -> str:
    """Generate Jest/Vitest .test.ts content: one placeholder per scenario,
    each failing until a real test replaces it (#3067)."""
    runner = get_runner(framework_config["framework"])
    import_line = runner.get_scaffold_imports()

    lines = [
        import_line,
        "",
        f"// Issue #{issue_number} - Auto-scaffolded tests",
        "",
        f"describe({_ts_string(f'Issue #{issue_number}')}, () => {{",
    ]

    for scenario in scenarios:
        test_name = scenario.get("description", scenario.get("id", "unnamed"))
        expected = scenario.get("expected_behavior", "no expected behaviour given")
        lines.extend([
            f"  it({_ts_string(test_name)}, () => {{",
            f"    // Expected: {_ts_comment(expected)}",
            "    // TDD RED: a placeholder; it fails until a real test replaces it",
            f"    {TS_RED_PLACEHOLDER}",
            "  });",
            "",
        ])

    lines.append("});")
    return "\n".join(lines)


# =============================================================================
# Issue #335 + #381: Test File Content Generation
# =============================================================================


def generate_test_file_content(
    scenarios: list[TestScenario],
    module_name: str,
    issue_number: int,
    files_to_modify: list[dict] | None = None,
) -> str:
    """Generate pytest file content from test scenarios.

    Args:
        scenarios: List of test scenarios.
        module_name: Name of the module being tested.
        issue_number: GitHub issue number.
        files_to_modify: List of files from LLD Section 2.1 (for import paths).

    Returns:
        Python test file content.
    """
    # Group scenarios by test type
    unit_tests = [s for s in scenarios if s.get("test_type") == "unit"]
    integration_tests = [s for s in scenarios if s.get("test_type") == "integration"]
    e2e_tests = [s for s in scenarios if s.get("test_type") == "e2e"]
    other_tests = [
        s for s in scenarios
        if s.get("test_type") not in ("unit", "integration", "e2e")
    ]

    # Extract module import path from files_to_modify
    impl_module = _extract_impl_module(files_to_modify)

    lines = [
        '"""Test file for Issue #{issue_number}.',
        "",
        "Generated by AssemblyZero TDD Testing Workflow.",
        "Tests will fail with ImportError until implementation exists (TDD RED phase).",
        '"""',
        "",
        "import pytest",
        "",
    ]

    # Add implementation module import - this is the TDD RED trigger
    if impl_module:
        lines.extend([
            "# TDD: This import fails until implementation exists (RED phase)",
            "# Once implemented, tests can run (GREEN phase)",
            f"from {impl_module} import *  # noqa: F401, F403",
            "",
        ])
    lines.append("")

    # Add fixtures if needed
    if any(s.get("mock_needed") for s in scenarios):
        lines.extend([
            "# Fixtures for mocking",
            "@pytest.fixture",
            "def mock_external_service():",
            '    """Mock external service for isolation."""',
            "    # TODO: Implement mock",
            "    yield None",
            "",
            "",
        ])

    if integration_tests or e2e_tests:
        lines.extend([
            "# Integration/E2E fixtures",
            "@pytest.fixture",
            "def test_client():",
            '    """Test client for API calls."""',
            "    # TODO: Implement test client",
            "    yield None",
            "",
            "",
        ])

    # Generate unit tests
    if unit_tests:
        lines.append("# Unit Tests")
        lines.append("# -----------")
        lines.append("")

        for scenario in unit_tests:
            lines.extend(_generate_test_function(scenario, issue_number))

    # Generate integration tests
    if integration_tests:
        lines.append("")
        lines.append("# Integration Tests")
        lines.append("# -----------------")
        lines.append("")

        for scenario in integration_tests:
            lines.extend(_generate_test_function(scenario, issue_number, fixture="test_client"))

    # Generate E2E tests
    if e2e_tests:
        lines.append("")
        lines.append("# E2E Tests")
        lines.append("# ---------")
        lines.append("")

        for scenario in e2e_tests:
            lines.extend(_generate_test_function(scenario, issue_number, fixture="test_client"))

    # Generate other tests
    if other_tests:
        lines.append("")
        lines.append("# Other Tests")
        lines.append("# -----------")
        lines.append("")

        for scenario in other_tests:
            lines.extend(_generate_test_function(scenario, issue_number))

    # Format issue_number in docstring
    content = "\n".join(lines)
    content = content.replace("{issue_number}", str(issue_number))

    return content


class ScaffoldImportError(ValueError):
    """The scaffold cannot say which plan file defines a name the suite uses (#4148).

    Raised, never guessed: assigning the name to the first Add file is what
    gave boostgauge #2's run 59 an import of `GaugeWidget` from the wrong
    module, which no implementation could satisfy.
    """


def _is_test_path(path: str) -> bool:
    """A planned test file, by the rule `_extract_impl_module` uses."""
    return "test" in path.lower()


def _top_level_definitions(tree: ast.Module) -> dict[str, ast.stmt]:
    """Names a module defines at top level: classes, functions, assignments."""
    defs: dict[str, ast.stmt] = {}
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs[stmt.name] = stmt
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    defs[target.id] = stmt
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            defs[stmt.target.id] = stmt
    return defs


def _import_binding(tree: ast.Module, name: str) -> str | None:
    """The import line, rendered for `name` alone, that binds it at top level."""
    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                if (alias.asname or alias.name) == name:
                    source = "." * stmt.level + (stmt.module or "")
                    rename = f" as {alias.asname}" if alias.asname else ""
                    return f"from {source} import {alias.name}{rename}"
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if (alias.asname or alias.name.split(".")[0]) == name:
                    rename = f" as {alias.asname}" if alias.asname else ""
                    return f"import {alias.name}{rename}"
    return None


def _definition_source(code: str, node: ast.stmt) -> str:
    """A top-level definition's source, decorators included."""
    lines = code.splitlines()
    decorators = getattr(node, "decorator_list", [])
    start = (decorators[0].lineno if decorators else node.lineno) - 1
    return "\n".join(lines[start:node.end_lineno])


def resolve_red_phase_imports(
    symbols: list[str],
    plan_code: dict[str, str],
    files_to_modify: list[dict] | None,
) -> tuple[list[str], list[str]]:
    """Which module each implementation name comes from, read from the plan (#4148).

    R1: each name resolves to the plan file whose Section 6 code defines it at
    module level, and names are grouped into one import line per module.

    R2: a name defined only in a planned TEST file is a test helper. Its
    definition is COPIED into the emitted suite, with the import lines from
    its own file that it needs; it is never imported from an implementation
    module. Copying, not importing from the test module, because the contract
    suite must not depend on another test file the implementer has yet to
    write, or on that file being importable as a package.

    R3: a name defined in more than one implementation file (or more than one
    test file), or in none, raises ScaffoldImportError naming it and the files.

    R4: when no resolved module is one the plan adds, the first Add module is
    imported too, so the suite still fails at collection before the
    implementation exists.

    Returns ``(import_lines, helper_lines)``.
    """
    added_paths = {
        str(f.get("path", "")) for f in files_to_modify or []
        if str(f.get("change_type", "")).lower() == "add"
    }
    parsed: dict[str, tuple[str, ast.Module, dict[str, ast.stmt]]] = {}
    unparseable: list[str] = []
    for path, code in plan_code.items():
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            # An Add file's Section 6 is its complete code. If it does not
            # parse, a name it defines could be resolved to another file
            # unseen, so the scaffold stops. A Modify file's Section 6 may
            # legitimately be an excerpt; it is named in any error below.
            if path in added_paths:
                raise ScaffoldImportError(
                    f"the Section 6 code for {path} (Add) does not parse "
                    f"(line {exc.lineno}: {exc.msg}), so the names it defines "
                    f"cannot be read (#4148)"
                ) from exc
            unparseable.append(path)
            continue
        parsed[path] = (code, tree, _top_level_definitions(tree))

    by_module: dict[str, list[str]] = {}
    helper_imports: list[str] = []
    helpers: list[str] = []
    builtin_names = set(dir(builtins))
    pending = list(symbols)
    seen: set[str] = set()
    while pending:
        name = pending.pop(0)
        if name in seen:
            continue
        seen.add(name)
        where = [path for path, (_c, _t, defs) in parsed.items() if name in defs]
        impl = [path for path in where if not _is_test_path(path)]
        tests = [path for path in where if _is_test_path(path)]
        if len(impl) > 1 or (not impl and len(tests) > 1):
            files = impl or tests
            raise ScaffoldImportError(
                f"`{name}` is defined at module level in more than one planned "
                f"file ({', '.join(files)}), so the Section 10 suite cannot say "
                f"which to import it from (#4148)"
            )
        if impl:
            by_module.setdefault(_path_to_module(impl[0]), []).append(name)
            continue
        if tests:
            code, tree, defs = parsed[tests[0]]
            node = defs[name]
            helpers.append(_definition_source(code, node))
            needed = {
                sub.id for sub in ast.walk(node)
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load)
            } - _names_bound_in(node) - builtin_names
            for dependency in sorted(needed):
                line = _import_binding(tree, dependency)
                if line:
                    if line not in helper_imports:
                        helper_imports.append(line)
                else:
                    pending.append(dependency)
            continue
        note = (
            f"; Section 6 code that does not parse, and so could not be read: "
            f"{', '.join(unparseable)}" if unparseable else ""
        )
        raise ScaffoldImportError(
            f"`{name}` is used by the Section 10 tests, but no planned file's "
            f"Section 6 code defines it at module level{note} (#4148)"
        )

    import_lines = [
        f"from {module} import {', '.join(sorted(names))}  # noqa: F401"
        for module, names in sorted(by_module.items())
    ]

    added = [
        _path_to_module(str(f.get("path", "")))
        for f in files_to_modify or []
        if str(f.get("change_type", "")).lower() == "add"
        and str(f.get("path", "")).endswith(".py")
        and not _is_test_path(str(f.get("path", "")))
        and not str(f.get("path", "")).endswith("__init__.py")
    ]
    if added and not any(module in added for module in by_module):
        import_lines.append(f"import {added[0]}  # noqa: F401")

    helper_lines: list[str] = []
    if helpers:
        helper_lines = [
            "# #4148: test helpers the spec defines in a planned test file,",
            "# copied with the imports they need (never imported from the",
            "# implementation)",
            *helper_imports,
            "",
            "",
            *[block for helper in helpers for block in (helper, "", "")],
        ]
    return import_lines, helper_lines


def generate_spec_test_file_content(
    spec_test_suite: dict,
    issue_number: int,
    files_to_modify: list[dict] | None = None,
    repo_root: Path | str | None = None,
) -> str:
    """Emit the spec's executable test functions verbatim (#2316).

    The spec author already wrote runnable tests with real assertions. The
    scaffolder's job here is transcription, not generation: anything it
    "improves" is a place the emitted suite can drift from the contract the
    spec set.

    The only additions are a provenance docstring; when the spec's own
    import block does not already import the implementation module, the TDD
    red-phase import that makes the suite fail before implementation exists
    -- by NAME, for the implementation symbols the bodies use (#2888), and
    `import *` only when they use none; and (#2887) a module-level
    `import <module>` for each module a body uses without importing --
    `repo_root` says which modules the target declares.
    """
    impl_module = _extract_impl_module(files_to_modify)
    imports = (spec_test_suite.get("imports") or "").strip()
    functions = spec_test_suite.get("functions") or []

    head = [
        f'"""Test file for Issue #{issue_number}.',
        "",
        "Emitted by AssemblyZero from the implementation spec's Section 10",
        "test functions. Bodies are the spec's own, verbatim (#2316).",
        '"""',
        "",
    ]
    if imports:
        head.append(imports)
        head.append("")

    body = [""]
    for fn in functions:
        body.append(fn["source"].rstrip())
        body.append("")
        body.append("")

    # The red-phase trigger, only when the spec's imports do not already
    # reach the implementation module. A duplicate import is harmless but
    # noisy, and a missing one costs the RED signal entirely.
    needs_red_phase = bool(impl_module) and (
        f"import {impl_module}" not in imports
        and f"from {impl_module}" not in imports
    )

    # One reading of the bodies decides both repairs. The draft carries the
    # star form so the analysis sees exactly the file the bodies live in;
    # a star-import binds nothing to the analysis either way.
    draft = "\n".join([*head, *body]).rstrip() + "\n"
    unbound = unbound_names(draft, repo_root)
    repairs = unbound["modules"]
    symbols = unbound["symbols"]

    # #2887: a body that uses a module it never imports fails on NameError in
    # every iteration, and nothing downstream can touch a scaffold file.
    repair_block: list[str] = []
    if repairs:
        for module, used_by in repairs:
            print(
                f"    [N2] {used_by} uses {module} without importing it; "
                f"added 'import {module}' (#2887)"
            )
        repair_block = [
            "# #2887: modules the spec's bodies use without importing them",
            *[f"import {module}" for module, _ in repairs],
            "",
        ]

    # #2888: the bodies name the implementation's symbols, so the red-phase
    # import names them too. `import *` drops every underscore name by
    # Python's own rule -- run-issue4-011019's `_psutil_cmdline` could never
    # arrive through it -- and hides a missing symbol as a NameError three
    # iterations later, when a named import fails at collection with the
    # module and the symbol in the message. The star form remains for a
    # suite whose bodies use no implementation name at all: the RED signal
    # must still come from somewhere.
    red_block: list[str] = []
    helper_block: list[str] = []
    plan_code = spec_test_suite.get("plan_code")
    if symbols and plan_code is not None:
        # #4148: each name from the plan file that defines it, one import line
        # per module. Raises ScaffoldImportError on an ambiguous or undefined
        # name rather than guessing the first Add file.
        import_lines, helper_block = resolve_red_phase_imports(
            [symbol for symbol, _ in symbols], plan_code, files_to_modify,
        )
        print(
            f"    [N2] red-phase imports for {len(symbols)} symbol(s), by "
            f"defining file: {'; '.join(import_lines)} (#4148)"
        )
        red_block = [
            "# TDD: these imports fail until the implementation exists (RED phase)",
            *import_lines,
            "",
        ]
    elif needs_red_phase:
        if symbols:
            names = ", ".join(symbol for symbol, _ in symbols)
            print(
                f"    [N2] red-phase import names {len(symbols)} symbol(s) "
                f"from {impl_module}: {names} (#2888)"
            )
            red_block = [
                "# TDD: this import fails until the implementation exists (RED phase)",
                f"from {impl_module} import {names}  # noqa: F401",
                "",
            ]
        else:
            red_block = [
                "# TDD: this import fails until the implementation exists (RED phase)",
                f"from {impl_module} import *  # noqa: F401, F403",
                "",
            ]

    return "\n".join([*head, *repair_block, *red_block, *helper_block, *body]).rstrip() + "\n"


def _names_bound_in(node: ast.AST) -> set[str]:
    """Every name a statement (or a whole function) binds, at any depth."""
    bound: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            bound.add(sub.id)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            for alias in sub.names:
                if alias.name != "*":
                    bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if not isinstance(sub, ast.Lambda):
                bound.add(sub.name)
            args = sub.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                bound.add(arg.arg)
            if args.vararg:
                bound.add(args.vararg.arg)
            if args.kwarg:
                bound.add(args.kwarg.arg)
        elif isinstance(sub, ast.ClassDef):
            bound.add(sub.name)
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            bound.add(sub.name)
        elif isinstance(sub, (ast.Global, ast.Nonlocal)):
            bound.update(sub.names)
        elif isinstance(sub, ast.MatchAs) and sub.name:
            bound.add(sub.name)
    return bound


def unbound_names(
    source: str, repo_root: Path | str | None,
) -> dict[str, list[tuple[str, str]]]:
    """Names the file's test functions use with no binding in scope, in two kinds.

    A name counts as unbound in a function when it is loaded there and bound
    neither in that function (its parameters, assignments, its own imports)
    nor at module level (the module's imports, defs and assignments) and is
    not a builtin. `import psutil` inside `test_req_1` binds nothing for
    `test_req_6` -- which is the case run-issue4-005046 spent three
    iterations on (#2887). A star-import binds nothing here: it is exactly
    the link this analysis exists to replace (#2888).

    Returns `{"modules": [...], "symbols": [...]}`, each a list of
    `(name, first_function_using_it)` sorted by name:

    * `modules` -- IMPORTABLE MODULE NAMES: stdlib, the target's declared
      dependencies (`_read_third_party_packages` on `repo_root`), the
      validator's known third-party set, and any name this environment can
      find a module spec for. The emitter adds `import <name>`.
    * `symbols` -- everything else: the implementation's classes and helpers
      the bodies exercise. The emitter imports them by name from the
      implementation module.

    Raises `ScaffoldImportError` when the source does not parse (ledger 0908,
    line 787), naming the line and the parser's message: the names the
    bodies use cannot be read, so the red-phase imports cannot be built. It
    used to repair nothing and leave the refusal to N2.5, which regenerated a
    transcription that comes out byte for byte the same. And when a module
    finder raises on a name (line 833), naming the name and the cause: a
    name nobody can classify is a symbol nobody can import.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ScaffoldImportError(
            f"the Section 10 test functions do not parse (line {exc.lineno} "
            f"of the emitted file: {exc.msg}), so the names they use cannot "
            f"be read"
        ) from exc

    from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
        _KNOWN_THIRD_PARTY,
        _read_third_party_packages,
    )

    importable: set[str] = set(sys.stdlib_module_names) | set(_KNOWN_THIRD_PARTY)
    if repo_root:
        importable |= _read_third_party_packages(Path(repo_root))

    module_bound: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_bound.add(stmt.name)
        else:
            module_bound |= _names_bound_in(stmt)
    builtin_names = set(dir(builtins))

    found: dict[str, str] = {}
    for stmt in tree.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        bound = module_bound | _names_bound_in(stmt) | builtin_names
        for sub in ast.walk(stmt):
            if not (isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load)):
                continue
            name = sub.id
            if name in bound or name in found:
                continue
            found[name] = stmt.name

    def _is_module(name: str) -> bool:
        if name in importable:
            return True
        # A name this interpreter can find a module spec for is a module,
        # declared or not -- `psutil` on a machine that has it. `find_spec`
        # searches the finders without executing anything.
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError) as exc:
            raise ScaffoldImportError(
                f"`{name}`, used by the Section 10 test {found[name]}, cannot "
                f"be classified as a module or an implementation symbol: the "
                f"module finder raised {type(exc).__name__}: {exc}"
            ) from exc

    return {
        "modules": sorted((n, f) for n, f in found.items() if _is_module(n)),
        "symbols": sorted((n, f) for n, f in found.items() if not _is_module(n)),
    }


def missing_module_imports(
    source: str, repo_root: Path | str | None,
) -> list[tuple[str, str]]:
    """The `modules` half of `unbound_names` (#2887): what `import <name>` repairs."""
    return unbound_names(source, repo_root)["modules"]


def _generate_test_function(
    scenario: TestScenario,
    issue_number: int,
    fixture: str | None = None,
) -> list[str]:
    """Generate a single test function.

    Args:
        scenario: Test scenario.
        issue_number: GitHub issue number.
        fixture: Optional fixture to include in function signature.

    Returns:
        Lines of the test function.
    """
    name = scenario.get("name", "test_unnamed")
    # Ensure name starts with test_
    if not name.startswith("test_"):
        name = f"test_{name}"

    # Clean up name to be a valid Python identifier
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name)  # Remove duplicate underscores

    description = scenario.get("description", "")
    requirement_ref = scenario.get("requirement_ref", "")
    assertions = scenario.get("assertions", [])
    mock_needed = scenario.get("mock_needed", False)
    test_type = scenario.get("test_type", "unit").lower()

    lines = []

    # Add pytest markers for non-unit test types
    # This enables e2e_validation.py to filter with '-m e2e or integration'
    if test_type == "e2e":
        lines.append("@pytest.mark.e2e")
    elif test_type == "integration":
        lines.append("@pytest.mark.integration")

    # Function signature
    if fixture:
        if mock_needed:
            lines.append(f"def {name}({fixture}, mock_external_service):")
        else:
            lines.append(f"def {name}({fixture}):")
    elif mock_needed:
        lines.append(f"def {name}(mock_external_service):")
    else:
        lines.append(f"def {name}():")

    # Docstring
    docstring_lines = ['    """']
    if description:
        # Wrap description at 70 chars
        wrapped = _wrap_text(description, 70)
        for line in wrapped:
            docstring_lines.append(f"    {line}")
    else:
        docstring_lines.append(f"    Test: {name}")

    if requirement_ref:
        docstring_lines.append("")
        docstring_lines.append(f"    Requirement: {requirement_ref}")

    if assertions:
        docstring_lines.append("")
        docstring_lines.append("    Assertions:")
        for assertion in assertions[:3]:  # Limit to 3
            docstring_lines.append(f"    - {assertion}")

    docstring_lines.append('    """')
    lines.extend(docstring_lines)

    # Test body - TDD style
    # The import at the top of the file will fail until implementation exists
    # Once implemented, these assertions will run
    lines.append("    # TDD: Arrange")
    lines.append("    # Set up test data")
    lines.append("")
    lines.append("    # TDD: Act")
    lines.append("    # Call the function under test")
    lines.append("")
    lines.append("    # TDD: Assert")

    # Convert assertion descriptions to actual assertions
    # Issue #261: Use assert False as failsafe - tests MUST fail until implemented
    if assertions:
        for i, assertion in enumerate(assertions[:3]):
            # Generate a failing assertion based on the description
            lines.append(f"    # {assertion}")
            lines.append(f"    assert False, 'TDD RED: {assertion}'")
        lines.append("")
    else:
        # Default assertion if no specific ones provided
        lines.append(f"    # Verify {name} works correctly")
        lines.append(f"    assert False, 'TDD RED: {name} not implemented'")
        lines.append("")

    lines.append("")

    return lines


def _wrap_text(text: str, width: int) -> list[str]:
    """Wrap text at specified width."""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        if current_length + len(word) + 1 <= width:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)

    if current_line:
        lines.append(" ".join(current_line))

    return lines if lines else [""]


class ScaffoldPathError(ValueError):
    """A scaffold would land where no framework of the run runs it (#4243).

    Raised, never written: a scaffold no framework collects fails nothing in
    the red phase and is graded by nothing in the green one.
    """


#: The directory a JavaScript framework's scaffold goes in, beneath the
#: framework's own directory (#4243). Vitest's, Jest's and Playwright's
#: default test patterns all collect it. Their config files are JavaScript
#: or TypeScript modules the run does not evaluate, so a narrower `include`
#: or `testDir` a project declares there is not read.
JS_SCAFFOLD_DIR = "tests"


def scaffold_path_for(
    issue_number: int, repo_root: Path | str, framework_config: dict | None = None,
) -> Path:
    """Where N2 writes a framework's scaffold, without touching the disk.

    pytest's is `tests/test_issue_<N>.py` at the root, as it always was. A
    JavaScript framework's is `<its directory>/tests/issue_<N><ext>` (#4243):
    it used to be the root's `tests/` whatever the framework's
    `working_directory`, where Vitest in `web/` never looks.
    """
    root = Path(repo_root)
    framework = resolve_framework(framework_config) if framework_config else None
    if framework in (TestFramework.PLAYWRIGHT, TestFramework.JEST, TestFramework.VITEST):
        ext = framework_config.get("test_file_extension") or (
            ".spec.ts" if framework == TestFramework.PLAYWRIGHT else ".test.ts"
        )
        directory = framework_config.get("working_directory") or "."
        return root / directory / JS_SCAFFOLD_DIR / f"issue_{issue_number}{ext}"
    return root / "tests" / f"test_issue_{issue_number}.py"


def _require_owned_by(
    path: Path, framework_config: dict, run_configs: list[dict] | None, repo_root: Path,
) -> None:
    """Raise ScaffoldPathError unless the run's ownership rule gives `path`
    to the framework it is the scaffold of (#4243)."""
    frameworks = run_frameworks({"framework_configs": run_configs or [framework_config]})
    framework = resolve_framework(framework_config)
    directory = os.path.normpath(framework_config.get("working_directory") or ".")
    label = framework_label(framework, directory)
    try:
        owner = frameworks[owner_of(str(path), frameworks, str(repo_root))]
    except TestFileOwnershipError as e:
        raise ScaffoldPathError(f"the {label} scaffold cannot be placed: {e}") from e
    if (owner.framework, owner.directory) != (framework, directory):
        raise ScaffoldPathError(
            f"the {label} scaffold {path} would be run by {owner.label}, not "
            f"by {label}"
        )


def determine_test_file_path(
    issue_number: int,
    scenarios: list[TestScenario],
    repo_root: Path,
    framework_config: FrameworkConfig | None = None,
    run_configs: list[dict] | None = None,
) -> Path:
    """Determine the appropriate path for the test file, and make its directory.

    Issue #381: Now supports framework-aware file extensions via
    optional framework_config parameter.

    #4243: a JavaScript framework's scaffold goes in that framework's own
    directory (`scaffold_path_for`), and the path must be one the run's
    ownership rule gives to that framework among `run_configs` (the run's
    `framework_configs`; the framework alone when absent). Raises
    ScaffoldPathError naming the path and the frameworks when it is not,
    before any directory is made.

    Args:
        issue_number: GitHub issue number.
        scenarios: List of test scenarios.
        repo_root: Repository root path.
        framework_config: Optional framework config for file extension.
        run_configs: Every framework of the run, as N0 wrote them.

    Returns:
        Path for the test file.
    """
    path = scaffold_path_for(issue_number, repo_root, framework_config)
    framework = resolve_framework(framework_config) if framework_config else None
    if framework not in (None, TestFramework.PYTEST):
        _require_owned_by(path, dict(framework_config), run_configs, Path(repo_root))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _require_audit_dir(state: TestingWorkflowState) -> Path:
    """The run's audit directory, which N0 made, or FileNotFoundError.

    Ledger 0908, lines 1069 and 1199: the scaffold's audit copy was skipped
    without a word when the directory was missing, so the run's lineage
    lacked the suite it went on to test. An unset `audit_dir` was worse:
    `Path("")` is the working directory, which exists, so the copy landed in
    whatever directory the run was started in. Both callers turn the raise
    into N2's halt, before anything is written.
    """
    named = state.get("audit_dir") or ""
    if not named:
        raise FileNotFoundError(
            "the run's state names no audit directory, so the scaffold's "
            "audit copy has nowhere to go (N0 makes the directory)"
        )
    audit_dir = Path(named)
    if not audit_dir.is_dir():
        raise FileNotFoundError(
            f"the run's audit directory {audit_dir} does not exist, so the "
            f"scaffold's audit copy cannot be written"
        )
    return audit_dir


# =============================================================================
# Issue #381: Non-Python Test Scaffolding Helper
# =============================================================================


def _scaffold_non_python_tests(
    state: TestingWorkflowState,
    framework_config: FrameworkConfig,
) -> dict[str, Any]:
    """Scaffold non-Python test files (Playwright, Jest, Vitest).

    Issue #381: Generates TypeScript test files based on framework config.
    """
    issue_number = state.get("issue_number", 0)
    scenarios = state.get("test_scenarios", [])
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    # Ledger 0908, line 1069: checked before anything is written.
    audit_dir = _require_audit_dir(state)

    # Generate TypeScript test content
    content = generate_ts_test_file_content(scenarios, framework_config, issue_number)

    # Determine file path: in the framework's own directory, where the run's
    # ownership rule gives it to this framework (#4243).
    test_file_path = determine_test_file_path(
        issue_number, scenarios, repo_root, framework_config,
        run_configs=state.get("framework_configs") or None,
    )

    # Write the file
    test_file_path.parent.mkdir(parents=True, exist_ok=True)
    test_file_path.write_text(content, encoding="utf-8")

    gate_log(f"[N2] Scaffolded {framework_config['framework'].value} test: {test_file_path}")
    # #3067: said out loud, because nothing of this file can pass: each of
    # its tests is a placeholder that fails until N4 writes the real one.
    print(
        f"    [N2] {framework_config['framework'].value}: {len(scenarios)} "
        f"placeholder test(s), each failing until replaced (the spec ships "
        f"no {framework_config['framework'].value} test bodies)"
    )
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=issue_number,
        workflow_type="testing",
        event="tests_scaffolded",
        details={
            "test_file": str(test_file_path),
            "framework": framework_config["framework"].value,
            "test_count": len(scenarios),
        },
    )

    # Save to audit trail
    file_num = next_file_number(audit_dir)
    ext = framework_config["test_file_extension"]
    save_audit_file(audit_dir, file_num, f"test-scaffold{ext}", content)

    # #3081: the key the validator reads, the one #789 named. This path
    # returned `test_file_content`, which nothing read, so every Playwright,
    # Jest and Vitest scaffold was validated as an empty file.
    return {
        "test_files": [str(test_file_path)],
        "generated_tests": content,
        "file_counter": file_num,
        "error_message": "",
    }


# =============================================================================
# Issue #335 + #381: Main Scaffold Node
# =============================================================================


def _halt_scaffold_framework(label: str, cause: str) -> dict[str, Any]:
    """N2's halt when one framework of the run cannot be scaffolded (#4244).

    Routed to HALT by `route_after_scaffold`, and HALT alerts the operator.
    Deterministic: the same tree and the same plan fail the same way again.
    """
    message = (
        f"{DETERMINISTIC_FAILURE}: [N2] the {label} tests cannot be "
        f"scaffolded: {cause}. N2 stops here: every framework of the run is "
        f"scaffolded, or the run does not go on (#4244)."
    )
    print(f"ERROR [N2] {message}", file=sys.stderr)
    return {"error_message": message}


def _scaffold_every_framework(
    state: TestingWorkflowState, frameworks: list[RunFramework],
) -> dict[str, Any]:
    """N2 for a run with more than one framework (#4244): each framework's
    scaffold, by its own scaffolder, in the order N0 wrote them.

    `generated_tests` stays the Python scaffold when pytest is one of them,
    because the pytest validator reads that key (#789); every other
    framework's scaffold is read from disk by its own validator. A framework
    whose scaffold cannot be built halts N2 naming it.
    """
    test_files: list[str] = []
    generated: str | None = None
    file_counter = state.get("file_counter", 0)
    for run in frameworks:
        try:
            if run.framework == TestFramework.PYTEST:
                result = _scaffold_python_tests(state)
            else:
                result = _scaffold_non_python_tests(
                    state, {**run.config, "framework": run.framework}
                )
        except (ValueError, OSError) as e:
            return _halt_scaffold_framework(run.label, f"{type(e).__name__}: {e}")
        if result.get("error_message"):
            return result
        test_files.extend(result.get("test_files", []))
        file_counter = result.get("file_counter", file_counter)
        content = result.get("generated_tests", "")
        if run.framework == TestFramework.PYTEST or generated is None:
            generated = content
    return {
        "test_files": test_files,
        "generated_tests": generated or "",  # Issue #789: validate_tests_mechanical reads this
        "file_counter": file_counter,
        "error_message": "",
    }


def scaffold_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """N2: Generate executable test stubs.

    Issue #381: Now supports multi-framework scaffolding. If framework_config
    is present in state and specifies a non-pytest framework, delegates to
    TypeScript scaffolding. Otherwise, uses existing pytest scaffolding.

    #4244: a run with more than one framework (`framework_configs`, #4236)
    gets every framework's scaffold; it used to get the first's alone.

    Args:
        state: Current workflow state.

    Returns:
        State updates with test file paths.
    """
    gate_log("[N2] Scaffolding tests...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_scaffold_tests(state)

    # Issue #547: Skip-on-resume — don't re-call Claude if tests already scaffolded
    # Issue #571: BUT if validation errors exist, this is a regeneration loop,
    # not a resume. Delete stale files so scaffold can regenerate.
    existing_test_files = state.get("test_files", [])
    if existing_test_files and all(Path(f).exists() for f in existing_test_files):
        if state.get("scaffold_validation_errors"):
            gate_log(f"[N2] Regeneration: deleting {len(existing_test_files)} stale test files")
            for f in existing_test_files:
                Path(f).unlink(missing_ok=True)
        else:
            gate_log(f"[N2] {len(existing_test_files)} test files already exist — skipping scaffold")
            return {}

    # #4244: every framework of the run, when there is more than one.
    try:
        frameworks = run_frameworks(state)
    except TestFileOwnershipError as e:
        return _halt_scaffold_framework("run's", str(e))
    if len(frameworks) > 1:
        return _scaffold_every_framework(state, frameworks)

    # Issue #381: Framework-aware scaffolding
    framework_config = state.get("framework_config")

    # If framework_config names a framework other than pytest, use TS
    # scaffolding. #3732: the state carries the framework as its string value
    # (#3708), so it is resolved to the enum before any comparison, and the
    # non-Python path gets the enum back for its `.value` and `get_runner`.
    framework = resolve_framework(framework_config)
    if framework is not None and framework != TestFramework.PYTEST:
        try:
            return _scaffold_non_python_tests(
                state, {**framework_config, "framework": framework}
            )
        except (ValueError, OSError) as e:
            # #4243: a scaffold no framework would run, or a runner that
            # cannot start, stops N2 the way it does with several frameworks.
            return _halt_scaffold_framework(frameworks[0].label, f"{type(e).__name__}: {e}")

    try:
        return _scaffold_python_tests(state)
    except (ValueError, OSError) as e:
        # Ledger 0908, line 1199: a missing audit directory, or any scaffold
        # that cannot be written, stops N2 as it does with several frameworks.
        return _halt_scaffold_framework(frameworks[0].label, f"{type(e).__name__}: {e}")


def _scaffold_python_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """The pytest scaffold: the spec's own Section 10 functions, verbatim
    (#2316), or generated from scenario metadata when it ships none."""
    # Get data from state
    issue_number = state.get("issue_number", 0)
    test_scenarios = state.get("test_scenarios", [])
    files_to_modify = state.get("files_to_modify", [])
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    # Issue #500: Log previous validation errors if re-scaffolding
    scaffold_validation_errors = state.get("scaffold_validation_errors", [])
    if scaffold_validation_errors:
        print(f"    Previous validation errors ({len(scaffold_validation_errors)}):")
        for err in scaffold_validation_errors[:5]:
            print(f"      - {err}")
        if len(scaffold_validation_errors) > 5:
            print(f"      ... and {len(scaffold_validation_errors) - 5} more")

    # --------------------------------------------------------------------------
    # GUARD: Validate scenarios
    # --------------------------------------------------------------------------
    if not test_scenarios:
        print("    [GUARD] BLOCKED: No test scenarios to scaffold")
        return {
            "error_message": "GUARD: No test scenarios available",
        }
    # --------------------------------------------------------------------------

    # Ledger 0908, line 1199: checked before anything is written.
    audit_dir = _require_audit_dir(state)

    # #2316: when the spec ships executable test functions they ARE the
    # suite. Emitting them verbatim is what makes the TDD loop able to
    # converge at all — the generated-stub path below produces
    # `assert False` bodies that no implementation can satisfy.
    spec_test_suite = state.get("spec_test_suite") or {}
    use_spec_bodies = bool(spec_test_suite.get("functions"))

    if use_spec_bodies:
        print(
            f"    Emitting {len(spec_test_suite['functions'])} executable test "
            f"functions from the spec, verbatim"
        )
    else:
        print(f"    Scaffolding {len(test_scenarios)} test scenarios")

    # Determine test file path
    test_file_path = determine_test_file_path(issue_number, test_scenarios, repo_root)
    print(f"    Test file: {test_file_path}")

    # Generate test file content
    module_name = f"issue_{issue_number}"
    if use_spec_bodies:
        try:
            content = generate_spec_test_file_content(
                spec_test_suite, issue_number, files_to_modify,
                repo_root=repo_root,
            )
        except ScaffoldImportError as exc:
            # #4148: stop loudly; the N2 router sends error_message to HALT.
            message = f"Scaffold cannot build the red-phase imports: {exc}"
            print(f"ERROR [N2] {message}", file=sys.stderr)
            return {"error_message": message}
        emitted = len(spec_test_suite["functions"])
    else:
        content = generate_test_file_content(
            test_scenarios, module_name, issue_number, files_to_modify
        )
        emitted = len(test_scenarios)

    # Write test file
    test_file_path.write_text(content, encoding="utf-8")
    print(f"    Generated {emitted} tests")

    # Save to audit trail
    file_num = next_file_number(audit_dir)
    save_audit_file(audit_dir, file_num, "test-scaffold.py", content)

    # Log scaffolding
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=issue_number,
        workflow_type="testing",
        event="tests_scaffolded",
        details={
            "test_file": str(test_file_path),
            "test_count": emitted,
        },
    )

    return {
        "test_files": [str(test_file_path)],
        "generated_tests": content,  # Issue #789: validate_tests_mechanical reads this
        "file_counter": file_num,
        "error_message": "",
    }


def _mock_scaffold_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    issue_number = state.get("issue_number", 42)
    test_scenarios = state.get("test_scenarios", [])
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    # Generate actual test file for mock mode too
    test_file_path = determine_test_file_path(issue_number, test_scenarios, repo_root)

    if test_scenarios:
        content = generate_test_file_content(test_scenarios, f"issue_{issue_number}", issue_number)
    else:
        content = '''"""Mock test file for testing."""

import pytest


def test_mock_example():
    """Mock test that will fail."""
    assert False, "TDD: Implementation pending for test_mock_example"
'''

    test_file_path.write_text(content, encoding="utf-8")

    # Save to audit
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "test-scaffold.py", content)
    else:
        file_num = state.get("file_counter", 0)

    print(f"    [MOCK] Scaffolded tests to {test_file_path}")

    return {
        "test_files": [str(test_file_path)],
        "generated_tests": content,  # Issue #789: validate_tests_mechanical reads this
        "file_counter": file_num,
        "error_message": "",
    }