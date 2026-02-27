# Implementation Request: assemblyzero/workflows/testing/nodes/adversarial_validator.py

## Task

Write the complete contents of `assemblyzero/workflows/testing/nodes/adversarial_validator.py`.

Change type: Add
Description: AST-based test validation

## LLD Specification

# Implementation Spec: Multi-Model Adversarial Testing Node (Gemini vs Claude)

| Field | Value |
|-------|-------|
| Issue | #352 |
| LLD | `docs/lld/active/352-adversarial-testing-node.md` |
| Generated | 2026-02-27 |
| Status | DRAFT |

## 1. Overview

This implementation adds a LangGraph node to the Testing Workflow (N2.7) that uses Gemini Pro to analyze Claude's implementation and LLD claims, generating aggressive adversarial tests with zero mocks. The node integrates as a non-blocking step with graceful degradation on Gemini unavailability.

**Objective:** Integrate a Gemini-powered adversarial test generation node into the existing testing workflow StateGraph.

**Success Criteria:** Adversarial node generates valid pytest files in `tests/adversarial/`, enforces no-mock constraint via AST analysis, and skips gracefully on Gemini errors.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/workflows/testing/adversarial_state.py` | Add | TypedDict state extensions |
| 2 | `assemblyzero/workflows/testing/knowledge/adversarial_patterns.py` | Add | Adversarial pattern knowledge base |
| 3 | `assemblyzero/workflows/testing/adversarial_prompts.py` | Add | Prompt templates for Gemini |
| 4 | `assemblyzero/workflows/testing/adversarial_gemini.py` | Add | Gemini client wrapper |
| 5 | `assemblyzero/workflows/testing/nodes/adversarial_validator.py` | Add | AST-based test validation |
| 6 | `assemblyzero/workflows/testing/nodes/adversarial_writer.py` | Add | Test file writer |
| 7 | `assemblyzero/workflows/testing/nodes/adversarial_node.py` | Add | Core LangGraph node |
| 8 | `tests/adversarial/__init__.py` | Add | Package init |
| 9 | `tests/adversarial/conftest.py` | Add | Shared fixtures |
| 10 | `assemblyzero/workflows/testing/graph.py` | Modify | Wire adversarial node into workflow |
| 11 | `tests/conftest.py` | Modify | Register `adversarial` marker |
| 12 | `pyproject.toml` | Modify | Add `adversarial` pytest marker |
| 13 | `tests/unit/test_adversarial_node.py` | Add | Unit tests for node logic |
| 14 | `tests/unit/test_adversarial_writer.py` | Add | Unit tests for writer |
| 15 | `tests/unit/test_adversarial_validator.py` | Add | Unit tests for validator |
| 16 | `tests/unit/test_adversarial_prompts.py` | Add | Unit tests for prompts |
| 17 | `tests/unit/test_adversarial_gemini.py` | Add | Unit tests for Gemini wrapper |
| 18 | `tests/integration/test_adversarial_integration.py` | Add | Integration test with real Gemini |

**Implementation Order Rationale:** State definitions first (no dependencies), then knowledge base and prompts (depend only on state), then Gemini client (depends on prompts), then validator (standalone), then writer (depends on state/validator), then the orchestrating node (depends on all prior). Graph modification last since it imports the node. Tests implemented alongside their targets.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/testing/graph.py`

**Relevant excerpt — imports** (lines 1-42):

```python
"""StateGraph definition for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #335: Add mechanical test validation node (N2.5)
Issue #147: Add completeness gate node (N4b) between N4 and N5
Issue #292: Exit code routing — N3/N5 can route to N2 on syntax/collection errors
Issue #180: Add cleanup node (N9) after N8

Defines the compiled graph with:
- N0-N9 nodes (plus N2.5 for test validation, N4b for completeness gate)
- Conditional edges for routing
- Checkpoint support via SqliteSaver

Graph structure:
    N0_load_lld -> N1_review_test_plan -> N2_scaffold_tests -> N2_5_validate_tests
           |              |                     |                      |
           v              v                     v                      v
         error         BLOCKED              scaffold_only         validation
           |              |                     |                   result
           v              v                     v                      |
          END     loop back to LLD             END                    / \
                  (outside workflow)                                 /   \
                                                                pass   fail
                                                                 |       |
                                                                 v       v
    N2_5 (pass) -> N3_verify_red -> N4_implement_code ------> N2 (retry)
           |                |                   |               or escalate
           v                v                   v               to N4
        red OK          iteration          N4b_completeness
           |            loop back              |
           v                |                 / \
          N4               N4              PASS  BLOCK
                                            |      |
                                            v      v
                                           N5   N4 (iter<3)
                                                 or END (iter>=3)

    N5_verify_green -> N6_e2e_validation -> N7_finalize -> N8_document -> N9_cleanup -> END
           |                  |                  |               |
           v                  v                  v               v
       iteration          skip_e2e           complete    route_after_doc
       loop back              |                                  |
           |                  v                                 / \
          N4                 N7                            N9     END
                                                          |
                                                          v
                                                         END
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.testing.nodes import (
    cleanup,
    document,
    e2e_validation,
    finalize,
    implement_code,
    load_lld,
    route_after_document,
    review_test_plan,
    scaffold_tests,
    verify_green_phase,
    verify_red_phase,
)

from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
    route_after_completeness_gate,
)

from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    validate_tests_mechanical_node,
    should_regenerate,
)

from assemblyzero.workflows.testing.state import TestingWorkflowState
```

**What changes:** Add import for `run_adversarial_node` and a routing function. Wire the adversarial node between `N5_verify_green` (or after standard test generation) and `evaluate_results`/`N6_e2e_validation`.

**Relevant excerpt — `build_testing_workflow()` function** (this is the function that constructs the StateGraph — actual body uses `...` in provided file but we know it adds nodes and conditional edges):

```python
def build_testing_workflow() -> StateGraph:
    """Build the TDD testing workflow StateGraph.

Issue #147: Added N4b completeness gate between N4 and N5."""
    ...
```

**What changes:** Add adversarial node (`N7_5_adversarial`) between `N7_finalize` and `N8_document`. Add routing function `route_after_adversarial` that always proceeds to `N8_document` (non-blocking).

### 3.2 `tests/conftest.py`

**Relevant excerpt** (lines 1-15):

```python
"""Pytest configuration for test suite."""

import os

import sys

from pathlib import Path

import pytest

def pytest_configure(config):
    """Configure pytest markers."""
    ...
```

**What changes:** Add `adversarial` marker registration inside `pytest_configure`.

### 3.3 `pyproject.toml`

**Relevant excerpt** (markers section):

```toml
[tool.pytest.ini_options]
addopts = "-m 'not integration and not e2e'"
markers = [
    "integration: tests that call real external services (deselect with '-m \"not integration\"')",
    "e2e: end-to-end workflow tests requiring sandbox repo",
    "expensive: tests that use significant API quota",
]
```

**What changes:** Add `adversarial` marker to the list.

## 4. Data Structures

### 4.1 AdversarialTestCase

**Definition:**

```python
class AdversarialTestCase(TypedDict):
    test_id: str
    target_function: str
    category: str
    description: str
    test_code: str
    claim_challenged: str
    severity: Literal["critical", "high", "medium"]
```

**Concrete Example:**

```json
{
    "test_id": "ADV_001",
    "target_function": "assemblyzero.workflows.testing.nodes.scaffold_tests.generate_test_scaffold",
    "category": "boundary",
    "description": "Tests scaffold generation with empty LLD content to verify graceful handling",
    "test_code": "def test_scaffold_empty_lld():\n    from assemblyzero.workflows.testing.nodes.scaffold_tests import generate_test_scaffold\n    result = generate_test_scaffold(\"\")\n    assert result is not None\n    assert result.get(\"error_message\") != \"\"",
    "claim_challenged": "LLD Section 2.4 claims scaffold handles all input formats including empty strings",
    "severity": "high"
}
```

### 4.2 AdversarialAnalysis

**Definition:**

```python
class AdversarialAnalysis(TypedDict):
    uncovered_edge_cases: list[str]
    false_claims: list[str]
    missing_error_handling: list[str]
    implicit_assumptions: list[str]
    test_cases: list[AdversarialTestCase]
```

**Concrete Example:**

```json
{
    "uncovered_edge_cases": [
        "scaffold_tests does not handle LLD content exceeding 500KB",
        "verify_red_phase assumes pytest is always in PATH"
    ],
    "false_claims": [
        "LLD claims 'all Unicode supported' but implementation uses ASCII-only regex at line 42"
    ],
    "missing_error_handling": [
        "implement_code.py line 87: FileNotFoundError not caught when reading implementation files",
        "scaffold_tests.py line 34: No timeout on subprocess.run call"
    ],
    "implicit_assumptions": [
        "graph.py assumes all nodes return within 60 seconds",
        "verify_green_phase assumes test output encoding is UTF-8"
    ],
    "test_cases": [
        {
            "test_id": "ADV_001",
            "target_function": "assemblyzero.workflows.testing.nodes.scaffold_tests.generate_test_scaffold",
            "category": "boundary",
            "description": "Tests scaffold generation with empty LLD content",
            "test_code": "def test_scaffold_empty_lld():\n    from assemblyzero.workflows.testing.nodes.scaffold_tests import generate_test_scaffold\n    result = generate_test_scaffold(\"\")\n    assert result is not None",
            "claim_challenged": "LLD Section 2.4 claims scaffold handles all input formats",
            "severity": "high"
        },
        {
            "test_id": "ADV_002",
            "target_function": "assemblyzero.workflows.testing.nodes.verify_red_phase.verify_red",
            "category": "contract",
            "description": "Verifies red phase returns correct exit code mapping",
            "test_code": "def test_verify_red_exit_code_boundary():\n    from assemblyzero.workflows.testing.nodes.verify_red_phase import verify_red\n    state = {\"test_files\": {}, \"iteration\": 0}\n    result = verify_red(state)\n    assert \"exit_code\" in result\n    assert isinstance(result[\"exit_code\"], int)",
            "claim_challenged": "Exit code routing documented in graph.py assumes codes 0-5 only",
            "severity": "medium"
        }
    ]
}
```

### 4.3 AdversarialNodeState

**Definition:**

```python
class AdversarialNodeState(TypedDict, total=False):
    implementation_files: dict[str, str]
    lld_content: str
    existing_tests: dict[str, str]
    issue_id: int
    adversarial_analysis: AdversarialAnalysis
    generated_test_files: dict[str, str]
    adversarial_verdict: Literal["pass", "fail", "error"]
    adversarial_error: str | None
    adversarial_test_count: int
    adversarial_skipped_reason: str | None
```

**Concrete Example (input state):**

```json
{
    "implementation_files": {
        "assemblyzero/workflows/testing/nodes/scaffold_tests.py": "def generate_test_scaffold(lld: str) -> dict:\n    ...",
        "assemblyzero/workflows/testing/nodes/verify_red_phase.py": "def verify_red(state: dict) -> dict:\n    ..."
    },
    "lld_content": "# 352 - Feature: Multi-Model Adversarial Testing\n## 1. Context & Goal\n...",
    "existing_tests": {
        "tests/unit/test_scaffold.py": "def test_scaffold_basic():\n    assert True"
    },
    "issue_id": 352
}
```

**Concrete Example (output state):**

```json
{
    "implementation_files": {"assemblyzero/workflows/testing/nodes/scaffold_tests.py": "..."},
    "lld_content": "# 352 - Feature...",
    "existing_tests": {"tests/unit/test_scaffold.py": "..."},
    "issue_id": 352,
    "adversarial_analysis": {
        "uncovered_edge_cases": ["empty LLD input"],
        "false_claims": ["claims all Unicode supported"],
        "missing_error_handling": ["FileNotFoundError uncaught"],
        "implicit_assumptions": ["assumes UTF-8 encoding"],
        "test_cases": []
    },
    "generated_test_files": {
        "tests/adversarial/test_352_boundary.py": "# ADVERSARIAL TEST FILE...\ndef test_scaffold_empty_lld():\n    ..."
    },
    "adversarial_verdict": "pass",
    "adversarial_error": null,
    "adversarial_test_count": 3,
    "adversarial_skipped_reason": null
}
```

### 4.4 ValidationResult

**Definition:**

```python
class ValidationResult(TypedDict):
    valid: bool
    errors: list[str]
    warnings: list[str]
    mock_violations: list[str]
```

**Concrete Example:**

```json
{
    "valid": false,
    "errors": [],
    "warnings": ["test_empty_input has no assertions"],
    "mock_violations": [
        "tests/adversarial/test_352_boundary.py:5: Mock import detected: 'from unittest.mock import patch'"
    ]
}
```

## 5. Function Specifications

### 5.1 `run_adversarial_node()`

**File:** `assemblyzero/workflows/testing/nodes/adversarial_node.py`

**Signature:**

```python
def run_adversarial_node(state: AdversarialNodeState) -> AdversarialNodeState:
    """LangGraph node: Orchestrates adversarial test generation via Gemini."""
    ...
```

**Input Example:**

```python
state = {
    "implementation_files": {
        "assemblyzero/workflows/testing/nodes/scaffold_tests.py": "def generate_test_scaffold(lld: str) -> dict:\n    if not lld:\n        return {'error_message': 'empty'}\n    return {'scaffold': lld[:100]}"
    },
    "lld_content": "# 352 - Feature: Adversarial Testing\n## 3. Requirements\n1. Node generates tests\n2. Uses Gemini Pro",
    "existing_tests": {
        "tests/unit/test_scaffold.py": "def test_scaffold_basic():\n    assert generate_test_scaffold('hello') is not None"
    },
    "issue_id": 352,
}
```

**Output Example:**

```python
{
    "implementation_files": {... },  # unchanged
    "lld_content": "...",  # unchanged
    "existing_tests": {... },  # unchanged
    "issue_id": 352,
    "adversarial_analysis": {
        "uncovered_edge_cases": ["empty string input", "None input"],
        "false_claims": [],
        "missing_error_handling": ["No TypeError handling for None input"],
        "implicit_assumptions": ["Assumes lld is always str type"],
        "test_cases": [
            {
                "test_id": "ADV_001",
                "target_function": "scaffold_tests.generate_test_scaffold",
                "category": "boundary",
                "description": "Test with None input",
                "test_code": "def test_scaffold_none_input():\n    ...",
                "claim_challenged": "Handles all input formats",
                "severity": "high"
            }
        ]
    },
    "generated_test_files": {
        "tests/adversarial/test_352_boundary.py": "# ADVERSARIAL TEST FILE...\n..."
    },
    "adversarial_verdict": "pass",
    "adversarial_error": None,
    "adversarial_test_count": 1,
    "adversarial_skipped_reason": None,
}
```

**Edge Cases:**
- `implementation_files` is empty `{}` → returns state with `adversarial_skipped_reason="No implementation files in state"`, `adversarial_verdict="error"`
- Gemini raises `GeminiQuotaExhaustedError` → returns state with `adversarial_skipped_reason="Gemini quota exhausted"`, `adversarial_verdict="error"`
- Gemini raises `GeminiModelDowngradeError` → returns state with `adversarial_skipped_reason="Gemini model downgraded to Flash"`, `adversarial_verdict="error"`
- Gemini returns invalid JSON → returns state with `adversarial_verdict="error"`, `adversarial_error="Malformed Gemini response"`

### 5.2 `_collect_context()`

**File:** `assemblyzero/workflows/testing/nodes/adversarial_node.py`

**Signature:**

```python
def _collect_context(state: AdversarialNodeState) -> tuple[str, str, str]:
    """Extract and token-budget-trim implementation code, LLD content, and existing tests."""
    ...
```

**Input Example:**

```python
state = {
    "implementation_files": {
        "file1.py": "x" * 40000,
        "file2.py": "y" * 40000,
    },
    "lld_content": "z" * 30000,
    "existing_tests": {
        "test1.py": "w" * 20000,
    },
    "issue_id": 352,
}
```

**Output Example:**

```python
(
    "# file1.py\nx...x\n\n# file2.py\ny...y",  # truncated to ~30KB
    "z...z",  # truncated to ~20KB
    "# test1.py\nw...w",  # truncated to ~10KB
)
# Total ≤ 60KB
```

**Edge Cases:**
- All empty → returns `("", "", "")`
- Implementation exceeds 30KB → truncated with `\n... [TRUNCATED] ...` marker at function boundaries
- Only implementation provided (no LLD, no tests) → implementation gets full 60KB budget

### 5.3 `_parse_gemini_response()`

**File:** `assemblyzero/workflows/testing/nodes/adversarial_node.py`

**Signature:**

```python
def _parse_gemini_response(raw_response: str) -> AdversarialAnalysis:
    """Parse Gemini's structured JSON response into AdversarialAnalysis."""
    ...
```

**Input Example:**

```python
raw_response = '{"uncovered_edge_cases": ["empty input"], "false_claims": ["claims Unicode support"], "missing_error_handling": ["no FileNotFoundError handler"], "implicit_assumptions": ["assumes UTF-8"], "test_cases": [{"test_id": "ADV_001", "target_function": "foo.bar", "category": "boundary", "description": "test empty", "test_code": "def test_empty():\\n    assert foo(\\'\\') is None", "claim_challenged": "handles all inputs", "severity": "high"}]}'
```

**Output Example:**

```python
{
    "uncovered_edge_cases": ["empty input"],
    "false_claims": ["claims Unicode support"],
    "missing_error_handling": ["no FileNotFoundError handler"],
    "implicit_assumptions": ["assumes UTF-8"],
    "test_cases": [
        {
            "test_id": "ADV_001",
            "target_function": "foo.bar",
            "category": "boundary",
            "description": "test empty",
            "test_code": "def test_empty():\n    assert foo('') is None",
            "claim_challenged": "handles all inputs",
            "severity": "high",
        }
    ],
}
```

**Edge Cases:**
- Invalid JSON `{broken` → raises `ValueError("Malformed JSON response from Gemini")`
- Missing `false_claims` field → raises `ValueError("Missing required analysis category: false_claims")`
- Missing `test_cases` field → raises `ValueError("Missing required field: test_cases")`
- Response wrapped in markdown code block → strips ` ```json ` and ` ``` ` before parsing
- Empty `test_cases` list → valid (returns analysis with empty list)

### 5.4 `write_adversarial_tests()`

**File:** `assemblyzero/workflows/testing/nodes/adversarial_writer.py`

**Signature:**

```python
def write_adversarial_tests(
    analysis: AdversarialAnalysis,
    issue_id: int,
    output_dir: str = "tests/adversarial",
) -> dict[str, str]:
    """Write adversarial test cases to disk as pytest-compatible files."""
    ...
```

**Input Example:**

```python
analysis = {
    "uncovered_edge_cases": ["empty input"],
    "false_claims": [],
    "missing_error_handling": [],
    "implicit_assumptions": [],
    "test_cases": [
        {
            "test_id": "ADV_001",
            "target_function": "scaffold.generate",
            "category": "boundary",
            "description": "Test empty input",
            "test_code": "def test_scaffold_empty():\n    from assemblyzero.workflows.testing.nodes.scaffold_tests import generate_test_scaffold\n    result = generate_test_scaffold('')\n    assert result is not None",
            "claim_challenged": "handles all formats",
            "severity": "high",
        },
        {
            "test_id": "ADV_002",
            "target_function": "scaffold.generate",
            "category": "boundary",
            "description": "Test None input",
            "test_code": "def test_scaffold_none():\n    from assemblyzero.workflows.testing.nodes.scaffold_tests import generate_test_scaffold\n    import pytest\n    with pytest.raises(TypeError):\n        generate_test_scaffold(None)",
            "claim_challenged": "handles all formats",
            "severity": "medium",
        },
        {
            "test_id": "ADV_003",
            "target_function": "verify.verify_red",
            "category": "contract",
            "description": "Test exit code contract",
            "test_code": "def test_exit_code_range():\n    from assemblyzero.workflows.testing.nodes.verify_red_phase import verify_red\n    result = verify_red({'test_files': {}, 'iteration': 0})\n    assert result.get('exit_code', -1) in range(6)",
            "claim_challenged": "exit codes 0-5",
            "severity": "high",
        },
    ],
}
issue_id = 352
output_dir = "tests/adversarial"
```

**Output Example:**

```python
{
    "tests/adversarial/test_352_boundary.py": "# ADVERSARIAL TEST FILE - Machine-generated by Gemini Pro\n# Issue: #352\n# Category: boundary\n# Generator: assemblyzero adversarial testing node\n# WARNING: Do not manually edit - regenerated on each workflow run\n\n\"\"\"Adversarial boundary tests for issue #352.\n\nThese tests exercise real code paths with NO mocks.\n\"\"\"\n\n\ndef test_scaffold_empty():\n    from assemblyzero.workflows.testing.nodes.scaffold_tests import generate_test_scaffold\n    result = generate_test_scaffold('')\n    assert result is not None\n\n\ndef test_scaffold_none():\n    from assemblyzero.workflows.testing.nodes.scaffold_tests import generate_test_scaffold\n    import pytest\n    with pytest.raises(TypeError):\n        generate_test_scaffold(None)\n",
    "tests/adversarial/test_352_contract.py": "# ADVERSARIAL TEST FILE - Machine-generated by Gemini Pro\n# Issue: #352\n# Category: contract\n# Generator: assemblyzero adversarial testing node\n# WARNING: Do not manually edit - regenerated on each workflow run\n\n\"\"\"Adversarial contract tests for issue #352.\n\nThese tests exercise real code paths with NO mocks.\n\"\"\"\n\n\ndef test_exit_code_range():\n    from assemblyzero.workflows.testing.nodes.verify_red_phase import verify_red\n    result = verify_red({'test_files': {}, 'iteration': 0})\n    assert result.get('exit_code', -1) in range(6)\n"
}
```

**Edge Cases:**
- Empty `test_cases` → returns `{}`
- Category with special characters → sanitized to alphanumeric + underscore
- `output_dir` doesn't exist → creates it via `os.makedirs(output_dir, exist_ok=True)`

### 5.5 `_render_test_file()`

**File:** `assemblyzero/workflows/testing/nodes/adversarial_writer.py`

**Signature:**

```python
def _render_test_file(
    test_cases: list[AdversarialTestCase],
    category: str,
    issue_id: int,
) -> str:
    """Render a list of test cases into a complete pytest file."""
    ...
```

**Input Example:**

