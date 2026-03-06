# Implementation Request: docs/standards/0701-implementation-spec-template.md

## Task

Write the complete contents of `docs/standards/0701-implementation-spec-template.md`.

Change type: Modify
Description: Update heading `## 9. Test Mapping` to `## 10.` and shift subsequent sections.

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
  ... and 13 more files
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

## Existing File Contents

The file currently contains:

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
|-------|------|-------------|-------------|
| 1 | `path/to/file.py` | Add / Modify / Delete | What changes |
| 2 | `path/to/other.py` | Add / Modify / Delete | What changes |

**Implementation Order Rationale:** {Why this order — dependencies, imports, etc.}

## 3. Current State (for Modify/Delete files)

*For every file with Change Type "Modify" or "Delete", include the actual current code excerpt. This section is **mandatory** — specs without current state excerpts fail completeness validation.*

### 3.1 `path/to/existing_file.py`

**Relevant excerpt** (lines {start}-{end}):

```python
# Actual current code from the file
# Not pseudocode — real code that exists today
def existing_function(arg: str) -> bool:
    """Current docstring."""
    return arg == "value"
```

**What changes:** {Description of modifications to this specific code}

### 3.2 `path/to/another_file.py`

**Relevant excerpt** (lines {start}-{end}):

```python
# Another actual excerpt
class ExistingClass:
    pass
```

**What changes:** {Description of modifications}

## 4. Data Structures

*Every data structure must include both the type definition AND a concrete example with realistic values.*

### 4.1 {StructureName}

**Definition:**

```python
class MyStructure(TypedDict):
    name: str
    count: int
    items: list[str]
```

**Concrete Example:**

```json
{
    "name": "implementation-spec",
    "count": 42,
    "items": ["state.py", "graph.py", "nodes/load.py"]
}
```

### 4.2 {AnotherStructure}

**Definition:**

```python
class AnotherStructure(TypedDict):
    path: str
    change_type: Literal["Add", "Modify", "Delete"]
```

**Concrete Example:**

```json
{
    "path": "assemblyzero/workflows/example/state.py",
    "change_type": "Add"
}
```

## 5. Function Specifications

*Every function must include: signature, docstring summary, input example with realistic values, output example with realistic values, and edge cases.*

### 5.1 `function_name()`

**File:** `path/to/file.py`

**Signature:**

```python
def function_name(arg1: str, arg2: int) -> dict[str, Any]:
    """One-line description."""
    ...
```

**Input Example:**

```python
arg1 = "docs/lld/active/304-implementation-readiness.md"
arg2 = 304
```

**Output Example:**

```python
{
    "result_key": "parsed content here",
    "error_message": "",
}
```

**Edge Cases:**
- Empty `arg1` -> raises `ValueError("arg1 cannot be empty")`
- `arg2 < 1` -> returns `{"result_key": "", "error_message": "Invalid issue number"}`

### 5.2 `another_function()`

**File:** `path/to/file.py`

**Signature:**

```python
async def another_function(state: MyState) -> dict[str, Any]:
    """One-line description."""
    ...
```

**Input Example:**

```python
state = {
    "issue_number": 304,
    "lld_content": "# 304 - Feature: ...\n## 1. Context...",
}
```

**Output Example:**

```python
{
    "spec_draft": "# Implementation Spec: ...",
    "error_message": "",
}
```

**Edge Cases:**
- Missing `lld_content` -> returns error_message describing the issue
- API timeout -> returns error_message with timeout details

## 6. Change Instructions

*Diff-level specific instructions for each file. Must be precise enough to generate actual diffs. Generic instructions like "add error handling" fail completeness validation.*

### 6.1 `path/to/file.py` (Add)

**Complete file contents:**

```python
"""Module docstring.

Issue #{issue_number}: {title}
"""

from typing import Any

def new_function(arg: str) -> Any:
    """Docstring."""
    return arg
```

### 6.2 `path/to/existing_file.py` (Modify)

**Change 1:** Add import at line {N}

```diff
 import os
 from pathlib import Path
+from typing import Any
+
+from mypackage.new_module import new_function
```

**Change 2:** Modify function at lines {M}-{N}

```diff
 def existing_function(arg: str) -> bool:
-    """Current docstring."""
-    return arg == "value"
+    """Updated docstring with new behavior."""
+    result = new_function(arg)
+    return result is not None
```

### 6.3 `path/to/deleted_file.py` (Delete)

**Action:** Delete the entire file. No other files import from it.

**Verification:** Search for imports of this module — should find zero references after changes.

## 7. Pattern References

*References to existing similar implementations in the codebase. Each reference must include file path, line range, and why it's relevant. Pattern references are verified to exist during completeness validation.*

