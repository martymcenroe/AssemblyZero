# Implementation Request: tests/unit/test_load_lld.py

## Task

Write the complete contents of `tests/unit/test_load_lld.py`.

Change type: Add
Description: Add unit tests to verify Section 10 extraction and Section 9 rejection.

## LLD Specification

# Implementation Spec: Align Section Numbers between LLD and Implementation Spec Templates

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #608 |
| LLD | `docs/lld/active/608.md` |
| Generated | 2026-03-05 |
| Status | APPROVED |

## 1. Overview

**Objective:** Standardize section numbering between the LLD Template and the Implementation Spec Template to Section 10 to prevent LLM cognitive drift and mechanical parsing failures.

**Success Criteria:** The Implementation Spec template (0701) must use `## 10. Test Mapping`. The mechanical parser in `load_lld.py` must hard-cutover to extracting only Section 10 (with whitespace tolerance like `## 10 .`), completely rejecting Section 9 via a `WorkflowParsingError` that explicitly returns "Expected: ## 10. Test Mapping". All TDD scenarios must pass.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `docs/standards/0701-implementation-spec-template.md` | Modify | Update heading `## 9. Test Mapping` to `## 10.` and shift subsequent sections. |
| 2 | `assemblyzero/workflows/testing/nodes/load_lld.py` | Modify | Update mechanical parser to enforce Section 10 extraction and introduce/raise `WorkflowParsingError`. |
| 3 | `tests/fixtures/lld_tracking/spec_whitespace.md` | Add | Add a test fixture testing whitespace variations in Section 10. |
| 4 | `tests/unit/test_load_lld.py` | Add | Add unit tests to verify Section 10 extraction and Section 9 rejection. |

**Implementation Order Rationale:** The template drives the expected structure. The parser enforces it. The test fixtures provide the data for the tests, and the unit tests verify the parser changes against the template standard and fixtures.

## 3. Current State (for Modify/Delete files)

### 3.1 `docs/standards/0701-implementation-spec-template.md`

**Relevant excerpt** (lines 144-165):
```markdown
## 9. Test Mapping

*Map each test from LLD Section 10.0 to specific functions and expected behavior.*

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `function_name()` | `arg1="valid"` | `{"result": "parsed", "error_message": ""}` |
| T020 | `function_name()` | `arg1=""` | Raises `ValueError` |
| T030 | `another_function()` | `state={...}` | `{"spec_draft": "...", "error_message": ""}` |

## 10. Implementation Notes

*Any additional context that helps implementation but doesn't fit above sections.*

### 10.1 Error Handling Convention

{Describe the error handling pattern — e.g., "All nodes return error_message field. Empty string means success. Non-empty means the node encountered an issue."}

### 10.2 Logging Convention

{Describe logging pattern — e.g., "Use print() with [N{X}] prefix for node identification. Example: print('[N0] Loading LLD...')"}

### 10.3 Constants
```

**What changes:** `## 9. Test Mapping` becomes `## 10. Test Mapping`. `## 10. Implementation Notes` becomes `## 11. Implementation Notes`. Any sub-headings like `### 10.1` become `### 11.1`.

### 3.2 `assemblyzero/workflows/testing/nodes/load_lld.py`

**Relevant excerpt** (lines 53-57):
```python
def extract_test_plan_section(lld_content: str) -> str:
    """Extract test plan section from LLD or Implementation Spec content.

Supports two document formats:"""
    ...
```

**What changes:** Add a custom exception `WorkflowParsingError`. Implement a structural validator `validate_spec_structure(content: str)` that checks for the strict presence of `## 10.`. Implement `extract_test_plan_section` to utilize the strict bounded regex `^##\s*10\s*\.\s*(.*)$` with whitespace tolerance and drop fallback compatibility for Section 9.

## 4. Data Structures

*No new complex data structures are introduced, but the expected exception payload and the valid Markdown structure is strictly defined as follows:*

### 4.1 `WorkflowParsingError`

**Definition:**
```python
class WorkflowParsingError(ValueError):
    """Raised when a generated spec fails mechanical structure validation."""
    pass
```

**Concrete Example:**
```json
{
    "type": "WorkflowParsingError",
    "message": "Failed to extract test plan. Expected: ## 10. Test Mapping"
}
```

## 5. Function Specifications

### 5.1 `extract_test_plan_section()`