```python
test_cases = [
    {
        "test_id": "ADV_001",
        "target_function": "scaffold.generate",
        "category": "boundary",
        "description": "Test empty input",
        "test_code": "def test_scaffold_empty():\n    assert True",
        "claim_challenged": "handles all formats",
        "severity": "high",
    }
]
category = "boundary"
issue_id = 352
```

**Output Example:**

```python
"""# ADVERSARIAL TEST FILE - Machine-generated by Gemini Pro
# Issue: #352
# Category: boundary
# Generator: assemblyzero adversarial testing node
# WARNING: Do not manually edit - regenerated on each workflow run

\"\"\"Adversarial boundary tests for issue #352.

These tests exercise real code paths with NO mocks.
\"\"\"


def test_scaffold_empty():
    assert True
"""
```

**Edge Cases:**
- `test_cases` is empty list → returns file with header/docstring only, no test functions
- `test_code` already includes `def test_` prefix → used as-is
- `test_code` does not include `def test_` prefix → wrapped in a generated function name

### 5.6 `validate_adversarial_tests()`

**File:** `assemblyzero/workflows/testing/nodes/adversarial_validator.py`

**Signature:**

```python
def validate_adversarial_tests(test_files: dict[str, str]) -> ValidationResult:
    """Validate generated adversarial test files."""
    ...
```

**Input Example:**

```python
test_files = {
    "tests/adversarial/test_352_boundary.py": "def test_empty():\n    assert True\n",
    "tests/adversarial/test_352_injection.py": "from unittest.mock import patch\ndef test_inject():\n    pass\n",
}
```

**Output Example:**

```python
{
    "valid": False,
    "errors": [],
    "warnings": [
        "tests/adversarial/test_352_injection.py: test_inject has no assertions"
    ],
    "mock_violations": [
        "tests/adversarial/test_352_injection.py:1: Mock import detected: 'from unittest.mock import patch'"
    ]
}
```

**Edge Cases:**
- Empty `test_files` → returns `{"valid": True, "errors": [], "warnings": [], "mock_violations": []}`
- File with syntax error → `errors` list populated, `valid=False`
- File with only mock violations (syntax ok) → `valid=False`, `mock_violations` populated

### 5.7 `_check_no_mocks()`

**File:** `assemblyzero/workflows/testing/nodes/adversarial_validator.py`

**Signature:**

```python
def _check_no_mocks(source_code: str, filepath: str) -> list[str]:
    """AST-scan source code for mock usage. Returns list of violations."""
    ...
```

**Input Example:**

```python
source_code = "from unittest.mock import patch, MagicMock\n\n@patch('os.path.exists')\ndef test_something(mock_exists):\n    mock_exists.return_value = True\n    assert True\n"
filepath = "tests/adversarial/test_352_boundary.py"
```

**Output Example:**

```python
[
    "tests/adversarial/test_352_boundary.py:1: Mock import detected: 'from unittest.mock import patch, MagicMock'",
    "tests/adversarial/test_352_boundary.py:3: Mock decorator detected: '@patch'"
]
```

**Edge Cases:**
- `from unittest import mock` → detected
- `import unittest.mock` → detected
- `from unittest.mock import patch as p` → detected (AST catches aliased imports)
- `m = MagicMock()` → detected via AST Name node
- `def test_x(monkeypatch):` → detected via function argument inspection
- Code with `mock` in a string literal `"use mock"` → NOT flagged (AST only inspects nodes, not string content)

### 5.8 `_check_syntax()`

**File:** `assemblyzero/workflows/testing/nodes/adversarial_validator.py`

**Signature:**

```python
def _check_syntax(source_code: str, filepath: str) -> list[str]:
    """Attempt to compile source code. Returns list of syntax errors."""
    ...
```

**Input Example:**

```python
source_code = "def test_x(:\n    pass\n"
filepath = "tests/adversarial/test_352_boundary.py"
```

**Output Example:**

```python
["tests/adversarial/test_352_boundary.py: SyntaxError: invalid syntax (line 1)"]
```

