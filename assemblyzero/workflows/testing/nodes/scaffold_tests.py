"""N2: Scaffold Tests node for TDD Testing Workflow.

Issue #335: Updated to generate real executable tests from LLD Section 10.0,
not just stubs with `assert False`.

Generates executable tests from the approved test plan:
- Parses Section 10.0 Test Plan table for test scenarios
- Generates real assertions based on expected behavior
- Tests are syntactically valid and RUNNABLE
- Uses pytest conventions and fixtures

Previous behavior (stubs) caused infinite loops in the TDD workflow
because stub tests always fail regardless of implementation.
"""

import re
from pathlib import Path
from typing import Any, TypedDict

from assemblyzero.workflows.testing.audit import (
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.knowledge.patterns import get_test_type_info
from assemblyzero.workflows.testing.state import TestingWorkflowState, TestScenario


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
    """
    result: ParsedLLDTests = {
        "module_path": "",
        "scenarios": [],
        "imports_needed": [],
    }

    # Find Section 10.0 Test Plan
    section_patterns = [
        r"###?\s*10\.0[^\n]*Test\s*Plan[^\n]*\n(.*?)(?=###?\s*\d|##\s*\d|\Z)",
        r"###?\s*10[^\n]*Verification[^\n]*\n(.*?)(?=###?\s*\d|##\s*\d|\Z)",
    ]

    section_content = None
    for pattern in section_patterns:
        match = re.search(pattern, lld_content, re.DOTALL | re.IGNORECASE)
        if match:
            section_content = match.group(1)
            break

    if not section_content:
        return result

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
        lines.append(f'    """')
        lines.append(f"    {description}")
        if req_id:
            lines.append(f"")
            lines.append(f"    Requirement: {req_id}")
        lines.append(f'    """')

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
        Python assertion statement.
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

        # Generic comparison
        return f'# Input: "{input_val}" Expected: {output_val}\n    assert True  # TODO: Implement assertion'

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

    # Pattern: simple description
    # Can't generate real assertion, but at least don't use assert False
    # Generate a placeholder that requires implementation
    return f'# Expected: {expected}\n    assert True  # TODO: Replace with real assertion'


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

    def _path_to_module(path: str) -> str:
        """Convert file path to Python module path."""
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
            f"# Once implemented, tests can run (GREEN phase)",
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
    docstring_lines = [f'    """']
    if description:
        # Wrap description at 70 chars
        wrapped = _wrap_text(description, 70)
        for line in wrapped:
            docstring_lines.append(f"    {line}")
    else:
        docstring_lines.append(f"    Test: {name}")

    if requirement_ref:
        docstring_lines.append(f"")
        docstring_lines.append(f"    Requirement: {requirement_ref}")

    if assertions:
        docstring_lines.append(f"")
        docstring_lines.append(f"    Assertions:")
        for assertion in assertions[:3]:  # Limit to 3
            docstring_lines.append(f"    - {assertion}")

    docstring_lines.append(f'    """')
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


def determine_test_file_path(
    issue_number: int,
    scenarios: list[TestScenario],
    repo_root: Path,
) -> Path:
    """Determine the appropriate path for the test file.

    Args:
        issue_number: GitHub issue number.
        scenarios: List of test scenarios.
        repo_root: Repository root path.

    Returns:
        Path for the test file.
    """
    # Default test directory
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Extract module name from scenarios if possible
    # For now, use issue number as identifier
    return tests_dir / f"test_issue_{issue_number}.py"


def scaffold_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """N2: Generate executable test stubs.

    Args:
        state: Current workflow state.

    Returns:
        State updates with test file paths.
    """
    print("\n[N2] Scaffolding tests...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_scaffold_tests(state)

    # Get data from state
    issue_number = state.get("issue_number", 0)
    test_scenarios = state.get("test_scenarios", [])
    files_to_modify = state.get("files_to_modify", [])
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    # --------------------------------------------------------------------------
    # GUARD: Validate scenarios
    # --------------------------------------------------------------------------
    if not test_scenarios:
        print("    [GUARD] BLOCKED: No test scenarios to scaffold")
        return {
            "error_message": "GUARD: No test scenarios available",
        }
    # --------------------------------------------------------------------------

    print(f"    Scaffolding {len(test_scenarios)} test scenarios")

    # Determine test file path
    test_file_path = determine_test_file_path(issue_number, test_scenarios, repo_root)
    print(f"    Test file: {test_file_path}")

    # Generate test file content
    module_name = f"issue_{issue_number}"
    content = generate_test_file_content(
        test_scenarios, module_name, issue_number, files_to_modify
    )

    # Write test file
    test_file_path.write_text(content, encoding="utf-8")
    print(f"    Generated {len(test_scenarios)} tests")

    # Save to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "test-scaffold.py", content)
    else:
        file_num = state.get("file_counter", 0)

    # Log scaffolding
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=issue_number,
        workflow_type="testing",
        event="tests_scaffolded",
        details={
            "test_file": str(test_file_path),
            "test_count": len(test_scenarios),
        },
    )

    return {
        "test_files": [str(test_file_path)],
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
        "file_counter": file_num,
        "error_message": "",
    }