**File:** `assemblyzero/workflows/testing/nodes/load_lld.py`

**Signature:**
```python
def extract_test_plan_section(lld_content: str) -> str:
    """Extract test plan section strictly from Section 10."""
    ...
```

**Input Example:**
```python
lld_content = """# Spec
## 10 . Test Mapping
| Test ID |
|---|
| T010 |
## 11. Notes
"""
```

**Output Example:**
```python
"| Test ID |\n|---|\n| T010 |"
```

**Edge Cases:**
- Input uses `## 9. Test Mapping` -> raises `WorkflowParsingError("Expected: ## 10. Test Mapping")`
- Input has whitespace `## 10 . Test Mapping` -> Successfully extracts the block due to whitespace tolerance.

### 5.2 `validate_spec_structure()`

**File:** `assemblyzero/workflows/testing/nodes/load_lld.py`

**Signature:**
```python
def validate_spec_structure(content: str) -> None:
    """Validates that the content strictly contains a Section 10 test mapping heading."""
    ...
```

**Input Example:**
```python
content = "## 9. Test Mapping\n..."
```

**Output Example:**
```python
# Raises WorkflowParsingError
```

## 6. Change Instructions

### 6.1 `docs/standards/0701-implementation-spec-template.md` (Modify)

**Change 1:** Shift sections 9 and 10 down by 1.

```diff
-## 9. Test Mapping
+## 10. Test Mapping
 
 *Map each test from LLD Section 10.0 to specific functions and expected behavior.*
 
 | Test ID | Tests Function | Input | Expected Output |
 |---------|---------------|-------|-----------------|
 | T010 | `function_name()` | `arg1="valid"` | `{"result": "parsed", "error_message": ""}` |
 | T020 | `function_name()` | `arg1=""` | Raises `ValueError` |
 | T030 | `another_function()` | `state={...}` | `{"spec_draft": "...", "error_message": ""}` |
 
-## 10. Implementation Notes
+## 11. Implementation Notes
 
 *Any additional context that helps implementation but doesn't fit above sections.*
 
-### 10.1 Error Handling Convention
+### 11.1 Error Handling Convention
 
 {Describe the error handling pattern — e.g., "All nodes return error_message field. Empty string means success. Non-empty means the node encountered an issue."}
 
-### 10.2 Logging Convention
+### 11.2 Logging Convention
 
 {Describe logging pattern — e.g., "Use print() with [N{X}] prefix for node identification. Example: print('[N0] Loading LLD...')"}
 
-### 10.3 Constants
+### 11.3 Constants
```

### 6.2 `assemblyzero/workflows/testing/nodes/load_lld.py` (Modify)

**Change 1:** Add the `WorkflowParsingError` near the top of the module below imports.

```diff
 from assemblyzero.workflows.testing.state import TestingWorkflowState, TestScenario
+
+class WorkflowParsingError(ValueError):
+    """Raised when an Implementation Spec fails mechanical structure validation."""
+    pass
```

**Change 2:** Add `validate_spec_structure` and update `extract_test_plan_section`.

```diff
-def extract_test_plan_section(lld_content: str) -> str:
-    """Extract test plan section from LLD or Implementation Spec content.
-
-Supports two document formats:"""
-    ...
+def validate_spec_structure(content: str) -> None:
+    """Validate the Implementation Spec structural requirements."""
+    # Require Section 10, tolerate whitespace around the number and period
+    pattern = r"^##\s*10\s*\.\s*(?:Test Mapping|Verification & Testing)"
+    if not re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
+        raise WorkflowParsingError("Expected: ## 10. Test Mapping")
+
+def extract_test_plan_section(lld_content: str) -> str:
+    """Extract test plan section from LLD or Implementation Spec content."""
+    validate_spec_structure(lld_content)
+    
+    # Extract content under Section 10 until the next H2 or EOF
+    pattern = r"^##\s*10\s*\.\s*(?:Test Mapping|Verification & Testing)[^\n]*\n(.*?)(?=^##\s|\Z)"
+    match = re.search(pattern, lld_content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
+    
+    if not match:
+        raise WorkflowParsingError("Expected: ## 10. Test Mapping")
+        
+    return match.group(1).strip()
```

### 6.3 `tests/fixtures/lld_tracking/spec_whitespace.md` (Add)