**Edge Cases:**
- Valid code → returns `[]`
- Multiple syntax errors → only first error reported (Python's `compile` stops at first)

### 5.9 `_check_assertions()`

**File:** `assemblyzero/workflows/testing/nodes/adversarial_validator.py`

**Signature:**

```python
def _check_assertions(source_code: str, filepath: str) -> list[str]:
    """AST-scan for assert statements in each test function."""
    ...
```

**Input Example:**

```python
source_code = "def test_something():\n    x = 1\n\ndef test_with_assert():\n    assert True\n"
filepath = "tests/adversarial/test_352_boundary.py"
```

**Output Example:**

```python
["tests/adversarial/test_352_boundary.py: test_something has no assertions"]
```

**Edge Cases:**
- Function not starting with `test_` → ignored
- `pytest.raises` context manager → counts as assertion (check for `with pytest.raises`)
- Empty file → returns `[]`

### 5.10 `build_adversarial_analysis_prompt()`

**File:** `assemblyzero/workflows/testing/adversarial_prompts.py`

**Signature:**

```python
def build_adversarial_analysis_prompt(
    implementation_code: str,
    lld_content: str,
    existing_tests: str,
    adversarial_patterns: list[str],
) -> str:
    """Build the user prompt for Gemini adversarial analysis."""
    ...
```

**Input Example:**

```python
implementation_code = "# scaffold_tests.py\ndef generate_test_scaffold(lld: str) -> dict:\n    return {'scaffold': lld[:100]}"
lld_content = "# 352 - Feature\n## 3. Requirements\n1. Generates tests"
existing_tests = "# test_scaffold.py\ndef test_basic():\n    assert True"
adversarial_patterns = [
    "Boundary: Test empty strings, None values, maximum length inputs",
    "Contract: Verify documented preconditions are enforced",
]
```

**Output Example:**

```python
"""## Implementation Code Under Test

```python
# scaffold_tests.py
def generate_test_scaffold(lld: str) -> dict:
    return {'scaffold': lld[:100]}
```

## Low-Level Design (LLD) Claims

```markdown
# 352 - Feature
## 3. Requirements
1. Generates tests
```

## Existing Test Suite

```python
# test_scaffold.py
def test_basic():
    assert True
```

## Adversarial Testing Patterns to Apply

- Boundary: Test empty strings, None values, maximum length inputs
- Contract: Verify documented preconditions are enforced

## Instructions

Analyze the implementation code against the LLD claims. Generate adversarial test cases following the JSON schema below. Your response MUST be valid JSON only, with no surrounding text.

{... schema definition ...}
"""
```

**Edge Cases:**
- Empty `existing_tests` → section omitted from prompt with note "No existing tests provided"
- Empty `adversarial_patterns` → uses default built-in pattern list

### 5.11 `build_adversarial_system_prompt()`

**File:** `assemblyzero/workflows/testing/adversarial_prompts.py`

**Signature:**

```python
def build_adversarial_system_prompt() -> str:
    """System prompt establishing Gemini's adversarial tester persona."""
    ...
```

**Input Example:** N/A (no parameters)

**Output Example:**

```python
"""You are an expert adversarial software tester. Your goal is to BREAK the implementation by finding edge cases, false claims, missing error handling, and implicit assumptions.

CRITICAL CONSTRAINTS:
- NEVER generate mocks, stubs, fakes, or monkey-patches in your test code
- Every test MUST exercise real code paths with real function calls
- NEVER use unittest.mock, MagicMock, Mock, AsyncMock, @patch, or monkeypatch
- Tests must contain at least one assert statement

OUTPUT FORMAT:
- Respond with ONLY valid JSON matching the AdversarialAnalysis schema
- Do NOT wrap in markdown code blocks
- Do NOT include any text before or after the JSON

REQUIRED ANALYSIS CATEGORIES (all must be populated):
- uncovered_edge_cases: Edge cases not covered by existing tests
- false_claims: LLD claims not backed by implementation
- missing_error_handling: Error paths without handlers
- implicit_assumptions: Undocumented assumptions in the code

SEVERITY LEVELS:
- critical: Would cause data loss or security vulnerability
- high: Would cause incorrect behavior or crashes
- medium: Could cause issues under specific conditions"""
```

**Edge Cases:** None (static prompt).

### 5.12 `AdversarialGeminiClient.__init__()`

**File:** `assemblyzero/workflows/testing/adversarial_gemini.py`

**Signature:**

```python
class AdversarialGeminiClient:
    def __init__(self, provider: object | None = None) -> None:
        """Initialize with an optional GeminiProvider instance."""
        ...
```

**Input Example:**

```python
# Default (auto-discover provider)
client = AdversarialGeminiClient()

# Injected provider (for testing)
mock_provider = SomeGeminiProvider()
client = AdversarialGeminiClient(provider=mock_provider)
```

**Edge Cases:**
- `provider=None` → attempts to import and instantiate from `assemblyzero.utils`; if import fails, raises `ImportError` with descriptive message

### 5.13 `AdversarialGeminiClient.verify_model_is_pro()`

**File:** `assemblyzero/workflows/testing/adversarial_gemini.py`

**Signature:**

```python
def verify_model_is_pro(self, response_metadata: dict) -> bool:
    """Check response metadata to confirm Gemini Pro was used."""
    ...
```

**Input Example (Pro):**

```python
response_metadata = {
    "model": "gemini-3-pro-preview-0514",
    "usage": {"prompt_tokens": 5000, "completion_tokens": 2000}
}
# Returns: True
```

**Input Example (Flash — downgrade):**

```python
response_metadata = {
    "model": "gemini-2.0-flash-001",
    "usage": {"prompt_tokens": 5000, "completion_tokens": 2000}
}
# Raises: GeminiModelDowngradeError("Expected Gemini Pro but received gemini-2.0-flash-001")
```

**Edge Cases:**
- `response_metadata` is empty `{}` → raises `GeminiModelDowngradeError("No model information in response metadata")`
- Model name contains "pro" (case-insensitive) → returns `True`
- Model name contains "flash" → raises `GeminiModelDowngradeError`

### 5.14 `AdversarialGeminiClient.generate_adversarial_tests()`

**File:** `assemblyzero/workflows/testing/adversarial_gemini.py`

**Signature:**

```python
def generate_adversarial_tests(
    self,
    implementation_code: str,
    lld_content: str,
    existing_tests: str,
    adversarial_patterns: list[str] | None = None,
    timeout: int = 120,
) -> str:
    """Invoke Gemini Pro for adversarial test generation."""
    ...
```

**Input Example:**

```python
implementation_code = "def foo(): return 42"
lld_content = "# Feature\nfoo returns 42 for all inputs"
existing_tests = "def test_foo(): assert foo() == 42"
adversarial_patterns = ["Boundary: test with no arguments"]
timeout = 120
```

**Output Example:**

```python
'{"uncovered_edge_cases": ["foo accepts no arguments but LLD says all inputs"], "false_claims": ["claims all inputs but function takes none"], "missing_error_handling": [], "implicit_assumptions": ["assumes no arguments"], "test_cases": [{"test_id": "ADV_001", "target_function": "foo", "category": "contract", "description": "Verify foo signature matches LLD claim", "test_code": "def test_foo_signature():\\n    import inspect\\n    sig = inspect.signature(foo)\\n    assert len(sig.parameters) == 0", "claim_challenged": "returns 42 for all inputs", "severity": "medium"}]}'
```

**Edge Cases:**
- API returns 429 → raises `GeminiQuotaExhaustedError("Gemini API quota exhausted (HTTP 429)")`
- API timeout → raises `GeminiTimeoutError(f"Gemini API response exceeded {timeout}s timeout")`
- Flash model detected in response → raises `GeminiModelDowngradeError`

### 5.15 `get_adversarial_patterns()`

**File:** `assemblyzero/workflows/testing/knowledge/adversarial_patterns.py`

**Signature:**

```python
def get_adversarial_patterns() -> list[str]:
    """Return curated list of adversarial testing pattern descriptions."""
    ...
```

**Input Example:** N/A (no parameters)

**Output Example:**

```python
[
    "Boundary: Test with empty strings, None values, zero-length collections, maximum integer values, extremely long strings (>1MB), negative numbers where positive expected",
    "Injection: Test with special characters (quotes, backslashes, null bytes \\x00), Unicode edge cases (RTL marks, zero-width joiners, emoji), path traversal (../), SQL-like strings",
    "Concurrency: Test shared state mutation under concurrent access, race conditions in file I/O, thread-safety of global state",
    "State: Test invalid state transitions, partially initialized objects, state after error recovery, double-initialization",
    "Contract: Test violations of documented preconditions, verify documented postconditions hold, test invariants under mutation, check return type contracts",
    "Resource: Test behavior under memory pressure, verify file handles are closed, test timeout behavior, verify cleanup on exception",
]
```

## 6. Change Instructions

### 6.1 `assemblyzero/workflows/testing/adversarial_state.py` (Add)

**Complete file contents:**

```python
"""State extensions for adversarial testing node.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

from typing import Literal, TypedDict


class AdversarialTestCase(TypedDict):
    """A single adversarial test case generated by Gemini."""

    test_id: str
    target_function: str
    category: str
    description: str
    test_code: str
    claim_challenged: str
    severity: Literal["critical", "high", "medium"]


class AdversarialAnalysis(TypedDict):
    """Gemini's analysis of implementation vs. LLD claims."""

    uncovered_edge_cases: list[str]
    false_claims: list[str]
    missing_error_handling: list[str]
    implicit_assumptions: list[str]
    test_cases: list[AdversarialTestCase]


class AdversarialNodeState(TypedDict, total=False):
    """State extension for the adversarial testing node."""

    # Inputs (populated by prior nodes)
    implementation_files: dict[str, str]
    lld_content: str
    existing_tests: dict[str, str]
    issue_id: int

    # Outputs (populated by adversarial node)
    adversarial_analysis: AdversarialAnalysis
    generated_test_files: dict[str, str]
    adversarial_verdict: Literal["pass", "fail", "error"]
    adversarial_error: str | None
    adversarial_test_count: int
    adversarial_skipped_reason: str | None
```

### 6.2 `assemblyzero/workflows/testing/knowledge/adversarial_patterns.py` (Add)

**Complete file contents:**

```python
"""Knowledge base of adversarial testing patterns.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""


def get_adversarial_patterns() -> list[str]:
    """Return curated list of adversarial testing pattern descriptions.

    Categories:
    - Boundary: off-by-one, empty input, max-size input, type limits
    - Injection: special characters, unicode, null bytes, path traversal
    - Concurrency: race conditions, shared state mutation
    - State: invalid state transitions, partial initialization
    - Contract: violating documented preconditions, postcondition verification
    - Resource: memory exhaustion, file handle leaks, timeout scenarios
    """
    return [
        (
            "Boundary: Test with empty strings, None values, zero-length "
            "collections, maximum integer values, extremely long strings "
            "(>1MB), negative numbers where positive expected, off-by-one "
            "on sequence indices, single-element and two-element collections"
        ),
        (
            "Injection: Test with special characters (quotes, backslashes, "
            "null bytes \\x00), Unicode edge cases (RTL marks, zero-width "
            "joiners, emoji, combining characters), path traversal sequences "
            "(../), SQL-like strings ('; DROP TABLE), HTML/XML tags"
        ),
        (
            "Concurrency: Test shared state mutation under concurrent access, "
            "race conditions in file I/O operations, thread-safety of global "
            "or module-level state, async/await cancellation mid-operation"
        ),
        (
            "State: Test invalid state transitions, partially initialized "
            "objects, state after error recovery, double-initialization, "
            "use-after-close patterns, accessing attributes before setup"
        ),
        (
            "Contract: Test violations of documented preconditions, verify "
            "documented postconditions hold after every call, test invariants "
            "under mutation, check return type contracts match docstrings, "
            "verify error messages match documented error specifications"
        ),
        (
            "Resource: Test behavior under memory pressure with large inputs, "
            "verify file handles are closed after operations, test timeout "
            "behavior for long-running operations, verify cleanup on exception "
            "in context managers and finally blocks"
        ),
    ]
```

### 6.3 `assemblyzero/workflows/testing/adversarial_prompts.py` (Add)

**Complete file contents:**

```python
"""Prompt templates for Gemini adversarial analysis.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import json


_ADVERSARIAL_ANALYSIS_SCHEMA = {
    "type": "object",
    "required": [
        "uncovered_edge_cases",
        "false_claims",
        "missing_error_handling",
        "implicit_assumptions",
        "test_cases",
    ],
    "properties": {
        "uncovered_edge_cases": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Edge cases not covered by existing tests",
        },
        "false_claims": {
            "type": "array",
            "items": {"type": "string"},
            "description": "LLD claims not backed by implementation",
        },
        "missing_error_handling": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Error paths without handlers",
        },
        "implicit_assumptions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Undocumented assumptions in the code",
        },
        "test_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "test_id",
                    "target_function",
                    "category",
                    "description",
                    "test_code",
                    "claim_challenged",
                    "severity",
                ],
                "properties": {
                    "test_id": {"type": "string"},
                    "target_function": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "boundary",
                            "injection",
                            "concurrency",
                            "state",
                            "contract",
                            "resource",
                        ],
                    },
                    "description": {"type": "string"},
                    "test_code": {"type": "string"},
                    "claim_challenged": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium"],
                    },
                },
            },
        },
    },
}


def build_adversarial_system_prompt() -> str:
    """System prompt establishing Gemini's adversarial tester persona.

    Key constraints:
    - You are a hostile reviewer trying to break the implementation.
    - NEVER generate mocks, stubs, or fakes.
    - Tests must exercise real code paths.
    - Focus on boundary conditions, error paths, and contract violations.
    - Output strict JSON.
    - Your analysis MUST include: uncovered_edge_cases, false_claims,
      missing_error_handling, and implicit_assumptions.
    """
    return (
        "You are an expert adversarial software tester. Your goal is to "
        "BREAK the implementation by finding edge cases, false claims, "
        "missing error handling, and implicit assumptions.\n\n"
        "CRITICAL CONSTRAINTS:\n"
        "- NEVER generate mocks, stubs, fakes, or monkey-patches in your test code\n"
        "- Every test MUST exercise real code paths with real function calls\n"
        "- NEVER use unittest.mock, MagicMock, Mock, AsyncMock, @patch, or monkeypatch\n"
        "- Tests must contain at least one assert statement\n"
        "- Each test function name MUST start with 'test_'\n\n"
        "OUTPUT FORMAT:\n"
        "- Respond with ONLY valid JSON matching the AdversarialAnalysis schema\n"
        "- Do NOT wrap in markdown code blocks\n"
        "- Do NOT include any text before or after the JSON\n\n"
        "REQUIRED ANALYSIS CATEGORIES (all four must be populated with at least "
        "one finding each, or explicitly state 'none found' as a list item):\n"
        "- uncovered_edge_cases: Edge cases not covered by existing tests\n"
        "- false_claims: LLD claims not backed by implementation\n"
        "- missing_error_handling: Error paths without handlers\n"
        "- implicit_assumptions: Undocumented assumptions in the code\n\n"
        "SEVERITY LEVELS for test_cases:\n"
        "- critical: Would cause data loss or security vulnerability\n"
        "- high: Would cause incorrect behavior or crashes\n"
        "- medium: Could cause issues under specific conditions\n\n"
        "Generate a maximum of 15 test cases. Focus on quality over quantity."
    )


def build_adversarial_analysis_prompt(
    implementation_code: str,
    lld_content: str,
    existing_tests: str,
    adversarial_patterns: list[str],
) -> str:
    """Build the user prompt for Gemini adversarial analysis.

    The prompt instructs Gemini to:
    1. Read the implementation and LLD.
    2. Identify claims in the LLD not backed by code.
    3. Find edge cases missing from existing tests.
    4. Generate aggressive test cases that use NO mocks.
    5. Return structured JSON matching AdversarialAnalysis schema.

    The prompt explicitly requires Gemini to populate all four analysis
    categories: uncovered_edge_cases, false_claims, missing_error_handling,
    and implicit_assumptions.
    """
    schema_json = json.dumps(_ADVERSARIAL_ANALYSIS_SCHEMA, indent=2)

    sections = []

    sections.append("## Implementation Code Under Test\n")
    sections.append(f"```python\n{implementation_code}\n```\n")

    sections.append("## Low-Level Design (LLD) Claims\n")
    sections.append(f"```markdown\n{lld_content}\n```\n")

    if existing_tests:
        sections.append("## Existing Test Suite\n")
        sections.append(f"```python\n{existing_tests}\n```\n")
    else:
        sections.append(
            "## Existing Test Suite\n\nNo existing tests provided. "
            "Generate comprehensive adversarial coverage.\n"
        )

    sections.append("## Adversarial Testing Patterns to Apply\n")
    for pattern in adversarial_patterns:
        sections.append(f"- {pattern}")
    sections.append("")

    sections.append("## Instructions\n")
    sections.append(
        "Analyze the implementation code against the LLD claims. "
        "Identify discrepancies, missing error handling, implicit assumptions, "
        "and uncovered edge cases. Then generate adversarial test cases that "
        "attempt to break the implementation.\n\n"
        "Your response MUST be valid JSON matching this schema:\n\n"
        f"```json\n{schema_json}\n```\n\n"
        "IMPORTANT REMINDERS:\n"
        "- NO mocks, stubs, fakes, or monkey-patches\n"
        "- Every test must call real functions\n"
        "- Every test must have at least one assert\n"
        "- All four analysis categories must be populated\n"
        "- Maximum 15 test cases\n"
        "- Respond with ONLY the JSON object, no surrounding text"
    )

    return "\n".join(sections)
```

### 6.4 `assemblyzero/workflows/testing/adversarial_gemini.py` (Add)

**Complete file contents:**

```python
"""Wrapper module for Gemini adversarial invocation logic.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

Encapsulates adversarial-specific invocation (system prompt, no-mock constraint,
timeout handling) while delegating actual API communication to the existing
provider infrastructure.
"""

import logging
import signal
from typing import Any

from assemblyzero.workflows.testing.adversarial_prompts import (
    build_adversarial_analysis_prompt,
    build_adversarial_system_prompt,
)
from assemblyzero.workflows.testing.knowledge.adversarial_patterns import (
    get_adversarial_patterns,
)

logger = logging.getLogger(__name__)


class GeminiQuotaExhaustedError(Exception):
    """Raised when Gemini API quota is exhausted (HTTP 429)."""

    pass


class GeminiModelDowngradeError(Exception):
    """Raised when Gemini silently downgrades from Pro to Flash."""

    pass


class GeminiTimeoutError(Exception):
    """Raised when Gemini API response exceeds timeout."""

    pass


class AdversarialGeminiClient:
    """Wrapper around the project's existing GeminiProvider for adversarial test generation.

    This module encapsulates the adversarial-specific invocation logic
    (system prompt, no-mock constraint, timeout handling) while delegating
    actual Gemini API communication to the existing provider infrastructure.
    """

    def __init__(self, provider: Any | None = None) -> None:
        """Initialize with an optional GeminiProvider instance.

        If provider is None, attempts to instantiate the default provider
        from assemblyzero.utils (auto-discovered at runtime).

        Args:
            provider: An object with a method to invoke Gemini. If None,
                      auto-discovers from assemblyzero.utils.
        """
        if provider is not None:
            self._provider = provider
        else:
            self._provider = self._discover_provider()

    def _discover_provider(self) -> Any:
        """Auto-discover and instantiate the Gemini provider from assemblyzero.utils.

        Searches for common provider class names in the utils package.

        Returns:
            An instantiated Gemini provider.

        Raises:
            ImportError: If no suitable Gemini provider found.
        """
        # Try known provider locations in order of likelihood
        provider_attempts = [
            ("assemblyzero.utils.gemini_provider", "GeminiProvider"),
            ("assemblyzero.utils.gemini", "GeminiProvider"),
            ("assemblyzero.utils.gemini_client", "GeminiClient"),
            ("assemblyzero.utils.providers", "GeminiProvider"),
        ]

        for module_path, class_name in provider_attempts:
            try:
                import importlib

                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                logger.info(
                    "Discovered Gemini provider: %s.%s", module_path, class_name
                )
                return cls()
            except (ImportError, AttributeError):
                continue

        # Fallback: try google.genai directly
        try:
            from google import genai

            logger.info("Using google.genai directly as Gemini provider")
            return genai.Client()
        except ImportError:
            pass

        raise ImportError(
            "No Gemini provider found. Ensure google-genai or "
            "langchain-google-genai is installed and a provider class "
            "exists in assemblyzero.utils."
        )

    def verify_model_is_pro(self, response_metadata: dict) -> bool:
        """Check response metadata to confirm Gemini Pro was used.

        Args:
            response_metadata: Dictionary containing model info from the API response.

        Returns:
            True if Pro model confirmed.

        Raises:
            GeminiModelDowngradeError: If Flash model detected or no model info present.
        """
        model_name = response_metadata.get("model", "")

        if not model_name:
            raise GeminiModelDowngradeError(
                "No model information in response metadata"
            )

        model_lower = model_name.lower()

        if "flash" in model_lower:
            raise GeminiModelDowngradeError(
                f"Expected Gemini Pro but received {model_name}"
            )

        if "pro" in model_lower:
            logger.info("Gemini Pro model confirmed: %s", model_name)
            return True

        # Unknown model — warn but don't block
        logger.warning(
            "Unknown Gemini model variant: %s. Proceeding cautiously.", model_name
        )
        return True

    def generate_adversarial_tests(
        self,
        implementation_code: str,
        lld_content: str,
        existing_tests: str,
        adversarial_patterns: list[str] | None = None,
        timeout: int = 120,
    ) -> str:
        """Invoke Gemini Pro for adversarial test generation.

        Builds the adversarial prompt, delegates to the underlying provider,
        and applies model-downgrade detection.

        Args:
            implementation_code: Source code of the implementation under test.
            lld_content: LLD markdown content.
            existing_tests: Existing test code for deduplication.
            adversarial_patterns: Optional list of patterns. Uses defaults if None.
            timeout: Maximum seconds to wait for response.

        Returns:
            Raw JSON string response from Gemini.

        Raises:
            GeminiQuotaExhaustedError: If 429 or quota message detected.
            GeminiModelDowngradeError: If Flash detected instead of Pro.
            GeminiTimeoutError: If response exceeds timeout.
        """
        if adversarial_patterns is None:
            adversarial_patterns = get_adversarial_patterns()

        system_prompt = build_adversarial_system_prompt()
        user_prompt = build_adversarial_analysis_prompt(
            implementation_code=implementation_code,
            lld_content=lld_content,
            existing_tests=existing_tests,
            adversarial_patterns=adversarial_patterns,
        )

        logger.info(
            "Invoking Gemini Pro for adversarial analysis (timeout=%ds)", timeout
        )

        try:
            raw_response, metadata = self._invoke_provider(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=timeout,
            )
        except TimeoutError as e:
            raise GeminiTimeoutError(
                f"Gemini API response exceeded {timeout}s timeout"
            ) from e

        # Check for quota exhaustion in response or exception
        if self._is_quota_error(raw_response, metadata):
            raise GeminiQuotaExhaustedError(
                "Gemini API quota exhausted (HTTP 429)"
            )

        # Verify model is Pro (not silently downgraded to Flash)
        self.verify_model_is_pro(metadata)

        logger.info("Gemini adversarial analysis received (%d chars)", len(raw_response))
        return raw_response

    def _invoke_provider(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: int,
    ) -> tuple[str, dict]:
        """Invoke the underlying provider and return (response_text, metadata).

        This method abstracts over different provider APIs (google.genai,
        langchain-google-genai, etc.).

        Returns:
            Tuple of (raw_response_text, response_metadata_dict).
        """
        provider = self._provider

        # Strategy 1: google.genai Client
        if hasattr(provider, "models") and hasattr(provider.models, "generate_content"):
            response = provider.models.generate_content(
                model="gemini-2.5-pro-preview-05-06",
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "response_mime_type": "application/json",
                    "timeout": timeout,
                },
            )
            text = response.text if hasattr(response, "text") else str(response)
            metadata = {}
            if hasattr(response, "model"):
                metadata["model"] = response.model
            elif hasattr(response, "candidates") and response.candidates:
                # Try to extract model from candidates
                metadata["model"] = getattr(
                    response, "model_version", "gemini-2.5-pro-preview-05-06"
                )
            else:
                metadata["model"] = "gemini-2.5-pro-preview-05-06"
            return text, metadata

        # Strategy 2: LangChain-style provider with invoke()
        if hasattr(provider, "invoke"):
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = provider.invoke(messages)
            text = response.content if hasattr(response, "content") else str(response)
            metadata = getattr(response, "response_metadata", {})
            return text, metadata

        # Strategy 3: Generic callable
        if callable(provider):
            result = provider(system_prompt=system_prompt, user_prompt=user_prompt)
            if isinstance(result, tuple):
                return result[0], result[1]
            return str(result), {"model": "unknown"}

        raise TypeError(
            f"Unsupported Gemini provider type: {type(provider).__name__}. "
            "Provider must have 'models.generate_content', 'invoke', or be callable."
        )

    def _is_quota_error(self, response: str, metadata: dict) -> bool:
        """Check if the response indicates quota exhaustion.

        Args:
            response: Raw response text.
            metadata: Response metadata.

        Returns:
            True if quota exhaustion detected.
        """
        quota_indicators = [
            "429",
            "quota",
            "rate limit",
            "resource exhausted",
            "RESOURCE_EXHAUSTED",
        ]
        status = metadata.get("status_code", 0)
        if status == 429:
            return True

        response_lower = response.lower() if response else ""
        for indicator in quota_indicators:
            if indicator.lower() in response_lower:
                return True

        return False
```

### 6.5 `assemblyzero/workflows/testing/nodes/adversarial_validator.py` (Add)

**Complete file contents:**

```python
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
```

### 6.6 `assemblyzero/workflows/testing/nodes/adversarial_writer.py` (Add)

**Complete file contents:**

```python
"""Writes Gemini's adversarial test output to test files.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

Groups test cases by category and writes them as pytest-compatible files
with adversarial identification headers.
"""

import logging
import os
import re
import shutil
import tempfile
from collections import defaultdict

from assemblyzero.workflows.testing.adversarial_state import (
    AdversarialAnalysis,
    AdversarialTestCase,
)

logger = logging.getLogger(__name__)


def write_adversarial_tests(
    analysis: AdversarialAnalysis,
    issue_id: int,
    output_dir: str = "tests/adversarial",
) -> dict[str, str]:
    """Write adversarial test cases to disk as pytest-compatible files.

    Each file follows naming: test_{issue_id}_{category}.py
    Groups test cases by category into separate files.
    Writes to a temp directory first, then performs atomic rename.

    Args:
        analysis: The parsed adversarial analysis from Gemini.
        issue_id: GitHub issue number for file naming.
        output_dir: Directory to write test files to.

    Returns:
        Dictionary of filepath -> file content written.
    """
    test_cases = analysis.get("test_cases", [])
    if not test_cases:
        logger.info("No adversarial test cases to write")
        return {}

    # Group by category
    grouped: dict[str, list[AdversarialTestCase]] = defaultdict(list)
    for tc in test_cases:
        category = _sanitize_category(tc.get("category", "general"))
        grouped[category].append(tc)

    # Write to temp directory first for atomicity
    temp_dir = tempfile.mkdtemp(prefix="adversarial_")
    result: dict[str, str] = {}

    try:
        os.makedirs(output_dir, exist_ok=True)

        for category, cases in grouped.items():
            filename = f"test_{issue_id}_{category}.py"
            filepath = os.path.join(output_dir, filename)
            temp_filepath = os.path.join(temp_dir, filename)

            content = _render_test_file(cases, category, issue_id)

            # Write to temp first
            with open(temp_filepath, "w", encoding="utf-8") as f:
                f.write(content)

            # Atomic move to final location
            shutil.move(temp_filepath, filepath)
            result[filepath] = content

            logger.info(
                "Wrote adversarial test file: %s (%d tests)", filepath, len(cases)
            )

    except Exception:
        logger.exception("Error writing adversarial test files")
        raise
    finally:
        # Clean up temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    return result


def _render_test_file(
    test_cases: list[AdversarialTestCase],
    category: str,
    issue_id: int,
) -> str:
    """Render a list of test cases into a complete pytest file.

    The rendered file begins with a header comment block identifying it
    as adversarial, machine-generated by Gemini Pro.

    Args:
        test_cases: List of test cases for this category.
        category: The adversarial category name.
        issue_id: GitHub issue number.

    Returns:
        Complete Python file content as a string.
    """
    lines: list[str] = []

    # Header comment block
    lines.append("# ADVERSARIAL TEST FILE - Machine-generated by Gemini Pro")
    lines.append(f"# Issue: #{issue_id}")
    lines.append(f"# Category: {category}")
    lines.append("# Generator: assemblyzero adversarial testing node")
    lines.append("# WARNING: Do not manually edit - regenerated on each workflow run")
    lines.append("")

    # Module docstring
    lines.append(f'"""Adversarial {category} tests for issue #{issue_id}.')
    lines.append("")
    lines.append("These tests exercise real code paths with NO mocks.")
    lines.append('"""')
    lines.append("")

    # Test functions
    for tc in test_cases:
        test_code = tc.get("test_code", "").strip()
        if not test_code:
            continue

        # Add a comment with test metadata
        description = tc.get("description", "")
        claim = tc.get("claim_challenged", "")
        severity = tc.get("severity", "medium")
        test_id = tc.get("test_id", "")

        lines.append("")
        if test_id or description:
            lines.append(f"# {test_id}: {description}")
        if claim:
            lines.append(f"# Challenges: {claim}")
        lines.append(f"# Severity: {severity}")

        # Ensure the test code starts with 'def test_'
        if not test_code.startswith("def test_"):
            # Wrap in a function if Gemini didn't provide proper function def
            func_name = f"test_{tc.get('test_id', 'unknown').lower()}"
            func_name = re.sub(r"[^a-z0-9_]", "_", func_name)
            lines.append(f"def {func_name}():")
            # Indent the test code
            for line in test_code.split("\n"):
                lines.append(f"    {line}")
        else:
            lines.append(test_code)

        lines.append("")

    return "\n".join(lines) + "\n"


def _sanitize_category(category: str) -> str:
    """Sanitize category name for use in filenames.

    Converts to lowercase, replaces non-alphanumeric characters with underscores.

    Args:
        category: Raw category string.

    Returns:
        Sanitized category string safe for filenames.
    """
    sanitized = re.sub(r"[^a-z0-9]", "_", category.lower())
    sanitized = re.sub(r"_+", "_", sanitized)  # Collapse multiple underscores
    sanitized = sanitized.strip("_")
    return sanitized or "general"
```

### 6.7 `assemblyzero/workflows/testing/nodes/adversarial_node.py` (Add)

**Complete file contents:**

```python
"""Core LangGraph node: orchestrates Gemini-based adversarial test generation.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

This node:
1. Collects implementation code and LLD from state
2. Builds adversarial analysis prompt
3. Invokes Gemini Pro for analysis
4. Parses structured response
5. Writes validated test files
6. Returns updated state
"""

import json
import logging
from typing import Any

from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)
from assemblyzero.workflows.testing.adversarial_state import (
    AdversarialAnalysis,
    AdversarialNodeState,
)
from assemblyzero.workflows.testing.nodes.adversarial_validator import (
    validate_adversarial_tests,
)
from assemblyzero.workflows.testing.nodes.adversarial_writer import (
    write_adversarial_tests,
)

logger = logging.getLogger(__name__)

# Token budget: ~60KB combined (implementation > LLD > existing tests)
_MAX_TOTAL_BYTES = 60_000
_IMPL_BUDGET_RATIO = 0.50  # 50% for implementation
_LLD_BUDGET_RATIO = 0.33   # 33% for LLD
_TEST_BUDGET_RATIO = 0.17  # 17% for existing tests

_REQUIRED_ANALYSIS_CATEGORIES = [
    "uncovered_edge_cases",
    "false_claims",
    "missing_error_handling",
    "implicit_assumptions",
]


def run_adversarial_node(state: AdversarialNodeState) -> AdversarialNodeState:
    """LangGraph node: Orchestrates adversarial test generation via Gemini.

    1. Collects implementation code and LLD from state.
    2. Builds adversarial analysis prompt.
    3. Invokes Gemini Pro for analysis via adversarial_gemini wrapper.
    4. Parses structured response into AdversarialAnalysis.
    5. Delegates to writer and validator.
    6. Returns updated state with generated tests.

    Fails gracefully on Gemini quota/downgrade errors (sets adversarial_skipped_reason).

    Args:
        state: The current workflow state.

    Returns:
        Updated state with adversarial test results.
    """
    logger.info("[ADV] Starting adversarial test generation node")

    # Check for implementation files
    impl_files = state.get("implementation_files", {})
    if not impl_files:
        logger.info("[ADV] No implementation files in state — skipping")
        return {
            **state,
            "adversarial_skipped_reason": "No implementation files in state",
            "adversarial_verdict": "error",
            "adversarial_test_count": 0,
            "adversarial_error": None,
            "generated_test_files": {},
        }

    # Collect and trim context
    impl_context, lld_context, test_context = _collect_context(state)

    # Invoke Gemini
    client = AdversarialGeminiClient()

    try:
        raw_response = client.generate_adversarial_tests(
            implementation_code=impl_context,
            lld_content=lld_context,
            existing_tests=test_context,
            timeout=120,
        )
    except GeminiQuotaExhaustedError:
        logger.warning("[ADV] Gemini quota exhausted — skipping adversarial tests")
        return {
            **state,
            "adversarial_skipped_reason": "Gemini quota exhausted",
            "adversarial_verdict": "error",
            "adversarial_test_count": 0,
            "adversarial_error": None,
            "generated_test_files": {},
        }
    except GeminiModelDowngradeError as e:
        logger.warning("[ADV] Gemini model downgraded to Flash — skipping: %s", e)
        return {
            **state,
            "adversarial_skipped_reason": f"Gemini model downgraded to Flash: {e}",
            "adversarial_verdict": "error",
            "adversarial_test_count": 0,
            "adversarial_error": None,
            "generated_test_files": {},
        }
    except GeminiTimeoutError:
        # Retry once with extended timeout
        logger.warning("[ADV] Gemini timeout — retrying with 180s timeout")
        try:
            raw_response = client.generate_adversarial_tests(
                implementation_code=impl_context,
                lld_content=lld_context,
                existing_tests=test_context,
                timeout=180,
            )
        except (GeminiTimeoutError, GeminiQuotaExhaustedError, GeminiModelDowngradeError) as e:
            logger.warning("[ADV] Gemini retry failed — skipping: %s", e)
            return {
                **state,
                "adversarial_skipped_reason": f"Gemini timeout after retry: {e}",
                "adversarial_verdict": "error",
                "adversarial_test_count": 0,
                "adversarial_error": None,
                "generated_test_files": {},
            }

    # Parse response
    try:
        analysis = _parse_gemini_response(raw_response)
    except ValueError as e:
        logger.error("[ADV] Malformed Gemini response: %s", e)
        return {
            **state,
            "adversarial_verdict": "error",
            "adversarial_error": f"Malformed Gemini response: {e}",
            "adversarial_test_count": 0,
            "adversarial_skipped_reason": None,
            "generated_test_files": {},
        }

    # Write test files
    issue_id = state.get("issue_id", 0)
    generated_files = write_adversarial_tests(analysis, issue_id)

    # Validate (AST no-mock scan, syntax, assertions)
    validation = validate_adversarial_tests(generated_files)

    # Remove files with mock violations or syntax errors
    clean_files: dict[str, str] = {}
    violation_files = set()

    for violation in validation["mock_violations"]:
        # Extract filepath from violation string (format: "filepath:line: message")
        parts = violation.split(":")
        if parts:
            vpath = parts[0]
            violation_files.add(vpath)

    for error in validation["errors"]:
        parts = error.split(":")
        if parts:
            epath = parts[0]
            violation_files.add(epath)

    for filepath, content in generated_files.items():
        if filepath not in violation_files:
            clean_files[filepath] = content
        else:
            logger.warning("[ADV] Rejected test file: %s", filepath)
            # Remove from disk
            try:
                os.remove(filepath)
            except OSError:
                pass

    # Count valid test functions
    test_count = 0
    for content in clean_files.values():
        test_count += content.count("\ndef test_")
        # Also count at start of file
        if content.startswith("def test_") or "\ndef test_" in content:
            pass  # already counted
        if content.lstrip().startswith("def test_"):
            test_count += 1

    # Recount more accurately using simple line scan
    test_count = 0
    for content in clean_files.values():
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def test_"):
                test_count += 1

    verdict = "pass" if test_count > 0 else "fail"

    logger.info(
        "[ADV] Adversarial testing complete: %d tests, verdict=%s",
        test_count,
        verdict,
    )

    return {
        **state,
        "adversarial_analysis": analysis,
        "generated_test_files": clean_files,
        "adversarial_verdict": verdict,
        "adversarial_error": None,
        "adversarial_test_count": test_count,
        "adversarial_skipped_reason": None,
    }


# Need os for file removal in the node
import os


def _collect_context(state: AdversarialNodeState) -> tuple[str, str, str]:
    """Extract and token-budget-trim implementation code, LLD content,
    and existing tests from state.

    Priority: implementation code > LLD > existing tests.
    Total budget: ~60KB combined.

    Args:
        state: The current workflow state.

    Returns:
        Tuple of (implementation_context, lld_context, existing_test_context).
    """
    impl_files = state.get("implementation_files", {})
    lld_content = state.get("lld_content", "")
    existing_tests = state.get("existing_tests", {})

    # Build raw context strings
    impl_parts: list[str] = []
    for filepath, content in impl_files.items():
        impl_parts.append(f"# {filepath}\n{content}")
    impl_raw = "\n\n".join(impl_parts)

    test_parts: list[str] = []
    for filepath, content in existing_tests.items():
        test_parts.append(f"# {filepath}\n{content}")
    test_raw = "\n\n".join(test_parts)

    # Apply budget
    impl_budget = int(_MAX_TOTAL_BYTES * _IMPL_BUDGET_RATIO)
    lld_budget = int(_MAX_TOTAL_BYTES * _LLD_BUDGET_RATIO)
    test_budget = int(_MAX_TOTAL_BYTES * _TEST_BUDGET_RATIO)

    impl_trimmed = _trim_to_budget(impl_raw, impl_budget)
    lld_trimmed = _trim_to_budget(lld_content, lld_budget)
    test_trimmed = _trim_to_budget(test_raw, test_budget)

    # If one section is under budget, redistribute to others
    impl_used = len(impl_trimmed.encode("utf-8"))
    lld_used = len(lld_trimmed.encode("utf-8"))
    test_used = len(test_trimmed.encode("utf-8"))
    remaining = _MAX_TOTAL_BYTES - impl_used - lld_used - test_used

    if remaining > 0 and len(impl_raw.encode("utf-8")) > impl_used:
        impl_trimmed = _trim_to_budget(impl_raw, impl_budget + remaining)

    return impl_trimmed, lld_trimmed, test_trimmed


def _trim_to_budget(text: str, max_bytes: int) -> str:
    """Trim text to fit within byte budget.

    Tries to trim at function/class boundaries to preserve readability.

    Args:
        text: Raw text to trim.
        max_bytes: Maximum bytes allowed.

    Returns:
        Trimmed text, possibly with truncation marker.
    """
    if not text:
        return ""

    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    # Truncate at byte boundary, then find last newline for clean break
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")

    # Try to find a good break point (end of a function/class)
    last_def = truncated.rfind("\ndef ")
    last_class = truncated.rfind("\nclass ")
    break_point = max(last_def, last_class)

    if break_point > len(truncated) // 2:
        truncated = truncated[:break_point]
    else:
        # Fall back to last newline
        last_newline = truncated.rfind("\n")
        if last_newline > 0:
            truncated = truncated[:last_newline]

    return truncated + "\n\n... [TRUNCATED - token budget exceeded] ..."


def _parse_gemini_response(raw_response: str) -> AdversarialAnalysis:
    """Parse Gemini's structured JSON response into AdversarialAnalysis.

    Handles:
    - Raw JSON
    - JSON wrapped in markdown code blocks (```json ... ```)
    - Validates all four required analysis categories are present

    Args:
        raw_response: Raw string response from Gemini.

    Returns:
        Parsed AdversarialAnalysis TypedDict.

    Raises:
        ValueError: If response is malformed or missing required fields.
    """
    if not raw_response or not raw_response.strip():
        raise ValueError("Empty response from Gemini")

    text = raw_response.strip()

    # Strip markdown code blocks if present
    if text.startswith("```"):
        # Remove opening ``` (with optional language tag)
        first_newline = text.find("\n")
        if first_newline > 0:
            text = text[first_newline + 1 :]
        # Remove closing ```
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    # Parse JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON response from Gemini: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected JSON object, got {type(data).__name__}"
        )

    # Validate required analysis categories
    for category in _REQUIRED_ANALYSIS_CATEGORIES:
        if category not in data:
            raise ValueError(f"Missing required analysis category: {category}")

    # Validate test_cases field
    if "test_cases" not in data:
        raise ValueError("Missing required field: test_cases")

    if not isinstance(data["test_cases"], list):
        raise ValueError("test_cases must be a list")

    # Validate each test case has required fields
    required_tc_fields = [
        "test_id",
        "target_function",
        "category",
        "description",
        "test_code",
        "claim_challenged",
        "severity",
    ]
    for i, tc in enumerate(data["test_cases"]):
        for field in required_tc_fields:
            if field not in tc:
                raise ValueError(
                    f"Test case {i} missing required field: {field}"
                )

    # Build typed result
    analysis: AdversarialAnalysis = {
        "uncovered_edge_cases": data["uncovered_edge_cases"],
        "false_claims": data["false_claims"],
        "missing_error_handling": data["missing_error_handling"],
        "implicit_assumptions": data["implicit_assumptions"],
        "test_cases": data["test_cases"],
    }

    logger.info(
        "[ADV] Parsed analysis: %d edge cases, %d false claims, "
        "%d missing handlers, %d assumptions, %d test cases",
        len(analysis["uncovered_edge_cases"]),
        len(analysis["false_claims"]),
        len(analysis["missing_error_handling"]),
        len(analysis["implicit_assumptions"]),
        len(analysis["test_cases"]),
    )

    return analysis
