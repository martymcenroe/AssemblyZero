# Implementation Request: tests/fixtures/lld_jest_sample.md

## Task

Write the complete contents of `tests/fixtures/lld_jest_sample.md`.

Change type: Add
Description: Sample Jest LLD fixture

## LLD Specification

# Implementation Spec: Multi-Framework TDD Workflow Support (Playwright/TypeScript, Jest, pytest)

| Field | Value |
|-------|-------|
| Issue | #381 |
| LLD | `docs/lld/active/381-multi-framework-tdd-workflow.md` |
| Generated | 2026-02-25 |
| Status | DRAFT |

## 1. Overview

Extend the TDD implementation workflow to detect and support non-pytest test frameworks (Playwright/TypeScript, Jest/Vitest) by adapting scaffolding, validation, test execution, and coverage measurement per framework using the Strategy Pattern.

**Objective:** Enable the testing workflow to automatically detect the test framework from an LLD and delegate scaffolding, execution, and coverage checking to framework-specific runners.

**Success Criteria:**
- Framework detection correctly identifies Playwright, Jest, Vitest, and pytest from LLD content
- Existing pytest-only workflows produce identical behavior (backward compatibility)
- Playwright and Jest runners scaffold, execute, and parse results via subprocess
- Scenario-based coverage prevents infinite loops for e2e tests

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/workflows/testing/runners/__init__.py` | Add | Package init exporting runner classes |
| 2 | `assemblyzero/workflows/testing/runners/base_runner.py` | Add | Abstract base class for all test runners |
| 3 | `assemblyzero/workflows/testing/framework_detector.py` | Add | Detects test framework from LLD content and project files |
| 4 | `assemblyzero/workflows/testing/runner_registry.py` | Add | Registry mapping framework types to runner configurations |
| 5 | `assemblyzero/workflows/testing/runners/pytest_runner.py` | Add | pytest runner adapter |
| 6 | `assemblyzero/workflows/testing/runners/playwright_runner.py` | Add | Playwright/TypeScript runner adapter |
| 7 | `assemblyzero/workflows/testing/runners/jest_runner.py` | Add | Jest/Vitest runner adapter |
| 8 | `assemblyzero/workflows/testing/nodes/scaffold_tests.py` | Modify | Use framework-aware scaffolding |
| 9 | `assemblyzero/workflows/testing/nodes/run_tests.py` | Add | Framework-aware test execution node |
| 10 | `assemblyzero/workflows/testing/nodes/check_coverage.py` | Add | Framework-aware coverage checking node |
| 11 | `tests/fixtures/lld_playwright_sample.md` | Add | Sample Playwright LLD fixture |
| 12 | `tests/fixtures/lld_jest_sample.md` | Add | Sample Jest LLD fixture |
| 13 | `tests/fixtures/lld_pytest_sample.md` | Add | Sample pytest LLD fixture |
| 14 | `tests/fixtures/playwright_json_report.json` | Add | Sample Playwright JSON reporter output |
| 15 | `tests/fixtures/jest_json_report.json` | Add | Sample Jest JSON reporter output |
| 16 | `tests/unit/test_framework_detector.py` | Add | Unit tests for framework detection |
| 17 | `tests/unit/test_runner_registry.py` | Add | Unit tests for runner registry |
| 18 | `tests/unit/test_pytest_runner.py` | Add | Unit tests for pytest runner |
| 19 | `tests/unit/test_playwright_runner.py` | Add | Unit tests for Playwright runner |
| 20 | `tests/unit/test_jest_runner.py` | Add | Unit tests for Jest runner |
| 21 | `tests/unit/test_scaffold_tests_multifw.py` | Add | Tests for multi-framework scaffolding |
| 22 | `tests/unit/test_run_tests_node.py` | Add | Tests for run_tests node |
| 23 | `tests/unit/test_check_coverage_node.py` | Add | Tests for check_coverage node |

**Implementation Order Rationale:** Base classes and enums first (orders 1-2), then detection/registry (3-4), then concrete runners (5-7), then node modifications (8-10), then fixtures (11-15), then tests (16-23). Each layer depends only on prior layers.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/testing/nodes/scaffold_tests.py`

**Relevant excerpt — imports and module docstring** (lines 1-30):

```python
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
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)

from assemblyzero.workflows.testing.knowledge.patterns import get_test_type_info

from assemblyzero.workflows.testing.state import TestingWorkflowState, TestScenario
```

**Relevant excerpt — `scaffold_tests` function signature** (approximate location, end of file):

```python
def scaffold_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """N2: Generate executable test stubs.

Args:"""
    ...
```

**Relevant excerpt — `determine_test_file_path` function** (generates test file paths):

```python
def determine_test_file_path(
    issue_number: int,
    scenarios: list[TestScenario],
    repo_root: Path,
) -> Path:
    """Determine the appropriate path for the test file.

Args:"""
    ...
```

**Relevant excerpt — `generate_test_file_content` function** (generates Python test content):

```python
def generate_test_file_content(
    scenarios: list[TestScenario],
    module_name: str,
    issue_number: int,
    files_to_modify: list[dict] | None = None,
) -> str:
    """Generate pytest file content from test scenarios.

Args:"""
    ...
```

**What changes:**
1. Add imports for `framework_detector` and `runner_registry`
2. Modify `scaffold_tests()` to read `framework_config` from state, and dispatch to framework-specific scaffolding
3. Modify `determine_test_file_path()` to use `framework_config.test_file_extension` instead of hardcoded `.py`
4. Add a new `generate_ts_test_file_content()` function for TypeScript test scaffolding
5. Existing Python scaffolding remains untouched for backward compatibility

## 4. Data Structures

### 4.1 TestFramework

**Definition:**

```python
from enum import Enum

class TestFramework(Enum):
    """Supported test frameworks."""
    PYTEST = "pytest"
    PLAYWRIGHT = "playwright"
    JEST = "jest"
    VITEST = "vitest"
```

**Concrete Example:**

```json
"playwright"
```

### 4.2 CoverageType

**Definition:**

```python
class CoverageType(Enum):
    """How coverage is measured for this framework."""
    LINE = "line"
    SCENARIO = "scenario"
    NONE = "none"
```

**Concrete Example:**

```json
"scenario"
```

### 4.3 FrameworkConfig

**Definition:**

```python
from typing import TypedDict, Optional

class FrameworkConfig(TypedDict):
    framework: TestFramework
    test_runner_command: str
    test_file_pattern: str
    test_file_extension: str
    import_patterns: list[str]
    result_parser: str
    coverage_type: CoverageType
    coverage_target: float
    scaffold_template: str
    working_directory: Optional[str]
```

**Concrete Example (Playwright):**

```json
{
    "framework": "playwright",
    "test_runner_command": "npx playwright test",
    "test_file_pattern": "*.spec.ts",
    "test_file_extension": ".spec.ts",
    "import_patterns": ["import { test", "from '@playwright/test'"],
    "result_parser": "playwright_json",
    "coverage_type": "scenario",
    "coverage_target": 1.0,
    "scaffold_template": "playwright_spec",
    "working_directory": null
}
```

**Concrete Example (pytest):**

```json
{
    "framework": "pytest",
    "test_runner_command": "pytest",
    "test_file_pattern": "test_*.py",
    "test_file_extension": ".py",
    "import_patterns": ["import pytest", "from pytest"],
    "result_parser": "pytest_json",
    "coverage_type": "line",
    "coverage_target": 0.95,
    "scaffold_template": "pytest_standard",
    "working_directory": null
}
```

**Concrete Example (Jest):**

```json
{
    "framework": "jest",
    "test_runner_command": "npx jest",
    "test_file_pattern": "*.test.ts",
    "test_file_extension": ".test.ts",
    "import_patterns": ["describe(", "it(", "expect("],
    "result_parser": "jest_json",
    "coverage_type": "line",
    "coverage_target": 0.95,
    "scaffold_template": "jest_standard",
    "working_directory": null
}
```

### 4.4 TestRunResult

**Definition:**

```python
class TestRunResult(TypedDict):
    passed: int
    failed: int
    skipped: int
    errors: int
    total: int
    coverage_percent: float
    coverage_type: CoverageType
    raw_output: str
    exit_code: int
    framework: TestFramework
```

**Concrete Example (successful Playwright run):**

```json
{
    "passed": 38,
    "failed": 0,
    "skipped": 2,
    "errors": 0,
    "total": 40,
    "coverage_percent": 0.0,
    "coverage_type": "scenario",
    "raw_output": "{\"suites\":[...]}",
    "exit_code": 0,
    "framework": "playwright"
}
```

**Concrete Example (failed pytest run with coverage):**

```json
{
    "passed": 12,
    "failed": 3,
    "skipped": 0,
    "errors": 1,
    "total": 16,
    "coverage_percent": 87.5,
    "coverage_type": "line",
    "raw_output": "FAILED tests/test_example.py::test_foo...",
    "exit_code": 1,
    "framework": "pytest"
}
```

## 5. Function Specifications

### 5.1 `detect_framework_from_lld()`

**File:** `assemblyzero/workflows/testing/framework_detector.py`

**Signature:**

```python
def detect_framework_from_lld(lld_content: str) -> TestFramework:
    """Parse LLD content for test framework indicators.
    
    Scans for explicit declarations, file patterns, and keywords.
    Returns TestFramework.PYTEST as default if no framework detected.
    """
```

**Input Example:**

```python
lld_content = """# 56 - Feature: Dashboard E2E Tests
## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `tests/dashboard.spec.ts` | Add |

## 10. Verification & Testing
Test Framework: Playwright
"""
```

**Output Example:**

```python
TestFramework.PLAYWRIGHT
```

**Input Example (no indicators):**

```python
lld_content = """# 100 - Feature: Add Utility
## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `src/utils.py` | Add |
"""
```

**Output Example:**

```python
TestFramework.PYTEST
```

**Edge Cases:**
- Empty `lld_content` → returns `TestFramework.PYTEST` (default)
- LLD mentions both Playwright and Jest → first match wins (scanning order: explicit declaration > file patterns > keywords)
- LLD mentions `.spec.ts` without explicit "Playwright" → returns `TestFramework.PLAYWRIGHT` (file pattern detection)

### 5.2 `detect_framework_from_project()`

**File:** `assemblyzero/workflows/testing/framework_detector.py`

**Signature:**

```python
def detect_framework_from_project(project_root: str) -> TestFramework | None:
    """Inspect project files to infer test framework.
    
    Checks: playwright.config.ts, jest.config.ts/js, vitest.config.ts,
    package.json scripts, pyproject.toml.
    Returns None if ambiguous or no indicators found.
    """
```

**Input Example:**

```python
project_root = "/home/user/projects/dashboard"
# Where /home/user/projects/dashboard/playwright.config.ts exists
```

**Output Example:**

```python
TestFramework.PLAYWRIGHT
```

**Input Example (package.json with jest):**

```python
project_root = "/home/user/projects/frontend"
# Where package.json contains: {"scripts": {"test": "jest"}}
```

**Output Example:**

```python
TestFramework.JEST
```

**Edge Cases:**
- `project_root` doesn't exist → returns `None`
- Multiple config files found → returns `None` (ambiguous)
- `package.json` has `"test": "vitest"` → returns `TestFramework.VITEST`

### 5.3 `resolve_framework()`

**File:** `assemblyzero/workflows/testing/framework_detector.py`

**Signature:**

```python
def resolve_framework(lld_content: str, project_root: str) -> TestFramework:
    """Resolve test framework. LLD primary, project files fallback.
    
    Priority:
    1. LLD explicit declaration
    2. LLD file patterns
    3. Project file inspection
    4. Default: PYTEST
    """
```

**Input Example:**

```python
lld_content = "## 10. Testing\nTest Framework: Playwright\n..."
project_root = "/home/user/projects/dashboard"
```

**Output Example:**

```python
TestFramework.PLAYWRIGHT
```

**Input Example (LLD overrides project):**

```python
lld_content = "## 2.1 Files\n| `tests/app.spec.ts` | Add |"
project_root = "/home/user/projects/mixed"  # has jest.config.ts
```

**Output Example:**

```python
TestFramework.PLAYWRIGHT  # LLD wins
```

**Edge Cases:**
- Both LLD and project return `None` → returns `TestFramework.PYTEST`
- `project_root` is empty string → skips project detection, uses LLD only

### 5.4 `get_framework_config()`

**File:** `assemblyzero/workflows/testing/runner_registry.py`

**Signature:**

```python
def get_framework_config(framework: TestFramework) -> FrameworkConfig:
    """Return the full configuration for a given test framework."""
```

**Input Example:**

```python
framework = TestFramework.PLAYWRIGHT
```

**Output Example:**

```python
{
    "framework": TestFramework.PLAYWRIGHT,
    "test_runner_command": "npx playwright test",
    "test_file_pattern": "*.spec.ts",
    "test_file_extension": ".spec.ts",
    "import_patterns": ["import { test", "from '@playwright/test'"],
    "result_parser": "playwright_json",
    "coverage_type": CoverageType.SCENARIO,
    "coverage_target": 1.0,
    "scaffold_template": "playwright_spec",
    "working_directory": None,
}
```

**Edge Cases:**
- Unknown framework enum value → raises `ValueError(f"Unsupported framework: {framework}")`

### 5.5 `get_runner()`

**File:** `assemblyzero/workflows/testing/runner_registry.py`

**Signature:**

```python
def get_runner(framework: TestFramework, project_root: str = ".") -> BaseTestRunner:
    """Factory method returning the appropriate runner instance."""
```

**Input Example:**

```python
framework = TestFramework.PYTEST
project_root = "/home/user/projects/backend"
```

**Output Example:**

```python
<PytestRunner instance with config for pytest>
```

**Edge Cases:**
- `TestFramework.PLAYWRIGHT` with no `npx` on PATH → raises `EnvironmentError`
- Unknown framework → raises `ValueError`

### 5.6 `BaseTestRunner.run_tests()`

**File:** `assemblyzero/workflows/testing/runners/base_runner.py`

**Signature:**

```python
@abstractmethod
def run_tests(
    self,
    test_paths: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> TestRunResult:
    """Execute tests and return unified results."""
```

### 5.7 `BaseTestRunner.parse_results()`

**File:** `assemblyzero/workflows/testing/runners/base_runner.py`

**Signature:**

```python
@abstractmethod
def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
    """Parse runner-specific output into unified TestRunResult."""
```

### 5.8 `BaseTestRunner.validate_test_file()`

**File:** `assemblyzero/workflows/testing/runners/base_runner.py`

**Signature:**

```python
@abstractmethod
def validate_test_file(self, file_path: str, content: str) -> list[str]:
    """Validate a test file for mechanical correctness.
    Returns list of error messages (empty = valid).
    """
```

**Input Example (Playwright — valid):**

```python
file_path = "tests/dashboard.spec.ts"
content = """import { test, expect } from '@playwright/test';

test('loads dashboard', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.locator('h1')).toHaveText('Dashboard');
});
"""
```

**Output Example:**

```python
[]  # No errors
```

**Input Example (Playwright — missing import):**

```python
file_path = "tests/dashboard.spec.ts"
content = """test('loads dashboard', async ({ page }) => {
  await page.goto('/dashboard');
});
"""
```

**Output Example:**

```python
["Missing '@playwright/test' import in tests/dashboard.spec.ts"]
```

### 5.9 `BaseTestRunner.get_scaffold_imports()`

**File:** `assemblyzero/workflows/testing/runners/base_runner.py`

**Signature:**

```python
@abstractmethod
def get_scaffold_imports(self) -> str:
    """Return the import block for scaffolded test files."""
```

### 5.10 `BaseTestRunner.compute_scenario_coverage()`

**File:** `assemblyzero/workflows/testing/runners/base_runner.py`

**Signature:**

```python
def compute_scenario_coverage(self, result: TestRunResult, total_scenarios: int) -> float:
    """Compute scenario-based coverage: passed / total_scenarios.
    Returns 0.0 if total_scenarios is 0.
    """
```

**Input Example:**

```python
result = {"passed": 35, "failed": 3, ...}
total_scenarios = 38
```

**Output Example:**

```python
0.9210526315789473  # 35/38
```

**Input Example (zero division guard):**

```python
result = {"passed": 0, "failed": 0, ...}
total_scenarios = 0
```

**Output Example:**

```python
0.0
```

### 5.11 `PytestRunner.run_tests()`

**File:** `assemblyzero/workflows/testing/runners/pytest_runner.py`

**Input Example:**

```python
test_paths = ["tests/test_issue_381.py"]
extra_args = ["--cov=assemblyzero/workflows/testing"]
```

**Output Example:**

```python
{
    "passed": 15,
    "failed": 0,
    "skipped": 1,
    "errors": 0,
    "total": 16,
    "coverage_percent": 97.3,
    "coverage_type": CoverageType.LINE,
    "raw_output": "tests/test_issue_381.py::test_detect ... PASSED\n...",
    "exit_code": 0,
    "framework": TestFramework.PYTEST,
}
```

### 5.12 `PytestRunner.validate_test_file()`

**Input Example (valid):**

```python
file_path = "tests/test_issue_381.py"
content = """import pytest
from assemblyzero.workflows.testing.framework_detector import detect_framework_from_lld

def test_detect_playwright():
    assert detect_framework_from_lld("*.spec.ts") == TestFramework.PLAYWRIGHT
"""
```

**Output:** `[]`

**Input Example (invalid):**

```python
file_path = "tests/test_bad.py"
content = """print("hello world")
"""
```

**Output:** `["No test functions (test_*) found in tests/test_bad.py"]`

### 5.13 `PytestRunner.get_scaffold_imports()`

**Output:**

```python
"import pytest"
```

### 5.14 `PlaywrightRunner.run_tests()`

**File:** `assemblyzero/workflows/testing/runners/playwright_runner.py`

**Input Example:**

```python
test_paths = ["tests/dashboard.spec.ts"]
extra_args = None
```

**Output Example:**

```python
{
    "passed": 38,
    "failed": 0,
    "skipped": 0,
    "errors": 0,
    "total": 38,
    "coverage_percent": 0.0,
    "coverage_type": CoverageType.SCENARIO,
    "raw_output": "{\"config\":{...},\"suites\":[...]}",
    "exit_code": 0,
    "framework": TestFramework.PLAYWRIGHT,
}
```

### 5.15 `PlaywrightRunner.parse_results()`

**Input Example:**

```python
raw_output = '{"config":{},"suites":[{"title":"Dashboard","specs":[{"title":"loads correctly","tests":[{"results":[{"status":"passed"}]}]},{"title":"shows sidebar","tests":[{"results":[{"status":"failed"}]}]}]}]}'
exit_code = 1
```

**Output Example:**

```python
{
    "passed": 1,
    "failed": 1,
    "skipped": 0,
    "errors": 0,
    "total": 2,
    "coverage_percent": 0.0,
    "coverage_type": CoverageType.SCENARIO,
    "raw_output": "{...}",
    "exit_code": 1,
    "framework": TestFramework.PLAYWRIGHT,
}
```

### 5.16 `PlaywrightRunner.validate_test_file()`

**Input (valid):**

```python
file_path = "tests/app.spec.ts"
content = "import { test, expect } from '@playwright/test';\ntest('works', async ({ page }) => {});"
```

**Output:** `[]`

**Input (missing import):**

```python
file_path = "tests/app.spec.ts"
content = "test('works', async ({ page }) => {});"
```

**Output:** `["Missing '@playwright/test' import in tests/app.spec.ts"]`

### 5.17 `PlaywrightRunner.get_scaffold_imports()`

**Output:**

```python
"import { test, expect } from '@playwright/test';"
```

### 5.18 `JestRunner.run_tests()`

**File:** `assemblyzero/workflows/testing/runners/jest_runner.py`

**Input Example:**

```python
test_paths = ["tests/utils.test.ts"]
extra_args = None
```

**Output Example:**

```python
{
    "passed": 10,
    "failed": 2,
    "skipped": 0,
    "errors": 0,
    "total": 12,
    "coverage_percent": 85.0,
    "coverage_type": CoverageType.LINE,
    "raw_output": "{\"success\":false,\"numPassedTests\":10,...}",
    "exit_code": 1,
    "framework": TestFramework.JEST,
}
```

### 5.19 `JestRunner.parse_results()`

**Input Example:**

```python
raw_output = '{"success":true,"numPassedTests":10,"numFailedTests":0,"numPendingTests":1,"numTotalTests":11,"coverageMap":{}}'
exit_code = 0
```

**Output Example:**

```python
{
    "passed": 10,
    "failed": 0,
    "skipped": 1,
    "errors": 0,
    "total": 11,
    "coverage_percent": 0.0,
    "coverage_type": CoverageType.LINE,
    "raw_output": "{...}",
    "exit_code": 0,
    "framework": TestFramework.JEST,
}
```

### 5.20 `JestRunner.validate_test_file()`

**Input (valid):**

```python
file_path = "tests/utils.test.ts"
content = "describe('utils', () => {\n  it('works', () => {\n    expect(true).toBe(true);\n  });\n});"
```