**Complete file contents:**
```markdown
# Implementation Spec: Whitespace Test

## 1. Context

Some context.

## 10 . Test Mapping

| Test ID | Description |
|---------|-------------|
| T010    | Pass check  |

## 11. Implementation Notes
```

### 6.4 `tests/unit/test_load_lld.py` (Add)

**Complete file contents:**
```python
"""Unit tests for load_lld mechanical parser."""

import pytest
from pathlib import Path
from assemblyzero.workflows.testing.nodes.load_lld import (
    extract_test_plan_section,
    validate_spec_structure,
    WorkflowParsingError
)

def test_extract_valid_lld():
    """T020: Parse valid LLD to extract Section 10."""
    content = "## 10. Verification & Testing\nSome testing content\n## 11. Next"
    result = extract_test_plan_section(content)
    assert "Some testing content" in result

def test_extract_valid_spec():
    """T030: Parse valid Spec to extract Section 10."""
    content = "## 10. Test Mapping\nSome test mapping content\n## 11. Next"
    result = extract_test_plan_section(content)
    assert "Some test mapping content" in result

def test_reject_legacy_section_9():
    """T040, T045: Reject invalid Spec using Section 9."""
    content = "## 9. Test Mapping\nOld content"
    with pytest.raises(WorkflowParsingError) as exc:
        extract_test_plan_section(content)
    assert "Expected: ## 10. Test Mapping" in str(exc.value)

def test_extract_whitespace_tolerance():
    """T050: Parse Spec with whitespace via fixture."""
    fixture_path = Path("tests/fixtures/lld_tracking/spec_whitespace.md")
    # Use inline content if fixture doesn't exist yet during early tests
    content = fixture_path.read_text() if fixture_path.exists() else "## 10 . Test Mapping\nWhitespace content\n## 11. Next"
    result = extract_test_plan_section(content)
    assert "T010" in result or "Whitespace content" in result

def test_0701_template_valid():
    """T010: Verify Spec Template 0701 contains ## 10. Test Mapping."""
    template_path = Path("docs/standards/0701-implementation-spec-template.md")
    if template_path.exists():
        content = template_path.read_text()
        # Should not raise
        validate_spec_structure(content)
```

## 7. Pattern References

### 7.1 ReDoS Prevention

**File:** `assemblyzero/workflows/testing/knowledge/patterns.py` (assumed standard regex guidelines)
**Relevance:** The extraction regex uses `(?=^##\s|\Z)` instead of catastrophic backtracking combinations `(.*)` to ensure safe, bounded parsing, which mitigates the ReDoS security concern noted in Section 7.1 of the LLD.

### 7.2 Custom Workflow Exceptions

**File:** `assemblyzero/workflows/testing/state.py` (or similar standard implementations across node files)
**Relevance:** Defining specific workflow exceptions (like `WorkflowParsingError`) allows LangGraph nodes to catch known validation failures and easily route them back to the LLM generation node for self-correction without crashing the entire graph.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import re` | stdlib | `load_lld.py` |
| `import pytest` | external | `test_load_lld.py` |
| `from pathlib import Path` | stdlib | `test_load_lld.py` |

**New Dependencies:** None

## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `validate_spec_structure()` | Content of `0701-implementation-spec-template.md` | Returns `None` (passes validation) |
| T020 | `extract_test_plan_section()` | `## 10. Verification & Testing\nBody` | Returns `"Body"` |
| T030 | `extract_test_plan_section()` | `## 10. Test Mapping\nBody` | Returns `"Body"` |
| T040 | `extract_test_plan_section()` | `## 9. Test Mapping\nBody` | Raises `WorkflowParsingError` |
| T045 | `validate_spec_structure()` | `## 9. Test Mapping\nBody` | Exception contains message: `"Expected: ## 10. Test Mapping"` |
| T050 | `extract_test_plan_section()` | Content of `spec_whitespace.md` containing `## 10 . Test Mapping` | Successfully returns extracted table. |

## 10. Implementation Notes

### 10.1 Regex Tolerance Logic

The Regex strictly requires the number `10`, but it utilizes `\s*` around the dot (`.`) and prefix. This accommodates common LLM generation variations (e.g., `## 10 . Test Mapping` vs `## 10. Test Mapping`) while strictly failing if the number is `9`. 

### 10.2 Error Propagation

