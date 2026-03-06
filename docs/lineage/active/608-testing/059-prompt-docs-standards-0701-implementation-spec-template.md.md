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
# From C:\Users\mcwiz\Projects\AssemblyZero-608\tests\unit\test_load_lld_v2.py
"""Tests for load_lld.py Section 10 enforcement (Issue #608).

Validates that:
- Section 10 is required for test plan extraction
- Legacy Section 9 is explicitly rejected with migration guidance
- Whitespace variations around the period are tolerated
- validate_spec_structure and extract_test_plan_section enforce the new rules
"""

import pytest

from assemblyzero.workflows.testing.nodes.load_lld import (
    WorkflowParsingError,
    extract_test_plan_section,
    validate_spec_structure,
)


# ---------------------------------------------------------------------------
# Fixtures: spec content variants
# ---------------------------------------------------------------------------

SECTION_10_STANDARD = """\
## 1. Overview

Some overview text.

## 10. Test Mapping

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | Standard Section 10 parsing | Success |

## 11. Implementation Notes

None.
"""

SECTION_10_VERIFICATION_TESTING = """\
## 1. Overview

Overview.

## 10. Verification & Testing

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T001 | Verification test | Pass |
"""

SECTION_10_TEST_PLAN = """\
## 1. Overview

Overview.

## 10. Test Plan

### test_something
Verify something works.
"""

SECTION_10_WHITESPACE_VARIATION = """\
## 1. Overview

Overview.

## 10 . Test Mapping

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | Whitespace around period | Success |
"""

SECTION_10_EXTRA_WHITESPACE = """\
## 1. Overview

Overview.

##  10  .  Test Mapping

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | Extra whitespace | Success |
"""

LEGACY_SECTION_9 = """\
## 1. Overview

Overview.

## 9. Test Mapping

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T001 | Legacy test | Pass |
"""

LEGACY_SECTION_9_VERIFICATION = """\
## 1. Overview

Overview.

## 9. Verification & Testing

Some test content.
"""

NO_TEST_SECTION = """\
## 1. Overview

Overview.

## 2. Files to Implement

Some files.
"""

SECTION_10_INSIDE_CODE_FENCE = """\
## 1. Overview

Overview.

```python
heading = "## 10. Test Mapping"
print(heading)
```

## 3. Requirements

Stuff.
"""

BOTH_SECTIONS_9_AND_10 = """\
## 1. Overview

Overview.

## 9. Test Mapping

Old content.

## 10. Test Mapping

| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | New content | Success |
"""


# ---------------------------------------------------------------------------
# T010: Standard Section 10 parsing
# ---------------------------------------------------------------------------

class TestValidateSpecStructure:
    """Tests for validate_spec_structure()."""

    def test_t010_standard_section_10(self):
        """Standard Section 10 parsing succeeds."""
        # Should not raise
        validate_spec_structure(SECTION_10_STANDARD)

    def test_section_10_verification_testing(self):
        """Section 10 with 'Verification & Testing' heading succeeds."""
        validate_spec_structure(SECTION_10_VERIFICATION_TESTING)

    def test_section_10_test_plan(self):
        """Section 10 with 'Test Plan' heading succeeds."""
        validate_spec_structure(SECTION_10_TEST_PLAN)

    def test_section_10_whitespace_around_period(self):
        """Section 10 with whitespace around the period succeeds."""
        validate_spec_structure(SECTION_10_WHITESPACE_VARIATION)

    def test_section_10_extra_whitespace(self):
        """Section 10 with extra whitespace succeeds."""
        validate_spec_structure(SECTION_10_EXTRA_WHITESPACE)

    def test_legacy_section_9_rejected(self):
        """Legacy Section 9 'Test Mapping' is rejected with migration message."""
        with pytest.raises(WorkflowParsingError, match="Legacy Section 9"):
            validate_spec_structure(LEGACY_SECTION_9)

    def test_legacy_section_9_verification_rejected(self):
        """Legacy Section 9 'Verification & Testing' is rejected."""
        with pytest.raises(WorkflowParsingError, match="Legacy Section 9"):
            validate_spec_structure(LEGACY_SECTION_9_VERIFICATION)

    def test_legacy_section_9_error_mentions_section_10(self):
        """Rejection message directs authors to Section 10."""
        with pytest.raises(WorkflowParsingError, match="Section 10"):
            validate_spec_structure(LEGACY_SECTION_9)

    def test_no_test_section_rejected(self):
        """Spec with no test section at all is rejected."""
        with pytest.raises(WorkflowParsingError, match="Expected.*10.*Test Mapping"):
            validate_spec_structure(NO_TEST_SECTION)

    def test_both_sections_9_and_10_rejects_section_9(self):
        """If both Section 9 and 10 exist, Section 9 is still rejected."""
        with pytest.raises(WorkflowParsingError, match="Legacy Section 9"):
            validate_spec_structure(BOTH_SECTIONS_9_AND_10)