```

### 6.8 `tests/adversarial/__init__.py` (Add)

**Complete file contents:**

```python
"""Adversarial test package.

Issue #352: Machine-generated adversarial tests produced by Gemini Pro.
These tests exercise real code paths with NO mocks.
"""
```

### 6.9 `tests/adversarial/conftest.py` (Add)

**Complete file contents:**

```python
"""Shared fixtures for adversarial tests.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

NOTE: This conftest enforces NO MOCKS. Adversarial tests must exercise
real code paths. Any test using mocks should be flagged by the validator.
"""

import pytest


@pytest.fixture
def adversarial_marker():
    """Marker fixture indicating this is an adversarial test.

    Adversarial tests are machine-generated and exercise real code paths.
    They do not use mocks, stubs, or fakes.
    """
    return True
```

### 6.10 `assemblyzero/workflows/testing/graph.py` (Modify)

**Change 1:** Add import for adversarial node — add after existing imports (after line ~42, after the `validate_tests_mechanical` import block):

```diff
 from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
     validate_tests_mechanical_node,
     should_regenerate,
 )
 
 from assemblyzero.workflows.testing.state import TestingWorkflowState
+
+from assemblyzero.workflows.testing.nodes.adversarial_node import (
+    run_adversarial_node,
+)
```

**Change 2:** Add routing function for adversarial node — add after `route_after_finalize` function:

```diff
 def route_after_finalize(
     state: TestingWorkflowState,
 ) -> Literal["N8_document", "end"]:
     """Route after N7 (finalize).
 
 Args:"""
     ...
 
+
+def route_after_adversarial(
+    state: TestingWorkflowState,
+) -> Literal["N8_document", "end"]:
+    """Route after N7.5 (adversarial node).
+
+    Issue #352: Adversarial node is non-blocking. Always routes to N8
+    regardless of adversarial verdict (pass, fail, or error).
+
+    Args:
+        state: The current workflow state.
+
+    Returns:
+        Always "N8_document" to continue the workflow.
+    """
+    return "N8_document"
```

**Change 3:** In `build_testing_workflow()`, add the adversarial node between N7 and N8. The exact insertion depends on the function body, but the pattern is:

```diff
     # Inside build_testing_workflow():
     # After adding N7_finalize node and its edges...
+
+    # N7.5: Adversarial testing (non-blocking)
+    # Issue #352: Gemini-based adversarial test generation
+    graph.add_node("N7_5_adversarial", run_adversarial_node)
 
     # Modify N7's routing: instead of N7 → N8, make N7 → N7.5
-    # (Original) graph.add_conditional_edges("N7_finalize", route_after_finalize, {...})
+    # Update route_after_finalize to route to N7_5_adversarial instead of N8_document
+    # Or if direct edge: change from N7 → N8 to N7 → N7.5
+    graph.add_conditional_edges(
+        "N7_5_adversarial",
+        route_after_adversarial,
+        {
+            "N8_document": "N8_document",
+            "end": END,
+        },
+    )
```

**IMPORTANT NOTE for implementer:** The `build_testing_workflow()` function body is truncated to `...` in the provided code. The implementer must:
1. Find where `N7_finalize` routes to `N8_document` 
2. Change that routing to go to `N7_5_adversarial` instead
3. Add `N7_5_adversarial` node
4. Route `N7_5_adversarial` to `N8_document` (always, since adversarial is non-blocking)

If `route_after_finalize` currently returns `"N8_document"`, change it to return `"N7_5_adversarial"` and update its type hint:

```diff
 def route_after_finalize(
     state: TestingWorkflowState,
-) -> Literal["N8_document", "end"]:
+) -> Literal["N7_5_adversarial", "end"]:
     """Route after N7 (finalize).
 
-Args:"""
+    Issue #352: Now routes to adversarial node instead of directly to N8.
+
+    Args:
+        state: The current workflow state.
+    """
     ...
```

And update the `build_testing_workflow()` conditional edges mapping for N7 accordingly.

**Change 4:** Update module docstring to mention adversarial node:

```diff
 """StateGraph definition for TDD Testing Workflow.
 
 Issue #101: Test Plan Reviewer
 Issue #102: TDD Initialization
 Issue #93: N8 Documentation Node
 Issue #335: Add mechanical test validation node (N2.5)
 Issue #147: Add completeness gate node (N4b) between N4 and N5
 Issue #292: Exit code routing — N3/N5 can route to N2 on syntax/collection errors
 Issue #180: Add cleanup node (N9) after N8
+Issue #352: Add adversarial testing node (N7.5) between N7 and N8
```

### 6.11 `tests/conftest.py` (Modify)

**Change 1:** Add `adversarial` marker inside `pytest_configure`:

```diff
 def pytest_configure(config):
     """Configure pytest markers."""
+    config.addinivalue_line(
+        "markers",
+        "adversarial: adversarial tests generated by Gemini Pro (deselect with '-m \"not adversarial\"')",
+    )
     ...
```

### 6.12 `pyproject.toml` (Modify)

**Change 1:** Add `adversarial` marker to the markers list:

```diff
 [tool.pytest.ini_options]
-addopts = "-m 'not integration and not e2e'"
+addopts = "-m 'not integration and not e2e and not adversarial'"
 markers = [
     "integration: tests that call real external services (deselect with '-m \"not integration\"')",
     "e2e: end-to-end workflow tests requiring sandbox repo",
     "expensive: tests that use significant API quota",
+    "adversarial: adversarial tests generated by Gemini Pro (deselect with '-m \"not adversarial\"')",
 ]
```

### 6.13 `tests/unit/test_adversarial_node.py` (Add)

**Complete file contents:**

```python
"""Unit tests for adversarial node logic.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.adversarial_gemini import (
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)
from assemblyzero.workflows.testing.nodes.adversarial_node import (
    _collect_context,
    _parse_gemini_response,
    run_adversarial_node,
)


def _make_valid_analysis_json(**overrides):
    """Helper to build valid AdversarialAnalysis JSON."""
    base = {
        "uncovered_edge_cases": ["empty input not tested"],
        "false_claims": ["claims Unicode support but uses ASCII regex"],
        "missing_error_handling": ["FileNotFoundError uncaught at line 42"],
        "implicit_assumptions": ["assumes UTF-8 encoding"],
        "test_cases": [
            {
                "test_id": "ADV_001",
                "target_function": "module.function",
                "category": "boundary",
                "description": "Test with empty string",
                "test_code": "def test_empty_input():\n    assert module.function('') is None",
                "claim_challenged": "handles all inputs",
                "severity": "high",
            }
        ],
    }
    base.update(overrides)
    return json.dumps(base)


class TestRunAdversarialNode:
    """Tests for run_adversarial_node (T010, T020, T030, T040)."""

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_happy_path_generates_tests(self, mock_client_cls, tmp_path):
        """T010: Given valid impl + LLD, generates test files and returns pass."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.return_value = _make_valid_analysis_json()

        state = {
            "implementation_files": {
                "module.py": "def function(x):\n    return x"
            },
            "lld_content": "# Feature\n## Requirements\n1. Handles all inputs",
            "existing_tests": {},
            "issue_id": 352,
        }

        # Patch output dir to tmp
        with patch(
            "assemblyzero.workflows.testing.nodes.adversarial_node.write_adversarial_tests"
        ) as mock_write:
            mock_write.return_value = {
                "tests/adversarial/test_352_boundary.py": "def test_empty_input():\n    assert True"
            }

            result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "pass"
        assert result["adversarial_test_count"] > 0
        assert result["adversarial_skipped_reason"] is None
        assert result["generated_test_files"]

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_quota_skip(self, mock_client_cls):
        """T020: On GeminiQuotaExhaustedError, sets skipped_reason and error verdict."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = GeminiQuotaExhaustedError(
            "quota"
        )

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "quota" in result["adversarial_skipped_reason"].lower()
        assert result["adversarial_test_count"] == 0

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_downgrade_skip(self, mock_client_cls):
        """T030: On GeminiModelDowngradeError, sets skipped_reason with Flash."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = (
            GeminiModelDowngradeError("Expected Pro but received gemini-2.0-flash")
        )

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "Flash" in result["adversarial_skipped_reason"]

    def test_empty_implementation_skip(self):
        """T040: With no implementation files, skips gracefully."""
        state = {
            "implementation_files": {},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "No implementation files" in result["adversarial_skipped_reason"]
        assert result["adversarial_test_count"] == 0


class TestParseGeminiResponse:
    """Tests for _parse_gemini_response (T050, T060, T260, T270)."""

    def test_valid_json_parsed(self):
        """T050: Parses well-formed AdversarialAnalysis JSON correctly."""
        raw = _make_valid_analysis_json()
        result = _parse_gemini_response(raw)

        assert isinstance(result["uncovered_edge_cases"], list)
        assert len(result["uncovered_edge_cases"]) > 0
        assert isinstance(result["false_claims"], list)
        assert isinstance(result["missing_error_handling"], list)
        assert isinstance(result["implicit_assumptions"], list)
        assert isinstance(result["test_cases"], list)
        assert len(result["test_cases"]) == 1
        assert result["test_cases"][0]["test_id"] == "ADV_001"

    def test_malformed_json_raises(self):
        """T060: Raises ValueError on invalid JSON."""
        with pytest.raises(ValueError, match="Malformed JSON"):
            _parse_gemini_response("{broken")

    def test_all_four_categories_present(self):
        """T260: Validates all four analysis categories are present."""
        raw = _make_valid_analysis_json()
        result = _parse_gemini_response(raw)

        assert "uncovered_edge_cases" in result
        assert "false_claims" in result
        assert "missing_error_handling" in result
        assert "implicit_assumptions" in result
        assert isinstance(result["uncovered_edge_cases"], list)
        assert isinstance(result["false_claims"], list)
        assert isinstance(result["missing_error_handling"], list)
        assert isinstance(result["implicit_assumptions"], list)

    def test_missing_category_raises(self):
        """T270: JSON missing false_claims field causes ValueError."""
        data = {
            "uncovered_edge_cases": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="false_claims"):
            _parse_gemini_response(raw)

    def test_markdown_code_block_stripped(self):
        """Handles JSON wrapped in markdown code blocks."""
        inner = _make_valid_analysis_json()
        raw = f"```json\n{inner}\n```"
        result = _parse_gemini_response(raw)
        assert isinstance(result["test_cases"], list)

    def test_empty_response_raises(self):
        """Raises ValueError on empty response."""
        with pytest.raises(ValueError, match="Empty response"):
            _parse_gemini_response("")


class TestCollectContext:
    """Tests for _collect_context (T190)."""

    def test_token_budget_trimming(self):
        """T190: With oversized input, output fits within 60KB."""
        state = {
            "implementation_files": {
                "big_file.py": "x" * 200_000,
            },
            "lld_content": "y" * 100_000,
            "existing_tests": {
                "test.py": "z" * 50_000,
            },
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)
        total = len(impl.encode("utf-8")) + len(lld.encode("utf-8")) + len(tests.encode("utf-8"))

        # Allow some margin for truncation markers
        assert total <= 65_000  # 60KB + some margin for markers

    def test_empty_state(self):
        """Handles empty state gracefully."""
        state = {
            "implementation_files": {},
            "lld_content": "",
            "existing_tests": {},
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)
        assert impl == ""
        assert lld == ""
        assert tests == ""
```

### 6.14 `tests/unit/test_adversarial_writer.py` (Add)

**Complete file contents:**

```python
"""Unit tests for adversarial test file writer.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import os
import tempfile

import pytest

from assemblyzero.workflows.testing.nodes.adversarial_writer import (
    _render_test_file,
    _sanitize_category,
    write_adversarial_tests,
)


def _make_test_case(**overrides):
    """Helper to create a test case dict."""
    base = {
        "test_id": "ADV_001",
        "target_function": "module.func",
        "category": "boundary",
        "description": "Test description",
        "test_code": "def test_example():\n    assert True",
        "claim_challenged": "some claim",
        "severity": "high",
    }
    base.update(overrides)
    return base


class TestWriteAdversarialTests:
    """Tests for write_adversarial_tests (T070, T080)."""

    def test_groups_by_category(self, tmp_path):
        """T070: 3 boundary + 2 contract cases → 2 files created."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(test_id="ADV_001", category="boundary", test_code="def test_b1():\n    assert True"),
                _make_test_case(test_id="ADV_002", category="boundary", test_code="def test_b2():\n    assert True"),
                _make_test_case(test_id="ADV_003", category="boundary", test_code="def test_b3():\n    assert True"),
                _make_test_case(test_id="ADV_004", category="contract", test_code="def test_c1():\n    assert True"),
                _make_test_case(test_id="ADV_005", category="contract", test_code="def test_c2():\n    assert True"),
            ],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)

        assert len(result) == 2
        filepaths = list(result.keys())
        filenames = [os.path.basename(fp) for fp in filepaths]
        assert "test_352_boundary.py" in filenames
        assert "test_352_contract.py" in filenames

    def test_file_naming_convention(self, tmp_path):
        """T080: Output file named test_{issue_id}_{category}.py."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(category="injection", test_code="def test_inj():\n    assert True"),
            ],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)

        filepaths = list(result.keys())
        assert len(filepaths) == 1
        assert filepaths[0].endswith("test_352_injection.py")

    def test_empty_test_cases_no_files(self, tmp_path):
        """Empty test_cases returns empty dict."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)
        assert result == {}


class TestRenderTestFile:
    """Tests for _render_test_file (T090, T280, T290)."""

    def test_renders_valid_pytest_syntax(self):
        """T090: Generated file passes compile()."""
        cases = [
            _make_test_case(
                test_code="def test_something():\n    x = 1\n    assert x == 1"
            )
        ]
        content = _render_test_file(cases, "boundary", 352)
        compile(content, "test_352_boundary.py", "exec")  # Should not raise

    def test_adversarial_header_present(self):
        """T280: File starts with '# ADVERSARIAL TEST FILE' header."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "boundary", 352)
        assert content.startswith("# ADVERSARIAL TEST FILE")

    def test_header_includes_issue_and_category(self):
        """T290: Header contains issue number and category."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "injection", 352)

        lines = content.split("\n")
        header = "\n".join(lines[:5])
        assert "Issue: #352" in header
        assert "Category: injection" in header

    def test_no_mock_docstring(self):
        """Rendered file includes no-mock enforcement docstring."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "boundary", 352)
        assert "NO mocks" in content


class TestSanitizeCategory:
    """Tests for _sanitize_category."""

    def test_normal_category(self):
        assert _sanitize_category("boundary") == "boundary"

    def test_uppercase(self):
        assert _sanitize_category("BOUNDARY") == "boundary"

    def test_special_chars(self):
        assert _sanitize_category("state-machine") == "state_machine"

    def test_empty(self):
        assert _sanitize_category("") == "general"
```

### 6.15 `tests/unit/test_adversarial_validator.py` (Add)

**Complete file contents:**

```python
"""Unit tests for adversarial test validation.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import pytest

from assemblyzero.workflows.testing.nodes.adversarial_validator import (
    _check_assertions,
    _check_no_mocks,
    _check_syntax,
    validate_adversarial_tests,
)


class TestCheckNoMocks:
    """Tests for _check_no_mocks (T100, T110, T120, T130)."""

    def test_detects_unittest_mock_import(self):
        """T100: Detects 'from unittest.mock import patch'."""
        code = "from unittest.mock import patch\n\ndef test_x():\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1
        assert any("Mock import" in v for v in violations)

    def test_detects_magicmock_instantiation(self):
        """T110: Detects MagicMock() instantiation."""
        code = (
            "from unittest.mock import MagicMock\n\n"
            "def test_x():\n"
            "    m = MagicMock()\n"
            "    assert True\n"
        )
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1
        assert any("MagicMock" in v for v in violations)

    def test_detects_patch_decorator(self):
        """T120: Detects @patch decorator."""
        code = (
            "from unittest.mock import patch\n\n"
            "@patch('os.path.exists')\n"
            "def test_x(mock_exists):\n"
            "    assert True\n"
        )
        violations = _check_no_mocks(code, "test.py")
        assert any("decorator" in v.lower() or "patch" in v.lower() for v in violations)

    def test_detects_monkeypatch_fixture(self):
        """T130: Detects monkeypatch fixture usage."""
        code = "def test_x(monkeypatch):\n    monkeypatch.setattr('os.path', None)\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1
        assert any("monkeypatch" in v.lower() for v in violations)

    def test_detects_aliased_import(self):
        """Detects 'from unittest.mock import patch as p'."""
        code = "from unittest.mock import patch as p\n\ndef test_x():\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1

    def test_detects_import_unittest_mock(self):
        """Detects 'import unittest.mock'."""
        code = "import unittest.mock\n\ndef test_x():\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1

    def test_detects_from_unittest_import_mock(self):
        """Detects 'from unittest import mock'."""
        code = "from unittest import mock\n\ndef test_x():\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1


class TestValidateAdversarialTests:
    """Tests for validate_adversarial_tests (T140, T250)."""

    def test_clean_file_passes(self):
        """T140: Valid test file with no mocks passes validation."""
        files = {
            "test_352_boundary.py": (
                "def test_something():\n"
                "    x = 1 + 1\n"
                "    assert x == 2\n"
            )
        }
        result = validate_adversarial_tests(files)
        assert result["valid"] is True
        assert result["mock_violations"] == []
        assert result["errors"] == []

    def test_mock_test_rejected(self):
        """T250: Tests with mocks result in mock_violations."""
        files = {
            "test_352_boundary.py": (
                "from unittest.mock import patch\n\n"
                "@patch('os.path.exists')\n"
                "def test_x(mock_exists):\n"
                "    assert True\n"
            )
        }
        result = validate_adversarial_tests(files)
        assert result["valid"] is False
        assert len(result["mock_violations"]) > 0

    def test_empty_files_valid(self):
        """Empty test_files returns valid."""
        result = validate_adversarial_tests({})
        assert result["valid"] is True


class TestCheckSyntax:
    """Tests for _check_syntax (T160)."""

    def test_syntax_error_detected(self):
        """T160: Returns error for file that doesn't compile."""
        code = "def test_x(:\n    pass\n"
        errors = _check_syntax(code, "test.py")
        assert len(errors) == 1
        assert "SyntaxError" in errors[0]

    def test_valid_syntax_no_errors(self):
        """Valid code produces no errors."""
        code = "def test_x():\n    pass\n"
        errors = _check_syntax(code, "test.py")
        assert errors == []


class TestCheckAssertions:
    """Tests for _check_assertions (T150)."""

    def test_missing_assertions_warning(self):
        """T150: Warning for test function with no assert."""
        code = "def test_x():\n    x = 1\n"
        warnings = _check_assertions(code, "test.py")
        assert len(warnings) == 1
        assert "test_x" in warnings[0]
        assert "no assertions" in warnings[0]

    def test_has_assertion_no_warning(self):
        """No warning for test with assert statement."""
        code = "def test_x():\n    assert True\n"
        warnings = _check_assertions(code, "test.py")
        assert warnings == []

    def test_pytest_raises_counts_as_assertion(self):
        """pytest.raises context manager counts as assertion."""
        code = (
            "import pytest\n\n"
            "def test_x():\n"
            "    with pytest.raises(ValueError):\n"
            "        int('abc')\n"
        )
        warnings = _check_assertions(code, "test.py")
        assert warnings == []

    def test_non_test_function_ignored(self):
        """Functions not starting with test_ are ignored."""
        code = "def helper():\n    x = 1\n"
        warnings = _check_assertions(code, "test.py")
        assert warnings == []
```

### 6.16 `tests/unit/test_adversarial_prompts.py` (Add)

**Complete file contents:**

```python
"""Unit tests for prompt construction.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import pytest

from assemblyzero.workflows.testing.adversarial_prompts import (
    build_adversarial_analysis_prompt,
    build_adversarial_system_prompt,
)


class TestBuildAdversarialSystemPrompt:
    """Tests for build_adversarial_system_prompt (T180)."""

    def test_no_mock_enforcement(self):
        """T180: System prompt explicitly forbids mocks."""
        prompt = build_adversarial_system_prompt()
        assert "NEVER" in prompt
        assert "mock" in prompt.lower()
        assert "MagicMock" in prompt
        assert "monkeypatch" in prompt

    def test_requires_four_categories(self):
        """System prompt requires all four analysis categories."""
        prompt = build_adversarial_system_prompt()
        assert "uncovered_edge_cases" in prompt
        assert "false_claims" in prompt
        assert "missing_error_handling" in prompt
        assert "implicit_assumptions" in prompt

    def test_json_output_required(self):
        """System prompt requires JSON output."""
        prompt = build_adversarial_system_prompt()
        assert "JSON" in prompt


class TestBuildAdversarialAnalysisPrompt:
    """Tests for build_adversarial_analysis_prompt (T170)."""

    def test_prompt_contains_all_sections(self):
        """T170: Built prompt contains impl code, LLD, existing tests, patterns."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def foo():\n    return 42",
            lld_content="## Requirements\n1. foo returns 42",
            existing_tests="def test_foo():\n    assert foo() == 42",
            adversarial_patterns=["Boundary: test empty input"],
        )

        assert "def foo():" in prompt
        assert "Requirements" in prompt
        assert "def test_foo():" in prompt
        assert "Boundary: test empty input" in prompt

    def test_empty_existing_tests(self):
        """When existing_tests is empty, note is included."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=["Boundary"],
        )

        assert "No existing tests provided" in prompt

    def test_schema_included(self):
        """Prompt includes the JSON schema."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )

        assert "uncovered_edge_cases" in prompt
        assert "test_cases" in prompt
