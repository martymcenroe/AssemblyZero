# Implementation Request: docs/standards/0701-implementation-spec-template.md

## Task

Write the complete contents of `docs/standards/0701-implementation-spec-template.md`.

Change type: Modify
Description: Header update

## LLD Specification

# Implementation Spec: 0608 - Align Section Numbers

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #608 |
| LLD | `docs/lld/active/LLD-608.md` |
| Generated | 2026-03-05 |
| Status | APPROVED |

## 1. Overview
Align Spec template with LLD Section 10.

## 2. Files to Implement
| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `docs/standards/0701-implementation-spec-template.md` | Modify | Header update |
| 2 | `assemblyzero/workflows/testing/nodes/load_lld.py` | Modify | Parser update |
| 3 | `tests/unit/test_load_lld_v2.py` | Add | Tests |

## 3. Requirements
1. Use Section 10 for Spec test mapping.
2. Parser extracts from Section 10.

## 9. Test Mapping
| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | Standard Section 10 parsing | Success |

## 10. Implementation Notes
None.


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
    Standard Section 10 parsing | Success
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t010 works correctly
    assert False, 'TDD RED: test_t010 not implemented'




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