### 7.1 {Pattern Description}

**File:** `path/to/similar/implementation.py` (lines {start}-{end})

```python
# Actual code from the referenced pattern
def similar_function(state: SomeState) -> dict[str, Any]:
    """This pattern shows how to..."""
    value = state.get("key", "")
    if not value:
        return {"error_message": "Missing key"}
    return {"result": value, "error_message": ""}
```

**Relevance:** {Why this pattern should be followed — e.g., "Same error handling convention used in all workflow nodes"}

### 7.2 {Another Pattern}

**File:** `path/to/another/pattern.py` (lines {start}-{end})

```python
# Actual code excerpt
```

**Relevance:** {Why this pattern is relevant}

## 8. Dependencies & Imports

*All imports needed across files. Verify each import resolves to an existing module.*

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import Any` | stdlib | All new files |
| `from pathlib import Path` | stdlib | `file1.py`, `file2.py` |
| `from mypackage.module import Class` | internal | `file3.py` |

**New Dependencies:** {None / list any new pyproject.toml additions}

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

*Map each test from LLD Section 10.0 to specific functions and expected behavior.*

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `function_name()` | `arg1="valid"` | `{"result": "parsed", "error_message": ""}` |
| T020 | `function_name()` | `arg1=""` | Raises `ValueError` |
| T030 | `another_function()` | `state={...}` | `{"spec_draft": "...", "error_message": ""}` |

## 11. Implementation Notes

*Any additional context that helps implementation but doesn't fit above sections.*

### 11.1 Error Handling Convention

{Describe the error handling pattern — e.g., "All nodes return error_message field. Empty string means success. Non-empty means the node encountered an issue."}

### 11.2 Logging Convention

{Describe logging pattern — e.g., "Use print() with [N{X}] prefix for node identification. Example: print('[N0] Loading LLD...')"}

### 11.3 Constants

{List any magic numbers, configuration values, or constants with their rationale.}

| Constant | Value | Rationale |
|----------|-------|-----------|
| `MAX_FILE_SIZE` | `1_000_000` | Prevent loading huge generated files |
| `MAX_ITERATIONS` | `3` | Balance quality vs. cost |

---

## Completeness Checklist

*This checklist is verified mechanically by N3 (validate_completeness). All items must pass.*

- [ ] Every "Modify" file has a current state excerpt (Section 3)
- [ ] Every data structure has a concrete JSON/YAML example (Section 4)
- [ ] Every function has input/output examples with realistic values (Section 5)
- [ ] Change instructions are diff-level specific (Section 6)
- [ ] Pattern references include file:line and are verified to exist (Section 7)
- [ ] All imports are listed and verified (Section 8)
- [ ] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

*Populated automatically by the workflow upon finalization.*

| Field | Value |
|-------|-------|
| Issue | #{issue_number} |
| Verdict | {APPROVED / REVISE / BLOCKED} |
| Date | {YYYY-MM-DD} |
| Iterations | {N} |
| Finalized | {ISO 8601 timestamp} |
```

Modify this file according to the LLD specification.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero-608\tests\unit\test_load_lld.py
"""Unit tests for load_lld mechanical parser.

Issue #608: Verify Section 10 extraction and Section 9 rejection.
"""

import pytest
from pathlib import Path
from assemblyzero.workflows.testing.nodes.load_lld import (
    extract_test_plan_section,
    validate_spec_structure,
    WorkflowParsingError,
)


def test_extract_valid_lld():
    """T020: Parse valid LLD to extract Section 10 (Verification & Testing)."""
    content = "## 10. Verification & Testing\nSome testing content\n## 11. Next"
    result = extract_test_plan_section(content)
    assert "Some testing content" in result


def test_extract_valid_spec():
    """T030: Parse valid Spec to extract Section 10 (Test Mapping)."""
    content = "## 10. Test Mapping\nSome test mapping content\n## 11. Next"
    result = extract_test_plan_section(content)
    assert "Some test mapping content" in result


def test_reject_legacy_section_9():
    """T040, T045: Reject invalid Spec using Section 9."""
    content = "## 9. Test Mapping\nOld content"
    with pytest.raises(WorkflowParsingError) as exc:
        extract_test_plan_section(content)
    assert "Expected: ## 10. Test Mapping" in str(exc.value)


def test_validate_rejects_section_9():
    """T045: validate_spec_structure raises WorkflowParsingError for Section 9."""
    content = "## 9. Test Mapping\nBody"
    with pytest.raises(WorkflowParsingError) as exc:
        validate_spec_structure(content)
    assert "Expected: ## 10. Test Mapping" in str(exc.value)