```

### 6.17 `tests/unit/test_adversarial_gemini.py` (Add)

**Complete file contents:**

```python
"""Unit tests for adversarial Gemini wrapper.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)


class TestAdversarialGeminiClient:
    """Tests for AdversarialGeminiClient (T210, T220, T230, T240)."""

    def test_delegates_to_provider(self):
        """T210: Client correctly wraps and invokes underlying provider."""
        mock_provider = MagicMock()
        # Make provider callable (Strategy 3)
        mock_provider.return_value = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}',
            {"model": "gemini-2.5-pro-preview-05-06"},
        )
        # Remove invoke and models attrs so it falls through to callable
        del mock_provider.invoke
        del mock_provider.models

        client = AdversarialGeminiClient(provider=mock_provider)
        result = client.generate_adversarial_tests(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
        )

        mock_provider.assert_called_once()
        assert "test_cases" in result

    def test_timeout_retry(self):
        """T220: On first timeout, retries once with extended timeout.

        Note: The retry logic is in run_adversarial_node, not the client.
        This tests that the client raises GeminiTimeoutError properly.
        """
        mock_provider = MagicMock()
        # Remove invoke and models to use callable strategy
        del mock_provider.invoke
        del mock_provider.models
        mock_provider.side_effect = TimeoutError("timeout")

        client = AdversarialGeminiClient(provider=mock_provider)

        with pytest.raises(GeminiTimeoutError, match="timeout"):
            client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
                timeout=120,
            )


class TestVerifyModelIsPro:
    """Tests for verify_model_is_pro (T230, T240)."""

    def test_pro_model_passes(self):
        """T230: verify_model_is_pro returns True for Pro metadata."""
        client = AdversarialGeminiClient(provider=MagicMock())
        result = client.verify_model_is_pro(
            {"model": "gemini-2.5-pro-preview-05-06"}
        )
        assert result is True

    def test_flash_detected_raises(self):
        """T240: verify_model_is_pro raises for Flash metadata."""
        client = AdversarialGeminiClient(provider=MagicMock())
        with pytest.raises(GeminiModelDowngradeError, match="Flash"):
            client.verify_model_is_pro({"model": "gemini-2.0-flash-001"})

    def test_empty_metadata_raises(self):
        """Empty metadata raises GeminiModelDowngradeError."""
        client = AdversarialGeminiClient(provider=MagicMock())
        with pytest.raises(GeminiModelDowngradeError, match="No model information"):
            client.verify_model_is_pro({})

    def test_unknown_model_passes_with_warning(self):
        """Unknown model name passes but with warning."""
        client = AdversarialGeminiClient(provider=MagicMock())
        result = client.verify_model_is_pro({"model": "gemini-ultra-2026"})
        assert result is True

    def test_pro_case_insensitive(self):
        """Model name check is case-insensitive."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client.verify_model_is_pro({"model": "Gemini-PRO-latest"}) is True
```

### 6.18 `tests/integration/test_adversarial_integration.py` (Add)

**Complete file contents:**

```python
"""Integration test: full adversarial node execution with real Gemini call.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

Requires:
- GOOGLE_API_KEY environment variable
- Network access to Gemini API
"""

import json
import os

import pytest

from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)
from assemblyzero.workflows.testing.nodes.adversarial_node import (
    _parse_gemini_response,
)


@pytest.mark.integration
@pytest.mark.adversarial
@pytest.mark.expensive
class TestAdversarialIntegration:
    """Integration tests requiring real Gemini API access (T200)."""

    @pytest.fixture(autouse=True)
    def skip_without_api_key(self):
        """Skip if no API key available."""
        if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get(
            "GEMINI_API_KEY"
        ):
            pytest.skip("No Gemini API key available (set GOOGLE_API_KEY)")

    def test_full_gemini_invocation(self):
        """T200: Real Gemini call returns parseable adversarial analysis."""
        client = AdversarialGeminiClient()

        implementation = (
            "def add(a: int, b: int) -> int:\n"
            "    '''Add two numbers.'''\n"
            "    return a + b\n"
        )
        lld = (
            "# Add Function\n"
            "## Requirements\n"
            "1. Adds two integers\n"
            "2. Returns integer result\n"
            "3. Handles overflow gracefully\n"
        )
        existing_tests = (
            "def test_add_basic():\n"
            "    assert add(1, 2) == 3\n"
        )

        try:
            raw_response = client.generate_adversarial_tests(
                implementation_code=implementation,
                lld_content=lld,
                existing_tests=existing_tests,
                timeout=120,
            )
        except (GeminiQuotaExhaustedError, GeminiTimeoutError) as e:
            pytest.skip(f"Gemini unavailable: {e}")
        except GeminiModelDowngradeError as e:
            pytest.skip(f"Gemini model downgraded: {e}")

        # Should be parseable JSON
        analysis = _parse_gemini_response(raw_response)

        # Validate structure
        assert "uncovered_edge_cases" in analysis
        assert "false_claims" in analysis
        assert "missing_error_handling" in analysis
        assert "implicit_assumptions" in analysis
        assert "test_cases" in analysis
        assert isinstance(analysis["test_cases"], list)

        # Should generate at least one test
        assert len(analysis["test_cases"]) >= 1

        # Each test case should have required fields
        for tc in analysis["test_cases"]:
            assert "test_id" in tc
            assert "test_code" in tc
            assert "category" in tc
```

## 7. Pattern References

### 7.1 LangGraph Node Implementation Pattern

**File:** `assemblyzero/workflows/testing/nodes/` (all node files in this directory)

The existing nodes follow a consistent pattern:
- Function takes `state: TypedDict` and returns updated state dict
- Graceful error handling with error message fields in state
- Logging with node identifier prefix (e.g., `[N0]`, `[N1]`)

**Relevance:** `run_adversarial_node` must follow this exact same pattern — take state, return state, log with prefix `[ADV]`, handle errors gracefully via state fields.

### 7.2 Graph Wiring Pattern

**File:** `assemblyzero/workflows/testing/graph.py` (the `build_testing_workflow` function and routing functions)

The existing graph uses:
- `graph.add_node("NAME", function)` to register nodes
- `graph.add_conditional_edges("SOURCE", route_fn, {"target1": "target1", ...})` for routing
- Route functions return `Literal[...]` types

**Relevance:** The adversarial node must be wired using the same `add_node` + `add_conditional_edges` pattern. The `route_after_adversarial` function follows the same signature as `route_after_finalize`.

### 7.3 Completeness Gate Node Pattern

**File:** `assemblyzero/workflows/testing/nodes/completeness_gate.py`

This is the most recently added node to the testing workflow (Issue #147). It demonstrates:
- How to add a new node between two existing nodes
- How to update routing functions
- How to add conditional edges

**Relevance:** The adversarial node insertion (between N7 and N8) follows the same insertion pattern used to add N4b between N4 and N5.

### 7.4 Validate Tests Mechanical Node Pattern

**File:** `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py`

This node validates test files (Issue #335). It demonstrates:
- AST-based code analysis on generated files
- Returning validation results in state
- The `should_regenerate` routing pattern

**Relevance:** `adversarial_validator.py` follows the same AST analysis approach. The validation-then-action pattern (validate → decide → proceed or skip) matches this node's architecture.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import TypedDict, Literal` | stdlib | `adversarial_state.py` |
| `import json` | stdlib | `adversarial_node.py`, `adversarial_prompts.py` |
| `import ast` | stdlib | `adversarial_validator.py` |
| `import logging` | stdlib | All new modules |
| `import os` | stdlib | `adversarial_writer.py`, `adversarial_node.py` |
| `import re` | stdlib | `adversarial_writer.py` |
| `import shutil` | stdlib | `adversarial_writer.py` |
| `import tempfile` | stdlib | `adversarial_writer.py` |
| `import importlib` | stdlib | `adversarial_gemini.py` |
| `from collections import defaultdict` | stdlib | `adversarial_writer.py` |
| `from assemblyzero.workflows.testing.adversarial_state import *` | internal | `adversarial_node.py`, `adversarial_writer.py` |
| `from assemblyzero.workflows.testing.adversarial_prompts import *` | internal | `adversarial_gemini.py` |
| `from assemblyzero.workflows.testing.adversarial_gemini import *` | internal | `adversarial_node.py` |
| `from assemblyzero.workflows.testing.knowledge.adversarial_patterns import *` | internal | `adversarial_gemini.py` |
| `from assemblyzero.workflows.testing.nodes.adversarial_validator import *` | internal | `adversarial_node.py` |
| `from assemblyzero.workflows.testing.nodes.adversarial_writer import *` | internal | `adversarial_node.py` |
| `from assemblyzero.workflows.testing.nodes.adversarial_node import run_adversarial_node` | internal | `graph.py` |
| `from langgraph.graph import END, StateGraph` | langgraph (existing dep) | `graph.py` (already imported) |
| `import pytest` | dev dependency (existing) | All test files |

**New Dependencies:** None. All imports resolve to existing stdlib or project packages.

## 9. Test Mapping

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `run_adversarial_node()` | `test_adversarial_node.py` | State with impl+LLD, mocked Gemini returning valid JSON | `verdict="pass"`, `test_count > 0` |
| T020 | `run_adversarial_node()` | `test_adversarial_node.py` | State + `GeminiQuotaExhaustedError` | `verdict="error"`, `skipped_reason` contains "quota" |
| T030 | `run_adversarial_node()` | `test_adversarial_node.py` | State + `GeminiModelDowngradeError` | `verdict="error"`, `skipped_reason` contains "Flash" |
| T040 | `run_adversarial_node()` | `test_adversarial_node.py` | State with `implementation_files={}` | `verdict="error"`, `skipped_reason` contains "No implementation" |
| T050 | `_parse_gemini_response()` | `test_adversarial_node.py` | Valid JSON string with all categories | `AdversarialAnalysis` with all fields |
| T060 | `_parse_gemini_response()` | `test_adversarial_node.py` | `"{broken"` | `ValueError` with "Malformed JSON" |
| T070 | `write_adversarial_tests()` | `test_adversarial_writer.py` | 3 boundary + 2 contract cases | 2 files created |
| T080 | `write_adversarial_tests()` | `test_adversarial_writer.py` | `issue_id=352`, `category="injection"` | File named `test_352_injection.py` |
| T090 | `_render_test_file()` | `test_adversarial_writer.py` | Single test case | `compile()` succeeds |
| T100 | `_check_no_mocks()` | `test_adversarial_validator.py` | `"from unittest.mock import patch"` | 1+ mock violation |
| T110 | `_check_no_mocks()` | `test_adversarial_validator.py` | `"m = MagicMock()"` | 1+ mock violation |
| T120 | `_check_no_mocks()` | `test_adversarial_validator.py` | `"@patch('module.func')"` | 1+ mock violation |
| T130 | `_check_no_mocks()` | `test_adversarial_validator.py` | `"def test_x(monkeypatch):"` | 1+ mock violation |
| T140 | `validate_adversarial_tests()` | `test_adversarial_validator.py` | Clean test file | `valid=True`, empty violations |
| T150 | `_check_assertions()` | `test_adversarial_validator.py` | `"def test_x(): pass"` | 1 warning |
| T160 | `_check_syntax()` | `test_adversarial_validator.py` | `"def test_x(:\n  pass"` | 1 error |
| T170 | `build_adversarial_analysis_prompt()` | `test_adversarial_prompts.py` | impl+LLD+tests+patterns | Prompt contains all sections |
| T180 | `build_adversarial_system_prompt()` | `test_adversarial_prompts.py` | N/A | Prompt contains "NEVER" and "mock" |
| T190 | `_collect_context()` | `test_adversarial_node.py` | 200KB impl + 100KB LLD | Total ≤ ~65KB |
| T200 | `AdversarialGeminiClient.generate_adversarial_tests()` | `test_adversarial_integration.py` | Real impl+LLD, real API | Valid JSON, parseable |
| T210 | `AdversarialGeminiClient.generate_adversarial_tests()` | `test_adversarial_gemini.py` | Mock provider, valid inputs | Provider called correctly |
| T220 | `AdversarialGeminiClient.generate_adversarial_tests()` | `test_adversarial_gemini.py` | Provider raises timeout | `GeminiTimeoutError` raised |
| T230 | `verify_model_is_pro()` | `test_adversarial_gemini.py` | `{"model": "gemini-2.5-pro-preview"}` | Returns `True` |
| T240 | `verify_model_is_pro()` | `test_adversarial_gemini.py` | `{"model": "gemini-2.0-flash-001"}` | Raises `GeminiModelDowngradeError` |
| T250 | `validate_adversarial_tests()` | `test_adversarial_validator.py` | File with mock import | `valid=False`, mock_violations populated |
| T260 | `_parse_gemini_response()` | `test_adversarial_node.py` | JSON with all 4 categories | All 4 category lists present |
| T270 | `_parse_gemini_response()` | `test_adversarial_node.py` | JSON missing `false_claims` | `ValueError` mentioning "false_claims" |
| T280 | `_render_test_file()` | `test_adversarial_writer.py` | Single test case | First line is `# ADVERSARIAL TEST FILE` |
| T290 | `_render_test_file()` | `test_adversarial_writer.py` | `issue_id=352`, category="injection" | Header contains "Issue: #352" and "Category: injection" |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All error scenarios in the adversarial node result in state updates rather than raised exceptions. The node follows a "fail-open" pattern:

- **Gemini errors** (quota, downgrade, timeout) → set `adversarial_verdict="error"` and `adversarial_skipped_reason` with descriptive message
- **Parse errors** (malformed JSON) → set `adversarial_verdict="error"` and `adversarial_error` with details
- **Empty input** → set `adversarial_skipped_reason` and return immediately
- **Validation failures** (mocks, syntax) → exclude offending files but continue with valid ones

The workflow should NEVER block or crash due to adversarial node issues.

### 10.2 Logging Convention

Use Python's `logging` module with the `__name__` logger in each module. Node-level log messages use `[ADV]` prefix:

```python
logger.info("[ADV] Starting adversarial test generation node")
logger.warning("[ADV] Gemini quota exhausted — skipping adversarial tests")
logger.error("[ADV] Malformed Gemini response: %s", error)
```

### 10.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `_MAX_TOTAL_BYTES` | `60_000` | ~15K tokens budget for Gemini input context |
| `_IMPL_BUDGET_RATIO` | `0.50` | Implementation code is highest priority |
| `_LLD_BUDGET_RATIO` | `0.33` | LLD provides contract claims |
| `_TEST_BUDGET_RATIO` | `0.17` | Existing tests for deduplication |
| `_REQUIRED_ANALYSIS_CATEGORIES` | 4 items | All must be present in Gemini response |
| Default `timeout` | `120` | Initial Gemini API timeout in seconds |
| Retry `timeout` | `180` | Extended timeout for single retry |
| Max test cases | `15` | Instructed in prompt to limit Gemini output |

### 10.4 File Write Atomicity

The writer uses a temp directory + `shutil.move()` pattern:
1. Create temp directory with `tempfile.mkdtemp(prefix="adversarial_")`
2. Write files to temp directory
3. Move each file to final location with `shutil.move()`
4. Clean up temp directory in `finally` block

This prevents partial/corrupt files if the process crashes mid-write.

### 10.5 Graph Wiring Note

The adversarial node is inserted as `N7_5_adversarial` between `N7_finalize` and `N8_document`. The routing is unconditional — it always proceeds to `N8_document` regardless of adversarial outcome. This means:

1. `route_after_finalize` must be updated to route to `N7_5_adversarial` instead of `N8_document`
2. A new `route_after_adversarial` function always returns `"N8_document"`
3. The conditional edges mapping for N7.5 must include both `"N8_document"` and `"end"` (for safety)

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — `graph.py`, `conftest.py`, `pyproject.toml`
- [x] Every data structure has a concrete JSON/YAML example (Section 4) — `AdversarialTestCase`, `AdversarialAnalysis`, `AdversarialNodeState`, `ValidationResult`
- [x] Every function has input/output examples with realistic values (Section 5) — 15 function specifications
- [x] Change instructions are diff-level specific (Section 6) — diffs for all 3 modify files, complete contents for all 15 add files
- [x] Pattern references include file:line and are verified to exist (Section 7) — 4 pattern references
- [x] All imports are listed and verified (Section 8) — 20+ imports mapped
- [x] Test mapping covers all LLD test scenarios (Section 9) — all 29 tests (T010–T290) mapped

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #352 |
| Verdict | DRAFT |
| Date | 2026-02-27 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #352 |
| Verdict | APPROVED |
| Date | 2026-02-27 |
| Iterations | 0 |
| Finalized | 2026-02-27T08:38:39Z |

### Review Feedback Summary

Approved with suggestions:
- **Atomicity:** In `assemblyzero/workflows/testing/nodes/adversarial_writer.py`, `shutil.move` is used for the "atomic move". While generally safe, `os.replace` is strictly atomic on POSIX systems and guarantees overwrite behavior, whereas `shutil.move` can behave differently depending on the destination (e.g., across filesystems). Given the context of writing to `tests/`, `shutil.move` is acceptable, but `os.replace` is more precise for the stated "atomic rename" goa...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  adversarial/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    issue_workflow/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
    test_metrics/
    test_rag/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 13 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  telemetry/
  utils/
  workflow/
  workflows/
    implementation_spec/
      nodes/
    issue/
      nodes/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      runners/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_adversarial_node.py