class TestExtractTestPlanSection:
    """Tests for extract_test_plan_section()."""

    def test_t010_extracts_standard_section_10(self):
        """Standard Section 10 table content is extracted correctly."""
        result = extract_test_plan_section(SECTION_10_STANDARD)
        assert "T010" in result
        assert "Standard Section 10 parsing" in result
        assert "Success" in result

    def test_extracts_until_next_h2(self):
        """Extraction stops at the next ## heading."""
        result = extract_test_plan_section(SECTION_10_STANDARD)
        assert "Implementation Notes" not in result

    def test_extracts_verification_testing(self):
        """Extracts content from '## 10. Verification & Testing'."""
        result = extract_test_plan_section(SECTION_10_VERIFICATION_TESTING)
        assert "T001" in result

    def test_extracts_test_plan_heading(self):
        """Extracts content from '## 10. Test Plan'."""
        result = extract_test_plan_section(SECTION_10_TEST_PLAN)
        assert "test_something" in result

    def test_extracts_with_whitespace_variation(self):
        """Extracts content when period has surrounding whitespace."""
        result = extract_test_plan_section(SECTION_10_WHITESPACE_VARIATION)
        assert "T010" in result

    def test_rejects_legacy_section_9(self):
        """extract_test_plan_section raises on legacy Section 9."""
        with pytest.raises(WorkflowParsingError, match="Legacy Section 9"):
            extract_test_plan_section(LEGACY_SECTION_9)

    def test_rejects_missing_section(self):
        """extract_test_plan_section raises when no test section exists."""
        with pytest.raises(WorkflowParsingError, match="Expected.*10.*Test Mapping"):
            extract_test_plan_section(NO_TEST_SECTION)

    def test_ignores_section_10_inside_code_fence(self):
        """Section 10 heading inside a code fence is not matched."""
        with pytest.raises(WorkflowParsingError, match="Expected.*10.*Test Mapping"):
            extract_test_plan_section(SECTION_10_INSIDE_CODE_FENCE)

    def test_extracted_content_is_stripped(self):
        """Extracted content has leading/trailing whitespace removed."""
        result = extract_test_plan_section(SECTION_10_STANDARD)
        assert result == result.strip()


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
collecting ... collected 19 items

tests/unit/test_load_lld_v2.py::TestValidateSpecStructure::test_t010_standard_section_10 PASSED [  5%]
tests/unit/test_load_lld_v2.py::TestValidateSpecStructure::test_section_10_verification_testing PASSED [ 10%]
tests/unit/test_load_lld_v2.py::TestValidateSpecStructure::test_section_10_test_plan PASSED [ 15%]
tests/unit/test_load_lld_v2.py::TestValidateSpecStructure::test_section_10_whitespace_around_period PASSED [ 21%]
tests/unit/test_load_lld_v2.py::TestValidateSpecStructure::test_section_10_extra_whitespace PASSED [ 26%]
tests/unit/test_load_lld_v2.py::TestValidateSpecStructure::test_legacy_section_9_rejected PASSED [ 31%]
tests/unit/test_load_lld_v2.py::TestValidateSpecStructure::test_legacy_section_9_verification_rejected PASSED [ 36%]
tests/unit/test_load_lld_v2.py::TestValidateSpecStructure::test_legacy_section_9_error_mentions_section_10 PASSED [ 42%]
tests/unit/test_load_lld_v2.py::TestValidateSpecStructure::test_no_test_section_rejected PASSED [ 47%]
tests/unit/test_load_lld_v2.py::TestValidateSpecStructure::test_both_sections_9_and_10_rejects_section_9 PASSED [ 52%]
tests/unit/test_load_lld_v2.py::TestExtractTestPlanSection::test_t010_extracts_standard_section_10 PASSED [ 57%]
tests/unit/test_load_lld_v2.py::TestExtractTestPlanSection::test_extracts_until_next_h2 PASSED [ 63%]
tests/unit/test_load_lld_v2.py::TestExtractTestPlanSection::test_extracts_verification_testing PASSED [ 68%]
tests/unit/test_load_lld_v2.py::TestExtractTestPlanSection::test_extracts_test_plan_heading PASSED [ 73%]
tests/unit/test_load_lld_v2.py::TestExtractTestPlanSection::test_extracts_with_whitespace_variation PASSED [ 78%]
tests/unit/test_load_lld_v2.py::TestExtractTestPlanSection::test_rejects_legacy_section_9 PASSED [ 84%]
tests/unit/test_load_lld_v2.py::TestExtractTestPlanSection::test_rejects_missing_section PASSED [ 89%]
tests/unit/test_load_lld_v2.py::TestExtractTestPlanSection::test_ignores_section_10_inside_code_fence PASSED [ 94%]
tests/unit/test_load_lld_v2.py::TestExtractTestPlanSection::test_extracted_content_is_stripped PASSED [100%]
ERROR: Coverage failure: total of 12 is less than fail-under=95


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
assemblyzero\workflows\testing\nodes\load_lld.py     360    316    12%   67-88, 105-140, 153, 226, 245-285, 302-350, 367-469, 474-475, 480-492, 497-508, 513-529, 546-558, 574-661, 681-762, 787-930, 950-1025
--------------------------------------------------------------------------------
TOTAL                                                360    316    12%
FAIL Required test coverage of 95% not reached. Total coverage: 12.22%
======================= 19 passed, 6 warnings in 2.29s ========================


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