**Output:** `[]`

**Input (no test structure):**

```python
file_path = "tests/utils.test.ts"
content = "const x = 5;\nconsole.log(x);"
```

**Output:** `["No test structure (describe/it/test) found in tests/utils.test.ts"]`

### 5.21 `JestRunner.get_scaffold_imports()`

**Output (Jest):**

```python
"import { describe, it, expect } from '@jest/globals';"
```

**Output (Vitest):**

```python
"import { describe, it, expect } from 'vitest';"
```

### 5.22 `run_tests()` node

**File:** `assemblyzero/workflows/testing/nodes/run_tests.py`

**Signature:**

```python
def run_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """Execute tests using the framework-appropriate runner.
    
    Reads framework_config from state, validates test files,
    runs tests, and stores unified TestRunResult.
    """
```

**Input Example:**

```python
state = {
    "issue_number": 56,
    "framework_config": {
        "framework": TestFramework.PLAYWRIGHT,
        "test_runner_command": "npx playwright test",
        ...
    },
    "test_files": ["tests/dashboard.spec.ts"],
    "repo_root": "/home/user/projects/dashboard",
    ...
}
```

**Output Example:**

```python
{
    "test_run_result": {
        "passed": 38,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "total": 38,
        "coverage_percent": 0.0,
        "coverage_type": CoverageType.SCENARIO,
        "raw_output": "...",
        "exit_code": 0,
        "framework": TestFramework.PLAYWRIGHT,
    },
    "validation_errors": [],
    "error_message": "",
}
```

**Edge Cases:**
- `framework_config` not in state → falls back to PYTEST config
- `test_files` empty → returns error_message "No test files to run"
- Subprocess timeout → returns error_message with timeout details and exit_code -1

### 5.23 `check_coverage()` node

**File:** `assemblyzero/workflows/testing/nodes/check_coverage.py`

**Signature:**

```python
def check_coverage(state: TestingWorkflowState) -> dict[str, Any]:
    """Evaluate coverage against framework-appropriate target.
    
    Dispatches on coverage_type: LINE, SCENARIO, or NONE.
    Sets 'green' and 'iterate_reason' in state.
    """
```

**Input Example (scenario coverage — passing):**

```python
state = {
    "test_run_result": {
        "passed": 38,
        "failed": 0,
        "total": 38,
        "coverage_type": CoverageType.SCENARIO,
        ...
    },
    "framework_config": {
        "coverage_type": CoverageType.SCENARIO,
        "coverage_target": 1.0,
        ...
    },
    "total_scenarios": 38,
}
```

**Output Example:**

```python
{
    "green": True,
    "iterate_reason": "",
}
```

**Input Example (line coverage — failing):**

```python
state = {
    "test_run_result": {
        "passed": 12,
        "failed": 0,
        "total": 12,
        "coverage_percent": 72.5,
        "coverage_type": CoverageType.LINE,
        ...
    },
    "framework_config": {
        "coverage_type": CoverageType.LINE,
        "coverage_target": 0.95,
        ...
    },
}
```

**Output Example:**

```python
{
    "green": False,
    "iterate_reason": "Line coverage 72.5% < target 95.0%",
}
```

**Input Example (tests failed):**

```python
state = {
    "test_run_result": {
        "passed": 35,
        "failed": 3,
        "total": 38,
        ...
    },
    ...
}
```

**Output Example:**

```python
{
    "green": False,
    "iterate_reason": "3 tests failed",
}
```

**Edge Cases:**
- `test_run_result` missing from state → returns `{"green": False, "iterate_reason": "No test results available"}`
- `coverage_type` is NONE → skips coverage, only checks pass/fail
- `total_scenarios` is 0 for SCENARIO type → `green = False`, iterate_reason explains no scenarios found

## 6. Change Instructions

### 6.1 `assemblyzero/workflows/testing/runners/__init__.py` (Add)

**Complete file contents:**

```python
"""Test runner package for multi-framework support.

Issue #381: Strategy Pattern runners for pytest, Playwright, and Jest.
"""

from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner
from assemblyzero.workflows.testing.runners.playwright_runner import PlaywrightRunner
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner

__all__ = [
    "BaseTestRunner",
    "PytestRunner",
    "PlaywrightRunner",
    "JestRunner",
]
```

### 6.2 `assemblyzero/workflows/testing/runners/base_runner.py` (Add)

**Complete file contents:**

```python
"""Abstract base class for framework-specific test runners.

Issue #381: Defines the interface all test runners must implement.
"""

import json
import logging
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)

logger = logging.getLogger(__name__)

# Default subprocess timeout in seconds
DEFAULT_TIMEOUT = 300


class BaseTestRunner(ABC):
    """Abstract base class for framework-specific test runners."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
        """Initialize with framework config and project root path."""
        self.config = config
        self.project_root = project_root

    @abstractmethod
    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
        """Execute tests and return unified results."""
        ...

    @abstractmethod
    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Parse runner-specific output into unified TestRunResult."""
        ...

    @abstractmethod
    def validate_test_file(self, file_path: str, content: str) -> list[str]:
        """Validate a test file for mechanical correctness.

        Returns list of validation error messages (empty = valid).
        """
        ...

    @abstractmethod
    def get_scaffold_imports(self) -> str:
        """Return the import block for scaffolded test files."""
        ...

    def compute_scenario_coverage(
        self, result: TestRunResult, total_scenarios: int
    ) -> float:
        """Compute scenario-based coverage: passed / total_scenarios.

        Returns 0.0 if total_scenarios is 0 to prevent ZeroDivisionError.
        """
        if total_scenarios == 0:
            logger.warning("total_scenarios is 0; returning 0.0 coverage")
            return 0.0
        return result["passed"] / total_scenarios

    def _run_subprocess(
        self,
        command: list[str],
        timeout: int = DEFAULT_TIMEOUT,
        cwd: str | None = None,
    ) -> tuple[str, int]:
        """Run a subprocess command and return (stdout, exit_code).

        Handles timeout and other subprocess errors gracefully.
        """
        working_dir = cwd or self.project_root
        if self.config.get("working_directory"):
            import os
            working_dir = os.path.join(working_dir, self.config["working_directory"])

        logger.info("Running command: %s in %s", " ".join(command), working_dir)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
            )
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            return output, result.returncode
        except subprocess.TimeoutExpired:
            logger.error("Command timed out after %ds: %s", timeout, " ".join(command))
            return f"Command timed out after {timeout}s", -1
        except FileNotFoundError as e:
            logger.error("Command not found: %s", e)
            return f"Command not found: {e}", -1
        except OSError as e:
            logger.error("OS error running command: %s", e)
            return f"OS error: {e}", -1
```

### 6.3 `assemblyzero/workflows/testing/framework_detector.py` (Add)

**Complete file contents:**

```python
"""Framework detection for multi-framework TDD workflow.

Issue #381: Detects test framework from LLD content and project files.
Supports pytest, Playwright, Jest, and Vitest.
"""

import json
import logging
import os
import re
from enum import Enum
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class TestFramework(Enum):
    """Supported test frameworks."""
    PYTEST = "pytest"
    PLAYWRIGHT = "playwright"
    JEST = "jest"
    VITEST = "vitest"


class CoverageType(Enum):
    """How coverage is measured for this framework."""
    LINE = "line"
    SCENARIO = "scenario"
    NONE = "none"


class FrameworkConfig(TypedDict):
    """Configuration for a detected test framework."""
    framework: TestFramework
    test_runner_command: str
    test_file_pattern: str
    test_file_extension: str
    import_patterns: list[str]
    result_parser: str
    coverage_type: CoverageType
    coverage_target: float
    scaffold_template: str
    working_directory: Optional[str]


class TestRunResult(TypedDict):
    """Unified result from any test runner."""
    passed: int
    failed: int
    skipped: int
    errors: int
    total: int
    coverage_percent: float
    coverage_type: CoverageType
    raw_output: str
    exit_code: int
    framework: TestFramework


# --- Explicit declaration patterns (highest priority) ---
_EXPLICIT_PATTERNS: list[tuple[re.Pattern[str], TestFramework]] = [
    (re.compile(r"test\s*framework\s*:\s*playwright", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"test\s*framework\s*:\s*jest", re.IGNORECASE), TestFramework.JEST),
    (re.compile(r"test\s*framework\s*:\s*vitest", re.IGNORECASE), TestFramework.VITEST),
    (re.compile(r"test\s*framework\s*:\s*pytest", re.IGNORECASE), TestFramework.PYTEST),
]

# --- File pattern indicators (second priority) ---
_FILE_PATTERNS: list[tuple[re.Pattern[str], TestFramework]] = [
    (re.compile(r"\.spec\.ts[`\"'\s|]"), TestFramework.PLAYWRIGHT),
    (re.compile(r"\.spec\.js[`\"'\s|]"), TestFramework.PLAYWRIGHT),
    (re.compile(r"\.test\.ts[`\"'\s|]"), TestFramework.JEST),
    (re.compile(r"\.test\.js[`\"'\s|]"), TestFramework.JEST),
    (re.compile(r"test_.*\.py[`\"'\s|]"), TestFramework.PYTEST),
]

# --- Keyword indicators (third priority) ---
_KEYWORD_PATTERNS: list[tuple[re.Pattern[str], TestFramework]] = [
    (re.compile(r"@playwright/test", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"playwright\.config\.(ts|js)", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"npx\s+playwright\s+test", re.IGNORECASE), TestFramework.PLAYWRIGHT),
    (re.compile(r"\bjest\b", re.IGNORECASE), TestFramework.JEST),
    (re.compile(r"\bvitest\b", re.IGNORECASE), TestFramework.VITEST),
    (re.compile(r"\bpytest\b", re.IGNORECASE), TestFramework.PYTEST),
]


def detect_framework_from_lld(lld_content: str) -> TestFramework:
    """Parse LLD content for test framework indicators.

    Scans for:
    1. Explicit declarations (e.g., "Test Framework: Playwright")
    2. File patterns in Section 2.1 (e.g., .spec.ts, .test.ts, test_*.py)
    3. Keywords anywhere in the LLD

    Returns TestFramework.PYTEST as default if no framework detected.
    """
    if not lld_content:
        return TestFramework.PYTEST

    # Priority 1: Explicit declarations
    for pattern, framework in _EXPLICIT_PATTERNS:
        if pattern.search(lld_content):
            logger.info("Detected framework from explicit declaration: %s", framework.value)
            return framework

    # Priority 2: File patterns
    for pattern, framework in _FILE_PATTERNS:
        if pattern.search(lld_content):
            logger.info("Detected framework from file pattern: %s", framework.value)
            return framework

    # Priority 3: Keywords (skip pytest keyword — it's the default fallback
    # and would match almost any Python project LLD)
    for pattern, framework in _KEYWORD_PATTERNS:
        if framework != TestFramework.PYTEST and pattern.search(lld_content):
            logger.info("Detected framework from keyword: %s", framework.value)
            return framework

    logger.info("No framework detected from LLD; defaulting to pytest")
    return TestFramework.PYTEST