"""Unit tests for adversarial node logic.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.adversarial_gemini import (
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)
from assemblyzero.workflows.testing.nodes.adversarial_node import (
    _collect_context,
    _parse_gemini_response,
    run_adversarial_node,
)


def _make_valid_analysis_json(**overrides):
    """Helper to build valid AdversarialAnalysis JSON."""
    base = {
        "uncovered_edge_cases": ["empty input not tested"],
        "false_claims": ["claims Unicode support but uses ASCII regex"],
        "missing_error_handling": ["FileNotFoundError uncaught at line 42"],
        "implicit_assumptions": ["assumes UTF-8 encoding"],
        "test_cases": [
            {
                "test_id": "ADV_001",
                "target_function": "module.function",
                "category": "boundary",
                "description": "Test with empty string",
                "test_code": "def test_empty_input():\n    assert module.function('') is None",
                "claim_challenged": "handles all inputs",
                "severity": "high",
            }
        ],
    }
    base.update(overrides)
    return json.dumps(base)


class TestRunAdversarialNode:
    """Tests for run_adversarial_node (T010, T020, T030, T040)."""

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.write_adversarial_tests"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.validate_adversarial_tests"
    )
    def test_happy_path_generates_tests(
        self, mock_validate, mock_write, mock_client_cls, tmp_path
    ):
        """T010: Given valid impl + LLD, generates test files and returns pass."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.return_value = (
            _make_valid_analysis_json()
        )

        mock_write.return_value = {
            "tests/adversarial/test_352_boundary.py": (
                "def test_empty_input():\n    assert True\n"
            )
        }

        mock_validate.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "mock_violations": [],
        }

        state = {
            "implementation_files": {
                "module.py": "def function(x):\n    return x"
            },
            "lld_content": "# Feature\n## Requirements\n1. Handles all inputs",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "pass"
        assert result["adversarial_test_count"] > 0
        assert result["adversarial_skipped_reason"] is None
        assert result["generated_test_files"]

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_quota_skip(self, mock_client_cls):
        """T020: On GeminiQuotaExhaustedError, sets skipped_reason and error verdict."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = (
            GeminiQuotaExhaustedError("quota")
        )

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "quota" in result["adversarial_skipped_reason"].lower()
        assert result["adversarial_test_count"] == 0

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_downgrade_skip(self, mock_client_cls):
        """T030: On GeminiModelDowngradeError, sets skipped_reason with Flash."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = (
            GeminiModelDowngradeError("Expected Pro but received gemini-2.0-flash")
        )

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "Flash" in result["adversarial_skipped_reason"]

    def test_empty_implementation_skip(self):
        """T040: With no implementation files, skips gracefully."""
        state = {
            "implementation_files": {},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "No implementation files" in result["adversarial_skipped_reason"]
        assert result["adversarial_test_count"] == 0

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_malformed_response_error(self, mock_client_cls):
        """On malformed Gemini response, sets adversarial_error."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.return_value = "{broken json"

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "Malformed Gemini response" in result["adversarial_error"]

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_timeout_triggers_retry(self, mock_client_cls):
        """On first timeout, retries once then skips if retry also fails."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = GeminiTimeoutError(
            "Gemini API response exceeded 120s timeout"
        )

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "timeout" in result["adversarial_skipped_reason"].lower()
        # Should have been called twice (initial + retry)
        assert mock_client.generate_adversarial_tests.call_count == 2

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.write_adversarial_tests"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.validate_adversarial_tests"
    )
    def test_mock_violations_rejected(
        self, mock_validate, mock_write, mock_client_cls
    ):
        """Files with mock violations are excluded from clean_files."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.return_value = (
            _make_valid_analysis_json()
        )

        mock_write.return_value = {
            "tests/adversarial/test_352_boundary.py": (
                "from unittest.mock import patch\n\n"
                "def test_bad():\n    assert True\n"
            ),
            "tests/adversarial/test_352_contract.py": (
                "def test_good():\n    assert True\n"
            ),
        }

        mock_validate.return_value = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "mock_violations": [
                "tests/adversarial/test_352_boundary.py:1: Mock import detected"
            ],
        }

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        # Only clean file should remain
        assert "tests/adversarial/test_352_contract.py" in result["generated_test_files"]
        assert (
            "tests/adversarial/test_352_boundary.py"
            not in result["generated_test_files"]
        )


class TestParseGeminiResponse:
    """Tests for _parse_gemini_response (T050, T060, T260, T270)."""

    def test_valid_json_parsed(self):
        """T050: Parses well-formed AdversarialAnalysis JSON correctly."""
        raw = _make_valid_analysis_json()
        result = _parse_gemini_response(raw)

        assert isinstance(result["uncovered_edge_cases"], list)
        assert len(result["uncovered_edge_cases"]) > 0
        assert isinstance(result["false_claims"], list)
        assert isinstance(result["missing_error_handling"], list)
        assert isinstance(result["implicit_assumptions"], list)
        assert isinstance(result["test_cases"], list)
        assert len(result["test_cases"]) == 1
        assert result["test_cases"][0]["test_id"] == "ADV_001"

    def test_malformed_json_raises(self):
        """T060: Raises ValueError on invalid JSON."""
        with pytest.raises(ValueError, match="Malformed JSON"):
            _parse_gemini_response("{broken")

    def test_all_four_categories_present(self):
        """T260: Validates all four analysis categories are present."""
        raw = _make_valid_analysis_json()
        result = _parse_gemini_response(raw)

        assert "uncovered_edge_cases" in result
        assert "false_claims" in result
        assert "missing_error_handling" in result
        assert "implicit_assumptions" in result
        assert isinstance(result["uncovered_edge_cases"], list)
        assert isinstance(result["false_claims"], list)
        assert isinstance(result["missing_error_handling"], list)
        assert isinstance(result["implicit_assumptions"], list)

    def test_missing_category_raises(self):
        """T270: JSON missing false_claims field causes ValueError."""
        data = {
            "uncovered_edge_cases": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="false_claims"):
            _parse_gemini_response(raw)

    def test_markdown_code_block_stripped(self):
        """Handles JSON wrapped in markdown code blocks."""
        inner = _make_valid_analysis_json()
        raw = f"```json\n{inner}\n```"
        result = _parse_gemini_response(raw)
        assert isinstance(result["test_cases"], list)

    def test_empty_response_raises(self):
        """Raises ValueError on empty response."""
        with pytest.raises(ValueError, match="Empty response"):
            _parse_gemini_response("")

    def test_whitespace_only_response_raises(self):
        """Raises ValueError on whitespace-only response."""
        with pytest.raises(ValueError, match="Empty response"):
            _parse_gemini_response("   \n  ")

    def test_missing_test_cases_raises(self):
        """Raises ValueError when test_cases field is missing."""
        data = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="test_cases"):
            _parse_gemini_response(raw)

    def test_test_cases_not_list_raises(self):
        """Raises ValueError when test_cases is not a list."""
        data = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": "not a list",
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="test_cases must be a list"):
            _parse_gemini_response(raw)

    def test_empty_test_cases_valid(self):
        """Empty test_cases list is valid."""
        raw = _make_valid_analysis_json(test_cases=[])
        result = _parse_gemini_response(raw)
        assert result["test_cases"] == []

    def test_test_case_missing_field_raises(self):
        """Raises ValueError when a test case is missing required fields."""
        data = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                {
                    "test_id": "ADV_001",
                    # missing target_function, category, etc.
                }
            ],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="missing required field"):
            _parse_gemini_response(raw)

    def test_non_dict_response_raises(self):
        """Raises ValueError when JSON is a list instead of object."""
        raw = json.dumps([1, 2, 3])
        with pytest.raises(ValueError, match="Expected JSON object"):
            _parse_gemini_response(raw)

    def test_multiple_test_cases_parsed(self):
        """Parses multiple test cases correctly."""
        test_cases = [
            {
                "test_id": f"ADV_{i:03d}",
                "target_function": f"module.func_{i}",
                "category": "boundary",
                "description": f"Test case {i}",
                "test_code": f"def test_case_{i}():\n    assert True",
                "claim_challenged": f"claim {i}",
                "severity": "medium",
            }
            for i in range(5)
        ]
        raw = _make_valid_analysis_json(test_cases=test_cases)
        result = _parse_gemini_response(raw)
        assert len(result["test_cases"]) == 5

    def test_missing_uncovered_edge_cases_raises(self):
        """Missing uncovered_edge_cases raises ValueError."""
        data = {
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="uncovered_edge_cases"):
            _parse_gemini_response(raw)

    def test_missing_missing_error_handling_raises(self):
        """Missing missing_error_handling raises ValueError."""
        data = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "implicit_assumptions": [],
            "test_cases": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="missing_error_handling"):
            _parse_gemini_response(raw)

    def test_missing_implicit_assumptions_raises(self):
        """Missing implicit_assumptions raises ValueError."""
        data = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "test_cases": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="implicit_assumptions"):
            _parse_gemini_response(raw)


class TestCollectContext:
    """Tests for _collect_context (T190)."""

    def test_token_budget_trimming(self):
        """T190: With oversized input, output fits within 60KB."""
        state = {
            "implementation_files": {
                "big_file.py": "x" * 200_000,
            },
            "lld_content": "y" * 100_000,
            "existing_tests": {
                "test.py": "z" * 50_000,
            },
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)
        total = (
            len(impl.encode("utf-8"))
            + len(lld.encode("utf-8"))
            + len(tests.encode("utf-8"))
        )

        # Allow some margin for truncation markers
        assert total <= 65_000  # 60KB + some margin for markers

    def test_empty_state(self):
        """Handles empty state gracefully."""
        state = {
            "implementation_files": {},
            "lld_content": "",
            "existing_tests": {},
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)
        assert impl == ""
        assert lld == ""
        assert tests == ""

    def test_small_input_not_truncated(self):
        """Small inputs are returned without truncation."""
        state = {
            "implementation_files": {
                "small.py": "def foo():\n    return 42\n",
            },
            "lld_content": "# Small LLD\n## Requirements\n1. foo returns 42",
            "existing_tests": {
                "test_small.py": "def test_foo():\n    assert foo() == 42\n",
            },
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)

        assert "def foo():" in impl
        assert "Small LLD" in lld
        assert "def test_foo():" in tests
        # No truncation marker
        assert "TRUNCATED" not in impl
        assert "TRUNCATED" not in lld
        assert "TRUNCATED" not in tests

    def test_multiple_impl_files_concatenated(self):
        """Multiple implementation files are concatenated with headers."""
        state = {
            "implementation_files": {
                "file1.py": "def foo(): pass",
                "file2.py": "def bar(): pass",
            },
            "lld_content": "",
            "existing_tests": {},
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)

        assert "file1.py" in impl
        assert "file2.py" in impl
        assert "def foo():" in impl
        assert "def bar():" in impl

    def test_oversized_impl_truncated_with_marker(self):
        """Implementation exceeding budget gets truncation marker."""
        state = {
            "implementation_files": {
                "big.py": "x" * 200_000,
            },
            "lld_content": "",
            "existing_tests": {},
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)

        assert "TRUNCATED" in impl
        assert len(impl.encode("utf-8")) < 200_000

    def test_missing_keys_handled(self):
        """Handles state with missing optional keys."""
        state = {
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)
        assert impl == ""
        assert lld == ""
        assert tests == ""

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_adversarial_writer.py
"""Unit tests for adversarial test file writer.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import os
import tempfile

import pytest

from assemblyzero.workflows.testing.nodes.adversarial_writer import (
    _render_test_file,
    _sanitize_category,
    write_adversarial_tests,
)


def _make_test_case(**overrides):
    """Helper to create a test case dict."""
    base = {
        "test_id": "ADV_001",
        "target_function": "module.func",
        "category": "boundary",
        "description": "Test description",
        "test_code": "def test_example():\n    assert True",
        "claim_challenged": "some claim",
        "severity": "high",
    }
    base.update(overrides)
    return base


class TestWriteAdversarialTests:
    """Tests for write_adversarial_tests (T070, T080)."""

    def test_groups_by_category(self, tmp_path):
        """T070: 3 boundary + 2 contract cases → 2 files created."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(test_id="ADV_001", category="boundary", test_code="def test_b1():\n    assert True"),
                _make_test_case(test_id="ADV_002", category="boundary", test_code="def test_b2():\n    assert True"),
                _make_test_case(test_id="ADV_003", category="boundary", test_code="def test_b3():\n    assert True"),
                _make_test_case(test_id="ADV_004", category="contract", test_code="def test_c1():\n    assert True"),
                _make_test_case(test_id="ADV_005", category="contract", test_code="def test_c2():\n    assert True"),
            ],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)

        assert len(result) == 2
        filepaths = list(result.keys())
        filenames = [os.path.basename(fp) for fp in filepaths]
        assert "test_352_boundary.py" in filenames
        assert "test_352_contract.py" in filenames

    def test_file_naming_convention(self, tmp_path):
        """T080: Output file named test_{issue_id}_{category}.py."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(category="injection", test_code="def test_inj():\n    assert True"),
            ],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)

        filepaths = list(result.keys())
        assert len(filepaths) == 1
        assert filepaths[0].endswith("test_352_injection.py")

    def test_empty_test_cases_no_files(self, tmp_path):
        """Empty test_cases returns empty dict."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)
        assert result == {}

    def test_creates_output_dir(self, tmp_path):
        """Output directory is created if it doesn't exist."""
        output_dir = str(tmp_path / "nested" / "adversarial")
        assert not os.path.exists(output_dir)

        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(test_code="def test_x():\n    assert True"),
            ],
        }

        result = write_adversarial_tests(analysis, issue_id=99, output_dir=output_dir)
        assert len(result) == 1
        assert os.path.exists(output_dir)

    def test_files_written_to_disk(self, tmp_path):
        """Files are actually written to disk, not just returned."""
        output_dir = str(tmp_path / "adversarial")
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(category="boundary", test_code="def test_disk():\n    assert True"),
            ],
        }

        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)

        for filepath, content in result.items():
            assert os.path.exists(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                assert f.read() == content

    def test_multiple_categories_separate_files(self, tmp_path):
        """Each category gets its own file."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(test_id="ADV_001", category="boundary", test_code="def test_b():\n    assert True"),
                _make_test_case(test_id="ADV_002", category="injection", test_code="def test_i():\n    assert True"),
                _make_test_case(test_id="ADV_003", category="state", test_code="def test_s():\n    assert True"),
            ],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=100, output_dir=output_dir)

        assert len(result) == 3
        filenames = [os.path.basename(fp) for fp in result.keys()]
        assert "test_100_boundary.py" in filenames
        assert "test_100_injection.py" in filenames
        assert "test_100_state.py" in filenames


class TestRenderTestFile:
    """Tests for _render_test_file (T090, T280, T290)."""

    def test_renders_valid_pytest_syntax(self):
        """T090: Generated file passes compile()."""
        cases = [
            _make_test_case(
                test_code="def test_something():\n    x = 1\n    assert x == 1"
            )
        ]
        content = _render_test_file(cases, "boundary", 352)
        compile(content, "test_352_boundary.py", "exec")  # Should not raise

    def test_adversarial_header_present(self):
        """T280: File starts with '# ADVERSARIAL TEST FILE' header."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "boundary", 352)
        assert content.startswith("# ADVERSARIAL TEST FILE")

    def test_header_includes_issue_and_category(self):
        """T290: Header contains issue number and category."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "injection", 352)

        lines = content.split("\n")
        header = "\n".join(lines[:5])
        assert "Issue: #352" in header
        assert "Category: injection" in header

    def test_no_mock_docstring(self):
        """Rendered file includes no-mock enforcement docstring."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "boundary", 352)
        assert "NO mocks" in content

    def test_empty_cases_renders_header_only(self):
        """Empty test_cases list renders file with header/docstring only."""
        content = _render_test_file([], "boundary", 352)
        assert "# ADVERSARIAL TEST FILE" in content
        assert "NO mocks" in content
        # Should still compile
        compile(content, "test_352_boundary.py", "exec")

    def test_test_code_without_def_wrapped(self):
        """Test code without 'def test_' prefix is wrapped in a function."""
        cases = [
            _make_test_case(
                test_id="ADV_042",
                test_code="assert 1 + 1 == 2",
            )
        ]
        content = _render_test_file(cases, "boundary", 352)
        assert "def test_" in content
        # Should compile
        compile(content, "test_352_boundary.py", "exec")

    def test_severity_comment_present(self):
        """Rendered file includes severity comment for each test."""
        cases = [
            _make_test_case(severity="critical")
        ]
        content = _render_test_file(cases, "boundary", 352)
        assert "# Severity: critical" in content

    def test_claim_challenged_comment(self):
        """Rendered file includes claim challenged comment."""
        cases = [
            _make_test_case(claim_challenged="LLD claims all inputs handled")
        ]
        content = _render_test_file(cases, "boundary", 352)
        assert "# Challenges: LLD claims all inputs handled" in content

    def test_multiple_cases_all_rendered(self):
        """All test cases are rendered in the output."""
        cases = [
            _make_test_case(test_id="ADV_001", test_code="def test_one():\n    assert True"),
            _make_test_case(test_id="ADV_002", test_code="def test_two():\n    assert True"),
            _make_test_case(test_id="ADV_003", test_code="def test_three():\n    assert True"),
        ]
        content = _render_test_file(cases, "boundary", 352)
        assert "def test_one():" in content
        assert "def test_two():" in content
        assert "def test_three():" in content
        compile(content, "test_352_boundary.py", "exec")

    def test_empty_test_code_skipped(self):
        """Test cases with empty test_code are skipped."""
        cases = [
            _make_test_case(test_id="ADV_001", test_code=""),
            _make_test_case(test_id="ADV_002", test_code="def test_real():\n    assert True"),
        ]
        content = _render_test_file(cases, "boundary", 352)
        assert "def test_real():" in content
        # The empty one should not generate a broken function
        compile(content, "test_352_boundary.py", "exec")

    def test_generator_comment_in_header(self):
        """Header includes generator identification."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "boundary", 352)
        assert "Generator: assemblyzero adversarial testing node" in content

    def test_warning_comment_in_header(self):
        """Header includes regeneration warning."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "boundary", 352)
        assert "WARNING: Do not manually edit" in content


class TestSanitizeCategory:
    """Tests for _sanitize_category."""

    def test_normal_category(self):
        assert _sanitize_category("boundary") == "boundary"

    def test_uppercase(self):
        assert _sanitize_category("BOUNDARY") == "boundary"

    def test_special_chars(self):
        assert _sanitize_category("state-machine") == "state_machine"

    def test_empty(self):
        assert _sanitize_category("") == "general"

    def test_spaces(self):
        assert _sanitize_category("edge case") == "edge_case"

    def test_multiple_special_chars(self):
        """Multiple consecutive special chars collapse to single underscore."""
        result = _sanitize_category("foo--bar__baz")
        assert "__" not in result
        assert "--" not in result

    def test_leading_trailing_special_chars(self):
        """Leading/trailing special characters are stripped."""
        result = _sanitize_category("-boundary-")
        assert result == "boundary"

    def test_numbers_preserved(self):
        """Numbers in category names are preserved."""
        assert _sanitize_category("test123") == "test123"

    def test_mixed_case_with_special(self):
        """Mixed case with special characters handled correctly."""
        result = _sanitize_category("State-Machine_Test")
        assert result == "state_machine_test"

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_adversarial_validator.py
"""Unit tests for adversarial test validation.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import pytest

from assemblyzero.workflows.testing.nodes.adversarial_validator import (
    _check_assertions,
    _check_no_mocks,
    _check_syntax,
    validate_adversarial_tests,
)


class TestCheckNoMocks:
    """Tests for _check_no_mocks (T100, T110, T120, T130)."""

    def test_detects_unittest_mock_import(self):
        """T100: Detects 'from unittest.mock import patch'."""
        code = "from unittest.mock import patch\n\ndef test_x():\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1
        assert any("Mock import" in v for v in violations)

    def test_detects_magicmock_instantiation(self):
        """T110: Detects MagicMock() instantiation."""
        code = (
            "from unittest.mock import MagicMock\n\n"
            "def test_x():\n"
            "    m = MagicMock()\n"
            "    assert True\n"
        )
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1
        assert any("MagicMock" in v for v in violations)

    def test_detects_patch_decorator(self):
        """T120: Detects @patch decorator."""
        code = (
            "from unittest.mock import patch\n\n"
            "@patch('os.path.exists')\n"
            "def test_x(mock_exists):\n"
            "    assert True\n"
        )
        violations = _check_no_mocks(code, "test.py")
        assert any("decorator" in v.lower() or "patch" in v.lower() for v in violations)

    def test_detects_monkeypatch_fixture(self):
        """T130: Detects monkeypatch fixture usage."""
        code = "def test_x(monkeypatch):\n    monkeypatch.setattr('os.path', None)\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1
        assert any("monkeypatch" in v.lower() for v in violations)

    def test_detects_aliased_import(self):
        """Detects 'from unittest.mock import patch as p'."""
        code = "from unittest.mock import patch as p\n\ndef test_x():\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1

    def test_detects_import_unittest_mock(self):
        """Detects 'import unittest.mock'."""
        code = "import unittest.mock\n\ndef test_x():\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1

    def test_detects_from_unittest_import_mock(self):
        """Detects 'from unittest import mock'."""
        code = "from unittest import mock\n\ndef test_x():\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1

    def test_clean_code_no_violations(self):
        """Clean code with no mocks returns empty violations list."""
        code = (
            "import os\n\n"
            "def test_x():\n"
            "    assert os.path.exists('/tmp')\n"
        )
        violations = _check_no_mocks(code, "test.py")
        assert violations == []

    def test_mock_in_string_not_flagged(self):
        """Mock mentioned in string literals is not flagged."""
        code = (
            "def test_x():\n"
            '    msg = "use mock for testing"\n'
            "    assert len(msg) > 0\n"
        )
        violations = _check_no_mocks(code, "test.py")
        assert violations == []

    def test_syntax_error_returns_empty(self):
        """Syntax errors in code return empty violations (handled separately)."""
        code = "def test_x(:\n    pass\n"
        violations = _check_no_mocks(code, "test.py")
        assert violations == []

    def test_detects_async_mock(self):
        """Detects AsyncMock instantiation."""
        code = (
            "from unittest.mock import AsyncMock\n\n"
            "def test_x():\n"
            "    m = AsyncMock()\n"
            "    assert True\n"
        )
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1
        assert any("AsyncMock" in v for v in violations)

    def test_detects_mock_patch_attribute(self):
        """Detects @mock.patch decorator style."""
        code = (
            "import unittest.mock\n\n"
            "@unittest.mock.patch('os.path.exists')\n"
            "def test_x(mock_exists):\n"
            "    assert True\n"
        )
        violations = _check_no_mocks(code, "test.py")
        assert len(violations) >= 1

    def test_filepath_in_violation_message(self):
        """Violation messages include the filepath."""
        code = "from unittest.mock import patch\n\ndef test_x():\n    assert True\n"
        violations = _check_no_mocks(code, "tests/adversarial/test_352_boundary.py")
        assert all("tests/adversarial/test_352_boundary.py" in v for v in violations)

    def test_line_number_in_violation_message(self):
        """Violation messages include line numbers."""
        code = "from unittest.mock import patch\n\ndef test_x():\n    assert True\n"
        violations = _check_no_mocks(code, "test.py")
        assert any(":1:" in v for v in violations)


class TestValidateAdversarialTests:
    """Tests for validate_adversarial_tests (T140, T250)."""

    def test_clean_file_passes(self):
        """T140: Valid test file with no mocks passes validation."""
        files = {
            "test_352_boundary.py": (
                "def test_something():\n"
                "    x = 1 + 1\n"
                "    assert x == 2\n"
            )
        }
        result = validate_adversarial_tests(files)
        assert result["valid"] is True
        assert result["mock_violations"] == []
        assert result["errors"] == []

    def test_mock_test_rejected(self):
        """T250: Tests with mocks result in mock_violations."""
        files = {
            "test_352_boundary.py": (
                "from unittest.mock import patch\n\n"
                "@patch('os.path.exists')\n"
                "def test_x(mock_exists):\n"
                "    assert True\n"
            )
        }
        result = validate_adversarial_tests(files)
        assert result["valid"] is False
        assert len(result["mock_violations"]) > 0

    def test_empty_files_valid(self):
        """Empty test_files returns valid."""
        result = validate_adversarial_tests({})
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["warnings"] == []
        assert result["mock_violations"] == []

    def test_syntax_error_invalid(self):
        """File with syntax error results in valid=False."""
        files = {
            "test_352_boundary.py": "def test_x(:\n    pass\n"
        }
        result = validate_adversarial_tests(files)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_multiple_files_mixed_results(self):
        """Multiple files: one clean, one with mocks."""
        files = {
            "test_352_boundary.py": (
                "def test_clean():\n"
                "    assert True\n"
            ),
            "test_352_injection.py": (
                "from unittest.mock import patch\n\n"
                "def test_mocked():\n"
                "    assert True\n"
            ),
        }
        result = validate_adversarial_tests(files)
        assert result["valid"] is False
        assert len(result["mock_violations"]) > 0

    def test_warnings_for_missing_assertions(self):
        """Files with test functions missing assertions produce warnings."""
        files = {
            "test_352_boundary.py": (
                "def test_no_assert():\n"
                "    x = 1\n"
            )
        }
        result = validate_adversarial_tests(files)
        # Missing assertions are warnings, not errors
        assert len(result["warnings"]) > 0
        assert "no assertions" in result["warnings"][0]

    def test_duplicate_test_names_warning(self):
        """Duplicate test function names across files produce warnings."""
        files = {
            "test_352_boundary.py": (
                "def test_duplicate():\n"
                "    assert True\n"
            ),
            "test_352_contract.py": (
                "def test_duplicate():\n"
                "    assert True\n"
            ),
        }
        result = validate_adversarial_tests(files)
        assert any("Duplicate" in w for w in result["warnings"])

    def test_syntax_error_skips_ast_analysis(self):
        """Files with syntax errors skip mock/assertion checks."""
        files = {
            "test_352_boundary.py": (
                "from unittest.mock import patch\n"
                "def test_x(:\n"
                "    pass\n"
            )
        }
        result = validate_adversarial_tests(files)
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        # Mock violations should NOT be reported for syntactically invalid files
        # since AST analysis is skipped
        assert result["mock_violations"] == []

    def test_only_mock_violations_make_invalid(self):
        """Warnings alone don't make result invalid; mock violations do."""
        files = {
            "test_352_boundary.py": (
                "def test_no_assert():\n"
                "    x = 1\n"
            )
        }
        result = validate_adversarial_tests(files)
        # Only warnings (missing assertions), no errors or mock violations
        assert result["valid"] is True
        assert len(result["warnings"]) > 0


class TestCheckSyntax:
    """Tests for _check_syntax (T160)."""

    def test_syntax_error_detected(self):
        """T160: Returns error for file that doesn't compile."""
        code = "def test_x(:\n    pass\n"
        errors = _check_syntax(code, "test.py")
        assert len(errors) == 1
        assert "SyntaxError" in errors[0]

    def test_valid_syntax_no_errors(self):
        """Valid code produces no errors."""
        code = "def test_x():\n    pass\n"
        errors = _check_syntax(code, "test.py")
        assert errors == []

    def test_filepath_in_error_message(self):
        """Error message includes the filepath."""
        code = "def test_x(:\n    pass\n"
        errors = _check_syntax(code, "tests/adversarial/test_352_boundary.py")
        assert "tests/adversarial/test_352_boundary.py" in errors[0]

    def test_line_number_in_error_message(self):
        """Error message includes line number."""
        code = "def test_x():\n    pass\ndef test_y(:\n    pass\n"
        errors = _check_syntax(code, "test.py")
        assert len(errors) == 1
        assert "line" in errors[0].lower()

    def test_empty_code_valid(self):
        """Empty string is valid Python."""
        errors = _check_syntax("", "test.py")
        assert errors == []

    def test_complex_valid_code(self):
        """Complex but valid code produces no errors."""
        code = (
            "import os\n"
            "import pytest\n\n"
            "class TestFoo:\n"
            "    def test_bar(self):\n"
            "        with pytest.raises(ValueError):\n"
            "            int('abc')\n"
            "\n"
            "    def test_baz(self):\n"
            "        assert os.path.sep in ('/', '\\\\')\n"
        )
        errors = _check_syntax(code, "test.py")
        assert errors == []


class TestCheckAssertions:
    """Tests for _check_assertions (T150)."""

    def test_missing_assertions_warning(self):
        """T150: Warning for test function with no assert."""
        code = "def test_x():\n    x = 1\n"
        warnings = _check_assertions(code, "test.py")
        assert len(warnings) == 1
        assert "test_x" in warnings[0]
        assert "no assertions" in warnings[0]

    def test_has_assertion_no_warning(self):
        """No warning for test with assert statement."""
        code = "def test_x():\n    assert True\n"
        warnings = _check_assertions(code, "test.py")
        assert warnings == []

    def test_pytest_raises_counts_as_assertion(self):
        """pytest.raises context manager counts as assertion."""
        code = (
            "import pytest\n\n"
            "def test_x():\n"
            "    with pytest.raises(ValueError):\n"
            "        int('abc')\n"
        )
        warnings = _check_assertions(code, "test.py")
        assert warnings == []

    def test_non_test_function_ignored(self):
        """Functions not starting with test_ are ignored."""
        code = "def helper():\n    x = 1\n"
        warnings = _check_assertions(code, "test.py")
        assert warnings == []

    def test_empty_file_no_warnings(self):
        """Empty file returns no warnings."""
        warnings = _check_assertions("", "test.py")
        assert warnings == []

    def test_multiple_test_functions_mixed(self):
        """Multiple test functions: some with assertions, some without."""
        code = (
            "def test_with_assert():\n"
            "    assert True\n\n"
            "def test_without_assert():\n"
            "    x = 1\n\n"
            "def test_also_with_assert():\n"
            "    assert 1 == 1\n"
        )
        warnings = _check_assertions(code, "test.py")
        assert len(warnings) == 1
        assert "test_without_assert" in warnings[0]

    def test_syntax_error_returns_empty(self):
        """Syntax errors in code return empty warnings (handled separately)."""
        code = "def test_x(:\n    assert True\n"
        warnings = _check_assertions(code, "test.py")
        assert warnings == []

    def test_filepath_in_warning_message(self):
        """Warning messages include the filepath."""
        code = "def test_x():\n    x = 1\n"
        warnings = _check_assertions(code, "tests/adversarial/test_352_boundary.py")
        assert "tests/adversarial/test_352_boundary.py" in warnings[0]

    def test_assert_in_nested_function_not_counted(self):
        """Assert in a nested function does not count for outer test."""
        code = (
            "def test_x():\n"
            "    def inner():\n"
            "        assert True\n"
            "    inner()\n"
        )
        # The AST walker walks into nested functions too, so ast.walk
        # on the test_x node WILL find the assert in inner().
        # This is a known limitation - the current implementation counts it.
        # We test the actual behavior:
        warnings = _check_assertions(code, "test.py")
        # ast.walk descends into nested functions, so assert IS found
        assert warnings == []

    def test_class_based_test_methods(self):
        """Test methods in classes are also checked."""
        code = (
            "class TestFoo:\n"
            "    def test_method_no_assert(self):\n"
            "        x = 1\n"
            "\n"
            "    def test_method_with_assert(self):\n"
            "        assert True\n"
        )
        warnings = _check_assertions(code, "test.py")
        assert len(warnings) == 1
        assert "test_method_no_assert" in warnings[0]

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_adversarial_prompts.py
"""Unit tests for prompt construction.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import pytest

from assemblyzero.workflows.testing.adversarial_prompts import (
    build_adversarial_analysis_prompt,
    build_adversarial_system_prompt,
)


class TestBuildAdversarialSystemPrompt:
    """Tests for build_adversarial_system_prompt (T180)."""

    def test_no_mock_enforcement(self):
        """T180: System prompt explicitly forbids mocks."""
        prompt = build_adversarial_system_prompt()
        assert "NEVER" in prompt
        assert "mock" in prompt.lower()
        assert "MagicMock" in prompt
        assert "monkeypatch" in prompt

    def test_requires_four_categories(self):
        """System prompt requires all four analysis categories."""
        prompt = build_adversarial_system_prompt()
        assert "uncovered_edge_cases" in prompt
        assert "false_claims" in prompt
        assert "missing_error_handling" in prompt
        assert "implicit_assumptions" in prompt

    def test_json_output_required(self):
        """System prompt requires JSON output."""
        prompt = build_adversarial_system_prompt()
        assert "JSON" in prompt

    def test_returns_string(self):
        """System prompt returns a non-empty string."""
        prompt = build_adversarial_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_severity_levels_documented(self):
        """System prompt documents severity levels."""
        prompt = build_adversarial_system_prompt()
        assert "critical" in prompt
        assert "high" in prompt
        assert "medium" in prompt

    def test_max_test_cases_mentioned(self):
        """System prompt mentions maximum test case limit."""
        prompt = build_adversarial_system_prompt()
        assert "15" in prompt

    def test_no_markdown_code_blocks_instruction(self):
        """System prompt instructs not to wrap in markdown code blocks."""
        prompt = build_adversarial_system_prompt()
        assert "Do NOT wrap" in prompt or "code block" in prompt.lower()

    def test_assert_requirement(self):
        """System prompt requires assert statements in tests."""
        prompt = build_adversarial_system_prompt()
        assert "assert" in prompt.lower()

    def test_test_prefix_requirement(self):
        """System prompt requires test_ prefix on function names."""
        prompt = build_adversarial_system_prompt()
        assert "test_" in prompt


class TestBuildAdversarialAnalysisPrompt:
    """Tests for build_adversarial_analysis_prompt (T170)."""

    def test_prompt_contains_all_sections(self):
        """T170: Built prompt contains impl code, LLD, existing tests, patterns."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def foo():\n    return 42",
            lld_content="## Requirements\n1. foo returns 42",
            existing_tests="def test_foo():\n    assert foo() == 42",
            adversarial_patterns=["Boundary: test empty input"],
        )

        assert "def foo():" in prompt
        assert "Requirements" in prompt
        assert "def test_foo():" in prompt
        assert "Boundary: test empty input" in prompt

    def test_empty_existing_tests(self):
        """When existing_tests is empty, note is included."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=["Boundary"],
        )

        assert "No existing tests provided" in prompt

    def test_schema_included(self):
        """Prompt includes the JSON schema."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )

        assert "uncovered_edge_cases" in prompt
        assert "test_cases" in prompt

    def test_returns_string(self):
        """Analysis prompt returns a non-empty string."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=["Boundary"],
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_implementation_code_section(self):
        """Prompt includes implementation code section header."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def bar(): return 1",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=[],
        )
        assert "Implementation Code Under Test" in prompt
        assert "def bar(): return 1" in prompt

    def test_lld_section(self):
        """Prompt includes LLD section header."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="## Feature Design\nSome claims here",
            existing_tests="",
            adversarial_patterns=[],
        )
        assert "Low-Level Design" in prompt or "LLD" in prompt
        assert "Some claims here" in prompt

    def test_existing_tests_section_when_provided(self):
        """Prompt includes existing test suite section when tests are provided."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="def test_existing():\n    assert True",
            adversarial_patterns=[],
        )
        assert "Existing Test Suite" in prompt
        assert "def test_existing():" in prompt
        assert "No existing tests provided" not in prompt

    def test_multiple_patterns_listed(self):
        """Multiple adversarial patterns are all listed in the prompt."""
        patterns = [
            "Boundary: test empty strings",
            "Contract: verify preconditions",
            "Resource: test timeout behavior",
        ]
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=patterns,
        )
        for pattern in patterns:
            assert pattern in prompt

    def test_no_mock_reminder(self):
        """Prompt includes a reminder about no mocks."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )
        assert "mock" in prompt.lower() or "NO mock" in prompt

    def test_instructions_section(self):
        """Prompt includes instructions section."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )
        assert "Instructions" in prompt

    def test_json_only_requirement(self):
        """Prompt specifies JSON-only response requirement."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )
        assert "JSON" in prompt

    def test_schema_has_required_fields(self):
        """Prompt schema includes all required test case fields."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )
        assert "test_id" in prompt
        assert "target_function" in prompt
        assert "category" in prompt
        assert "test_code" in prompt
        assert "claim_challenged" in prompt
        assert "severity" in prompt

    def test_empty_patterns_list(self):
        """Empty patterns list still produces a valid prompt."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=[],
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should still have the patterns section header
        assert "Adversarial Testing Patterns" in prompt

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_adversarial_gemini.py
"""Unit tests for adversarial Gemini wrapper.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)