The `WorkflowParsingError` subclass is defined locally in `load_lld.py` and inherits from `ValueError`. This ensures that downstream code using `try/except ValueError` remains functional if it relies on standard Python exceptions, but allows specific catching via `except WorkflowParsingError` for targeted LLM feedback.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 9)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #608 |
| Verdict | APPROVED |
| Date | 2026-03-06 |
| Iterations | 0 |
| Finalized | 2026-03-06T05:22:56Z |

### Review Feedback Summary

The Implementation Spec is highly executable, providing exact regex patterns, complete content for new test files, and clear diffs for existing files. The logic for the mechanical parser and the template updates is unambiguous and directly implements the requirements.

## Suggestions
- In 'assemblyzero/workflows/testing/nodes/load_lld.py', ensure `import re` is added to the imports section if it is not already present, as the new validation logic relies on it.
- For the template modification in ...


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
# From C:\Users\mcwiz\Projects\AssemblyZero-608\tests\test_issue_608.py
"""Test file for Issue #608.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest


# Unit Tests
# -----------

def test_t010():
    """
    `validate_spec_structure()` | Content of
    `0701-implementation-spec-template.md` | Returns `None` (passes
    validation)
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t010 works correctly
    assert False, 'TDD RED: test_t010 not implemented'


def test_t020():
    """
    `extract_test_plan_section()` | `## 10. Verification & Testing\nBody`
    | Returns `"Body"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t020 works correctly
    assert False, 'TDD RED: test_t020 not implemented'


def test_t030():
    """
    `extract_test_plan_section()` | `## 10. Test Mapping\nBody` | Returns
    `"Body"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t030 works correctly
    assert False, 'TDD RED: test_t030 not implemented'


def test_t040():
    """
    `extract_test_plan_section()` | `## 9. Test Mapping\nBody` | Raises
    `WorkflowParsingError`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t040 works correctly
    assert False, 'TDD RED: test_t040 not implemented'


def test_t045():
    """
    `validate_spec_structure()` | `## 9. Test Mapping\nBody` | Exception
    contains message: `"Expected: ## 10. Test Mapping"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t045 works correctly
    assert False, 'TDD RED: test_t045 not implemented'


def test_t050():
    """
    `extract_test_plan_section()` | Content of `spec_whitespace.md`
    containing `## 10 . Test Mapping` | Successfully returns extracted
    table.
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t050 works correctly
    assert False, 'TDD RED: test_t050 not implemented'




```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### docs/standards/0701-implementation-spec-template.md (signatures)

```python
# Implementation Spec Template

<!-- Standard: 0701 -->
<!-- Version: 1.1 -->
<!-- Last Updated: 2026-03-05 -->
<!-- Issue: #304, #608 -->

> **Purpose:** This template defines the structure for Implementation Specs — documents that bridge the gap between an approved LLD (design) and autonomous AI implementation (execution). An Implementation Spec contains enough concrete detail that an AI agent can implement the changes with >80% first-try success rate.

---

## How to Use This Template

1. Start with an **approved LLD** (must have APPROVED status)
2. Run the Implementation Spec workflow: `poetry run python tools/run_implementation_spec_workflow.py --issue NUMBER`
3. The workflow generates a spec following this template automatically
4. Manual creation: copy this template and fill in each section

### Key Principles

- **Concrete over abstract:** Every data structure needs a JSON/YAML example, every function needs I/O examples
- **Current state matters:** For every file being modified, include the actual current code excerpt
- **Patterns guide implementation:** Reference existing similar code with file:line locations
- **Diff-level specificity:** Change instructions should be precise enough to generate diffs

---

# Implementation Spec: {Issue Title}

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #{issue_number} |
| LLD | `docs/lld/{active|done}/{lld_filename}.md` |
| Generated | {YYYY-MM-DD} |
| Status | DRAFT / APPROVED |

## 1. Overview

*Brief summary of what this implementation achieves. 2-3 sentences maximum.*

**Objective:** {One-line goal from the LLD}

**Success Criteria:** {Key acceptance criteria from LLD Section 3}

## 2. Files to Implement

*Complete list of files from LLD Section 2.1 with implementation order.*

| Order | File | Change Type | Description |
# ... (truncated, syntax error in original)

