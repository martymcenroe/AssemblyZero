# Implementation Request: assemblyzero/utils/ast_sentinel.py

## Task

Write the complete contents of `assemblyzero/utils/ast_sentinel.py`.

Change type: Add
Description: Core AST parsing logic and visitor.

## LLD Specification

# Implementation Spec: 0600 - AST-Based Import Sentinel

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #600 |
| LLD | `docs/lld/active/LLD-600.md` |
| Generated | 2026-03-05 |
| Status | APPROVED |

## 1. Overview
Enhance mechanical validation to strictly catch "Lingering Symbols" (missing imports or undefined variables) before execution using AST analysis.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/utils/ast_sentinel.py` | Add | Core AST parsing logic and visitor. |
| 2 | `tests/unit/test_ast_sentinel.py` | Add | Unit tests for AST Sentinel logic. |
| 3 | `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` | Modify | Integrate the new AST Sentinel check. |

## 3. Current State (for Modify/Delete files)

### 3.1 assemblyzero/workflows/requirements/nodes/validate_mechanical.py
```python
def validate_mechanical(state: RequirementsWorkflowState) -> dict:
    # ... existing validation logic ...
    return {"validation_errors": errors}
```

## 4. Technical Strategy
1. **ast_sentinel.py:** Implement `SymbolSentinel` using `ast.NodeVisitor`.
   - Maintain a `scope_stack` (list of sets) to track definitions.
   - `visit_Import`/`visit_ImportFrom`: Register aliases in the current scope. Reject `*`.
   - `visit_FunctionDef`/`visit_ClassDef`: Push new scope, register args/name, pop on exit.
   - `visit_Name(ctx=ast.Load)`: Check if name exists in any scope in the stack or `builtins`.
2. **Integration:** Update `validate_mechanical.py` to call `ast_sentinel.analyze_file(path)`.

## 5. Requirements Mapping (from LLD)
- REQ-1: Parse using `ast.parse` and `NodeVisitor`.
- REQ-2: Detect `ast.Load` without corresponding definition.
- REQ-3: State specific error: "Symbol '{name}' used on line {line} but not imported."
- REQ-4: Strictly fail gate (`exit 1`) on un-ignored errors.
- REQ-5: Recursive stack-based scope tracking (nested scopes, comprehensions, walrus).
- REQ-6: Ban star imports explicitly.
- REQ-7: Support `if TYPE_CHECKING:` blocks.
- REQ-8: Support `# sentinel: disable-line`.

## 10. Verification & Testing

### 10.1 Test Scenarios
| ID | Scenario | Input | Expected | Pass Criteria |
|----|----------|-------|----------|---------------|
| 010 | Happy path valid AST Analysis (REQ-1) | `import os; os.path.join()` | No errors | No errors emitted |
| 020 | Missing import verified (REQ-2) | `json.dumps({})` | `SentinelError` | Error for 'json' |
| 030 | Feedback to stderr (REQ-3) | `json.dumps({})` | Error in stderr | Exact string in stderr |
| 040 | Mechanical validation fail (REQ-4) | Bad file | `sys.exit(1)` | Exit code 1 |
| 050 | Local scope resilience (REQ-5) | `def foo(a): b = a; return b` | No errors | Args/locals recognized |
| 060 | Comprehensions (REQ-5) | `[x for x in y]` | No errors | 'x' isolated |
| 070 | Walrus Operators (REQ-5) | `if (n := len(a)) > 1: print(n)` | No errors | 'n' recognized |
| 080 | Star imports banned (REQ-6) | `from typing import *` | "Star imports are not allowed" | REQ-6 failure |
| 090 | Global/Nonlocal tracking (REQ-5) | `global x; x = 1` | No errors | No false positives |
| 100 | TYPE_CHECKING support (REQ-7) | `if TYPE_CHECKING: from x import y` | No errors | 'y' registered |
| 110 | Ignore comments (REQ-8) | `var # sentinel: disable-line` | No errors | Symbol ignored |

**Final Status:** APPROVED (Manually Patched)


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
    death/
    issue_workflow/
    janitor/
      mock_repo/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    spelunking/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_death/
    test_gate/
    test_janitor/
    test_rag/
    test_spelunking/
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
  ... and 14 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  spelunking/
  telemetry/
  utils/
  workflows/
    death/
    implementation_spec/
      nodes/
    issue/
      nodes/
    janitor/
      probes/
    lld/
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
  hourglass/
  unleashed/
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero-600\tests\test_issue_600.py
"""Test file for Issue #600.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from assemblyzero.utils.ast_sentinel import *  # noqa: F401, F403


# Unit Tests
# -----------

def test_010():
    """
    Happy path valid AST Analysis (REQ-1) | `import os; os.path.join()` |
    No errors | No errors emitted
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_010 works correctly
    assert False, 'TDD RED: test_010 not implemented'


def test_020():
    """
    Missing import verified (REQ-2) | `json.dumps({})` | `SentinelError`
    | Error for 'json'
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_020 works correctly
    assert False, 'TDD RED: test_020 not implemented'


def test_030():
    """
    Feedback to stderr (REQ-3) | `json.dumps({})` | Error in stderr |
    Exact string in stderr
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_030 works correctly
    assert False, 'TDD RED: test_030 not implemented'


def test_040():
    """
    Mechanical validation fail (REQ-4) | Bad file | `sys.exit(1)` | Exit
    code 1
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_040 works correctly
    assert False, 'TDD RED: test_040 not implemented'


def test_050():
    """
    Local scope resilience (REQ-5) | `def foo(a): b = a; return b` | No
    errors | Args/locals recognized
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_050 works correctly
    assert False, 'TDD RED: test_050 not implemented'


def test_060():
    """
    Comprehensions (REQ-5) | `[x for x in y]` | No errors | 'x' isolated
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_060 works correctly
    assert False, 'TDD RED: test_060 not implemented'


def test_070():
    """
    Walrus Operators (REQ-5) | `if (n := len(a)) > 1: print(n)` | No
    errors | 'n' recognized
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_070 works correctly
    assert False, 'TDD RED: test_070 not implemented'


def test_080():
    """
    Star imports banned (REQ-6) | `from typing import *` | "Star imports
    are not allowed" | REQ-6 failure
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_080 works correctly
    assert False, 'TDD RED: test_080 not implemented'


def test_090():
    """
    Global/Nonlocal tracking (REQ-5) | `global x; x = 1` | No errors | No
    false positives
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_090 works correctly
    assert False, 'TDD RED: test_090 not implemented'


def test_100():
    """
    TYPE_CHECKING support (REQ-7) | `if TYPE_CHECKING: from x import y` |
    No errors | 'y' registered
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_100 works correctly
    assert False, 'TDD RED: test_100 not implemented'


def test_110():
    """
    Ignore comments (REQ-8) | `var # sentinel: disable-line` | No errors
    | Symbol ignored
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_110 works correctly
    assert False, 'TDD RED: test_110 not implemented'




```

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