class TestAdversarialGeminiClient:
    """Tests for AdversarialGeminiClient (T210, T220, T230, T240)."""

    def test_delegates_to_provider(self):
        """T210: Client correctly wraps and invokes underlying provider."""
        mock_provider = MagicMock(spec=[])  # empty spec so no attrs leak
        mock_provider.return_value = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}',
            {"model": "gemini-2.5-pro-preview-05-06"},
        )

        client = AdversarialGeminiClient(provider=mock_provider)
        result = client.generate_adversarial_tests(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
        )

        mock_provider.assert_called_once()
        assert "test_cases" in result

    def test_timeout_raises_gemini_timeout_error(self):
        """T220: On timeout from provider, raises GeminiTimeoutError."""
        mock_provider = MagicMock(spec=[])
        mock_provider.side_effect = TimeoutError("timeout")

        client = AdversarialGeminiClient(provider=mock_provider)

        with pytest.raises(GeminiTimeoutError, match="timeout"):
            client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
                timeout=120,
            )

    def test_quota_error_from_response_content(self):
        """Detects quota exhaustion from response content."""
        mock_provider = MagicMock(spec=[])
        mock_provider.return_value = (
            "RESOURCE_EXHAUSTED: quota exceeded",
            {"model": "gemini-2.5-pro-preview-05-06"},
        )

        client = AdversarialGeminiClient(provider=mock_provider)

        with pytest.raises(GeminiQuotaExhaustedError, match="429"):
            client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
            )

    def test_quota_error_from_status_code(self):
        """Detects quota exhaustion from HTTP 429 status code."""
        mock_provider = MagicMock(spec=[])
        mock_provider.return_value = (
            "some response",
            {"model": "gemini-2.5-pro-preview-05-06", "status_code": 429},
        )

        client = AdversarialGeminiClient(provider=mock_provider)

        with pytest.raises(GeminiQuotaExhaustedError):
            client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
            )

    def test_flash_model_in_response_raises(self):
        """Detects Flash model downgrade from response metadata."""
        mock_provider = MagicMock(spec=[])
        mock_provider.return_value = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}',
            {"model": "gemini-2.0-flash-001"},
        )

        client = AdversarialGeminiClient(provider=mock_provider)

        with pytest.raises(GeminiModelDowngradeError, match="flash"):
            client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
            )

    def test_uses_default_patterns_when_none(self):
        """When adversarial_patterns is None, uses defaults from knowledge base."""
        mock_provider = MagicMock(spec=[])
        mock_provider.return_value = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}',
            {"model": "gemini-2.5-pro-preview-05-06"},
        )

        client = AdversarialGeminiClient(provider=mock_provider)
        client.generate_adversarial_tests(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=None,
        )

        # Should have called provider (meaning prompts were built with default patterns)
        mock_provider.assert_called_once()

    def test_custom_patterns_used(self):
        """Custom adversarial patterns are passed through to prompt builder."""
        mock_provider = MagicMock(spec=[])
        mock_provider.return_value = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}',
            {"model": "gemini-2.5-pro-preview-05-06"},
        )

        client = AdversarialGeminiClient(provider=mock_provider)
        custom_patterns = ["Custom: test with custom pattern"]
        client.generate_adversarial_tests(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=custom_patterns,
        )

        # Verify provider was called (patterns were used in prompt construction)
        mock_provider.assert_called_once()
        call_kwargs = mock_provider.call_args
        # The user_prompt arg should contain the custom pattern
        assert "Custom: test with custom pattern" in str(call_kwargs)

    def test_provider_injected(self):
        """Injected provider is used directly without auto-discovery."""
        mock_provider = MagicMock(spec=[])
        client = AdversarialGeminiClient(provider=mock_provider)
        assert client._provider is mock_provider

    def test_auto_discovery_import_error(self):
        """When no provider can be discovered, raises ImportError."""
        with patch(
            "assemblyzero.workflows.testing.adversarial_gemini.AdversarialGeminiClient._discover_provider",
            side_effect=ImportError("No Gemini provider found"),
        ):
            with pytest.raises(ImportError, match="No Gemini provider found"):
                AdversarialGeminiClient(provider=None)

    def test_langchain_provider_strategy(self):
        """Client can use LangChain-style provider with invoke() method."""
        mock_response = MagicMock()
        mock_response.content = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}'
        )
        mock_response.response_metadata = {"model": "gemini-2.5-pro-preview-05-06"}

        mock_provider = MagicMock()
        # Remove callable behavior so it falls to invoke() strategy
        mock_provider.models = MagicMock(spec=[])  # no generate_content
        del mock_provider.models.generate_content
        mock_provider.invoke.return_value = mock_response

        client = AdversarialGeminiClient(provider=mock_provider)

        with patch(
            "assemblyzero.workflows.testing.adversarial_gemini.AdversarialGeminiClient._invoke_provider",
            return_value=(mock_response.content, mock_response.response_metadata),
        ):
            result = client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
            )

        assert "test_cases" in result


class TestVerifyModelIsPro:
    """Tests for verify_model_is_pro (T230, T240)."""

    def test_pro_model_passes(self):
        """T230: verify_model_is_pro returns True for Pro metadata."""
        client = AdversarialGeminiClient(provider=MagicMock())
        result = client.verify_model_is_pro(
            {"model": "gemini-2.5-pro-preview-05-06"}
        )
        assert result is True

    def test_flash_detected_raises(self):
        """T240: verify_model_is_pro raises for Flash metadata."""
        client = AdversarialGeminiClient(provider=MagicMock())
        with pytest.raises(GeminiModelDowngradeError, match="flash"):
            client.verify_model_is_pro({"model": "gemini-2.0-flash-001"})

    def test_empty_metadata_raises(self):
        """Empty metadata raises GeminiModelDowngradeError."""
        client = AdversarialGeminiClient(provider=MagicMock())
        with pytest.raises(GeminiModelDowngradeError, match="No model information"):
            client.verify_model_is_pro({})

    def test_unknown_model_passes_with_warning(self):
        """Unknown model name passes but with warning."""
        client = AdversarialGeminiClient(provider=MagicMock())
        result = client.verify_model_is_pro({"model": "gemini-ultra-2026"})
        assert result is True

    def test_pro_case_insensitive(self):
        """Model name check is case-insensitive."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client.verify_model_is_pro({"model": "Gemini-PRO-latest"}) is True

    def test_empty_model_string_raises(self):
        """Empty model string raises GeminiModelDowngradeError."""
        client = AdversarialGeminiClient(provider=MagicMock())
        with pytest.raises(GeminiModelDowngradeError, match="No model information"):
            client.verify_model_is_pro({"model": ""})

    def test_flash_exp_detected(self):
        """Flash experimental model is also detected."""
        client = AdversarialGeminiClient(provider=MagicMock())
        with pytest.raises(GeminiModelDowngradeError):
            client.verify_model_is_pro({"model": "gemini-2.0-flash-exp"})

    def test_pro_preview_variant(self):
        """Pro preview variant passes."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client.verify_model_is_pro({"model": "gemini-3-pro-preview-0514"}) is True


class TestIsQuotaError:
    """Tests for _is_quota_error."""

    def test_status_code_429(self):
        """HTTP 429 status code is detected as quota error."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error("", {"status_code": 429}) is True

    def test_resource_exhausted_in_response(self):
        """RESOURCE_EXHAUSTED in response text is detected."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error("RESOURCE_EXHAUSTED: quota limit", {}) is True

    def test_rate_limit_in_response(self):
        """'rate limit' in response text is detected."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error("rate limit exceeded", {}) is True

    def test_normal_response_not_quota_error(self):
        """Normal JSON response is not a quota error."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error('{"test_cases": []}', {"status_code": 200}) is False

    def test_empty_response_not_quota_error(self):
        """Empty response is not a quota error."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error("", {}) is False

    def test_none_response_not_quota_error(self):
        """None response is not a quota error."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error(None, {}) is False

    def test_quota_word_in_response(self):
        """'quota' in response text is detected."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error("quota exceeded for project", {}) is True

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\integration\test_adversarial_integration.py
"""Integration test: full adversarial node execution with real Gemini call.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

Requires:
- GOOGLE_API_KEY environment variable
- Network access to Gemini API
"""

import json
import os

import pytest

from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)
from assemblyzero.workflows.testing.nodes.adversarial_node import (
    _parse_gemini_response,
)


@pytest.mark.integration
@pytest.mark.adversarial
@pytest.mark.expensive
class TestAdversarialIntegration:
    """Integration tests requiring real Gemini API access (T200)."""

    @pytest.fixture(autouse=True)
    def skip_without_api_key(self):
        """Skip if no API key available."""
        if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get(
            "GEMINI_API_KEY"
        ):
            pytest.skip("No Gemini API key available (set GOOGLE_API_KEY)")

    def test_full_gemini_invocation(self):
        """T200: Real Gemini call returns parseable adversarial analysis."""
        client = AdversarialGeminiClient()

        implementation = (
            "def add(a: int, b: int) -> int:\n"
            "    '''Add two numbers.'''\n"
            "    return a + b\n"
        )
        lld = (
            "# Add Function\n"
            "## Requirements\n"
            "1. Adds two integers\n"
            "2. Returns integer result\n"
            "3. Handles overflow gracefully\n"
        )
        existing_tests = (
            "def test_add_basic():\n"
            "    assert add(1, 2) == 3\n"
        )

        try:
            raw_response = client.generate_adversarial_tests(
                implementation_code=implementation,
                lld_content=lld,
                existing_tests=existing_tests,
                timeout=120,
            )
        except (GeminiQuotaExhaustedError, GeminiTimeoutError) as e:
            pytest.skip(f"Gemini unavailable: {e}")
        except GeminiModelDowngradeError as e:
            pytest.skip(f"Gemini model downgraded: {e}")

        # Should be parseable JSON
        analysis = _parse_gemini_response(raw_response)

        # Validate structure
        assert "uncovered_edge_cases" in analysis
        assert "false_claims" in analysis
        assert "missing_error_handling" in analysis
        assert "implicit_assumptions" in analysis
        assert "test_cases" in analysis
        assert isinstance(analysis["test_cases"], list)

        # Should generate at least one test
        assert len(analysis["test_cases"]) >= 1

        # Each test case should have required fields
        for tc in analysis["test_cases"]:
            assert "test_id" in tc
            assert "test_code" in tc
            assert "category" in tc


```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/workflows/testing/adversarial_state.py (signatures)

```python
"""State extensions for adversarial testing node.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

from typing import Literal, TypedDict

class AdversarialTestCase(TypedDict):

    """A single adversarial test case generated by Gemini."""

class AdversarialAnalysis(TypedDict):

    """Gemini's analysis of implementation vs. LLD claims."""

class AdversarialNodeState(TypedDict, total=False):

    """State extension for the adversarial testing node."""

class ValidationResult(TypedDict):

    """Result of adversarial test validation."""
```

### assemblyzero/workflows/testing/knowledge/adversarial_patterns.py (signatures)

```python
"""Knowledge base of adversarial testing patterns.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

def get_adversarial_patterns() -> list[str]:
    """Return curated list of adversarial testing pattern descriptions.

Categories:"""
    ...
```

### assemblyzero/workflows/testing/adversarial_prompts.py (signatures)

```python
"""Prompt templates for Gemini adversarial analysis.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import json

def build_adversarial_system_prompt() -> str:
    """System prompt establishing Gemini's adversarial tester persona.

Key constraints:"""
    ...

def build_adversarial_analysis_prompt(
    implementation_code: str,
    lld_content: str,
    existing_tests: str,
    adversarial_patterns: list[str],
) -> str:
    """Build the user prompt for Gemini adversarial analysis.

The prompt instructs Gemini to:"""
    ...
```

### assemblyzero/workflows/testing/adversarial_gemini.py (full)

```python
"""Wrapper module for Gemini adversarial invocation logic.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

Encapsulates adversarial-specific invocation (system prompt, no-mock constraint,
timeout handling) while delegating actual API communication to the existing
provider infrastructure.
"""

import logging
from typing import Any