```

### assemblyzero/workflows/testing/nodes/load_lld.py (signatures)

```python
"""N0: Load Implementation Spec node for TDD Testing Workflow.

Issue #384: The TDD workflow now requires an Implementation Spec (produced
by the #304 spec workflow), not a raw LLD. If no spec exists, the workflow
exits with a specific command to generate one.

Issue #608: Enforce Section 10 extraction for test plan/test mapping.
Reject legacy Section 9 with WorkflowParsingError.

Reads the spec from docs/lineage/active/{N}-implspec/ (preferred) or
docs/lld/drafts/spec-{N}.md (fallback) and extracts:
- Full spec content (used as LLD content downstream)
- Test plan from Section 10 (LLD format) or Section 10 (impl spec format)
- Test scenarios with metadata (from tables, headings, bold, or code blocks)
- Requirements for coverage tracking
"""

import json

import re

import subprocess

from pathlib import Path

from typing import Any

from assemblyzero.workflows.testing.audit import (
    create_testing_audit_dir,
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)

from assemblyzero.workflows.testing.framework_detector import resolve_framework

from assemblyzero.workflows.testing.knowledge.patterns import detect_test_types

from assemblyzero.workflows.testing.runner_registry import get_framework_config

from assemblyzero.workflows.testing.state import TestingWorkflowState, TestScenario

class WorkflowParsingError(ValueError):

    """Raised when an Implementation Spec fails mechanical structure validation."""

def find_lld_path(issue_number: int, repo_root: Path) -> Path | None:
    """Find the LLD file for an issue number.

Args:"""
    ...

def find_spec_path(issue_number: int, repo_root: Path) -> Path | None:
    """Find the Implementation Spec file for an issue number.

Issue #384: TDD workflow requires an implementation spec, not a raw LLD."""
    ...

def build_spec_command(issue_number: int, repo_root: Path) -> str:
    """Build the exact command to generate a missing implementation spec.

Args:"""
    ...

def validate_spec_structure(content: str) -> None:
    """Validate the Implementation Spec structural requirements.

Issue #608: Require Section 10 for test plan / test mapping heading."""
    ...

def extract_test_plan_section(lld_content: str) -> str:
    """Extract test plan section strictly from Section 10.

Issue #608: Hard-cutover to Section 10 only. Section 9 is rejected"""
    ...

def _extract_test_scenarios_from_code_blocks(content: str) -> str:
    """Extract test scenario information from Python test code blocks.

Implementation specs include complete test file contents in code blocks"""
    ...

def extract_requirements(lld_content: str) -> list[str]:
    """Extract requirements from LLD content.

Looks for patterns like:"""
    ...

def parse_test_scenarios(test_plan: str) -> list[TestScenario]:
    """Parse test scenarios from test plan section.

Looks for patterns like:"""
    ...

def _extract_requirement_ref(content: str) -> str:
    """Extract requirement reference from content."""
    ...

def _infer_test_type(name: str, content: str) -> str:
    """Infer test type from name and content."""
    ...

def _needs_mock(content: str) -> bool:
    """Determine if mocking is needed based on content."""
    ...

def _extract_assertions(content: str) -> list[str]:
    """Extract assertion descriptions from content."""
    ...

def extract_coverage_target(lld_content: str) -> int:
    """Extract coverage target from LLD.

Looks for patterns like:"""
    ...

def extract_files_to_modify(lld_content: str) -> list[dict]:
    """Extract files to modify from LLD or Implementation Spec.

Supports two table formats:"""
    ...

def _load_from_issue(
    state: TestingWorkflowState,
    issue_number: int,
    repo_root: Path,
) -> dict[str, Any]:
    """Load issue body via gh CLI and construct synthetic LLD content.

Issue #287: --issue-only mode for lightweight workflows."""
    ...

def load_lld(state: TestingWorkflowState) -> dict[str, Any]:
    """N0: Load LLD and extract test plan.

Args:"""
    ...

def _mock_load_lld(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    ...

LLD_ACTIVE_DIR = Path("docs/lld/active")

SPEC_DRAFTS_DIR = Path("docs/lld/drafts")

LINEAGE_ACTIVE_DIR = Path("docs/lineage/active")
```

### tests/fixtures/lld_tracking/spec_whitespace.md (full)

```python
# Implementation Spec: Whitespace Test

## 1. Context

Some context.

## 10 . Test Mapping

| Test ID | Description |
|---------|-------------|
| T010    | Pass check  |

## 11. Implementation Notes
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