def detect_framework_from_project(project_root: str) -> TestFramework | None:
    """Inspect project files to infer the test framework.

    Checks for:
    - playwright.config.ts / playwright.config.js
    - jest.config.ts / jest.config.js
    - vitest.config.ts / vitest.config.js
    - package.json "scripts.test" field
    - pyproject.toml with pytest configuration

    Returns None if ambiguous or not found.
    """
    if not project_root or not os.path.isdir(project_root):
        return None

    detected: list[TestFramework] = []

    # Check for config files
    config_map = {
        "playwright.config.ts": TestFramework.PLAYWRIGHT,
        "playwright.config.js": TestFramework.PLAYWRIGHT,
        "jest.config.ts": TestFramework.JEST,
        "jest.config.js": TestFramework.JEST,
        "jest.config.json": TestFramework.JEST,
        "vitest.config.ts": TestFramework.VITEST,
        "vitest.config.js": TestFramework.VITEST,
    }

    for filename, framework in config_map.items():
        if os.path.isfile(os.path.join(project_root, filename)):
            if framework not in detected:
                detected.append(framework)
                logger.info("Found config file %s → %s", filename, framework.value)

    # Check package.json scripts
    package_json_path = os.path.join(project_root, "package.json")
    if os.path.isfile(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
            test_script = pkg.get("scripts", {}).get("test", "")
            if "playwright" in test_script:
                if TestFramework.PLAYWRIGHT not in detected:
                    detected.append(TestFramework.PLAYWRIGHT)
            elif "vitest" in test_script:
                if TestFramework.VITEST not in detected:
                    detected.append(TestFramework.VITEST)
            elif "jest" in test_script:
                if TestFramework.JEST not in detected:
                    detected.append(TestFramework.JEST)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read package.json: %s", e)

    # Check pyproject.toml for pytest
    pyproject_path = os.path.join(project_root, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path, "r") as f:
                content = f.read()
            if "[tool.pytest" in content or "pytest" in content:
                if TestFramework.PYTEST not in detected:
                    detected.append(TestFramework.PYTEST)
        except OSError as e:
            logger.warning("Failed to read pyproject.toml: %s", e)

    if len(detected) == 1:
        return detected[0]
    elif len(detected) > 1:
        logger.warning("Ambiguous framework detection: %s", [d.value for d in detected])
        return None
    return None


def resolve_framework(lld_content: str, project_root: str) -> TestFramework:
    """Resolve test framework using LLD as primary signal, project files as fallback.

    Priority:
    1. LLD explicit declaration (e.g., "Test Framework: Playwright")
    2. LLD file patterns (e.g., .spec.ts files in Section 2.1)
    3. Project file inspection (package.json scripts, config files)
    4. Default: PYTEST
    """
    # Try LLD detection first
    lld_result = detect_framework_from_lld(lld_content)
    if lld_result != TestFramework.PYTEST:
        # LLD found a non-default framework → high confidence
        logger.info("Framework resolved from LLD: %s", lld_result.value)
        return lld_result

    # LLD returned default pytest — check if project files disagree
    project_result = detect_framework_from_project(project_root)
    if project_result is not None:
        logger.info("Framework resolved from project files: %s", project_result.value)
        return project_result

    # Both returned default or None → use pytest
    logger.info("Framework resolved to default: pytest")
    return TestFramework.PYTEST
```

### 6.4 `assemblyzero/workflows/testing/runner_registry.py` (Add)

**Complete file contents:**

```python
"""Runner registry mapping framework types to configurations and runner instances.

Issue #381: Factory pattern for obtaining framework-specific test runners.
"""

import logging

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

logger = logging.getLogger(__name__)


# --- Framework configuration registry ---
_FRAMEWORK_CONFIGS: dict[TestFramework, FrameworkConfig] = {
    TestFramework.PYTEST: {
        "framework": TestFramework.PYTEST,
        "test_runner_command": "pytest",
        "test_file_pattern": "test_*.py",
        "test_file_extension": ".py",
        "import_patterns": ["import pytest", "from pytest"],
        "result_parser": "pytest_json",
        "coverage_type": CoverageType.LINE,
        "coverage_target": 0.95,
        "scaffold_template": "pytest_standard",
        "working_directory": None,
    },
    TestFramework.PLAYWRIGHT: {
        "framework": TestFramework.PLAYWRIGHT,
        "test_runner_command": "npx playwright test",
        "test_file_pattern": "*.spec.ts",
        "test_file_extension": ".spec.ts",
        "import_patterns": ["import { test", "from '@playwright/test'"],
        "result_parser": "playwright_json",
        "coverage_type": CoverageType.SCENARIO,
        "coverage_target": 1.0,
        "scaffold_template": "playwright_spec",
        "working_directory": None,
    },
    TestFramework.JEST: {
        "framework": TestFramework.JEST,
        "test_runner_command": "npx jest",
        "test_file_pattern": "*.test.ts",
        "test_file_extension": ".test.ts",
        "import_patterns": ["describe(", "it(", "expect("],
        "result_parser": "jest_json",
        "coverage_type": CoverageType.LINE,
        "coverage_target": 0.95,
        "scaffold_template": "jest_standard",
        "working_directory": None,
    },
    TestFramework.VITEST: {
        "framework": TestFramework.VITEST,
        "test_runner_command": "npx vitest run",
        "test_file_pattern": "*.test.ts",
        "test_file_extension": ".test.ts",
        "import_patterns": ["import { describe", "from 'vitest'"],
        "result_parser": "jest_json",  # Vitest JSON output is jest-compatible
        "coverage_type": CoverageType.LINE,
        "coverage_target": 0.95,
        "scaffold_template": "vitest_standard",
        "working_directory": None,
    },
}


def get_framework_config(framework: TestFramework) -> FrameworkConfig:
    """Return the full configuration for a given test framework.

    Raises ValueError if the framework is not registered.
    """
    if framework not in _FRAMEWORK_CONFIGS:
        raise ValueError(f"Unsupported framework: {framework}")
    # Return a copy to prevent mutation
    return dict(_FRAMEWORK_CONFIGS[framework])  # type: ignore[return-value]


def get_runner(framework: TestFramework, project_root: str = ".") -> BaseTestRunner:
    """Factory method returning the appropriate runner instance.

    Raises ValueError for unsupported frameworks.
    Raises EnvironmentError if required external tools are missing
    (propagated from runner __init__).
    """
    config = get_framework_config(framework)

    if framework == TestFramework.PYTEST:
        from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner
        return PytestRunner(config, project_root)
    elif framework == TestFramework.PLAYWRIGHT:
        from assemblyzero.workflows.testing.runners.playwright_runner import PlaywrightRunner
        return PlaywrightRunner(config, project_root)
    elif framework in (TestFramework.JEST, TestFramework.VITEST):
        from assemblyzero.workflows.testing.runners.jest_runner import JestRunner
        return JestRunner(config, project_root)
    else:
        raise ValueError(f"No runner registered for framework: {framework}")
```

### 6.5 `assemblyzero/workflows/testing/runners/pytest_runner.py` (Add)

**Complete file contents:**

```python
"""Pytest test runner adapter.

Issue #381: Encapsulates pytest execution logic, extracting it from
previously hardcoded workflow nodes.
"""

import json
import logging
import re
from typing import Any

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

logger = logging.getLogger(__name__)


class PytestRunner(BaseTestRunner):
    """Test runner adapter for pytest + pytest-cov."""

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
        """Run pytest with --tb=short -q and parse output.

        Uses --json-report if available, falls back to stdout parsing.
        """
        command = ["pytest", "--tb=short", "-q"]

        if extra_args:
            command.extend(extra_args)

        if test_paths:
            command.extend(test_paths)

        raw_output, exit_code = self._run_subprocess(command)
        return self.parse_results(raw_output, exit_code)

    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Parse pytest output into unified TestRunResult.

        Attempts JSON report parsing first, falls back to regex on stdout.
        """
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        coverage_percent = 0.0

        # Try to parse the summary line: "X passed, Y failed, Z skipped"
        summary_match = re.search(
            r"(\d+)\s+passed", raw_output
        )
        if summary_match:
            passed = int(summary_match.group(1))

        failed_match = re.search(r"(\d+)\s+failed", raw_output)
        if failed_match:
            failed = int(failed_match.group(1))

        skipped_match = re.search(r"(\d+)\s+skipped", raw_output)
        if skipped_match:
            skipped = int(skipped_match.group(1))

        error_match = re.search(r"(\d+)\s+error", raw_output)
        if error_match:
            errors = int(error_match.group(1))

        # Try to extract coverage percentage
        cov_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", raw_output)
        if cov_match:
            coverage_percent = float(cov_match.group(1))

        total = passed + failed + skipped + errors

        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total": total,
            "coverage_percent": coverage_percent,
            "coverage_type": CoverageType.LINE,
            "raw_output": raw_output,
            "exit_code": exit_code,
            "framework": TestFramework.PYTEST,
        }

    def validate_test_file(self, file_path: str, content: str) -> list[str]:
        """Validate Python test file for mechanical correctness.

        Checks:
        - Has import statements
        - Has test_ prefixed functions or classes
        """
        errors: list[str] = []

        if not content.strip():
            errors.append(f"Empty test file: {file_path}")
            return errors

        # Check for any import statement
        if not re.search(r"^(import |from )", content, re.MULTILINE):
            errors.append(f"No import statements found in {file_path}")

        # Check for test functions
        if not re.search(r"^def test_", content, re.MULTILINE):
            if not re.search(r"^class Test", content, re.MULTILINE):
                errors.append(f"No test functions (test_*) found in {file_path}")

        return errors

    def get_scaffold_imports(self) -> str:
        """Return pytest import block."""
        return "import pytest"
```

### 6.6 `assemblyzero/workflows/testing/runners/playwright_runner.py` (Add)

**Complete file contents:**

```python
"""Playwright test runner adapter.

Issue #381: Handles Playwright (@playwright/test) execution via npx,
JSON report parsing, and TypeScript test file validation.
"""

import json
import logging
import re
import shutil

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

logger = logging.getLogger(__name__)


class PlaywrightRunner(BaseTestRunner):
    """Test runner adapter for Playwright (@playwright/test)."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
        """Initialize and verify node/npx availability.

        Raises EnvironmentError if 'npx' is not found on PATH.
        """
        super().__init__(config, project_root)
        if not shutil.which("npx"):
            raise EnvironmentError(
                "npx not found on PATH. Playwright tests require Node.js >= 18. "
                "Install Node.js from https://nodejs.org/ and ensure npx is available."
            )

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
        """Run 'npx playwright test' with --reporter=json."""
        command = ["npx", "playwright", "test", "--reporter=json"]

        if extra_args:
            command.extend(extra_args)

        if test_paths:
            command.extend(test_paths)

        raw_output, exit_code = self._run_subprocess(command)
        return self.parse_results(raw_output, exit_code)

    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Parse Playwright JSON reporter output into TestRunResult.

        Playwright JSON format has:
        {
            "config": {...},
            "suites": [
                {
                    "title": "Suite Name",
                    "specs": [
                        {
                            "title": "test title",
                            "tests": [
                                {
                                    "results": [
                                        {"status": "passed"|"failed"|"skipped"|"timedOut"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        """
        passed = 0
        failed = 0
        skipped = 0
        errors = 0

        try:
            # Playwright may emit non-JSON output before the JSON blob.
            # Find the first '{' to locate the JSON.
            json_start = raw_output.find("{")
            if json_start == -1:
                logger.warning("No JSON found in Playwright output; using exit code only")
                return self._fallback_result(raw_output, exit_code)

            json_str = raw_output[json_start:]
            report = json.loads(json_str)

            for suite in report.get("suites", []):
                passed_s, failed_s, skipped_s, errors_s = self._count_suite(suite)
                passed += passed_s
                failed += failed_s
                skipped += skipped_s
                errors += errors_s

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse Playwright JSON report: %s", e)
            return self._fallback_result(raw_output, exit_code)

        total = passed + failed + skipped + errors

        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total": total,
            "coverage_percent": 0.0,  # Playwright doesn't provide line coverage
            "coverage_type": CoverageType.SCENARIO,
            "raw_output": raw_output,
            "exit_code": exit_code,
            "framework": TestFramework.PLAYWRIGHT,
        }

    def _count_suite(self, suite: dict) -> tuple[int, int, int, int]:
        """Recursively count test results in a Playwright suite."""
        passed = 0
        failed = 0
        skipped = 0
        errors = 0

        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                for result in test.get("results", []):
                    status = result.get("status", "")
                    if status == "passed" or status == "expected":
                        passed += 1
                    elif status == "failed" or status == "unexpected":
                        failed += 1
                    elif status == "skipped":
                        skipped += 1
                    elif status == "timedOut":
                        errors += 1
                    else:
                        # Unknown status
                        errors += 1

        # Recurse into nested suites
        for child_suite in suite.get("suites", []):
            p, f, s, e = self._count_suite(child_suite)
            passed += p
            failed += f
            skipped += s
            errors += e

        return passed, failed, skipped, errors

    def _fallback_result(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Create a fallback result when JSON parsing fails."""
        return {
            "passed": 0,
            "failed": 1 if exit_code != 0 else 0,
            "skipped": 0,
            "errors": 1 if exit_code != 0 else 0,
            "total": 1,
            "coverage_percent": 0.0,
            "coverage_type": CoverageType.SCENARIO,
            "raw_output": raw_output,
            "exit_code": exit_code,
            "framework": TestFramework.PLAYWRIGHT,
        }

    def validate_test_file(self, file_path: str, content: str) -> list[str]:
        """Validate .spec.ts file for Playwright-specific correctness.

        Checks:
        - Has @playwright/test import
        - Has test() calls
        """
        errors: list[str] = []

        if not content.strip():
            errors.append(f"Empty test file: {file_path}")
            return errors

        if "@playwright/test" not in content:
            errors.append(f"Missing '@playwright/test' import in {file_path}")

        if not re.search(r"\btest\s*\(", content):
            errors.append(f"No test() calls found in {file_path}")

        return errors

    def get_scaffold_imports(self) -> str:
        """Return Playwright import block."""
        return "import { test, expect } from '@playwright/test';"
```

### 6.7 `assemblyzero/workflows/testing/runners/jest_runner.py` (Add)

**Complete file contents:**

```python
"""Jest/Vitest test runner adapter.

Issue #381: Handles Jest and Vitest execution via npx,
JSON report parsing, and TypeScript test file validation.
"""

import json
import logging
import re
import shutil

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

logger = logging.getLogger(__name__)


class JestRunner(BaseTestRunner):
    """Test runner adapter for Jest / Vitest."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
        """Initialize and verify node/npx availability.

        Raises EnvironmentError if 'npx' is not found on PATH.
        """
        super().__init__(config, project_root)
        if not shutil.which("npx"):
            raise EnvironmentError(
                "npx not found on PATH. Jest/Vitest tests require Node.js >= 18. "
                "Install Node.js from https://nodejs.org/ and ensure npx is available."
            )
        self._is_vitest = config["framework"] == TestFramework.VITEST

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
        """Run 'npx jest --json' or 'npx vitest run --reporter=json'."""
        if self._is_vitest:
            command = ["npx", "vitest", "run", "--reporter=json"]
        else:
            command = ["npx", "jest", "--json"]

        if extra_args:
            command.extend(extra_args)

        if test_paths:
            command.extend(test_paths)

        raw_output, exit_code = self._run_subprocess(command)
        return self.parse_results(raw_output, exit_code)

    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Parse Jest/Vitest JSON output into unified TestRunResult.

        Jest JSON format:
        {
            "success": bool,
            "numPassedTests": int,
            "numFailedTests": int,
            "numPendingTests": int,
            "numTotalTests": int,
            "coverageMap": {...} (optional)
        }
        """
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        coverage_percent = 0.0

        try:
            # Jest may output non-JSON before the JSON blob
            json_start = raw_output.find("{")
            if json_start == -1:
                logger.warning("No JSON found in Jest/Vitest output")
                return self._fallback_result(raw_output, exit_code)

            json_str = raw_output[json_start:]
            report = json.loads(json_str)

            passed = report.get("numPassedTests", 0)
            failed = report.get("numFailedTests", 0)
            skipped = report.get("numPendingTests", 0)

            # Extract coverage if available
            if "coverageMap" in report and report["coverageMap"]:
                coverage_percent = self._extract_coverage(report["coverageMap"])

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse Jest/Vitest JSON output: %s", e)
            return self._fallback_result(raw_output, exit_code)

        total = passed + failed + skipped + errors

        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total": total,
            "coverage_percent": coverage_percent,
            "coverage_type": CoverageType.LINE,
            "raw_output": raw_output,
            "exit_code": exit_code,
            "framework": self.config["framework"],
        }

    def _extract_coverage(self, coverage_map: dict) -> float:
        """Extract overall line coverage percentage from Jest coverageMap.

        Averages line coverage across all files.
        """
        if not coverage_map:
            return 0.0

        total_statements = 0
        covered_statements = 0

        for _file_path, file_coverage in coverage_map.items():
            statement_map = file_coverage.get("statementMap", {})
            s_counts = file_coverage.get("s", {})
            total_statements += len(statement_map)
            covered_statements += sum(1 for count in s_counts.values() if count > 0)

        if total_statements == 0:
            return 0.0

        return (covered_statements / total_statements) * 100.0

    def _fallback_result(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Create a fallback result when JSON parsing fails."""
        return {
            "passed": 0,
            "failed": 1 if exit_code != 0 else 0,
            "skipped": 0,
            "errors": 1 if exit_code != 0 else 0,
            "total": 1,
            "coverage_percent": 0.0,
            "coverage_type": CoverageType.LINE,
            "raw_output": raw_output,
            "exit_code": exit_code,
            "framework": self.config["framework"],
        }

    def validate_test_file(self, file_path: str, content: str) -> list[str]:
        """Validate .test.ts file for Jest/Vitest correctness.

        Checks:
        - Has describe/it/test blocks
        - Has expect() assertions
        """
        errors: list[str] = []

        if not content.strip():
            errors.append(f"Empty test file: {file_path}")
            return errors

        has_describe = bool(re.search(r"\bdescribe\s*\(", content))
        has_it = bool(re.search(r"\bit\s*\(", content))
        has_test = bool(re.search(r"\btest\s*\(", content))

        if not (has_describe or has_it or has_test):
            errors.append(f"No test structure (describe/it/test) found in {file_path}")

        return errors

    def get_scaffold_imports(self) -> str:
        """Return jest or vitest import block."""
        if self._is_vitest:
            return "import { describe, it, expect } from 'vitest';"
        return "import { describe, it, expect } from '@jest/globals';"
```

### 6.8 `assemblyzero/workflows/testing/nodes/scaffold_tests.py` (Modify)

**Change 1:** Add imports after existing imports (after line ~30, after the `from assemblyzero.workflows.testing.state` import)

```diff
 from assemblyzero.workflows.testing.state import TestingWorkflowState, TestScenario
+
+from assemblyzero.workflows.testing.framework_detector import (
+    TestFramework,
+    FrameworkConfig,
+)
+from assemblyzero.workflows.testing.runner_registry import get_framework_config, get_runner
```

**Change 2:** Add TypeScript scaffolding function (add before the `scaffold_tests` function)

```python
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


def _generate_playwright_content(
    scenarios: list[TestScenario],
    issue_number: int,
) -> str:
    """Generate Playwright .spec.ts test content."""
    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"// Issue #{issue_number} - Auto-scaffolded Playwright tests",
        "",
    ]

    for scenario in scenarios:
        test_name = scenario.get("description", scenario.get("id", "unnamed"))
        expected = scenario.get("expected_behavior", "// TODO: implement assertion")
        lines.extend([
            f"test('{test_name}', async ({{ page }}) => {{",
            f"  // Expected: {expected}",
            "  // TODO: Implement test logic",
            "  await expect(page).toBeTruthy();",
            "});",
            "",
        ])

    return "\n".join(lines)


def _generate_jest_content(
    scenarios: list[TestScenario],
    framework_config: FrameworkConfig,
    issue_number: int,
) -> str:
    """Generate Jest/Vitest .test.ts content."""
    runner = get_runner(framework_config["framework"])
    import_line = runner.get_scaffold_imports()

    lines = [
        import_line,
        "",
        f"// Issue #{issue_number} - Auto-scaffolded tests",
        "",
        f"describe('Issue #{issue_number}', () => {{",
    ]

    for scenario in scenarios:
        test_name = scenario.get("description", scenario.get("id", "unnamed"))
        expected = scenario.get("expected_behavior", "// TODO: implement assertion")
        lines.extend([
            f"  it('{test_name}', () => {{",
            f"    // Expected: {expected}",
            "    // TODO: Implement test logic",
            "    expect(true).toBe(true);",
            "  });",
            "",
        ])

    lines.append("});")
    return "\n".join(lines)
```

**Change 3:** Modify `determine_test_file_path` to accept optional `framework_config` (modify the existing function)

```diff
 def determine_test_file_path(
     issue_number: int,
     scenarios: list[TestScenario],
     repo_root: Path,
+    framework_config: FrameworkConfig | None = None,
 ) -> Path:
     """Determine the appropriate path for the test file.
 
-Args:"""
-    ...
+    Args:
+        issue_number: Issue number
+        scenarios: Test scenarios
+        repo_root: Repository root
+        framework_config: Optional framework config for file extension
+    """
+    if framework_config is not None:
+        framework = framework_config["framework"]
+        ext = framework_config["test_file_extension"]
+        if framework == TestFramework.PLAYWRIGHT:
+            return repo_root / "tests" / f"issue_{issue_number}{ext}"
+        elif framework in (TestFramework.JEST, TestFramework.VITEST):
+            return repo_root / "tests" / f"issue_{issue_number}{ext}"
+    # Default: existing pytest behavior (unchanged)
+    # ... existing implementation continues here unchanged ...
```

**Change 4:** Modify `scaffold_tests` function to dispatch on framework (modify the existing function body)

Add at the beginning of `scaffold_tests()`, right after reading state:

```diff
 def scaffold_tests(state: TestingWorkflowState) -> dict[str, Any]:
     """N2: Generate executable test stubs.
 
     Args:"""
+    # Issue #381: Framework-aware scaffolding
+    framework_config = state.get("framework_config")
+    
+    # If framework_config exists and is not pytest, use TS scaffolding
+    if framework_config and framework_config.get("framework") not in (
+        None, TestFramework.PYTEST
+    ):
+        return _scaffold_non_python_tests(state, framework_config)
+    
+    # Default: existing pytest scaffolding (unchanged)
     ...
```

Add new helper function:

```python
def _scaffold_non_python_tests(
    state: TestingWorkflowState,
    framework_config: FrameworkConfig,
) -> dict[str, Any]:
    """Scaffold non-Python test files (Playwright, Jest, Vitest).

    Issue #381: Generates TypeScript test files based on framework config.
    """
    issue_number = state.get("issue_number", 0)
    scenarios = state.get("test_scenarios", [])
    repo_root = get_repo_root()

    # Generate TypeScript test content
    content = generate_ts_test_file_content(scenarios, framework_config, issue_number)

    # Determine file path
    test_file_path = determine_test_file_path(
        issue_number, scenarios, repo_root, framework_config
    )

    # Write the file
    test_file_path.parent.mkdir(parents=True, exist_ok=True)
    test_file_path.write_text(content, encoding="utf-8")

    gate_log(f"[N2] Scaffolded {framework_config['framework'].value} test: {test_file_path}")
    log_workflow_execution(
        issue_number,
        "scaffold_tests",
        f"Created {framework_config['framework'].value} test file: {test_file_path}",
    )

    return {
        "test_files": [str(test_file_path)],
        "test_file_content": content,
        "error_message": "",
    }
```

### 6.9 `assemblyzero/workflows/testing/nodes/run_tests.py` (Add)

**Complete file contents:**

```python
"""RunTests node for TDD Testing Workflow.

Issue #381: Framework-aware test execution that delegates to the
appropriate runner from the runner registry.
"""

import logging
from typing import Any

from assemblyzero.workflows.testing.audit import gate_log, log_workflow_execution
from assemblyzero.workflows.testing.framework_detector import (
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runner_registry import (
    get_framework_config,
    get_runner,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState

logger = logging.getLogger(__name__)


def run_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """Execute tests using the framework-appropriate runner.

    Reads framework_config from state, validates test files,
    runs tests, and stores unified TestRunResult in state.

    Args:
        state: Workflow state containing framework_config, test_files, etc.

    Returns:
        Dict with test_run_result, validation_errors, and error_message.
    """
    issue_number = state.get("issue_number", 0)
    framework_config = state.get("framework_config")
    test_files: list[str] = state.get("test_files", [])
    repo_root: str = str(state.get("repo_root", "."))

    gate_log(f"[RunTests] Starting test execution for issue #{issue_number}")

    # Fallback to pytest if no framework config
    if not framework_config:
        logger.info("No framework_config in state; defaulting to pytest")
        framework_config = get_framework_config(TestFramework.PYTEST)

    framework = framework_config["framework"]
    gate_log(f"[RunTests] Framework: {framework.value}")

    if not test_files:
        return {
            "test_run_result": None,
            "validation_errors": [],
            "error_message": "No test files to run",
        }

    # Get the runner
    try:
        runner = get_runner(framework, project_root=repo_root)
    except EnvironmentError as e:
        gate_log(f"[RunTests] Environment error: {e}")
        return {
            "test_run_result": None,
            "validation_errors": [],
            "error_message": str(e),
        }

    # Validate each test file
    all_validation_errors: list[str] = []
    for file_path in test_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            errors = runner.validate_test_file(file_path, content)
            all_validation_errors.extend(errors)
        except (OSError, IOError) as e:
            all_validation_errors.append(f"Cannot read test file {file_path}: {e}")

    if all_validation_errors:
        gate_log(
            f"[RunTests] Validation errors found: {len(all_validation_errors)}"
        )
        for err in all_validation_errors:
            gate_log(f"[RunTests]   - {err}")
        return {
            "test_run_result": None,
            "validation_errors": all_validation_errors,
            "error_message": f"Test file validation failed: {len(all_validation_errors)} error(s)",
        }

    # Run the tests
    gate_log(f"[RunTests] Executing {len(test_files)} test file(s)")
    try:
        result: TestRunResult = runner.run_tests(test_paths=test_files)
    except Exception as e:
        logger.error("Test execution failed: %s", e)
        return {
            "test_run_result": None,
            "validation_errors": [],
            "error_message": f"Test execution failed: {e}",
        }

    gate_log(
        f"[RunTests] Results: {result['passed']} passed, "
        f"{result['failed']} failed, {result['skipped']} skipped, "
        f"{result['errors']} errors (exit code: {result['exit_code']})"
    )

    log_workflow_execution(
        issue_number,
        "run_tests",
        f"Tests executed: {result['total']} total, "
        f"{result['passed']} passed, {result['failed']} failed",
    )

    return {
        "test_run_result": result,
        "validation_errors": [],
        "error_message": "",
    }
```

### 6.10 `assemblyzero/workflows/testing/nodes/check_coverage.py` (Add)

**Complete file contents:**

```python
"""CheckCoverage node for TDD Testing Workflow.

Issue #381: Framework-aware coverage checking that dispatches on
coverage_type (LINE, SCENARIO, NONE).
"""

import logging
from typing import Any

from assemblyzero.workflows.testing.audit import gate_log, log_workflow_execution
from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import (
    get_framework_config,
    get_runner,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState

logger = logging.getLogger(__name__)


def check_coverage(state: TestingWorkflowState) -> dict[str, Any]:
    """Evaluate coverage against framework-appropriate target.

    Dispatches on coverage_type:
    - LINE: compare result.coverage_percent against coverage_target
    - SCENARIO: compute passed/total_scenarios against coverage_target
    - NONE: skip coverage gate, only check pass/fail

    Args:
        state: Workflow state containing test_run_result and framework_config.

    Returns:
        Dict with 'green' (bool) and 'iterate_reason' (str).
    """
    issue_number = state.get("issue_number", 0)
    test_run_result = state.get("test_run_result")
    framework_config = state.get("framework_config")

    gate_log(f"[CheckCoverage] Evaluating results for issue #{issue_number}")

    if not test_run_result:
        return {
            "green": False,
            "iterate_reason": "No test results available",
        }

    # Fallback to pytest config if not set
    if not framework_config:
        framework_config = get_framework_config(TestFramework.PYTEST)

    coverage_type = framework_config["coverage_type"]
    coverage_target = framework_config["coverage_target"]

    # Step 1: Check for test failures (applies to all frameworks)
    if test_run_result["failed"] > 0:
        reason = f"{test_run_result['failed']} tests failed"
        gate_log(f"[CheckCoverage] NOT GREEN: {reason}")
        return {
            "green": False,
            "iterate_reason": reason,
        }

    if test_run_result["errors"] > 0:
        reason = f"{test_run_result['errors']} test errors"
        gate_log(f"[CheckCoverage] NOT GREEN: {reason}")
        return {
            "green": False,
            "iterate_reason": reason,
        }

    # Step 2: Coverage check based on type
    if coverage_type == CoverageType.SCENARIO:
        total_scenarios = state.get("total_scenarios", 0)

        if total_scenarios == 0:
            # Try to use test total as fallback
            total_scenarios = test_run_result.get("total", 0)

        if total_scenarios == 0:
            gate_log("[CheckCoverage] WARNING: No scenarios to measure coverage against")
            return {
                "green": False,
                "iterate_reason": "No scenarios defined for coverage measurement",
            }

        runner = get_runner(framework_config["framework"])
        coverage = runner.compute_scenario_coverage(test_run_result, total_scenarios)

        if coverage < coverage_target:
            reason = (
                f"Scenario coverage {coverage:.1%} < target {coverage_target:.1%}"
            )
            gate_log(f"[CheckCoverage] NOT GREEN: {reason}")
            return {
                "green": False,
                "iterate_reason": reason,
            }

        gate_log(f"[CheckCoverage] GREEN: Scenario coverage {coverage:.1%} >= {coverage_target:.1%}")
        log_workflow_execution(
            issue_number, "check_coverage",
            f"Scenario coverage {coverage:.1%} meets target {coverage_target:.1%}",
        )
        return {"green": True, "iterate_reason": ""}

    elif coverage_type == CoverageType.LINE:
        coverage_percent = test_run_result.get("coverage_percent", 0.0)
        target_percent = coverage_target * 100  # Convert 0.95 to 95.0

        if coverage_percent < target_percent:
            reason = (
                f"Line coverage {coverage_percent:.1f}% < target {target_percent:.1f}%"
            )
            gate_log(f"[CheckCoverage] NOT GREEN: {reason}")
            return {
                "green": False,
                "iterate_reason": reason,
            }

        gate_log(
            f"[CheckCoverage] GREEN: Line coverage {coverage_percent:.1f}% >= {target_percent:.1f}%"
        )
        log_workflow_execution(
            issue_number, "check_coverage",
            f"Line coverage {coverage_percent:.1f}% meets target {target_percent:.1f}%",
        )
        return {"green": True, "iterate_reason": ""}

    elif coverage_type == CoverageType.NONE:
        gate_log("[CheckCoverage] GREEN: Coverage type is NONE, pass/fail check only")
        log_workflow_execution(
            issue_number, "check_coverage",
            "Coverage type NONE - pass/fail check passed",
        )
        return {"green": True, "iterate_reason": ""}

    else:
        logger.warning("Unknown coverage type: %s", coverage_type)
        return {
            "green": False,
            "iterate_reason": f"Unknown coverage type: {coverage_type}",
        }
```

### 6.11 `tests/fixtures/lld_playwright_sample.md` (Add)

**Complete file contents:**

```markdown
# 56 - Feature: Dashboard E2E Tests

## 1. Context & Goal
Automated end-to-end tests for the dashboard using Playwright.

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/dashboard.spec.ts` | Add | E2E tests for dashboard |
| `tests/sidebar.spec.ts` | Add | E2E tests for sidebar navigation |

## 10. Verification & Testing

Test Framework: Playwright

### 10.0 Test Plan

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Dashboard loads correctly | Page shows dashboard heading | RED |
| T020 | Sidebar navigation works | Clicking menu item navigates | RED |
| T030 | Data table displays | Table has correct columns | RED |
```

### 6.12 `tests/fixtures/lld_jest_sample.md` (Add)

**Complete file contents:**

```markdown
# 100 - Feature: Utility Functions Unit Tests

## 1. Context & Goal
Unit tests for utility functions using Jest.

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/utils.test.ts` | Add | Unit tests for utility functions |

## 10. Verification & Testing

Test Framework: Jest

### 10.0 Test Plan

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | formatDate handles valid date | Returns formatted string | RED |
| T020 | formatDate handles null | Returns empty string | RED |
```

### 6.13 `tests/fixtures/lld_pytest_sample.md` (Add)

**Complete file contents:**

```markdown
# 200 - Feature: Data Processing Pipeline

## 1. Context & Goal
Standard Python data processing with pytest tests.

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/pipeline.py` | Add | Data processing pipeline |
| `tests/test_pipeline.py` | Add | Unit tests for pipeline |

## 10. Verification & Testing

### 10.0 Test Plan

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Pipeline processes valid input | Returns transformed data | RED |
| T020 | Pipeline handles empty input | Returns empty result | RED |
```

### 6.14 `tests/fixtures/playwright_json_report.json` (Add)

**Complete file contents:**

```json
{
  "config": {
    "rootDir": "/home/user/projects/dashboard"
  },
  "suites": [
    {
      "title": "Dashboard Tests",
      "specs": [
        {
          "title": "loads dashboard correctly",
          "tests": [
            {
              "results": [
                {"status": "passed", "duration": 1523}
              ]
            }
          ]
        },
        {
          "title": "shows sidebar navigation",
          "tests": [
            {
              "results": [
                {"status": "passed", "duration": 892}
              ]
            }
          ]
        },
        {
          "title": "data table renders",
          "tests": [
            {
              "results": [
                {"status": "failed", "duration": 3001}
              ]
            }
          ]
        },
        {
          "title": "responsive layout works",
          "tests": [
            {
              "results": [
                {"status": "skipped", "duration": 0}
              ]
            }
          ]
        }
      ],
      "suites": []
    }
  ]
}
```

### 6.15 `tests/fixtures/jest_json_report.json` (Add)

**Complete file contents:**

```json
{
  "success": false,
  "numPassedTests": 8,
  "numFailedTests": 2,
  "numPendingTests": 1,
  "numTotalTests": 11,
  "numPassedTestSuites": 1,
  "numFailedTestSuites": 1,
  "numPendingTestSuites": 0,
  "numTotalTestSuites": 2,
  "startTime": 1708900000000,
  "testResults": [
    {
      "testFilePath": "/home/user/projects/frontend/tests/utils.test.ts",
      "testResults": [
        {"title": "formatDate handles valid date", "status": "passed", "duration": 5},
        {"title": "formatDate handles null", "status": "passed", "duration": 2},
        {"title": "parseConfig valid JSON", "status": "failed", "duration": 10}
      ]
    }
  ],
  "coverageMap": {}
}
```

### 6.16 `tests/unit/test_framework_detector.py` (Add)

**Complete file contents:**

```python
"""Unit tests for framework detection.

Issue #381: Tests T010-T070 from LLD Section 10.0.
"""

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
    detect_framework_from_lld,
    detect_framework_from_project,
    resolve_framework,
)


class TestDetectFrameworkFromLLD:
    """Tests for detect_framework_from_lld()."""

    def test_t010_detects_playwright_from_spec_ts(self):
        """T010: detect_framework_from_lld identifies Playwright from .spec.ts."""
        lld = """## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `tests/dashboard.spec.ts` | Add |
"""
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_t020_detects_jest_from_test_ts(self):
        """T020: detect_framework_from_lld identifies Jest from .test.ts."""
        lld = """## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `tests/utils.test.ts` | Add |
"""
        assert detect_framework_from_lld(lld) == TestFramework.JEST

    def test_t030_defaults_to_pytest(self):
        """T030: detect_framework_from_lld defaults to pytest."""
        lld = """## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `src/pipeline.py` | Add |
"""
        assert detect_framework_from_lld(lld) == TestFramework.PYTEST

    def test_t040_explicit_playwright_declaration(self):
        """T040: detect_framework_from_lld handles explicit declaration."""
        lld = """## 10. Verification & Testing
Test Framework: Playwright
"""
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_explicit_jest_declaration(self):
        """Detect Jest from explicit declaration."""
        lld = "Test Framework: Jest\nSome other content."
        assert detect_framework_from_lld(lld) == TestFramework.JEST

    def test_explicit_vitest_declaration(self):
        """Detect Vitest from explicit declaration."""
        lld = "Test Framework: Vitest"
        assert detect_framework_from_lld(lld) == TestFramework.VITEST

    def test_explicit_pytest_declaration(self):
        """Detect pytest from explicit declaration."""
        lld = "Test Framework: pytest"
        assert detect_framework_from_lld(lld) == TestFramework.PYTEST

    def test_empty_lld_defaults_to_pytest(self):
        """Empty LLD returns pytest."""
        assert detect_framework_from_lld("") == TestFramework.PYTEST

    def test_playwright_keyword_detection(self):
        """Detect Playwright from @playwright/test keyword."""
        lld = "We use @playwright/test for e2e testing."
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_npx_playwright_command(self):
        """Detect Playwright from npx command in LLD."""
        lld = "Run `npx playwright test` to execute."
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_spec_js_detected_as_playwright(self):
        """Detect Playwright from .spec.js file pattern."""
        lld = "| `tests/app.spec.js` | Add |"
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT


class TestDetectFrameworkFromProject:
    """Tests for detect_framework_from_project()."""

    def test_t050_playwright_config_file(self):
        """T050: detect_framework_from_project finds playwright.config.ts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "playwright.config.ts").touch()
            assert detect_framework_from_project(tmpdir) == TestFramework.PLAYWRIGHT

    def test_t060_jest_in_package_json(self):
        """T060: detect_framework_from_project finds jest in package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"scripts": {"test": "jest --coverage"}}
            Path(tmpdir, "package.json").write_text(json.dumps(pkg))
            assert detect_framework_from_project(tmpdir) == TestFramework.JEST

    def test_vitest_in_package_json(self):
        """Detect Vitest from package.json scripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"scripts": {"test": "vitest run"}}
            Path(tmpdir, "package.json").write_text(json.dumps(pkg))
            assert detect_framework_from_project(tmpdir) == TestFramework.VITEST

    def test_jest_config_file(self):
        """Detect Jest from jest.config.ts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "jest.config.ts").touch()
            assert detect_framework_from_project(tmpdir) == TestFramework.JEST

    def test_vitest_config_file(self):
        """Detect Vitest from vitest.config.ts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "vitest.config.ts").touch()
            assert detect_framework_from_project(tmpdir) == TestFramework.VITEST

    def test_pyproject_toml_pytest(self):
        """Detect pytest from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
            assert detect_framework_from_project(tmpdir) == TestFramework.PYTEST

    def test_nonexistent_directory(self):
        """Non-existent directory returns None."""
        assert detect_framework_from_project("/nonexistent/path/xyz") is None

    def test_empty_directory(self):
        """Empty directory returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert detect_framework_from_project(tmpdir) is None

    def test_ambiguous_multiple_configs(self):
        """Multiple config files returns None (ambiguous)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "playwright.config.ts").touch()
            Path(tmpdir, "jest.config.ts").touch()
            assert detect_framework_from_project(tmpdir) is None

    def test_invalid_package_json(self):
        """Malformed package.json is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package.json").write_text("not valid json")
            assert detect_framework_from_project(tmpdir) is None


class TestResolveFramework:
    """Tests for resolve_framework()."""

    def test_t070_lld_overrides_project(self):
        """T070: LLD overrides project detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "jest.config.ts").touch()
            lld = "Test Framework: Playwright"
            assert resolve_framework(lld, tmpdir) == TestFramework.PLAYWRIGHT

    def test_project_fallback_when_lld_default(self):
        """When LLD detects default pytest, project files can override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "playwright.config.ts").touch()
            lld = "Some generic LLD without framework indicators."
            assert resolve_framework(lld, tmpdir) == TestFramework.PLAYWRIGHT

    def test_both_default_returns_pytest(self):
        """When both LLD and project have no indicators, return pytest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert resolve_framework("No indicators here.", tmpdir) == TestFramework.PYTEST

    def test_empty_project_root(self):
        """Empty project root skips project detection."""
        lld = "Test Framework: Jest"
        assert resolve_framework(lld, "") == TestFramework.JEST
```

### 6.17 `tests/unit/test_runner_registry.py` (Add)

**Complete file contents:**

```python
"""Unit tests for runner registry.

Issue #381: Tests T080-T110 from LLD Section 10.0.
"""

import pytest
from unittest.mock import patch

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import (
    get_framework_config,
    get_runner,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner
from assemblyzero.workflows.testing.runners.playwright_runner import PlaywrightRunner
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner


class TestGetFrameworkConfig:
    """Tests for get_framework_config()."""

    def test_t080_playwright_config(self):
        """T080: get_framework_config returns correct config for PLAYWRIGHT."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        assert config["framework"] == TestFramework.PLAYWRIGHT
        assert config["test_runner_command"] == "npx playwright test"
        assert config["test_file_pattern"] == "*.spec.ts"
        assert config["test_file_extension"] == ".spec.ts"
        assert config["coverage_type"] == CoverageType.SCENARIO
        assert config["coverage_target"] == 1.0

    def test_t090_pytest_config(self):
        """T090: get_framework_config returns correct config for PYTEST."""
        config = get_framework_config(TestFramework.PYTEST)
        assert config["framework"] == TestFramework.PYTEST
        assert config["test_runner_command"] == "pytest"
        assert config["test_file_pattern"] == "test_*.py"
        assert config["test_file_extension"] == ".py"
        assert config["coverage_type"] == CoverageType.LINE
        assert config["coverage_target"] == 0.95

    def test_jest_config(self):
        """get_framework_config returns correct config for JEST."""
        config = get_framework_config(TestFramework.JEST)
        assert config["framework"] == TestFramework.JEST
        assert config["test_runner_command"] == "npx jest"
        assert config["test_file_pattern"] == "*.test.ts"
        assert config["coverage_type"] == CoverageType.LINE

    def test_vitest_config(self):
        """get_framework_config returns correct config for VITEST."""
        config = get_framework_config(TestFramework.VITEST)
        assert config["framework"] == TestFramework.VITEST
        assert config["test_runner_command"] == "npx vitest run"

    def test_config_is_copy(self):
        """Returned config should be a copy (not mutable registry)."""
        config1 = get_framework_config(TestFramework.PYTEST)
        config2 = get_framework_config(TestFramework.PYTEST)
        config1["coverage_target"] = 0.5
        assert config2["coverage_target"] == 0.95  # Unaffected


class TestGetRunner:
    """Tests for get_runner()."""

    def test_t100_pytest_runner(self):
        """T100: get_runner returns PytestRunner for PYTEST."""
        runner = get_runner(TestFramework.PYTEST)
        assert isinstance(runner, PytestRunner)
        assert isinstance(runner, BaseTestRunner)

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t110_playwright_runner(self, mock_which):
        """T110: get_runner returns PlaywrightRunner for PLAYWRIGHT."""
        runner = get_runner(TestFramework.PLAYWRIGHT)
        assert isinstance(runner, PlaywrightRunner)
        assert isinstance(runner, BaseTestRunner)

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_jest_runner(self, mock_which):
        """get_runner returns JestRunner for JEST."""
        runner = get_runner(TestFramework.JEST)
        assert isinstance(runner, JestRunner)

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_vitest_runner(self, mock_which):
        """get_runner returns JestRunner for VITEST (shared runner)."""
        runner = get_runner(TestFramework.VITEST)
        assert isinstance(runner, JestRunner)
```

### 6.18 `tests/unit/test_pytest_runner.py` (Add)

**Complete file contents:**

```python
"""Unit tests for PytestRunner.

Issue #381: Tests T120, T130, T200, T240 from LLD Section 10.0.
"""

from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner


@pytest.fixture
def pytest_runner():
    """Create a PytestRunner with default config."""
    config = get_framework_config(TestFramework.PYTEST)
    return PytestRunner(config, project_root="/tmp/test_project")


class TestPytestRunnerValidation:
    """Tests for PytestRunner.validate_test_file()."""

    def test_t120_valid_python_test(self, pytest_runner):
        """T120: PytestRunner.validate_test_file accepts valid Python test."""
        content = """import pytest
from mymodule import my_function

def test_my_function():
    assert my_function(42) == 84
"""
        errors = pytest_runner.validate_test_file("tests/test_example.py", content)
        assert errors == []

    def test_t130_missing_imports(self, pytest_runner):
        """T130: PytestRunner.validate_test_file rejects missing imports."""
        content = """def test_something():
    assert True
"""
        errors = pytest_runner.validate_test_file("tests/test_bad.py", content)
        assert any("No import statements" in e for e in errors)

    def test_missing_test_functions(self, pytest_runner):
        """Reject file with no test_ functions."""
        content = """import pytest

def helper():
    return 42
"""
        errors = pytest_runner.validate_test_file("tests/test_bad.py", content)
        assert any("No test functions" in e for e in errors)

    def test_empty_file(self, pytest_runner):
        """Reject empty test file."""
        errors = pytest_runner.validate_test_file("tests/test_empty.py", "")
        assert any("Empty test file" in e for e in errors)

    def test_class_based_tests_accepted(self, pytest_runner):
        """Accept class-based test style (class TestXxx)."""
        content = """import pytest

class TestMyFeature:
    def test_something(self):
        assert True
"""
        errors = pytest_runner.validate_test_file("tests/test_class.py", content)
        assert errors == []


class TestPytestRunnerParseResults:
    """Tests for PytestRunner.parse_results()."""

    def test_t200_parse_pytest_output(self, pytest_runner):
        """T200: PytestRunner.parse_results handles pytest output."""
        output = """tests/test_example.py ..F.s
============ 3 passed, 1 failed, 1 skipped in 0.25s ============
TOTAL    150     12    92%
"""
        result = pytest_runner.parse_results(output, exit_code=1)
        assert result["passed"] == 3
        assert result["failed"] == 1
        assert result["skipped"] == 1
        assert result["total"] == 5
        assert result["coverage_percent"] == 92.0
        assert result["coverage_type"] == CoverageType.LINE
        assert result["framework"] == TestFramework.PYTEST
        assert result["exit_code"] == 1

    def test_parse_all_passing(self, pytest_runner):
        """Parse all-passing output."""
        output = "10 passed in 1.5s"
        result = pytest_runner.parse_results(output, exit_code=0)
        assert result["passed"] == 10
        assert result["failed"] == 0
        assert result["exit_code"] == 0

    def test_parse_no_coverage(self, pytest_runner):
        """Parse output without coverage info."""
        output = "5 passed in 0.5s"
        result = pytest_runner.parse_results(output, exit_code=0)
        assert result["coverage_percent"] == 0.0


class TestPytestRunnerRunTests:
    """Tests for PytestRunner.run_tests()."""

    @patch.object(PytestRunner, "_run_subprocess")
    def test_t240_invokes_correct_command(self, mock_subprocess, pytest_runner):
        """T240: PytestRunner.run_tests invokes correct command."""
        mock_subprocess.return_value = ("5 passed in 0.5s", 0)
        pytest_runner.run_tests(test_paths=["tests/test_example.py"])

        args, kwargs = mock_subprocess.call_args
        command = args[0]
        assert "pytest" in command
        assert "--tb=short" in command
        assert "-q" in command
        assert "tests/test_example.py" in command

    @patch.object(PytestRunner, "_run_subprocess")
    def test_extra_args_passed(self, mock_subprocess, pytest_runner):
        """Extra args are appended to the command."""
        mock_subprocess.return_value = ("5 passed", 0)
        pytest_runner.run_tests(extra_args=["--cov=mymodule"])

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "--cov=mymodule" in command


class TestPytestRunnerScaffold:
    """Tests for PytestRunner.get_scaffold_imports()."""

    def test_scaffold_imports(self, pytest_runner):
        """Returns correct pytest import."""
        assert pytest_runner.get_scaffold_imports() == "import pytest"
```

### 6.19 `tests/unit/test_playwright_runner.py` (Add)

**Complete file contents:**

```python
"""Unit tests for PlaywrightRunner.

Issue #381: Tests T140, T150, T180, T220, T250 from LLD Section 10.0.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.playwright_runner import PlaywrightRunner


@pytest.fixture
def playwright_runner():
    """Create a PlaywrightRunner with mocked npx availability."""
    with patch("shutil.which", return_value="/usr/bin/npx"):
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        return PlaywrightRunner(config, project_root="/tmp/test_project")


class TestPlaywrightRunnerValidation:
    """Tests for PlaywrightRunner.validate_test_file()."""

    def test_t140_valid_spec_ts(self, playwright_runner):
        """T140: PlaywrightRunner.validate_test_file accepts valid .spec.ts."""
        content = """import { test, expect } from '@playwright/test';

test('loads dashboard', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.locator('h1')).toHaveText('Dashboard');
});
"""
        errors = playwright_runner.validate_test_file("tests/dashboard.spec.ts", content)
        assert errors == []

    def test_t150_missing_playwright_import(self, playwright_runner):
        """T150: PlaywrightRunner.validate_test_file rejects missing imports."""
        content = """test('loads dashboard', async ({ page }) => {
  await page.goto('/dashboard');
});
"""
        errors = playwright_runner.validate_test_file("tests/dashboard.spec.ts", content)
        assert any("@playwright/test" in e for e in errors)

    def test_missing_test_calls(self, playwright_runner):
        """Reject file with no test() calls."""
        content = """import { test, expect } from '@playwright/test';

const x = 5;
console.log(x);
"""
        errors = playwright_runner.validate_test_file("tests/bad.spec.ts", content)
        assert any("No test() calls" in e for e in errors)

    def test_empty_file(self, playwright_runner):
        """Reject empty file."""
        errors = playwright_runner.validate_test_file("tests/empty.spec.ts", "")
        assert any("Empty test file" in e for e in errors)


class TestPlaywrightRunnerParseResults:
    """Tests for PlaywrightRunner.parse_results()."""

    def test_t180_parse_json_report(self, playwright_runner):
        """T180: PlaywrightRunner.parse_results handles JSON report."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "playwright_json_report.json"
        with open(fixture_path) as f:
            raw_output = f.read()

        result = playwright_runner.parse_results(raw_output, exit_code=1)
        assert result["passed"] == 2
        assert result["failed"] == 1
        assert result["skipped"] == 1
        assert result["total"] == 4
        assert result["coverage_type"] == CoverageType.SCENARIO
        assert result["framework"] == TestFramework.PLAYWRIGHT
        assert result["exit_code"] == 1

    def test_parse_all_passing(self, playwright_runner):
        """Parse all-passing Playwright report."""
        report = {
            "config": {},
            "suites": [{
                "title": "Tests",
                "specs": [
                    {"title": "t1", "tests": [{"results": [{"status": "passed"}]}]},
                    {"title": "t2", "tests": [{"results": [{"status": "passed"}]}]},
                ],
                "suites": [],
            }],
        }
        result = playwright_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert result["total"] == 2

    def test_parse_invalid_json(self, playwright_runner):
        """Fallback when JSON is invalid."""
        result = playwright_runner.parse_results("not json at all", exit_code=1)
        assert result["failed"] >= 1
        assert result["errors"] >= 1

    def test_parse_nested_suites(self, playwright_runner):
        """Parse nested suite structure."""
        report = {
            "config": {},
            "suites": [{
                "title": "Root",
                "specs": [],
                "suites": [{
                    "title": "Nested",
                    "specs": [
                        {"title": "t1", "tests": [{"results": [{"status": "passed"}]}]},
                    ],
                    "suites": [],
                }],
            }],
        }
        result = playwright_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["passed"] == 1
        assert result["total"] == 1


class TestPlaywrightRunnerRunTests:
    """Tests for PlaywrightRunner.run_tests()."""

    @patch.object(PlaywrightRunner, "_run_subprocess")
    def test_t220_invokes_correct_command(self, mock_subprocess, playwright_runner):
        """T220: PlaywrightRunner.run_tests invokes correct command."""
        mock_subprocess.return_value = ('{"config":{},"suites":[]}', 0)
        playwright_runner.run_tests(test_paths=["tests/dashboard.spec.ts"])

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "npx" in command
        assert "playwright" in command
        assert "test" in command
        assert "--reporter=json" in command
        assert "tests/dashboard.spec.ts" in command


class TestPlaywrightRunnerEnvironment:
    """Tests for PlaywrightRunner environment checks."""

    def test_t250_missing_npx(self):
        """T250: Runner raises EnvironmentError if npx not found."""
        with patch("shutil.which", return_value=None):
            config = get_framework_config(TestFramework.PLAYWRIGHT)
            with pytest.raises(EnvironmentError, match="npx not found"):
                PlaywrightRunner(config, "/tmp/test")


class TestPlaywrightRunnerScaffold:
    """Tests for PlaywrightRunner.get_scaffold_imports()."""

    def test_scaffold_imports(self, playwright_runner):
        """Returns correct Playwright import."""
        imports = playwright_runner.get_scaffold_imports()
        assert "@playwright/test" in imports
        assert "test" in imports
        assert "expect" in imports
```

### 6.20 `tests/unit/test_jest_runner.py` (Add)

**Complete file contents:**

```python
"""Unit tests for JestRunner.

Issue #381: Tests T160, T170, T190, T230 from LLD Section 10.0.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner


@pytest.fixture
def jest_runner():
    """Create a JestRunner with mocked npx availability."""
    with patch("shutil.which", return_value="/usr/bin/npx"):
        config = get_framework_config(TestFramework.JEST)
        return JestRunner(config, project_root="/tmp/test_project")


@pytest.fixture
def vitest_runner():
    """Create a JestRunner for Vitest with mocked npx availability."""
    with patch("shutil.which", return_value="/usr/bin/npx"):
        config = get_framework_config(TestFramework.VITEST)
        return JestRunner(config, project_root="/tmp/test_project")


class TestJestRunnerValidation:
    """Tests for JestRunner.validate_test_file()."""

    def test_t160_valid_test_ts(self, jest_runner):
        """T160: JestRunner.validate_test_file accepts valid .test.ts."""
        content = """describe('utils', () => {
  it('formats date correctly', () => {
    expect(formatDate(new Date())).toBeDefined();
  });
});
"""
        errors = jest_runner.validate_test_file("tests/utils.test.ts", content)
        assert errors == []

    def test_t170_no_describe_it(self, jest_runner):
        """T170: JestRunner.validate_test_file rejects no describe/it."""
        content = """const x = 5;
console.log(x);
"""
        errors = jest_runner.validate_test_file("tests/utils.test.ts", content)
        assert any("No test structure" in e for e in errors)

    def test_test_function_accepted(self, jest_runner):
        """Accept test() function style (without describe)."""
        content = """test('works', () => {
  expect(true).toBe(true);
});
"""
        errors = jest_runner.validate_test_file("tests/simple.test.ts", content)
        assert errors == []

    def test_empty_file(self, jest_runner):
        """Reject empty file."""
        errors = jest_runner.validate_test_file("tests/empty.test.ts", "")
        assert any("Empty test file" in e for e in errors)


class TestJestRunnerParseResults:
    """Tests for JestRunner.parse_results()."""

    def test_t190_parse_json_report(self, jest_runner):
        """T190: JestRunner.parse_results handles JSON report."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "jest_json_report.json"
        with open(fixture_path) as f:
            raw_output = f.read()

        result = jest_runner.parse_results(raw_output, exit_code=1)
        assert result["passed"] == 8
        assert result["failed"] == 2
        assert result["skipped"] == 1
        assert result["total"] == 11
        assert result["coverage_type"] == CoverageType.LINE
        assert result["framework"] == TestFramework.JEST
        assert result["exit_code"] == 1

    def test_parse_all_passing(self, jest_runner):
        """Parse all-passing Jest report."""
        report = {
            "success": True,
            "numPassedTests": 5,
            "numFailedTests": 0,
            "numPendingTests": 0,
            "numTotalTests": 5,
        }
        result = jest_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["passed"] == 5
        assert result["failed"] == 0
        assert result["total"] == 5

    def test_parse_invalid_json(self, jest_runner):
        """Fallback when JSON is invalid."""
        result = jest_runner.parse_results("not json", exit_code=1)
        assert result["failed"] >= 1

    def test_parse_with_coverage_map(self, jest_runner):
        """Parse report with coverage data."""
        report = {
            "success": True,
            "numPassedTests": 3,
            "numFailedTests": 0,
            "numPendingTests": 0,
            "numTotalTests": 3,
            "coverageMap": {
                "src/utils.ts": {
                    "statementMap": {"0": {}, "1": {}, "2": {}, "3": {}},
                    "s": {"0": 1, "1": 1, "2": 0, "3": 1},
                }
            },
        }
        result = jest_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["coverage_percent"] == 75.0  # 3/4 statements covered


class TestJestRunnerRunTests:
    """Tests for JestRunner.run_tests()."""

    @patch.object(JestRunner, "_run_subprocess")
    def test_t230_invokes_correct_command(self, mock_subprocess, jest_runner):
        """T230: JestRunner.run_tests invokes correct command."""
        mock_subprocess.return_value = ('{"success":true,"numPassedTests":1,"numFailedTests":0,"numPendingTests":0,"numTotalTests":1}', 0)
        jest_runner.run_tests(test_paths=["tests/utils.test.ts"])

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "npx" in command
        assert "jest" in command
        assert "--json" in command
        assert "tests/utils.test.ts" in command

    @patch.object(JestRunner, "_run_subprocess")
    def test_vitest_invokes_correct_command(self, mock_subprocess, vitest_runner):
        """Vitest runner uses vitest run --reporter=json."""
        mock_subprocess.return_value = ('{"success":true,"numPassedTests":1,"numFailedTests":0,"numPendingTests":0,"numTotalTests":1}', 0)
        vitest_runner.run_tests()

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "npx" in command
        assert "vitest" in command
        assert "run" in command
        assert "--reporter=json" in command


class TestJestRunnerEnvironment:
    """Tests for JestRunner environment checks."""

    def test_missing_npx(self):
        """Runner raises EnvironmentError if npx not found."""
        with patch("shutil.which", return_value=None):
            config = get_framework_config(TestFramework.JEST)
            with pytest.raises(EnvironmentError, match="npx not found"):
                JestRunner(config, "/tmp/test")


class TestJestRunnerScaffold:
    """Tests for JestRunner.get_scaffold_imports()."""

    def test_jest_imports(self, jest_runner):
        """Returns correct Jest import."""
        imports = jest_runner.get_scaffold_imports()
        assert "@jest/globals" in imports

    def test_vitest_imports(self, vitest_runner):
        """Returns correct Vitest import."""
        imports = vitest_runner.get_scaffold_imports()
        assert "vitest" in imports
```

### 6.21 `tests/unit/test_scaffold_tests_multifw.py` (Add)

**Complete file contents:**

```python
"""Unit tests for multi-framework scaffolding.

Issue #381: Tests T270, T280 from LLD Section 10.0.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.nodes.scaffold_tests import (
    determine_test_file_path,
    generate_ts_test_file_content,
)


class TestDetermineTestFilePath:
    """Tests for determine_test_file_path with framework config."""

    def test_t270_playwright_creates_spec_ts(self):
        """T270: scaffold_tests uses correct file extension for Playwright."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        repo_root = Path("/tmp/test_project")
        path = determine_test_file_path(56, [], repo_root, framework_config=config)
        assert path.suffix == ".ts"
        assert ".spec.ts" in str(path)

    def test_t280_pytest_creates_test_py(self):
        """T280: scaffold_tests uses correct file extension for pytest."""
        # Without framework_config, should use default behavior
        repo_root = Path("/tmp/test_project")
        # Pass None for framework_config to use default pytest behavior
        path = determine_test_file_path(200, [], repo_root, framework_config=None)
        # Default behavior varies, but should not have .ts extension
        assert ".spec.ts" not in str(path)

    def test_jest_creates_test_ts(self):
        """Jest framework creates .test.ts files."""
        config = get_framework_config(TestFramework.JEST)
        repo_root = Path("/tmp/test_project")
        path = determine_test_file_path(100, [], repo_root, framework_config=config)
        assert ".test.ts" in str(path)

    def test_vitest_creates_test_ts(self):
        """Vitest framework creates .test.ts files."""
        config = get_framework_config(TestFramework.VITEST)
        repo_root = Path("/tmp/test_project")
        path = determine_test_file_path(100, [], repo_root, framework_config=config)
        assert ".test.ts" in str(path)


class TestGenerateTsTestFileContent:
    """Tests for generate_ts_test_file_content."""

    def test_playwright_content_has_correct_imports(self):
        """Playwright content includes @playwright/test import."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        scenarios = [
            {"id": "T010", "description": "Dashboard loads", "expected_behavior": "Page shows heading"},
        ]
        content = generate_ts_test_file_content(scenarios, config, issue_number=56)
        assert "@playwright/test" in content
        assert "test(" in content
        assert "Dashboard loads" in content

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_jest_content_has_correct_imports(self, mock_which):
        """Jest content includes @jest/globals import."""
        config = get_framework_config(TestFramework.JEST)
        scenarios = [
            {"id": "T010", "description": "formatDate works", "expected_behavior": "Returns string"},
        ]
        content = generate_ts_test_file_content(scenarios, config, issue_number=100)
        assert "@jest/globals" in content
        assert "describe(" in content
        assert "it(" in content
        assert "formatDate works" in content

    def test_pytest_raises_value_error(self):
        """Raises ValueError for pytest (not a TS framework)."""
        config = get_framework_config(TestFramework.PYTEST)
        with pytest.raises(ValueError, match="Cannot generate TS content"):
            generate_ts_test_file_content([], config, issue_number=200)

    def test_multiple_scenarios(self):
        """Multiple scenarios generate multiple test blocks."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        scenarios = [
            {"id": "T010", "description": "Test A", "expected_behavior": "Result A"},
            {"id": "T020", "description": "Test B", "expected_behavior": "Result B"},
            {"id": "T030", "description": "Test C", "expected_behavior": "Result C"},
        ]
        content = generate_ts_test_file_content(scenarios, config, issue_number=56)
        assert content.count("test(") == 3
```

### 6.22 `tests/unit/test_run_tests_node.py` (Add)

**Complete file contents:**

```python
"""Unit tests for the run_tests node.

Issue #381: Tests T290, T260 from LLD Section 10.0.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.nodes.run_tests import run_tests


@pytest.fixture
def valid_playwright_test_file(tmp_path):
    """Create a valid Playwright test file."""
    test_file = tmp_path / "tests" / "dashboard.spec.ts"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        "import { test, expect } from '@playwright/test';\n"
        "test('works', async ({ page }) => {\n"
        "  await expect(page).toBeTruthy();\n"
        "});\n"
    )
    return str(test_file)


@pytest.fixture
def valid_pytest_file(tmp_path):
    """Create a valid pytest file."""
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        "import pytest\n\n"
        "def test_example():\n"
        "    assert True\n"
    )
    return str(test_file)


class TestRunTestsNode:
    """Tests for run_tests() node function."""

    def test_no_test_files(self):
        """Returns error when no test files in state."""
        state = {"issue_number": 100, "test_files": [], "framework_config": None}
        result = run_tests(state)
        assert result["error_message"] == "No test files to run"

    def test_default_pytest_when_no_config(self, valid_pytest_file):
        """Falls back to pytest config when framework_config missing."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 1, "failed": 0, "skipped": 0, "errors": 0,
                "total": 1, "coverage_percent": 100.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "1 passed", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            }
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 200,
                "test_files": [valid_pytest_file],
                "framework_config": None,
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert result["error_message"] == ""
            assert result["test_run_result"]["passed"] == 1

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t290_playwright_validation(self, mock_which, valid_playwright_test_file):
        """T290: run_tests delegates to runner.validate_test_file for Playwright."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 1, "failed": 0, "skipped": 0, "errors": 0,
                "total": 1, "coverage_percent": 0.0,
                "coverage_type": CoverageType.SCENARIO,
                "raw_output": "{}", "exit_code": 0,
                "framework": TestFramework.PLAYWRIGHT,
            }
            mock_get_runner.return_value = mock_runner

            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": [valid_playwright_test_file],
                "framework_config": config,
                "repo_root": "/tmp",
            }
            result = run_tests(state)

            # Verify validate_test_file was called with the right file
            mock_runner.validate_test_file.assert_called_once()
            call_args = mock_runner.validate_test_file.call_args
            assert "dashboard.spec.ts" in call_args[0][0]

    def test_validation_errors_stop_execution(self, tmp_path):
        """When validation fails, tests are not run."""
        bad_file = tmp_path / "tests" / "bad.spec.ts"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("// no playwright import\n")

        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = [
                "Missing '@playwright/test' import"
            ]
            mock_get_runner.return_value = mock_runner

            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": [str(bad_file)],
                "framework_config": config,
                "repo_root": str(tmp_path),
            }
            result = run_tests(state)

            assert result["test_run_result"] is None
            assert len(result["validation_errors"]) > 0
            assert "validation failed" in result["error_message"]
            # run_tests should NOT have been called
            mock_runner.run_tests.assert_not_called()

    def test_environment_error_handled(self):
        """EnvironmentError (missing npx) is handled gracefully."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner",
            side_effect=EnvironmentError("npx not found on PATH"),
        ):
            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": ["tests/test.spec.ts"],
                "framework_config": config,
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert "npx not found" in result["error_message"]

    def test_t260_subprocess_timeout_handled(self, valid_pytest_file):
        """T260: Subprocess timeout handled gracefully."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 0, "failed": 0, "skipped": 0, "errors": 1,
                "total": 1, "coverage_percent": 0.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "Command timed out after 300s",
                "exit_code": -1,
                "framework": TestFramework.PYTEST,
            }
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 200,
                "test_files": [valid_pytest_file],
                "framework_config": get_framework_config(TestFramework.PYTEST),
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert result["test_run_result"]["exit_code"] == -1
            assert "timed out" in result["test_run_result"]["raw_output"]
```

### 6.23 `tests/unit/test_check_coverage_node.py` (Add)

**Complete file contents:**

```python
"""Unit tests for the check_coverage node.

Issue #381: Tests T210, T300, T310, T320 from LLD Section 10.0.
"""

from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.nodes.check_coverage import check_coverage


class TestScenarioCoverage:
    """Tests for scenario-based coverage (Playwright)."""

    def test_t210_scenario_coverage_math(self):
        """T210: compute_scenario_coverage calculates correctly."""
        # Tested indirectly through check_coverage node
        from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner
        from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner

        config = get_framework_config(TestFramework.PYTEST)
        runner = PytestRunner(config, "/tmp")

        # 38/38 = 100%
        result_full = {"passed": 38, "failed": 0}
        assert runner.compute_scenario_coverage(result_full, 38) == 1.0

        # 35/38 ≈ 92.1%
        result_partial = {"passed": 35, "failed": 3}
        cov = runner.compute_scenario_coverage(result_partial, 38)
        assert abs(cov - 0.9210526315789473) < 0.0001

        # 0/0 = 0.0 (no ZeroDivisionError)
        result_empty = {"passed": 0, "failed": 0}
        assert runner.compute_scenario_coverage(result_empty, 0) == 0.0

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t300_scenario_coverage_for_e2e(self, mock_which):
        """T300: check_coverage uses scenario coverage for e2e (38/38 = 100%)."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)

        with patch(
            "assemblyzero.workflows.testing.nodes.check_coverage.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.compute_scenario_coverage.return_value = 1.0
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 56,
                "test_run_result": {
                    "passed": 38, "failed": 0, "skipped": 0, "errors": 0,
                    "total": 38, "coverage_percent": 0.0,
                    "coverage_type": CoverageType.SCENARIO,
                    "raw_output": "", "exit_code": 0,
                    "framework": TestFramework.PLAYWRIGHT,
                },
                "framework_config": config,
                "total_scenarios": 38,
            }
            result = check_coverage(state)
            assert result["green"] is True
            assert result["iterate_reason"] == ""

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_scenario_coverage_below_target(self, mock_which):
        """Scenario coverage below target → not green."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)

        with patch(
            "assemblyzero.workflows.testing.nodes.check_coverage.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.compute_scenario_coverage.return_value = 0.80
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 56,
                "test_run_result": {
                    "passed": 30, "failed": 0, "skipped": 0, "errors": 0,
                    "total": 30, "coverage_percent": 0.0,
                    "coverage_type": CoverageType.SCENARIO,
                    "raw_output": "", "exit_code": 0,
                    "framework": TestFramework.PLAYWRIGHT,
                },
                "framework_config": config,
                "total_scenarios": 38,
            }
            result = check_coverage(state)
            assert result["green"] is False
            assert "Scenario coverage" in result["iterate_reason"]


class TestLineCoverage:
    """Tests for line-based coverage (pytest, Jest)."""

    def test_t310_line_coverage_for_pytest(self):
        """T310: check_coverage uses line coverage for pytest."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 15, "failed": 0, "skipped": 0, "errors": 0,
                "total": 15, "coverage_percent": 97.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is True

    def test_line_coverage_below_target(self):
        """Line coverage below target → not green."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 15, "failed": 0, "skipped": 0, "errors": 0,
                "total": 15, "coverage_percent": 72.5,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "Line coverage 72.5%" in result["iterate_reason"]
        assert "95.0%" in result["iterate_reason"]


class TestNoneCoverage:
    """Tests for coverage_type NONE."""

    def test_t320_none_coverage_skips_check(self):
        """T320: check_coverage with coverage_type NONE skips coverage check."""
        config = get_framework_config(TestFramework.PYTEST)
        config["coverage_type"] = CoverageType.NONE  # Override for test

        state = {
            "issue_number": 300,
            "test_run_result": {
                "passed": 10, "failed": 0, "skipped": 0, "errors": 0,
                "total": 10, "coverage_percent": 0.0,
                "coverage_type": CoverageType.NONE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is True


class TestFailureHandling:
    """Tests for test failure detection."""

    def test_failed_tests_not_green(self):
        """Failed tests → not green, regardless of coverage."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 12, "failed": 3, "skipped": 0, "errors": 0,
                "total": 15, "coverage_percent": 97.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 1,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "3 tests failed" in result["iterate_reason"]

    def test_errors_not_green(self):
        """Test errors → not green."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 10, "failed": 0, "skipped": 0, "errors": 2,
                "total": 12, "coverage_percent": 90.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 1,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "2 test errors" in result["iterate_reason"]

    def test_no_test_results(self):
        """Missing test results → not green."""
        state = {
            "issue_number": 200,
            "test_run_result": None,
            "framework_config": get_framework_config(TestFramework.PYTEST),
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "No test results" in result["iterate_reason"]

    def test_zero_scenarios_not_green(self):
        """Zero total scenarios for SCENARIO type → not green."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)

        state = {
            "issue_number": 56,
            "test_run_result": {
                "passed": 0, "failed": 0, "skipped": 0, "errors": 0,
                "total": 0, "coverage_percent": 0.0,
                "coverage_type": CoverageType.SCENARIO,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PLAYWRIGHT,
            },
            "framework_config": config,
            "total_scenarios": 0,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "No scenarios" in result["iterate_reason"]
```

## 7. Pattern References

### 7.1 Node Implementation Pattern

**File:** `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py` (lines 1-50)

```python
"""N1: Analyze Codebase node for Implementation Spec workflow.
...
"""
import logging
from typing import Any
...

logger = logging.getLogger(__name__)

def analyze_codebase(state: ImplementationSpecState) -> dict[str, Any]:
    """N1: Analyze the codebase for relevant patterns.
    ...
    """
    ...
```

**Relevance:** All new node files (`run_tests.py`, `check_coverage.py`) follow this same pattern: module docstring with issue reference, logging import, logger at module level, single function with `state -> dict[str, Any]` signature.

### 7.2 State Extension Pattern

**File:** `assemblyzero/workflows/testing/state.py`

**Relevance:** The existing `TestingWorkflowState` TypedDict should be used as the state type. New keys (`framework_config`, `test_run_result`, `total_scenarios`, `validation_errors`) are accessed via `.get()` with defaults for backward compatibility — the workflow state is a plain dict and new keys are optional.

### 7.3 Audit Logging Pattern

**File:** `assemblyzero/workflows/testing/nodes/scaffold_tests.py` (usage of `gate_log`, `log_workflow_execution`)

```python
from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
```

**Relevance:** New nodes must use the same audit functions for consistent logging. `gate_log()` for immediate output with node prefix, `log_workflow_execution()` for persistent audit trail.

### 7.4 Test Pattern

**File:** `tests/test_integration_workflow.py` (lines 1-80)

**Relevance:** Existing test file structure with `import pytest`, class-based test organization, and fixture usage. All new test files follow this pattern.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from enum import Enum` | stdlib | `framework_detector.py` |
| `from typing import TypedDict, Optional` | stdlib | `framework_detector.py` |
| `from abc import ABC, abstractmethod` | stdlib | `base_runner.py` |
| `import json` | stdlib | `framework_detector.py`, all runners |
| `import logging` | stdlib | All new files |
| `import os` | stdlib | `framework_detector.py` |
| `import re` | stdlib | `framework_detector.py`, `pytest_runner.py` |
| `import shutil` | stdlib | `playwright_runner.py`, `jest_runner.py` |
| `import subprocess` | stdlib | `base_runner.py` |
| `from pathlib import Path` | stdlib | `scaffold_tests.py` (already imported) |
| `from assemblyzero.workflows.testing.framework_detector import TestFramework, CoverageType, FrameworkConfig, TestRunResult` | internal | `runner_registry.py`, all runners, all nodes |
| `from assemblyzero.workflows.testing.runner_registry import get_framework_config, get_runner` | internal | `scaffold_tests.py`, `run_tests.py`, `check_coverage.py` |
| `from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner` | internal | `runner_registry.py`, `runners/__init__.py` |
| `from assemblyzero.workflows.testing.audit import gate_log, get_repo_root, log_workflow_execution` | internal (existing) | `run_tests.py`, `check_coverage.py`, `scaffold_tests.py` |
| `from assemblyzero.workflows.testing.state import TestingWorkflowState` | internal (existing) | `run_tests.py`, `check_coverage.py` |

**New Dependencies:** None. All imports are stdlib or internal modules.

## 9. Test Mapping

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with `.spec.ts` pattern | `TestFramework.PLAYWRIGHT` |
| T020 | `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with `.test.ts` and jest | `TestFramework.JEST` |
| T030 | `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with no indicators | `TestFramework.PYTEST` |
| T040 | `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with "Test Framework: Playwright" | `TestFramework.PLAYWRIGHT` |
| T050 | `detect_framework_from_project()` | `test_framework_detector.py` | Dir with `playwright.config.ts` | `TestFramework.PLAYWRIGHT` |
| T060 | `detect_framework_from_project()` | `test_framework_detector.py` | Dir with jest in package.json | `TestFramework.JEST` |
| T070 | `resolve_framework()` | `test_framework_detector.py` | LLD=Playwright, project=Jest | `TestFramework.PLAYWRIGHT` |
| T080 | `get_framework_config()` | `test_runner_registry.py` | `TestFramework.PLAYWRIGHT` | Config with npx playwright, .spec.ts, SCENARIO |
| T090 | `get_framework_config()` | `test_runner_registry.py` | `TestFramework.PYTEST` | Config with pytest, test_*.py, LINE |
| T100 | `get_runner()` | `test_runner_registry.py` | `TestFramework.PYTEST` | `PytestRunner` instance |
| T110 | `get_runner()` | `test_runner_registry.py` | `TestFramework.PLAYWRIGHT` | `PlaywrightRunner` instance |
| T120 | `PytestRunner.validate_test_file()` | `test_pytest_runner.py` | Valid Python test | `[]` |
| T130 | `PytestRunner.validate_test_file()` | `test_pytest_runner.py` | Python file, no imports | Error list |
| T140 | `PlaywrightRunner.validate_test_file()` | `test_playwright_runner.py` | Valid .spec.ts | `[]` |
| T150 | `PlaywrightRunner.validate_test_file()` | `test_playwright_runner.py` | .spec.ts missing import | Error list |
| T160 | `JestRunner.validate_test_file()` | `test_jest_runner.py` | Valid .test.ts | `[]` |
| T170 | `JestRunner.validate_test_file()` | `test_jest_runner.py` | .test.ts no describe/it | Error list |
| T180 | `PlaywrightRunner.parse_results()` | `test_playwright_runner.py` | Fixture JSON | Correct counts |
| T190 | `JestRunner.parse_results()` | `test_jest_runner.py` | Fixture JSON | Correct counts |
| T200 | `PytestRunner.parse_results()` | `test_pytest_runner.py` | pytest stdout | Correct counts + coverage |
| T210 | `compute_scenario_coverage()` | `test_check_coverage_node.py` | 35/38, 38/38, 0/0 | 92.1%, 100%, 0.0% |
| T220 | `PlaywrightRunner.run_tests()` | `test_playwright_runner.py` | Mocked subprocess | npx playwright test --reporter=json |
| T230 | `JestRunner.run_tests()` | `test_jest_runner.py` | Mocked subprocess | npx jest --json |
| T240 | `PytestRunner.run_tests()` | `test_pytest_runner.py` | Mocked subprocess | pytest --tb=short -q |
| T250 | `PlaywrightRunner.__init__()` | `test_playwright_runner.py` | npx missing | `EnvironmentError` |
| T260 | `run_tests()` node | `test_run_tests_node.py` | Timeout result | Graceful handling |
| T270 | `determine_test_file_path()` | `test_scaffold_tests_multifw.py` | Playwright config | `.spec.ts` path |
| T280 | `determine_test_file_path()` | `test_scaffold_tests_multifw.py` | No framework config | Not `.spec.ts` |
| T290 | `run_tests()` node | `test_run_tests_node.py` | Playwright state | runner.validate called |
| T300 | `check_coverage()` node | `test_check_coverage_node.py` | 38/38 SCENARIO | green=True |
| T310 | `check_coverage()` node | `test_check_coverage_node.py` | 97% LINE | green=True |
| T320 | `check_coverage()` node | `test_check_coverage_node.py` | NONE type | green=True |
| T330 | Full chain | `test_run_tests_node.py` + `test_check_coverage_node.py` | Mocked full flow | All nodes succeed |
| T340 | Full chain | `test_check_coverage_node.py` | Standard pytest state | Backward compat |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All node functions return `dict[str, Any]` with an `error_message` key. Empty string means success. Non-empty means the node encountered an issue but didn't raise an exception. This is consistent with the existing testing workflow pattern.

For runner methods, errors are returned as part of `TestRunResult` (via `exit_code` and `raw_output`). `EnvironmentError` is the only exception raised from runner constructors.

### 10.2 Logging Convention

Use `logging.getLogger(__name__)` at module level. Use `gate_log()` from `assemblyzero.workflows.testing.audit` for node-level output with bracket prefix:

```python
gate_log(f"[RunTests] Starting test execution for issue #{issue_number}")
gate_log(f"[CheckCoverage] GREEN: Line coverage 97.0% >= 95.0%")
```

### 10.3 Constants

| Constant | Value | Location | Rationale |
|----------|-------|----------|-----------|
| `DEFAULT_TIMEOUT` | `300` | `base_runner.py` | 5-minute subprocess timeout prevents infinite hangs |
| Coverage target (pytest) | `0.95` | `runner_registry.py` | 95% line coverage standard |
| Coverage target (playwright) | `1.0` | `runner_registry.py` | 100% scenario pass rate for e2e |
| Coverage target (jest/vitest) | `0.95` | `runner_registry.py` | 95% line coverage standard |

### 10.4 Backward Compatibility

The `scaffold_tests()` function modification is designed to be backward compatible:
- If `framework_config` is not in state, behavior is 100% unchanged
- If `framework_config.framework` is `PYTEST`, behavior is 100% unchanged
- Only when a non-Python framework is detected does the new code path execute
- The new `run_tests` and `check_coverage` nodes are added independently and do not replace existing nodes — they need to be wired into the LangGraph state machine separately

### 10.5 State Dict Key Additions

New optional keys that may appear in the workflow state dict:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `framework_config` | `FrameworkConfig` | `None` → defaults to PYTEST | Framework configuration |
| `test_run_result` | `TestRunResult` | `None` | Unified test results |
| `total_scenarios` | `int` | `0` | Total scenario count for e2e coverage |
| `validation_errors` | `list[str]` | `[]` | Test file validation errors |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — `scaffold_tests.py` covered
- [x] Every data structure has a concrete JSON/YAML example (Section 4) — TestFramework, CoverageType, FrameworkConfig (3 examples), TestRunResult (2 examples)
- [x] Every function has input/output examples with realistic values (Section 5) — 23 function specs with examples
- [x] Change instructions are diff-level specific (Section 6) — diffs for scaffold_tests.py, complete files for all Add files
- [x] Pattern references include file:line and are verified to exist (Section 7) — 4 patterns referenced
- [x] All imports are listed and verified (Section 8) — 16 import entries
- [x] Test mapping covers all LLD test scenarios (Section 9) — all 34 test IDs mapped

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #381 |
| Verdict | DRAFT |
| Date | 2026-02-25 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #381 |
| Verdict | APPROVED |
| Date | 2026-02-25 |
| Iterations | 0 |
| Finalized | 2026-02-25T09:10:47Z |

### Review Feedback Summary

Approved with suggestions:
- **Error Handling**: In `PlaywrightRunner.parse_results`, the fallback logic (`_fallback_result`) sets `passed=0, failed=1` if parsing fails but the exit code is non-zero. Ensure that `raw_output` is logged or available in the UI so the user can debug *why* the JSON report generation failed (e.g., syntax error in config file vs. actual test failure).
- **Import Ordering**: In `scaffold_tests.py`, ensure the new imports are placed to avoid circular dependencies if `fra...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
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
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_framework_detector.py
"""Unit tests for framework detection.

Issue #381: Tests T010-T070 from LLD Section 10.0.
"""

import json
import tempfile
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
    detect_framework_from_lld,
    detect_framework_from_project,
    resolve_framework,
)


class TestDetectFrameworkFromLLD:
    """Tests for detect_framework_from_lld()."""

    def test_t010_detects_playwright_from_spec_ts(self):
        """T010: detect_framework_from_lld identifies Playwright from .spec.ts."""
        lld = """## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `tests/dashboard.spec.ts` | Add |
"""
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_t020_detects_jest_from_test_ts(self):
        """T020: detect_framework_from_lld identifies Jest from .test.ts."""
        lld = """## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `tests/utils.test.ts` | Add |
"""
        assert detect_framework_from_lld(lld) == TestFramework.JEST

    def test_t030_defaults_to_pytest(self):
        """T030: detect_framework_from_lld defaults to pytest."""
        lld = """## 2.1 Files Changed
| File | Change Type |
|------|-------------|
| `src/pipeline.py` | Add |
"""
        assert detect_framework_from_lld(lld) == TestFramework.PYTEST

    def test_t040_explicit_playwright_declaration(self):
        """T040: detect_framework_from_lld handles explicit declaration."""
        lld = """## 10. Verification & Testing
Test Framework: Playwright
"""
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_explicit_jest_declaration(self):
        """Detect Jest from explicit declaration."""
        lld = "Test Framework: Jest\nSome other content."
        assert detect_framework_from_lld(lld) == TestFramework.JEST

    def test_explicit_vitest_declaration(self):
        """Detect Vitest from explicit declaration."""
        lld = "Test Framework: Vitest"
        assert detect_framework_from_lld(lld) == TestFramework.VITEST

    def test_explicit_pytest_declaration(self):
        """Detect pytest from explicit declaration."""
        lld = "Test Framework: pytest"
        assert detect_framework_from_lld(lld) == TestFramework.PYTEST

    def test_empty_lld_defaults_to_pytest(self):
        """Empty LLD returns pytest."""
        assert detect_framework_from_lld("") == TestFramework.PYTEST

    def test_playwright_keyword_detection(self):
        """Detect Playwright from @playwright/test keyword."""
        lld = "We use @playwright/test for e2e testing."
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_npx_playwright_command(self):
        """Detect Playwright from npx command in LLD."""
        lld = "Run `npx playwright test` to execute."
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT

    def test_spec_js_detected_as_playwright(self):
        """Detect Playwright from .spec.js file pattern."""
        lld = "| `tests/app.spec.js` | Add |"
        assert detect_framework_from_lld(lld) == TestFramework.PLAYWRIGHT


class TestDetectFrameworkFromProject:
    """Tests for detect_framework_from_project()."""

    def test_t050_playwright_config_file(self):
        """T050: detect_framework_from_project finds playwright.config.ts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "playwright.config.ts").touch()
            assert detect_framework_from_project(tmpdir) == TestFramework.PLAYWRIGHT

    def test_t060_jest_in_package_json(self):
        """T060: detect_framework_from_project finds jest in package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"scripts": {"test": "jest --coverage"}}
            Path(tmpdir, "package.json").write_text(json.dumps(pkg))
            assert detect_framework_from_project(tmpdir) == TestFramework.JEST

    def test_vitest_in_package_json(self):
        """Detect Vitest from package.json scripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"scripts": {"test": "vitest run"}}
            Path(tmpdir, "package.json").write_text(json.dumps(pkg))
            assert detect_framework_from_project(tmpdir) == TestFramework.VITEST

    def test_jest_config_file(self):
        """Detect Jest from jest.config.ts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "jest.config.ts").touch()
            assert detect_framework_from_project(tmpdir) == TestFramework.JEST

    def test_vitest_config_file(self):
        """Detect Vitest from vitest.config.ts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "vitest.config.ts").touch()
            assert detect_framework_from_project(tmpdir) == TestFramework.VITEST

    def test_pyproject_toml_pytest(self):
        """Detect pytest from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
            assert detect_framework_from_project(tmpdir) == TestFramework.PYTEST

    def test_nonexistent_directory(self):
        """Non-existent directory returns None."""
        assert detect_framework_from_project("/nonexistent/path/xyz") is None

    def test_empty_directory(self):
        """Empty directory returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert detect_framework_from_project(tmpdir) is None

    def test_ambiguous_multiple_configs(self):
        """Multiple config files returns None (ambiguous)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "playwright.config.ts").touch()
            Path(tmpdir, "jest.config.ts").touch()
            assert detect_framework_from_project(tmpdir) is None

    def test_invalid_package_json(self):
        """Malformed package.json is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package.json").write_text("not valid json")
            assert detect_framework_from_project(tmpdir) is None


class TestResolveFramework:
    """Tests for resolve_framework()."""

    def test_t070_lld_overrides_project(self):
        """T070: LLD overrides project detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "jest.config.ts").touch()
            lld = "Test Framework: Playwright"
            assert resolve_framework(lld, tmpdir) == TestFramework.PLAYWRIGHT

    def test_project_fallback_when_lld_default(self):
        """When LLD detects default pytest, project files can override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "playwright.config.ts").touch()
            lld = "Some generic LLD without framework indicators."
            assert resolve_framework(lld, tmpdir) == TestFramework.PLAYWRIGHT

    def test_both_default_returns_pytest(self):
        """When both LLD and project have no indicators, return pytest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert resolve_framework("No indicators here.", tmpdir) == TestFramework.PYTEST

    def test_empty_project_root(self):
        """Empty project root skips project detection."""
        lld = "Test Framework: Jest"
        assert resolve_framework(lld, "") == TestFramework.JEST

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_runner_registry.py
"""Unit tests for runner registry.

Issue #381: Tests T080-T110 from LLD Section 10.0.
"""

import pytest
from unittest.mock import patch

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import (
    get_framework_config,
    get_runner,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner
from assemblyzero.workflows.testing.runners.playwright_runner import PlaywrightRunner
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner


class TestGetFrameworkConfig:
    """Tests for get_framework_config()."""

    def test_t080_playwright_config(self):
        """T080: get_framework_config returns correct config for PLAYWRIGHT."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        assert config["framework"] == TestFramework.PLAYWRIGHT
        assert config["test_runner_command"] == "npx playwright test"
        assert config["test_file_pattern"] == "*.spec.ts"
        assert config["test_file_extension"] == ".spec.ts"
        assert config["coverage_type"] == CoverageType.SCENARIO
        assert config["coverage_target"] == 1.0

    def test_t090_pytest_config(self):
        """T090: get_framework_config returns correct config for PYTEST."""
        config = get_framework_config(TestFramework.PYTEST)
        assert config["framework"] == TestFramework.PYTEST
        assert config["test_runner_command"] == "pytest"
        assert config["test_file_pattern"] == "test_*.py"
        assert config["test_file_extension"] == ".py"
        assert config["coverage_type"] == CoverageType.LINE
        assert config["coverage_target"] == 0.95

    def test_jest_config(self):
        """get_framework_config returns correct config for JEST."""
        config = get_framework_config(TestFramework.JEST)
        assert config["framework"] == TestFramework.JEST
        assert config["test_runner_command"] == "npx jest"
        assert config["test_file_pattern"] == "*.test.ts"
        assert config["coverage_type"] == CoverageType.LINE

    def test_vitest_config(self):
        """get_framework_config returns correct config for VITEST."""
        config = get_framework_config(TestFramework.VITEST)
        assert config["framework"] == TestFramework.VITEST
        assert config["test_runner_command"] == "npx vitest run"

    def test_config_is_copy(self):
        """Returned config should be a copy (not mutable registry)."""
        config1 = get_framework_config(TestFramework.PYTEST)
        config2 = get_framework_config(TestFramework.PYTEST)
        config1["coverage_target"] = 0.5
        assert config2["coverage_target"] == 0.95  # Unaffected


class TestGetRunner:
    """Tests for get_runner()."""

    def test_t100_pytest_runner(self):
        """T100: get_runner returns PytestRunner for PYTEST."""
        runner = get_runner(TestFramework.PYTEST)
        assert isinstance(runner, PytestRunner)
        assert isinstance(runner, BaseTestRunner)

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t110_playwright_runner(self, mock_which):
        """T110: get_runner returns PlaywrightRunner for PLAYWRIGHT."""
        runner = get_runner(TestFramework.PLAYWRIGHT)
        assert isinstance(runner, PlaywrightRunner)
        assert isinstance(runner, BaseTestRunner)

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_jest_runner(self, mock_which):
        """get_runner returns JestRunner for JEST."""
        runner = get_runner(TestFramework.JEST)
        assert isinstance(runner, JestRunner)

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_vitest_runner(self, mock_which):
        """get_runner returns JestRunner for VITEST (shared runner)."""
        runner = get_runner(TestFramework.VITEST)
        assert isinstance(runner, JestRunner)

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_pytest_runner.py
"""Unit tests for PytestRunner.

Issue #381: Tests T120, T130, T200, T240 from LLD Section 10.0.
"""

from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner


@pytest.fixture
def pytest_runner():
    """Create a PytestRunner with default config."""
    config = get_framework_config(TestFramework.PYTEST)
    return PytestRunner(config, project_root="/tmp/test_project")


class TestPytestRunnerValidation:
    """Tests for PytestRunner.validate_test_file()."""

    def test_t120_valid_python_test(self, pytest_runner):
        """T120: PytestRunner.validate_test_file accepts valid Python test."""
        content = """import pytest
from mymodule import my_function

def test_my_function():
    assert my_function(42) == 84
"""
        errors = pytest_runner.validate_test_file("tests/test_example.py", content)
        assert errors == []

    def test_t130_missing_imports(self, pytest_runner):
        """T130: PytestRunner.validate_test_file rejects missing imports."""
        content = """def test_something():
    assert True
"""
        errors = pytest_runner.validate_test_file("tests/test_bad.py", content)
        assert any("No import statements" in e for e in errors)

    def test_missing_test_functions(self, pytest_runner):
        """Reject file with no test_ functions."""
        content = """import pytest

def helper():
    return 42
"""
        errors = pytest_runner.validate_test_file("tests/test_bad.py", content)
        assert any("No test functions" in e for e in errors)

    def test_empty_file(self, pytest_runner):
        """Reject empty test file."""
        errors = pytest_runner.validate_test_file("tests/test_empty.py", "")
        assert any("Empty test file" in e for e in errors)

    def test_class_based_tests_accepted(self, pytest_runner):
        """Accept class-based test style (class TestXxx)."""
        content = """import pytest

class TestMyFeature:
    def test_something(self):
        assert True
"""
        errors = pytest_runner.validate_test_file("tests/test_class.py", content)
        assert errors == []


class TestPytestRunnerParseResults:
    """Tests for PytestRunner.parse_results()."""

    def test_t200_parse_pytest_output(self, pytest_runner):
        """T200: PytestRunner.parse_results handles pytest output."""
        output = """tests/test_example.py ..F.s
============ 3 passed, 1 failed, 1 skipped in 0.25s ============
TOTAL    150     12    92%
"""
        result = pytest_runner.parse_results(output, exit_code=1)
        assert result["passed"] == 3
        assert result["failed"] == 1
        assert result["skipped"] == 1
        assert result["total"] == 5
        assert result["coverage_percent"] == 92.0
        assert result["coverage_type"] == CoverageType.LINE
        assert result["framework"] == TestFramework.PYTEST
        assert result["exit_code"] == 1

    def test_parse_all_passing(self, pytest_runner):
        """Parse all-passing output."""
        output = "10 passed in 1.5s"
        result = pytest_runner.parse_results(output, exit_code=0)
        assert result["passed"] == 10
        assert result["failed"] == 0
        assert result["exit_code"] == 0

    def test_parse_no_coverage(self, pytest_runner):
        """Parse output without coverage info."""
        output = "5 passed in 0.5s"
        result = pytest_runner.parse_results(output, exit_code=0)
        assert result["coverage_percent"] == 0.0


class TestPytestRunnerRunTests:
    """Tests for PytestRunner.run_tests()."""

    @patch.object(PytestRunner, "_run_subprocess")
    def test_t240_invokes_correct_command(self, mock_subprocess, pytest_runner):
        """T240: PytestRunner.run_tests invokes correct command."""
        mock_subprocess.return_value = ("5 passed in 0.5s", 0)
        pytest_runner.run_tests(test_paths=["tests/test_example.py"])

        args, kwargs = mock_subprocess.call_args
        command = args[0]
        assert "pytest" in command
        assert "--tb=short" in command
        assert "-q" in command
        assert "tests/test_example.py" in command

    @patch.object(PytestRunner, "_run_subprocess")
    def test_extra_args_passed(self, mock_subprocess, pytest_runner):
        """Extra args are appended to the command."""
        mock_subprocess.return_value = ("5 passed", 0)
        pytest_runner.run_tests(extra_args=["--cov=mymodule"])

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "--cov=mymodule" in command


class TestPytestRunnerScaffold:
    """Tests for PytestRunner.get_scaffold_imports()."""

    def test_scaffold_imports(self, pytest_runner):
        """Returns correct pytest import."""
        assert pytest_runner.get_scaffold_imports() == "import pytest"

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_playwright_runner.py
"""Unit tests for PlaywrightRunner.

Issue #381: Tests T140, T150, T180, T220, T250 from LLD Section 10.0.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.playwright_runner import PlaywrightRunner


@pytest.fixture
def playwright_runner():
    """Create a PlaywrightRunner with mocked npx availability."""
    with patch("shutil.which", return_value="/usr/bin/npx"):
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        return PlaywrightRunner(config, project_root="/tmp/test_project")


class TestPlaywrightRunnerValidation:
    """Tests for PlaywrightRunner.validate_test_file()."""

    def test_t140_valid_spec_ts(self, playwright_runner):
        """T140: PlaywrightRunner.validate_test_file accepts valid .spec.ts."""
        content = """import { test, expect } from '@playwright/test';

test('loads dashboard', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.locator('h1')).toHaveText('Dashboard');
});
"""
        errors = playwright_runner.validate_test_file("tests/dashboard.spec.ts", content)
        assert errors == []

    def test_t150_missing_playwright_import(self, playwright_runner):
        """T150: PlaywrightRunner.validate_test_file rejects missing imports."""
        content = """test('loads dashboard', async ({ page }) => {
  await page.goto('/dashboard');
});
"""
        errors = playwright_runner.validate_test_file("tests/dashboard.spec.ts", content)
        assert any("@playwright/test" in e for e in errors)

    def test_missing_test_calls(self, playwright_runner):
        """Reject file with no test() calls."""
        content = """import { test, expect } from '@playwright/test';

const x = 5;
console.log(x);
"""
        errors = playwright_runner.validate_test_file("tests/bad.spec.ts", content)
        assert any("No test() calls" in e for e in errors)

    def test_empty_file(self, playwright_runner):
        """Reject empty file."""
        errors = playwright_runner.validate_test_file("tests/empty.spec.ts", "")
        assert any("Empty test file" in e for e in errors)


class TestPlaywrightRunnerParseResults:
    """Tests for PlaywrightRunner.parse_results()."""

    def test_t180_parse_json_report(self, playwright_runner):
        """T180: PlaywrightRunner.parse_results handles JSON report."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "playwright_json_report.json"
        with open(fixture_path) as f:
            raw_output = f.read()

        result = playwright_runner.parse_results(raw_output, exit_code=1)
        assert result["passed"] == 2
        assert result["failed"] == 1
        assert result["skipped"] == 1
        assert result["total"] == 4
        assert result["coverage_type"] == CoverageType.SCENARIO
        assert result["framework"] == TestFramework.PLAYWRIGHT
        assert result["exit_code"] == 1

    def test_parse_all_passing(self, playwright_runner):
        """Parse all-passing Playwright report."""
        report = {
            "config": {},
            "suites": [{
                "title": "Tests",
                "specs": [
                    {"title": "t1", "tests": [{"results": [{"status": "passed"}]}]},
                    {"title": "t2", "tests": [{"results": [{"status": "passed"}]}]},
                ],
                "suites": [],
            }],
        }
        result = playwright_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert result["total"] == 2

    def test_parse_invalid_json(self, playwright_runner):
        """Fallback when JSON is invalid."""
        result = playwright_runner.parse_results("not json at all", exit_code=1)
        assert result["failed"] >= 1
        assert result["errors"] >= 1

    def test_parse_nested_suites(self, playwright_runner):
        """Parse nested suite structure."""
        report = {
            "config": {},
            "suites": [{
                "title": "Root",
                "specs": [],
                "suites": [{
                    "title": "Nested",
                    "specs": [
                        {"title": "t1", "tests": [{"results": [{"status": "passed"}]}]},
                    ],
                    "suites": [],
                }],
            }],
        }
        result = playwright_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["passed"] == 1
        assert result["total"] == 1


class TestPlaywrightRunnerRunTests:
    """Tests for PlaywrightRunner.run_tests()."""

    @patch.object(PlaywrightRunner, "_run_subprocess")
    def test_t220_invokes_correct_command(self, mock_subprocess, playwright_runner):
        """T220: PlaywrightRunner.run_tests invokes correct command."""
        mock_subprocess.return_value = ('{"config":{},"suites":[]}', 0)
        playwright_runner.run_tests(test_paths=["tests/dashboard.spec.ts"])

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "npx" in command
        assert "playwright" in command
        assert "test" in command
        assert "--reporter=json" in command
        assert "tests/dashboard.spec.ts" in command


class TestPlaywrightRunnerEnvironment:
    """Tests for PlaywrightRunner environment checks."""

    def test_t250_missing_npx(self):
        """T250: Runner raises EnvironmentError if npx not found."""
        with patch("shutil.which", return_value=None):
            config = get_framework_config(TestFramework.PLAYWRIGHT)
            with pytest.raises(EnvironmentError, match="npx not found"):
                PlaywrightRunner(config, "/tmp/test")


class TestPlaywrightRunnerScaffold:
    """Tests for PlaywrightRunner.get_scaffold_imports()."""

    def test_scaffold_imports(self, playwright_runner):
        """Returns correct Playwright import."""
        imports = playwright_runner.get_scaffold_imports()
        assert "@playwright/test" in imports
        assert "test" in imports
        assert "expect" in imports

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_jest_runner.py
"""Unit tests for JestRunner.

Issue #381: Tests T160, T170, T190, T230 from LLD Section 10.0.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner


@pytest.fixture
def jest_runner():
    """Create a JestRunner with mocked npx availability."""
    with patch("shutil.which", return_value="/usr/bin/npx"):
        config = get_framework_config(TestFramework.JEST)
        return JestRunner(config, project_root="/tmp/test_project")


@pytest.fixture
def vitest_runner():
    """Create a JestRunner for Vitest with mocked npx availability."""
    with patch("shutil.which", return_value="/usr/bin/npx"):
        config = get_framework_config(TestFramework.VITEST)
        return JestRunner(config, project_root="/tmp/test_project")


class TestJestRunnerValidation:
    """Tests for JestRunner.validate_test_file()."""

    def test_t160_valid_test_ts(self, jest_runner):
        """T160: JestRunner.validate_test_file accepts valid .test.ts."""
        content = """describe('utils', () => {
  it('formats date correctly', () => {
    expect(formatDate(new Date())).toBeDefined();
  });
});
"""
        errors = jest_runner.validate_test_file("tests/utils.test.ts", content)
        assert errors == []

    def test_t170_no_describe_it(self, jest_runner):
        """T170: JestRunner.validate_test_file rejects no describe/it."""
        content = """const x = 5;
console.log(x);
"""
        errors = jest_runner.validate_test_file("tests/utils.test.ts", content)
        assert any("No test structure" in e for e in errors)

    def test_test_function_accepted(self, jest_runner):
        """Accept test() function style (without describe)."""
        content = """test('works', () => {
  expect(true).toBe(true);
});
"""
        errors = jest_runner.validate_test_file("tests/simple.test.ts", content)
        assert errors == []

    def test_empty_file(self, jest_runner):
        """Reject empty file."""
        errors = jest_runner.validate_test_file("tests/empty.test.ts", "")
        assert any("Empty test file" in e for e in errors)


class TestJestRunnerParseResults:
    """Tests for JestRunner.parse_results()."""

    def test_t190_parse_json_report(self, jest_runner):
        """T190: JestRunner.parse_results handles JSON report."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "jest_json_report.json"
        with open(fixture_path) as f:
            raw_output = f.read()

        result = jest_runner.parse_results(raw_output, exit_code=1)
        assert result["passed"] == 8
        assert result["failed"] == 2
        assert result["skipped"] == 1
        assert result["total"] == 11
        assert result["coverage_type"] == CoverageType.LINE
        assert result["framework"] == TestFramework.JEST
        assert result["exit_code"] == 1

    def test_parse_all_passing(self, jest_runner):
        """Parse all-passing Jest report."""
        report = {
            "success": True,
            "numPassedTests": 5,
            "numFailedTests": 0,
            "numPendingTests": 0,
            "numTotalTests": 5,
        }
        result = jest_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["passed"] == 5
        assert result["failed"] == 0
        assert result["total"] == 5

    def test_parse_invalid_json(self, jest_runner):
        """Fallback when JSON is invalid."""
        result = jest_runner.parse_results("not json", exit_code=1)
        assert result["failed"] >= 1

    def test_parse_with_coverage_map(self, jest_runner):
        """Parse report with coverage data."""
        report = {
            "success": True,
            "numPassedTests": 3,
            "numFailedTests": 0,
            "numPendingTests": 0,
            "numTotalTests": 3,
            "coverageMap": {
                "src/utils.ts": {
                    "statementMap": {"0": {}, "1": {}, "2": {}, "3": {}},
                    "s": {"0": 1, "1": 1, "2": 0, "3": 1},
                }
            },
        }
        result = jest_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["coverage_percent"] == 75.0  # 3/4 statements covered


class TestJestRunnerRunTests:
    """Tests for JestRunner.run_tests()."""

    @patch.object(JestRunner, "_run_subprocess")
    def test_t230_invokes_correct_command(self, mock_subprocess, jest_runner):
        """T230: JestRunner.run_tests invokes correct command."""
        mock_subprocess.return_value = ('{"success":true,"numPassedTests":1,"numFailedTests":0,"numPendingTests":0,"numTotalTests":1}', 0)
        jest_runner.run_tests(test_paths=["tests/utils.test.ts"])

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "npx" in command
        assert "jest" in command
        assert "--json" in command
        assert "tests/utils.test.ts" in command

    @patch.object(JestRunner, "_run_subprocess")
    def test_vitest_invokes_correct_command(self, mock_subprocess, vitest_runner):
        """Vitest runner uses vitest run --reporter=json."""
        mock_subprocess.return_value = ('{"success":true,"numPassedTests":1,"numFailedTests":0,"numPendingTests":0,"numTotalTests":1}', 0)
        vitest_runner.run_tests()

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "npx" in command
        assert "vitest" in command
        assert "run" in command
        assert "--reporter=json" in command


class TestJestRunnerEnvironment:
    """Tests for JestRunner environment checks."""

    def test_missing_npx(self):
        """Runner raises EnvironmentError if npx not found."""
        with patch("shutil.which", return_value=None):
            config = get_framework_config(TestFramework.JEST)
            with pytest.raises(EnvironmentError, match="npx not found"):
                JestRunner(config, "/tmp/test")


class TestJestRunnerScaffold:
    """Tests for JestRunner.get_scaffold_imports()."""

    def test_jest_imports(self, jest_runner):
        """Returns correct Jest import."""
        imports = jest_runner.get_scaffold_imports()
        assert "@jest/globals" in imports

    def test_vitest_imports(self, vitest_runner):
        """Returns correct Vitest import."""
        imports = vitest_runner.get_scaffold_imports()
        assert "vitest" in imports

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_scaffold_tests_multifw.py
"""Unit tests for multi-framework scaffolding.

Issue #381: Tests T270, T280 from LLD Section 10.0.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.nodes.scaffold_tests import (
    determine_test_file_path,
    generate_ts_test_file_content,
)


class TestDetermineTestFilePath:
    """Tests for determine_test_file_path with framework config."""

    def test_t270_playwright_creates_spec_ts(self):
        """T270: scaffold_tests uses correct file extension for Playwright."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        repo_root = Path("/tmp/test_project")
        path = determine_test_file_path(56, [], repo_root, framework_config=config)
        assert path.suffix == ".ts"
        assert ".spec.ts" in str(path)

    def test_t280_pytest_creates_test_py(self):
        """T280: scaffold_tests uses correct file extension for pytest."""
        # Without framework_config, should use default behavior
        repo_root = Path("/tmp/test_project")
        # Pass None for framework_config to use default pytest behavior
        path = determine_test_file_path(200, [], repo_root, framework_config=None)
        # Default behavior varies, but should not have .ts extension
        assert ".spec.ts" not in str(path)

    def test_jest_creates_test_ts(self):
        """Jest framework creates .test.ts files."""
        config = get_framework_config(TestFramework.JEST)
        repo_root = Path("/tmp/test_project")
        path = determine_test_file_path(100, [], repo_root, framework_config=config)
        assert ".test.ts" in str(path)

    def test_vitest_creates_test_ts(self):
        """Vitest framework creates .test.ts files."""
        config = get_framework_config(TestFramework.VITEST)
        repo_root = Path("/tmp/test_project")
        path = determine_test_file_path(100, [], repo_root, framework_config=config)
        assert ".test.ts" in str(path)


class TestGenerateTsTestFileContent:
    """Tests for generate_ts_test_file_content."""

    def test_playwright_content_has_correct_imports(self):
        """Playwright content includes @playwright/test import."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        scenarios = [
            {"id": "T010", "description": "Dashboard loads", "expected_behavior": "Page shows heading"},
        ]
        content = generate_ts_test_file_content(scenarios, config, issue_number=56)
        assert "@playwright/test" in content
        assert "test(" in content
        assert "Dashboard loads" in content

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_jest_content_has_correct_imports(self, mock_which):
        """Jest content includes @jest/globals import."""
        config = get_framework_config(TestFramework.JEST)
        scenarios = [
            {"id": "T010", "description": "formatDate works", "expected_behavior": "Returns string"},
        ]
        content = generate_ts_test_file_content(scenarios, config, issue_number=100)
        assert "@jest/globals" in content
        assert "describe(" in content
        assert "it(" in content
        assert "formatDate works" in content

    def test_pytest_raises_value_error(self):
        """Raises ValueError for pytest (not a TS framework)."""
        config = get_framework_config(TestFramework.PYTEST)
        with pytest.raises(ValueError, match="Cannot generate TS content"):
            generate_ts_test_file_content([], config, issue_number=200)

    def test_multiple_scenarios(self):
        """Multiple scenarios generate multiple test blocks."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        scenarios = [
            {"id": "T010", "description": "Test A", "expected_behavior": "Result A"},
            {"id": "T020", "description": "Test B", "expected_behavior": "Result B"},
            {"id": "T030", "description": "Test C", "expected_behavior": "Result C"},
        ]
        content = generate_ts_test_file_content(scenarios, config, issue_number=56)
        assert content.count("test(") == 3

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_run_tests_node.py
"""Unit tests for the run_tests node.

Issue #381: Tests T290, T260 from LLD Section 10.0.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.nodes.run_tests import run_tests


@pytest.fixture
def valid_playwright_test_file(tmp_path):
    """Create a valid Playwright test file."""
    test_file = tmp_path / "tests" / "dashboard.spec.ts"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        "import { test, expect } from '@playwright/test';\n"
        "test('works', async ({ page }) => {\n"
        "  await expect(page).toBeTruthy();\n"
        "});\n"
    )
    return str(test_file)


@pytest.fixture
def valid_pytest_file(tmp_path):
    """Create a valid pytest file."""
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        "import pytest\n\n"
        "def test_example():\n"
        "    assert True\n"
    )
    return str(test_file)


class TestRunTestsNode:
    """Tests for run_tests() node function."""

    def test_no_test_files(self):
        """Returns error when no test files in state."""
        state = {"issue_number": 100, "test_files": [], "framework_config": None}
        result = run_tests(state)
        assert result["error_message"] == "No test files to run"

    def test_default_pytest_when_no_config(self, valid_pytest_file):
        """Falls back to pytest config when framework_config missing."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 1, "failed": 0, "skipped": 0, "errors": 0,
                "total": 1, "coverage_percent": 100.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "1 passed", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            }
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 200,
                "test_files": [valid_pytest_file],
                "framework_config": None,
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert result["error_message"] == ""
            assert result["test_run_result"]["passed"] == 1

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t290_playwright_validation(self, mock_which, valid_playwright_test_file):
        """T290: run_tests delegates to runner.validate_test_file for Playwright."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 1, "failed": 0, "skipped": 0, "errors": 0,
                "total": 1, "coverage_percent": 0.0,
                "coverage_type": CoverageType.SCENARIO,
                "raw_output": "{}", "exit_code": 0,
                "framework": TestFramework.PLAYWRIGHT,
            }
            mock_get_runner.return_value = mock_runner

            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": [valid_playwright_test_file],
                "framework_config": config,
                "repo_root": "/tmp",
            }
            result = run_tests(state)

            # Verify validate_test_file was called with the right file
            mock_runner.validate_test_file.assert_called_once()
            call_args = mock_runner.validate_test_file.call_args
            assert "dashboard.spec.ts" in call_args[0][0]

    def test_validation_errors_stop_execution(self, tmp_path):
        """When validation fails, tests are not run."""
        bad_file = tmp_path / "tests" / "bad.spec.ts"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("// no playwright import\n")

        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = [
                "Missing '@playwright/test' import"
            ]
            mock_get_runner.return_value = mock_runner

            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": [str(bad_file)],
                "framework_config": config,
                "repo_root": str(tmp_path),
            }
            result = run_tests(state)

            assert result["test_run_result"] is None
            assert len(result["validation_errors"]) > 0
            assert "validation failed" in result["error_message"]
            # run_tests should NOT have been called
            mock_runner.run_tests.assert_not_called()

    def test_environment_error_handled(self):
        """EnvironmentError (missing npx) is handled gracefully."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner",
            side_effect=EnvironmentError("npx not found on PATH"),
        ):
            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": ["tests/test.spec.ts"],
                "framework_config": config,
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert "npx not found" in result["error_message"]

    def test_t260_subprocess_timeout_handled(self, valid_pytest_file):
        """T260: Subprocess timeout handled gracefully."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 0, "failed": 0, "skipped": 0, "errors": 1,
                "total": 1, "coverage_percent": 0.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "Command timed out after 300s",
                "exit_code": -1,
                "framework": TestFramework.PYTEST,
            }
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 200,
                "test_files": [valid_pytest_file],
                "framework_config": get_framework_config(TestFramework.PYTEST),
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert result["test_run_result"]["exit_code"] == -1
            assert "timed out" in result["test_run_result"]["raw_output"]

    def test_unreadable_test_file(self, tmp_path):
        """Non-existent test file produces validation error."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_get_runner.return_value = mock_runner

            config = get_framework_config(TestFramework.PYTEST)
            state = {
                "issue_number": 200,
                "test_files": [str(tmp_path / "nonexistent_test.py")],
                "framework_config": config,
                "repo_root": str(tmp_path),
            }
            result = run_tests(state)
            assert result["test_run_result"] is None
            assert len(result["validation_errors"]) > 0
            assert "Cannot read test file" in result["validation_errors"][0]

    def test_runner_exception_handled(self, valid_pytest_file):
        """Generic exception during test execution is handled."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.side_effect = RuntimeError("Unexpected crash")
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 200,
                "test_files": [valid_pytest_file],
                "framework_config": get_framework_config(TestFramework.PYTEST),
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert result["test_run_result"] is None
            assert "Test execution failed" in result["error_message"]
            assert "Unexpected crash" in result["error_message"]

    def test_multiple_test_files(self, tmp_path):
        """Multiple test files are all validated and passed to runner."""
        test_file_1 = tmp_path / "tests" / "test_a.py"
        test_file_2 = tmp_path / "tests" / "test_b.py"
        test_file_1.parent.mkdir(parents=True, exist_ok=True)
        test_file_1.write_text("import pytest\n\ndef test_a():\n    assert True\n")
        test_file_2.write_text("import pytest\n\ndef test_b():\n    assert True\n")

        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 2, "failed": 0, "skipped": 0, "errors": 0,
                "total": 2, "coverage_percent": 95.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "2 passed", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            }
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 200,
                "test_files": [str(test_file_1), str(test_file_2)],
                "framework_config": get_framework_config(TestFramework.PYTEST),
                "repo_root": str(tmp_path),
            }
            result = run_tests(state)
            assert result["error_message"] == ""
            assert result["test_run_result"]["passed"] == 2
            assert mock_runner.validate_test_file.call_count == 2
            mock_runner.run_tests.assert_called_once_with(
                test_paths=[str(test_file_1), str(test_file_2)]
            )

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t330_full_chain_mocked(self, mock_which, valid_playwright_test_file):
        """T330: Full chain — run_tests produces result consumed by check_coverage."""
        from assemblyzero.workflows.testing.nodes.check_coverage import check_coverage

        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_run_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 38, "failed": 0, "skipped": 0, "errors": 0,
                "total": 38, "coverage_percent": 0.0,
                "coverage_type": CoverageType.SCENARIO,
                "raw_output": "{}", "exit_code": 0,
                "framework": TestFramework.PLAYWRIGHT,
            }
            mock_run_get_runner.return_value = mock_runner

            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": [valid_playwright_test_file],
                "framework_config": config,
                "repo_root": "/tmp",
            }
            run_result = run_tests(state)

            assert run_result["error_message"] == ""
            assert run_result["test_run_result"]["passed"] == 38

        # Now feed into check_coverage
        with patch(
            "assemblyzero.workflows.testing.nodes.check_coverage.get_runner"
        ) as mock_cov_get_runner:
            mock_cov_runner = MagicMock()
            mock_cov_runner.compute_scenario_coverage.return_value = 1.0
            mock_cov_get_runner.return_value = mock_cov_runner

            coverage_state = {
                "issue_number": 56,
                "test_run_result": run_result["test_run_result"],
                "framework_config": config,
                "total_scenarios": 38,
            }
            cov_result = check_coverage(coverage_state)
            assert cov_result["green"] is True
            assert cov_result["iterate_reason"] == ""

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_check_coverage_node.py
"""Unit tests for the check_coverage node.

Issue #381: Tests T210, T300, T310, T320 from LLD Section 10.0.
"""

from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.nodes.check_coverage import check_coverage


class TestScenarioCoverage:
    """Tests for scenario-based coverage (Playwright)."""

    def test_t210_scenario_coverage_math(self):
        """T210: compute_scenario_coverage calculates correctly."""
        # Tested indirectly through check_coverage node
        from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner
        from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner

        config = get_framework_config(TestFramework.PYTEST)
        runner = PytestRunner(config, "/tmp")

        # 38/38 = 100%
        result_full = {"passed": 38, "failed": 0}
        assert runner.compute_scenario_coverage(result_full, 38) == 1.0

        # 35/38 ≈ 92.1%
        result_partial = {"passed": 35, "failed": 3}
        cov = runner.compute_scenario_coverage(result_partial, 38)
        assert abs(cov - 0.9210526315789473) < 0.0001

        # 0/0 = 0.0 (no ZeroDivisionError)
        result_empty = {"passed": 0, "failed": 0}
        assert runner.compute_scenario_coverage(result_empty, 0) == 0.0

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t300_scenario_coverage_for_e2e(self, mock_which):
        """T300: check_coverage uses scenario coverage for e2e (38/38 = 100%)."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)

        with patch(
            "assemblyzero.workflows.testing.nodes.check_coverage.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.compute_scenario_coverage.return_value = 1.0
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 56,
                "test_run_result": {
                    "passed": 38, "failed": 0, "skipped": 0, "errors": 0,
                    "total": 38, "coverage_percent": 0.0,
                    "coverage_type": CoverageType.SCENARIO,
                    "raw_output": "", "exit_code": 0,
                    "framework": TestFramework.PLAYWRIGHT,
                },
                "framework_config": config,
                "total_scenarios": 38,
            }
            result = check_coverage(state)
            assert result["green"] is True
            assert result["iterate_reason"] == ""

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_scenario_coverage_below_target(self, mock_which):
        """Scenario coverage below target → not green."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)

        with patch(
            "assemblyzero.workflows.testing.nodes.check_coverage.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.compute_scenario_coverage.return_value = 0.80
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 56,
                "test_run_result": {
                    "passed": 30, "failed": 0, "skipped": 0, "errors": 0,
                    "total": 30, "coverage_percent": 0.0,
                    "coverage_type": CoverageType.SCENARIO,
                    "raw_output": "", "exit_code": 0,
                    "framework": TestFramework.PLAYWRIGHT,
                },
                "framework_config": config,
                "total_scenarios": 38,
            }
            result = check_coverage(state)
            assert result["green"] is False
            assert "Scenario coverage" in result["iterate_reason"]


class TestLineCoverage:
    """Tests for line-based coverage (pytest, Jest)."""

    def test_t310_line_coverage_for_pytest(self):
        """T310: check_coverage uses line coverage for pytest."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 15, "failed": 0, "skipped": 0, "errors": 0,
                "total": 15, "coverage_percent": 97.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is True

    def test_line_coverage_below_target(self):
        """Line coverage below target → not green."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 15, "failed": 0, "skipped": 0, "errors": 0,
                "total": 15, "coverage_percent": 72.5,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "Line coverage 72.5%" in result["iterate_reason"]
        assert "95.0%" in result["iterate_reason"]


class TestNoneCoverage:
    """Tests for coverage_type NONE."""

    def test_t320_none_coverage_skips_check(self):
        """T320: check_coverage with coverage_type NONE skips coverage check."""
        config = get_framework_config(TestFramework.PYTEST)
        config["coverage_type"] = CoverageType.NONE  # Override for test

        state = {
            "issue_number": 300,
            "test_run_result": {
                "passed": 10, "failed": 0, "skipped": 0, "errors": 0,
                "total": 10, "coverage_percent": 0.0,
                "coverage_type": CoverageType.NONE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is True


class TestFailureHandling:
    """Tests for test failure detection."""

    def test_failed_tests_not_green(self):
        """Failed tests → not green, regardless of coverage."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 12, "failed": 3, "skipped": 0, "errors": 0,
                "total": 15, "coverage_percent": 97.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 1,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "3 tests failed" in result["iterate_reason"]

    def test_errors_not_green(self):
        """Test errors → not green."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 10, "failed": 0, "skipped": 0, "errors": 2,
                "total": 12, "coverage_percent": 90.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 1,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "2 test errors" in result["iterate_reason"]

    def test_no_test_results(self):
        """Missing test results → not green."""
        state = {
            "issue_number": 200,
            "test_run_result": None,
            "framework_config": get_framework_config(TestFramework.PYTEST),
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "No test results" in result["iterate_reason"]

    def test_zero_scenarios_not_green(self):
        """Zero total scenarios for SCENARIO type → not green."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)

        state = {
            "issue_number": 56,
            "test_run_result": {
                "passed": 0, "failed": 0, "skipped": 0, "errors": 0,
                "total": 0, "coverage_percent": 0.0,
                "coverage_type": CoverageType.SCENARIO,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PLAYWRIGHT,
            },
            "framework_config": config,
            "total_scenarios": 0,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "No scenarios" in result["iterate_reason"]

    def test_t340_backward_compat_pytest(self):
        """T340: Standard pytest state works with backward compatibility."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 20, "failed": 0, "skipped": 0, "errors": 0,
                "total": 20, "coverage_percent": 96.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "20 passed", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is True
        assert result["iterate_reason"] == ""

    def test_no_framework_config_defaults_to_pytest(self):
        """Missing framework_config defaults to pytest config."""
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 10, "failed": 0, "skipped": 0, "errors": 0,
                "total": 10, "coverage_percent": 96.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": None,
        }
        result = check_coverage(state)
        assert result["green"] is True


```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/workflows/testing/runners/__init__.py (signatures)

```python
"""Test runner package for multi-framework support.

Issue #381: Strategy Pattern runners for pytest, Playwright, and Jest.
"""

from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner

from assemblyzero.workflows.testing.runners.playwright_runner import PlaywrightRunner

from assemblyzero.workflows.testing.runners.jest_runner import JestRunner

__all__ = [
    "BaseTestRunner",
    "PytestRunner",
    "PlaywrightRunner",
    "JestRunner",
]
```

### assemblyzero/workflows/testing/runners/base_runner.py (signatures)

```python
"""Abstract base class for framework-specific test runners.

Issue #381: Defines the interface all test runners must implement.
"""

import json

import logging

import subprocess

from abc import ABC, abstractmethod

from typing import Any

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)

class BaseTestRunner(ABC):

    """Abstract base class for framework-specific test runners."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
    """Initialize with framework config and project root path."""
    ...

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
    """Execute tests and return unified results."""
    ...

    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
    """Parse runner-specific output into unified TestRunResult."""
    ...

    def validate_test_file(self, file_path: str, content: str) -> list[str]:
    """Validate a test file for mechanical correctness.

Returns list of validation error messages (empty = valid)."""
    ...

    def get_scaffold_imports(self) -> str:
    """Return the import block for scaffolded test files."""
    ...

    def compute_scenario_coverage(
        self, result: TestRunResult, total_scenarios: int
    ) -> float:
    """Compute scenario-based coverage: passed / total_scenarios.

Returns 0.0 if total_scenarios is 0 to prevent ZeroDivisionError."""
    ...

    def _run_subprocess(
        self,
        command: list[str],
        timeout: int = DEFAULT_TIMEOUT,
        cwd: str | None = None,
    ) -> tuple[str, int]:
    """Run a subprocess command and return (stdout, exit_code).

Handles timeout and other subprocess errors gracefully."""
    ...

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300
```

### assemblyzero/workflows/testing/framework_detector.py (signatures)

```python
"""Framework detection for multi-framework TDD workflow.

Issue #381: Detects test framework from LLD content and project files.
Supports pytest, Playwright, Jest, and Vitest.
"""

import json

import logging

import os

import re

from enum import Enum

from typing import Optional, TypedDict

class TestFramework(Enum):

    """Supported test frameworks."""

class CoverageType(Enum):

    """How coverage is measured for this framework."""

class FrameworkConfig(TypedDict):

    """Configuration for a detected test framework."""

class TestRunResult(TypedDict):

    """Unified result from any test runner."""

def detect_framework_from_lld(lld_content: str) -> TestFramework:
    """Parse LLD content for test framework indicators.

Scans for:"""
    ...

def detect_framework_from_project(project_root: str) -> TestFramework | None:
    """Inspect project files to infer the test framework.

Checks for:"""
    ...

def resolve_framework(lld_content: str, project_root: str) -> TestFramework:
    """Resolve test framework using LLD as primary signal, project files as fallback.

Priority:"""
    ...

logger = logging.getLogger(__name__)
```

### assemblyzero/workflows/testing/runner_registry.py (signatures)

```python
"""Runner registry mapping framework types to configurations and runner instances.

Issue #381: Factory pattern for obtaining framework-specific test runners.
"""

import logging

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
)

from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

def get_framework_config(framework: TestFramework) -> FrameworkConfig:
    """Return the full configuration for a given test framework.

Raises ValueError if the framework is not registered."""
    ...

def get_runner(framework: TestFramework, project_root: str = ".") -> BaseTestRunner:
    """Factory method returning the appropriate runner instance.

Raises ValueError for unsupported frameworks."""
    ...

logger = logging.getLogger(__name__)
```

### assemblyzero/workflows/testing/runners/pytest_runner.py (signatures)

```python
"""Pytest test runner adapter.

Issue #381: Encapsulates pytest execution logic, extracting it from
previously hardcoded workflow nodes.
"""

import json

import logging

import re

from typing import Any

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)

from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

class PytestRunner(BaseTestRunner):

    """Test runner adapter for pytest + pytest-cov."""

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
    """Run pytest with --tb=short -q and parse output.

Uses --json-report if available, falls back to stdout parsing."""
    ...

    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
    """Parse pytest output into unified TestRunResult.

Attempts JSON report parsing first, falls back to regex on stdout."""
    ...

    def validate_test_file(self, file_path: str, content: str) -> list[str]:
    """Validate Python test file for mechanical correctness.

Checks:"""
    ...

    def get_scaffold_imports(self) -> str:
    """Return pytest import block."""
    ...

logger = logging.getLogger(__name__)
```

### assemblyzero/workflows/testing/runners/playwright_runner.py (signatures)

```python
"""Playwright test runner adapter.

Issue #381: Handles Playwright (@playwright/test) execution via npx,
JSON report parsing, and TypeScript test file validation.
"""

import json

import logging

import re

import shutil

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)

from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

class PlaywrightRunner(BaseTestRunner):

    """Test runner adapter for Playwright (@playwright/test)."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
    """Initialize and verify node/npx availability.

Raises EnvironmentError if 'npx' is not found on PATH."""
    ...

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
    """Run 'npx playwright test' with --reporter=json."""
    ...

    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
    """Parse Playwright JSON reporter output into TestRunResult.

Playwright JSON format has:"""
    ...

    def _count_suite(self, suite: dict) -> tuple[int, int, int, int]:
    """Recursively count test results in a Playwright suite."""
    ...

    def _fallback_result(self, raw_output: str, exit_code: int) -> TestRunResult:
    """Create a fallback result when JSON parsing fails."""
    ...

    def validate_test_file(self, file_path: str, content: str) -> list[str]:
    """Validate .spec.ts file for Playwright-specific correctness.

Checks:"""
    ...

    def get_scaffold_imports(self) -> str:
    """Return Playwright import block."""
    ...

logger = logging.getLogger(__name__)
```

### assemblyzero/workflows/testing/runners/jest_runner.py (signatures)

```python
"""Jest/Vitest test runner adapter.

Issue #381: Handles Jest and Vitest execution via npx,
JSON report parsing, and TypeScript test file validation.
"""

import json

import logging

import re

import shutil

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)

from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

class JestRunner(BaseTestRunner):

    """Test runner adapter for Jest / Vitest."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
    """Initialize and verify node/npx availability.

Raises EnvironmentError if 'npx' is not found on PATH."""
    ...

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
    """Run 'npx jest --json' or 'npx vitest run --reporter=json'."""
    ...

    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
    """Parse Jest/Vitest JSON output into unified TestRunResult.

Jest JSON format:"""
    ...

    def _extract_coverage(self, coverage_map: dict) -> float:
    """Extract overall line coverage percentage from Jest coverageMap.

Averages line coverage across all files."""
    ...

    def _fallback_result(self, raw_output: str, exit_code: int) -> TestRunResult:
    """Create a fallback result when JSON parsing fails."""
    ...

    def validate_test_file(self, file_path: str, content: str) -> list[str]:
    """Validate .test.ts file for Jest/Vitest correctness.

Checks:"""
    ...

    def get_scaffold_imports(self) -> str:
    """Return jest or vitest import block."""
    ...

logger = logging.getLogger(__name__)
```

### assemblyzero/workflows/testing/nodes/scaffold_tests.py (signatures)

```python
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

import re

from pathlib import Path

from typing import Any, TypedDict

from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)

from assemblyzero.workflows.testing.knowledge.patterns import get_test_type_info

from assemblyzero.workflows.testing.state import TestingWorkflowState, TestScenario

from assemblyzero.workflows.testing.framework_detector import (
    TestFramework,
    FrameworkConfig,
)

from assemblyzero.workflows.testing.runner_registry import get_framework_config, get_runner

class ParsedTestScenario(TypedDict):

    """A test scenario parsed from LLD Section 10.0."""

class ParsedLLDTests(TypedDict):

    """Parsed test information from LLD."""

def parse_lld_test_section(lld_content: str) -> ParsedLLDTests:
    """Extract test scenarios from LLD Section 10.0 Test Plan table.

Issue #335: Parses the Test Plan table to extract structured test"""
    ...

def infer_module_path(lld_content: str) -> str:
    """Determine target module from LLD Section 2.1 Files Changed.

Issue #335: Extracts the Python module path from the Files Changed"""
    ...

def generate_test_code(scenarios: ParsedLLDTests) -> str:
    """Generate executable pytest code from parsed scenarios.

Issue #335: Generates real test code with actual assertions"""
    ...

def _generate_assertion_from_expected(expected: str) -> str:
    """Generate assertion code from expected behavior string.

Issue #335: Parses expected behavior like '"Add (Directory)" -> ("add", True)'"""
    ...

def _extract_impl_module(files_to_modify: list[dict] | None) -> str | None:
    """Extract Python module path from files_to_modify.

Prioritizes NEW files (change_type="Add") over existing files (change_type="Modify")"""
    ...

def generate_ts_test_file_content(
    scenarios: list[TestScenario],
    framework_config: FrameworkConfig,
    issue_number: int,
) -> str:
    """Generate TypeScript test file content for Playwright or Jest/Vitest.

Issue #381: Generates .spec.ts or .test.ts files with framework-appropriate"""
    ...

def _generate_playwright_content(
    scenarios: list[TestScenario],
    issue_number: int,
) -> str:
    """Generate Playwright .spec.ts test content."""
    ...

def _generate_jest_content(
    scenarios: list[TestScenario],
    framework_config: FrameworkConfig,
    issue_number: int,
) -> str:
    """Generate Jest/Vitest .test.ts content."""
    ...

def generate_test_file_content(
    scenarios: list[TestScenario],
    module_name: str,
    issue_number: int,
    files_to_modify: list[dict] | None = None,
) -> str:
    """Generate pytest file content from test scenarios.

Args:"""
    ...

def _generate_test_function(
    scenario: TestScenario,
    issue_number: int,
    fixture: str | None = None,
) -> list[str]:
    """Generate a single test function.

Args:"""
    ...

def _wrap_text(text: str, width: int) -> list[str]:
    """Wrap text at specified width."""
    ...

def determine_test_file_path(
    issue_number: int,
    scenarios: list[TestScenario],
    repo_root: Path,
    framework_config: FrameworkConfig | None = None,
) -> Path:
    """Determine the appropriate path for the test file.

Issue #381: Now supports framework-aware file extensions via"""
    ...

def _scaffold_non_python_tests(
    state: TestingWorkflowState,
    framework_config: FrameworkConfig,
) -> dict[str, Any]:
    """Scaffold non-Python test files (Playwright, Jest, Vitest).

Issue #381: Generates TypeScript test files based on framework config."""
    ...

def scaffold_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """N2: Generate executable test stubs.

Issue #381: Now supports multi-framework scaffolding. If framework_config"""
    ...

def _mock_scaffold_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    ...
```

### assemblyzero/workflows/testing/nodes/run_tests.py (signatures)

```python
"""RunTests node for TDD Testing Workflow.

Issue #381: Framework-aware test execution that delegates to the
appropriate runner from the runner registry.
"""

import logging

from typing import Any

from assemblyzero.workflows.testing.audit import gate_log, log_workflow_execution

from assemblyzero.workflows.testing.framework_detector import (
    TestFramework,
    TestRunResult,
)

from assemblyzero.workflows.testing.runner_registry import (
    get_framework_config,
    get_runner,
)

from assemblyzero.workflows.testing.state import TestingWorkflowState

def run_tests(state: TestingWorkflowState) -> dict[str, Any]:
    """Execute tests using the framework-appropriate runner.

Reads framework_config from state, validates test files,"""
    ...

logger = logging.getLogger(__name__)
```

### assemblyzero/workflows/testing/nodes/check_coverage.py (signatures)

```python
"""CheckCoverage node for TDD Testing Workflow.

Issue #381: Framework-aware coverage checking that dispatches on
coverage_type (LINE, SCENARIO, NONE).
"""

import logging

from typing import Any

from assemblyzero.workflows.testing.audit import gate_log, log_workflow_execution

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)

from assemblyzero.workflows.testing.runner_registry import (
    get_framework_config,
    get_runner,
)

from assemblyzero.workflows.testing.state import TestingWorkflowState

def check_coverage(state: TestingWorkflowState) -> dict[str, Any]:
    """Evaluate coverage against framework-appropriate target.

Dispatches on coverage_type:"""
    ...

logger = logging.getLogger(__name__)
```

### tests/fixtures/lld_playwright_sample.md (full)

```python
# 56 - Feature: Dashboard E2E Tests

## 1. Context & Goal
Automated end-to-end tests for the dashboard using Playwright.

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/dashboard.spec.ts` | Add | E2E tests for dashboard |
| `tests/sidebar.spec.ts` | Add | E2E tests for sidebar navigation |

## 10. Verification & Testing

Test Framework: Playwright

### 10.0 Test Plan

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Dashboard loads correctly | Page shows dashboard heading | RED |
| T020 | Sidebar navigation works | Clicking menu item navigates | RED |
| T030 | Data table displays | Table has correct columns | RED |
```

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Markdown content.

```markdown
# Your Markdown content here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Markdown content in a single fenced code block