def test_extract_whitespace_tolerance():
    """T050: Parse Spec with whitespace via fixture."""
    fixture_path = Path("tests/fixtures/lld_tracking/spec_whitespace.md")
    # Use inline content if fixture doesn't exist yet during early tests
    content = (
        fixture_path.read_text()
        if fixture_path.exists()
        else "## 10 . Test Mapping\nWhitespace content\n## 11. Next"
    )
    result = extract_test_plan_section(content)
    assert "T010" in result or "Whitespace content" in result


def test_0701_template_valid():
    """T010: Verify Spec Template 0701 contains ## 10. Test Mapping."""
    template_path = Path("docs/standards/0701-implementation-spec-template.md")
    if template_path.exists():
        content = template_path.read_text()
        # Should not raise
        validate_spec_structure(content)


def test_extract_returns_body_only_for_verification():
    """T020 extended: extract_test_plan_section returns just the body text."""
    content = "## 10. Verification & Testing\nBody\n## 11. Notes"
    result = extract_test_plan_section(content)
    assert result == "Body"


def test_extract_returns_body_only_for_test_mapping():
    """T030 extended: extract_test_plan_section returns just the body text."""
    content = "## 10. Test Mapping\nBody\n## 11. Notes"
    result = extract_test_plan_section(content)
    assert result == "Body"


def test_extract_section_10_at_end_of_file():
    """Section 10 at EOF without a following heading still extracts content."""
    content = "## 10. Test Mapping\nFinal content here"
    result = extract_test_plan_section(content)
    assert "Final content here" in result


def test_no_section_10_raises():
    """Content with no Section 10 at all raises WorkflowParsingError."""
    content = "## 1. Overview\nSome overview\n## 2. Details\nSome details"
    with pytest.raises(WorkflowParsingError) as exc:
        extract_test_plan_section(content)
    assert "Expected: ## 10. Test Mapping" in str(exc.value)


def test_whitespace_inline_tolerance():
    """Whitespace between number and period is tolerated."""
    content = "## 10 . Test Mapping\nWhitespace content\n## 11. Next"
    result = extract_test_plan_section(content)
    assert "Whitespace content" in result


def test_validate_spec_structure_passes_section_10():
    """validate_spec_structure returns None for valid Section 10."""
    content = "## 10. Test Mapping\nBody"
    result = validate_spec_structure(content)
    assert result is None


```

## Previous Attempt Failed — Fix These Specific Errors

The previous implementation failed these tests:

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Scripts\python.exe
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: C:\Users\mcwiz\Projects\AssemblyZero-608
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.9, benchmark-5.2.3, cov-7.0.0
collecting ... collected 12 items

tests/unit/test_load_lld.py::test_extract_valid_lld PASSED               [  8%]
tests/unit/test_load_lld.py::test_extract_valid_spec PASSED              [ 16%]
tests/unit/test_load_lld.py::test_reject_legacy_section_9 PASSED         [ 25%]
tests/unit/test_load_lld.py::test_validate_rejects_section_9 PASSED      [ 33%]
tests/unit/test_load_lld.py::test_extract_whitespace_tolerance PASSED    [ 41%]
tests/unit/test_load_lld.py::test_0701_template_valid PASSED             [ 50%]
tests/unit/test_load_lld.py::test_extract_returns_body_only_for_verification PASSED [ 58%]
tests/unit/test_load_lld.py::test_extract_returns_body_only_for_test_mapping PASSED [ 66%]
tests/unit/test_load_lld.py::test_extract_section_10_at_end_of_file PASSED [ 75%]
tests/unit/test_load_lld.py::test_no_section_10_raises PASSED            [ 83%]
tests/unit/test_load_lld.py::test_whitespace_inline_tolerance PASSED     [ 91%]
tests/unit/test_load_lld.py::test_validate_spec_structure_passes_section_10 PASSED [100%]
ERROR: Coverage failure: total of 11 is less than fail-under=95


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

Name                                               Stmts   Miss  Cover   Missing
--------------------------------------------------------------------------------
assemblyzero\workflows\testing\nodes\load_lld.py     357    316    11%   61-82, 99-134, 147, 207, 226-266, 283-331, 348-450, 455-456, 461-473, 478-489, 494-510, 527-539, 555-642, 662-743, 768-911, 931-1006
--------------------------------------------------------------------------------
TOTAL                                                357    316    11%
FAIL Required test coverage of 95% not reached. Total coverage: 11.48%
======================= 12 passed, 6 warnings in 1.14s ========================


```

Read the error messages carefully and fix the root cause in your implementation.

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