from assemblyzero.workflows.testing.adversarial_prompts import (
    build_adversarial_analysis_prompt,
    build_adversarial_system_prompt,
)
from assemblyzero.workflows.testing.knowledge.adversarial_patterns import (
    get_adversarial_patterns,
)

logger = logging.getLogger(__name__)


class GeminiQuotaExhaustedError(Exception):
    """Raised when Gemini API quota is exhausted (HTTP 429)."""

    pass


class GeminiModelDowngradeError(Exception):
    """Raised when Gemini silently downgrades from Pro to Flash."""

    pass


class GeminiTimeoutError(Exception):
    """Raised when Gemini API response exceeds timeout."""

    pass


class AdversarialGeminiClient:
    """Wrapper around the project's existing GeminiProvider for adversarial test generation.

    This module encapsulates the adversarial-specific invocation logic
    (system prompt, no-mock constraint, timeout handling) while delegating
    actual Gemini API communication to the existing provider infrastructure.
    """

    def __init__(self, provider: Any | None = None) -> None:
        """Initialize with an optional GeminiProvider instance.

        If provider is None, attempts to instantiate the default provider
        from assemblyzero.utils (auto-discovered at runtime).

        Args:
            provider: An object with a method to invoke Gemini. If None,
                      auto-discovers from assemblyzero.utils.
        """
        if provider is not None:
            self._provider = provider
        else:
            self._provider = self._discover_provider()

    def _discover_provider(self) -> Any:
        """Auto-discover and instantiate the Gemini provider from assemblyzero.utils.

        Searches for common provider class names in the utils package.

        Returns:
            An instantiated Gemini provider.

        Raises:
            ImportError: If no suitable Gemini provider found.
        """
        # Try known provider locations in order of likelihood
        provider_attempts = [
            ("assemblyzero.utils.gemini_provider", "GeminiProvider"),
            ("assemblyzero.utils.gemini", "GeminiProvider"),
            ("assemblyzero.utils.gemini_client", "GeminiClient"),
            ("assemblyzero.utils.providers", "GeminiProvider"),
        ]

        for module_path, class_name in provider_attempts:
            try:
                import importlib

                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                logger.info(
                    "Discovered Gemini provider: %s.%s", module_path, class_name
                )
                return cls()
            except (ImportError, AttributeError):
                continue

        # Fallback: try google.genai directly
        try:
            from google import genai

            logger.info("Using google.genai directly as Gemini provider")
            return genai.Client()
        except ImportError:
            pass

        raise ImportError(
            "No Gemini provider found. Ensure google-genai or "
            "langchain-google-genai is installed and a provider class "
            "exists in assemblyzero.utils."
        )

    def verify_model_is_pro(self, response_metadata: dict) -> bool:
        """Check response metadata to confirm Gemini Pro was used.

        Args:
            response_metadata: Dictionary containing model info from the API response.

        Returns:
            True if Pro model confirmed.

        Raises:
            GeminiModelDowngradeError: If Flash model detected or no model info present.
        """
        model_name = response_metadata.get("model", "")

        if not model_name:
            raise GeminiModelDowngradeError(
                "No model information in response metadata"
            )

        model_lower = model_name.lower()

        if "flash" in model_lower:
            raise GeminiModelDowngradeError(
                f"Expected Gemini Pro but received {model_name}"
            )

        if "pro" in model_lower:
            logger.info("Gemini Pro model confirmed: %s", model_name)
            return True

        # Unknown model — warn but don't block
        logger.warning(
            "Unknown Gemini model variant: %s. Proceeding cautiously.", model_name
        )
        return True

    def generate_adversarial_tests(
        self,
        implementation_code: str,
        lld_content: str,
        existing_tests: str,
        adversarial_patterns: list[str] | None = None,
        timeout: int = 120,
    ) -> str:
        """Invoke Gemini Pro for adversarial test generation.

        Builds the adversarial prompt, delegates to the underlying provider,
        and applies model-downgrade detection.

        Args:
            implementation_code: Source code of the implementation under test.
            lld_content: LLD markdown content.
            existing_tests: Existing test code for deduplication.
            adversarial_patterns: Optional list of patterns. Uses defaults if None.
            timeout: Maximum seconds to wait for response.

        Returns:
            Raw JSON string response from Gemini.

        Raises:
            GeminiQuotaExhaustedError: If 429 or quota message detected.
            GeminiModelDowngradeError: If Flash detected instead of Pro.
            GeminiTimeoutError: If response exceeds timeout.
        """
        if adversarial_patterns is None:
            adversarial_patterns = get_adversarial_patterns()

        system_prompt = build_adversarial_system_prompt()
        user_prompt = build_adversarial_analysis_prompt(
            implementation_code=implementation_code,
            lld_content=lld_content,
            existing_tests=existing_tests,
            adversarial_patterns=adversarial_patterns,
        )

        logger.info(
            "Invoking Gemini Pro for adversarial analysis (timeout=%ds)", timeout
        )

        try:
            raw_response, metadata = self._invoke_provider(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=timeout,
            )
        except TimeoutError as e:
            raise GeminiTimeoutError(
                f"Gemini API response exceeded {timeout}s timeout"
            ) from e

        # Check for quota exhaustion in response or exception
        if self._is_quota_error(raw_response, metadata):
            raise GeminiQuotaExhaustedError(
                "Gemini API quota exhausted (HTTP 429)"
            )

        # Verify model is Pro (not silently downgraded to Flash)
        self.verify_model_is_pro(metadata)

        logger.info(
            "Gemini adversarial analysis received (%d chars)", len(raw_response)
        )
        return raw_response

    def _invoke_provider(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: int,
    ) -> tuple[str, dict]:
        """Invoke the underlying provider and return (response_text, metadata).

        This method abstracts over different provider APIs (google.genai,
        langchain-google-genai, etc.).

        Returns:
            Tuple of (raw_response_text, response_metadata_dict).
        """
        provider = self._provider

        # Strategy 1: google.genai Client
        if hasattr(provider, "models") and hasattr(
            getattr(provider, "models", None), "generate_content"
        ):
            response = provider.models.generate_content(
                model="gemini-2.5-pro-preview-05-06",
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "response_mime_type": "application/json",
                    "timeout": timeout,
                },
            )
            text = response.text if hasattr(response, "text") else str(response)
            metadata: dict[str, Any] = {}
            if hasattr(response, "model"):
                metadata["model"] = response.model
            elif hasattr(response, "candidates") and response.candidates:
                metadata["model"] = getattr(
                    response, "model_version", "gemini-2.5-pro-preview-05-06"
                )
            else:
                metadata["model"] = "gemini-2.5-pro-preview-05-06"
            return text, metadata

        # Strategy 2: LangChain-style provider with invoke()
        if hasattr(provider, "invoke"):
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = provider.invoke(messages)
            text = response.content if hasattr(response, "content") else str(response)
            metadata = getattr(response, "response_metadata", {})
            return text, metadata

        # Strategy 3: Generic callable
        if callable(provider):
            result = provider(system_prompt=system_prompt, user_prompt=user_prompt)
            if isinstance(result, tuple):
                return result[0], result[1]
            return str(result), {"model": "unknown"}

        raise TypeError(
            f"Unsupported Gemini provider type: {type(provider).__name__}. "
            "Provider must have 'models.generate_content', 'invoke', or be callable."
        )

    def _is_quota_error(self, response: str | None, metadata: dict) -> bool:
        """Check if the response indicates quota exhaustion.

        Args:
            response: Raw response text.
            metadata: Response metadata.

        Returns:
            True if quota exhaustion detected.
        """
        status = metadata.get("status_code", 0)
        if status == 429:
            return True

        if not response:
            return False

        quota_indicators = [
            "429",
            "quota",
            "rate limit",
            "resource exhausted",
            "resource_exhausted",
        ]

        response_lower = response.lower()
        for indicator in quota_indicators:
            if indicator.lower() in response_lower:
                return True

        return False
```

## Previous Attempt Failed

The previous implementation had this error:

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Scripts\python.exe
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: C:\Users\mcwiz\Projects\AssemblyZero
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.9, benchmark-5.2.3, cov-7.0.0
collecting ... collected 143 items / 1 deselected / 142 selected

tests/unit/test_adversarial_node.py::TestRunAdversarialNode::test_happy_path_generates_tests PASSED [  0%]
tests/unit/test_adversarial_node.py::TestRunAdversarialNode::test_quota_skip PASSED [  1%]
tests/unit/test_adversarial_node.py::TestRunAdversarialNode::test_downgrade_skip PASSED [  2%]
tests/unit/test_adversarial_node.py::TestRunAdversarialNode::test_empty_implementation_skip PASSED [  2%]
tests/unit/test_adversarial_node.py::TestRunAdversarialNode::test_malformed_response_error PASSED [  3%]
tests/unit/test_adversarial_node.py::TestRunAdversarialNode::test_timeout_triggers_retry PASSED [  4%]
tests/unit/test_adversarial_node.py::TestRunAdversarialNode::test_mock_violations_rejected PASSED [  4%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_valid_json_parsed PASSED [  5%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_malformed_json_raises PASSED [  6%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_all_four_categories_present PASSED [  7%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_missing_category_raises PASSED [  7%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_markdown_code_block_stripped PASSED [  8%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_empty_response_raises PASSED [  9%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_whitespace_only_response_raises PASSED [  9%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_missing_test_cases_raises PASSED [ 10%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_test_cases_not_list_raises PASSED [ 11%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_empty_test_cases_valid PASSED [ 11%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_test_case_missing_field_raises PASSED [ 12%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_non_dict_response_raises PASSED [ 13%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_multiple_test_cases_parsed PASSED [ 14%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_missing_uncovered_edge_cases_raises PASSED [ 14%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_missing_missing_error_handling_raises PASSED [ 15%]
tests/unit/test_adversarial_node.py::TestParseGeminiResponse::test_missing_implicit_assumptions_raises PASSED [ 16%]
tests/unit/test_adversarial_node.py::TestCollectContext::test_token_budget_trimming PASSED [ 16%]
tests/unit/test_adversarial_node.py::TestCollectContext::test_empty_state PASSED [ 17%]
tests/unit/test_adversarial_node.py::TestCollectContext::test_small_input_not_truncated PASSED [ 18%]
tests/unit/test_adversarial_node.py::TestCollectContext::test_multiple_impl_files_concatenated PASSED [ 19%]
tests/unit/test_adversarial_node.py::TestCollectContext::test_oversized_impl_truncated_with_marker PASSED [ 19%]
tests/unit/test_adversarial_node.py::TestCollectContext::test_missing_keys_handled PASSED [ 20%]
tests/unit/test_adversarial_writer.py::TestWriteAdversarialTests::test_groups_by_category PASSED [ 21%]
tests/unit/test_adversarial_writer.py::TestWriteAdversarialTests::test_file_naming_convention PASSED [ 21%]
tests/unit/test_adversarial_writer.py::TestWriteAdversarialTests::test_empty_test_cases_no_files PASSED [ 22%]
tests/unit/test_adversarial_writer.py::TestWriteAdversarialTests::test_creates_output_dir PASSED [ 23%]
tests/unit/test_adversarial_writer.py::TestWriteAdversarialTests::test_files_written_to_disk PASSED [ 23%]
tests/unit/test_adversarial_writer.py::TestWriteAdversarialTests::test_multiple_categories_separate_files PASSED [ 24%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_renders_valid_pytest_syntax PASSED [ 25%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_adversarial_header_present PASSED [ 26%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_header_includes_issue_and_category PASSED [ 26%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_no_mock_docstring PASSED [ 27%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_empty_cases_renders_header_only PASSED [ 28%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_test_code_without_def_wrapped PASSED [ 28%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_severity_comment_present PASSED [ 29%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_claim_challenged_comment PASSED [ 30%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_multiple_cases_all_rendered PASSED [ 30%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_empty_test_code_skipped PASSED [ 31%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_generator_comment_in_header PASSED [ 32%]
tests/unit/test_adversarial_writer.py::TestRenderTestFile::test_warning_comment_in_header PASSED [ 33%]
tests/unit/test_adversarial_writer.py::TestSanitizeCategory::test_normal_category PASSED [ 33%]
tests/unit/test_adversarial_writer.py::TestSanitizeCategory::test_uppercase PASSED [ 34%]
tests/unit/test_adversarial_writer.py::TestSanitizeCategory::test_special_chars PASSED [ 35%]
tests/unit/test_adversarial_writer.py::TestSanitizeCategory::test_empty PASSED [ 35%]
tests/unit/test_adversarial_writer.py::TestSanitizeCategory::test_spaces PASSED [ 36%]
tests/unit/test_adversarial_writer.py::TestSanitizeCategory::test_multiple_special_chars PASSED [ 37%]
tests/unit/test_adversarial_writer.py::TestSanitizeCategory::test_leading_trailing_special_chars PASSED [ 38%]
tests/unit/test_adversarial_writer.py::TestSanitizeCategory::test_numbers_preserved PASSED [ 38%]
tests/unit/test_adversarial_writer.py::TestSanitizeCategory::test_mixed_case_with_special PASSED [ 39%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_detects_unittest_mock_import PASSED [ 40%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_detects_magicmock_instantiation PASSED [ 40%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_detects_patch_decorator PASSED [ 41%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_detects_monkeypatch_fixture PASSED [ 42%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_detects_aliased_import PASSED [ 42%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_detects_import_unittest_mock PASSED [ 43%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_detects_from_unittest_import_mock PASSED [ 44%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_clean_code_no_violations PASSED [ 45%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_mock_in_string_not_flagged PASSED [ 45%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_syntax_error_returns_empty PASSED [ 46%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_detects_async_mock PASSED [ 47%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_detects_mock_patch_attribute PASSED [ 47%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_filepath_in_violation_message PASSED [ 48%]
tests/unit/test_adversarial_validator.py::TestCheckNoMocks::test_line_number_in_violation_message PASSED [ 49%]
tests/unit/test_adversarial_validator.py::TestValidateAdversarialTests::test_clean_file_passes PASSED [ 50%]
tests/unit/test_adversarial_validator.py::TestValidateAdversarialTests::test_mock_test_rejected PASSED [ 50%]
tests/unit/test_adversarial_validator.py::TestValidateAdversarialTests::test_empty_files_valid PASSED [ 51%]
tests/unit/test_adversarial_validator.py::TestValidateAdversarialTests::test_syntax_error_invalid PASSED [ 52%]
tests/unit/test_adversarial_validator.py::TestValidateAdversarialTests::test_multiple_files_mixed_results PASSED [ 52%]
tests/unit/test_adversarial_validator.py::TestValidateAdversarialTests::test_warnings_for_missing_assertions PASSED [ 53%]
tests/unit/test_adversarial_validator.py::TestValidateAdversarialTests::test_duplicate_test_names_warning PASSED [ 54%]
tests/unit/test_adversarial_validator.py::TestValidateAdversarialTests::test_syntax_error_skips_ast_analysis PASSED [ 54%]
tests/unit/test_adversarial_validator.py::TestValidateAdversarialTests::test_only_mock_violations_make_invalid PASSED [ 55%]
tests/unit/test_adversarial_validator.py::TestCheckSyntax::test_syntax_error_detected PASSED [ 56%]
tests/unit/test_adversarial_validator.py::TestCheckSyntax::test_valid_syntax_no_errors PASSED [ 57%]
tests/unit/test_adversarial_validator.py::TestCheckSyntax::test_filepath_in_error_message PASSED [ 57%]
tests/unit/test_adversarial_validator.py::TestCheckSyntax::test_line_number_in_error_message PASSED [ 58%]
tests/unit/test_adversarial_validator.py::TestCheckSyntax::test_empty_code_valid PASSED [ 59%]
tests/unit/test_adversarial_validator.py::TestCheckSyntax::test_complex_valid_code PASSED [ 59%]
tests/unit/test_adversarial_validator.py::TestCheckAssertions::test_missing_assertions_warning PASSED [ 60%]
tests/unit/test_adversarial_validator.py::TestCheckAssertions::test_has_assertion_no_warning PASSED [ 61%]
tests/unit/test_adversarial_validator.py::TestCheckAssertions::test_pytest_raises_counts_as_assertion PASSED [ 61%]
tests/unit/test_adversarial_validator.py::TestCheckAssertions::test_non_test_function_ignored PASSED [ 62%]
tests/unit/test_adversarial_validator.py::TestCheckAssertions::test_empty_file_no_warnings PASSED [ 63%]
tests/unit/test_adversarial_validator.py::TestCheckAssertions::test_multiple_test_functions_mixed PASSED [ 64%]
tests/unit/test_adversarial_validator.py::TestCheckAssertions::test_syntax_error_returns_empty PASSED [ 64%]
tests/unit/test_adversarial_validator.py::TestCheckAssertions::test_filepath_in_warning_message PASSED [ 65%]
tests/unit/test_adversarial_validator.py::TestCheckAssertions::test_assert_in_nested_function_not_counted PASSED [ 66%]
tests/unit/test_adversarial_validator.py::TestCheckAssertions::test_class_based_test_methods PASSED [ 66%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialSystemPrompt::test_no_mock_enforcement PASSED [ 67%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialSystemPrompt::test_requires_four_categories PASSED [ 68%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialSystemPrompt::test_json_output_required PASSED [ 69%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialSystemPrompt::test_returns_string PASSED [ 69%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialSystemPrompt::test_severity_levels_documented PASSED [ 70%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialSystemPrompt::test_max_test_cases_mentioned PASSED [ 71%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialSystemPrompt::test_no_markdown_code_blocks_instruction PASSED [ 71%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialSystemPrompt::test_assert_requirement PASSED [ 72%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialSystemPrompt::test_test_prefix_requirement PASSED [ 73%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_prompt_contains_all_sections PASSED [ 73%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_empty_existing_tests PASSED [ 74%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_schema_included PASSED [ 75%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_returns_string PASSED [ 76%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_implementation_code_section PASSED [ 76%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_lld_section PASSED [ 77%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_existing_tests_section_when_provided PASSED [ 78%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_multiple_patterns_listed PASSED [ 78%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_no_mock_reminder PASSED [ 79%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_instructions_section PASSED [ 80%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_json_only_requirement PASSED [ 80%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_schema_has_required_fields PASSED [ 81%]
tests/unit/test_adversarial_prompts.py::TestBuildAdversarialAnalysisPrompt::test_empty_patterns_list PASSED [ 82%]
tests/unit/test_adversarial_gemini.py::TestAdversarialGeminiClient::test_delegates_to_provider PASSED [ 83%]
tests/unit/test_adversarial_gemini.py::TestAdversarialGeminiClient::test_timeout_raises_gemini_timeout_error PASSED [ 83%]
tests/unit/test_adversarial_gemini.py::TestAdversarialGeminiClient::test_quota_error_from_response_content PASSED [ 84%]
tests/unit/test_adversarial_gemini.py::TestAdversarialGeminiClient::test_quota_error_from_status_code PASSED [ 85%]
tests/unit/test_adversarial_gemini.py::TestAdversarialGeminiClient::test_flash_model_in_response_raises PASSED [ 85%]
tests/unit/test_adversarial_gemini.py::TestAdversarialGeminiClient::test_uses_default_patterns_when_none PASSED [ 86%]
tests/unit/test_adversarial_gemini.py::TestAdversarialGeminiClient::test_custom_patterns_used PASSED [ 87%]
tests/unit/test_adversarial_gemini.py::TestAdversarialGeminiClient::test_provider_injected PASSED [ 88%]
tests/unit/test_adversarial_gemini.py::TestAdversarialGeminiClient::test_auto_discovery_import_error PASSED [ 88%]
tests/unit/test_adversarial_gemini.py::TestAdversarialGeminiClient::test_langchain_provider_strategy PASSED [ 89%]
tests/unit/test_adversarial_gemini.py::TestVerifyModelIsPro::test_pro_model_passes PASSED [ 90%]
tests/unit/test_adversarial_gemini.py::TestVerifyModelIsPro::test_flash_detected_raises PASSED [ 90%]
tests/unit/test_adversarial_gemini.py::TestVerifyModelIsPro::test_empty_metadata_raises PASSED [ 91%]
tests/unit/test_adversarial_gemini.py::TestVerifyModelIsPro::test_unknown_model_passes_with_warning PASSED [ 92%]
tests/unit/test_adversarial_gemini.py::TestVerifyModelIsPro::test_pro_case_insensitive PASSED [ 92%]
tests/unit/test_adversarial_gemini.py::TestVerifyModelIsPro::test_empty_model_string_raises PASSED [ 93%]
tests/unit/test_adversarial_gemini.py::TestVerifyModelIsPro::test_flash_exp_detected PASSED [ 94%]
tests/unit/test_adversarial_gemini.py::TestVerifyModelIsPro::test_pro_preview_variant PASSED [ 95%]
tests/unit/test_adversarial_gemini.py::TestIsQuotaError::test_status_code_429 PASSED [ 95%]
tests/unit/test_adversarial_gemini.py::TestIsQuotaError::test_resource_exhausted_in_response PASSED [ 96%]
tests/unit/test_adversarial_gemini.py::TestIsQuotaError::test_rate_limit_in_response PASSED [ 97%]
tests/unit/test_adversarial_gemini.py::TestIsQuotaError::test_normal_response_not_quota_error PASSED [ 97%]
tests/unit/test_adversarial_gemini.py::TestIsQuotaError::test_empty_response_not_quota_error PASSED [ 98%]
tests/unit/test_adversarial_gemini.py::TestIsQuotaError::test_none_response_not_quota_error PASSED [ 99%]
tests/unit/test_adversarial_gemini.py::TestIsQuotaError::test_quota_word_in_response PASSED [100%]

============================== warnings summary ===============================
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25: UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
    from pydantic.v1.fields import FieldInfo as FieldInfoV1

..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43: DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17
    VersionedUnionType = Union[builtin_types.UnionType, _UnionGenericAlias]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.14.0-final-0 _______________

Name                                                  Stmts   Miss  Cover   Missing
-----------------------------------------------------------------------------------
assemblyzero\workflows\testing\adversarial_state.py       5      0   100%
-----------------------------------------------------------------------------------
TOTAL                                                     5      0   100%
Required test coverage of 95% reached. Total coverage: 100.00%
================ 142 passed, 1 deselected, 6 warnings in 1.22s ================


```

Fix the issue in your implementation.

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
