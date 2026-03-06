# Implementation Request: assemblyzero/nodes/document_assembler.py

## Task

Write the complete contents of `assemblyzero/nodes/document_assembler.py`.

Change type: Add
Description: Core utility regex stripping and base formatting logic.

## LLD Specification

# Implementation Spec: Feature: Mechanical Document Assembly Node

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #607 |
| LLD | `docs/lld/active/607-mechanical-document-assembly.md` |
| Generated | 2026-03-06 |
| Status | APPROVED |

## 1. Overview

**Objective:** Transition from LLM-generated documents to Code-assembled documents to eliminate "Section Number Drift" and ensure 100% template compliance.

**Success Criteria:** The system mechanically concatenates predefined template headers with LLM-generated content, successfully stripping out any hallucinated headers from the LLM response. Retries are constrained to individual sections (max 3 attempts) rather than the entire document.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/nodes/document_assembler.py` | Add | Core utility regex stripping and base formatting logic. |
| 2 | `assemblyzero/workflows/lld/templates.py` | Add | Hardcoded Python data structures defining the LLD structural sections. |
| 3 | `assemblyzero/workflows/lld/nodes/assembly_node.py` | Add | LangGraph node executing sequential section generation with retries. |
| 4 | `assemblyzero/workflows/lld/__init__.py` | Modify | Export the newly created `assemble_document_node`. |
| 5 | `tests/unit/test_document_assembler.py` | Add | Unit tests for regex stripping, template compliance, and retry boundaries. |

**Implementation Order Rationale:** Utilities and templates must be built first as they are imported by the LangGraph node. The node is then exported, and finally tests validate the entire assembly flow.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/lld/__init__.py`

**Relevant excerpt** (lines 1-5):

```python
"""LLD workflow with Librarian RAG augmentation.

Issue #88: The Librarian - Automated Context Retrieval
"""
```

**What changes:** Add the import and export of the new `assemble_document_node` so the node can be wired into the main LangGraph state machine.

## 4. Data Structures

### 4.1 `SectionTemplate`

**Definition:**

```python
class SectionTemplate(TypedDict):
    id: str
    header: str
    prompt_instruction: str
    dependencies: list[str]
```

**Concrete Example:**

```json
{
    "id": "section_2",
    "header": "## 2. Proposed Changes",
    "prompt_instruction": "Describe exactly what will be built based on the issue description.",
    "dependencies": ["section_1"]
}
```

### 4.2 `CompletedSection`

**Definition:**

```python
class CompletedSection(TypedDict):
    id: str
    header: str
    content: str
    attempts: int
```

**Concrete Example:**

```json
{
    "id": "section_2",
    "header": "## 2. Proposed Changes",
    "content": "The system will implement a mechanical assembly pipeline...",
    "attempts": 1
}
```

## 5. Function Specifications

### 5.1 `strip_hallucinated_headers()`

**File:** `assemblyzero/nodes/document_assembler.py`

**Signature:**

```python
def strip_hallucinated_headers(content: str, expected_header: str) -> str:
    """Removes hallucinated markdown headers from LLM output using resilient regex."""
    ...
```

**Input Example:**

```python
content = "### 2. Proposed Changes\n**2. Proposed Changes**\nHere is the actual content for the section."
expected_header = "2. Proposed Changes"
```

**Output Example:**

```python
"Here is the actual content for the section."
```

**Edge Cases:**
- `content` doesn't contain the header -> returns `content.strip()`.
- `content` contains minor variations (e.g., extra `#`, bold `**`) -> successfully strips them and returns pure content.

### 5.2 `assemble_document_node()`

**File:** `assemblyzero/workflows/lld/nodes/assembly_node.py`

**Signature:**

```python
def assemble_document_node(state: Any) -> dict[str, Any]:
    """LangGraph node to sequentially generate and mechanically assemble document sections."""
    ...
```

**Input Example:**

```python
state = {
    "issue_context": "We need to fix section drift in LLDs by doing mechanical assembly.",
    "completed_sections": [
        {"id": "section_1", "header": "## 1. Context & Goal", "content": "Fix section drift.", "attempts": 1}
    ]
}
```

**Output Example:**

```python
{
    "completed_sections": [
        {"id": "section_1", "header": "## 1. Context & Goal", "content": "Fix section drift.", "attempts": 1},
        {"id": "section_2", "header": "## 2. Proposed Changes", "content": "Mechanically assemble via Python.", "attempts": 2}
    ],
    "final_document": "## 1. Context & Goal\n\nFix section drift.\n\n## 2. Proposed Changes\n\nMechanically assemble via Python.\n",
    "error_message": ""
}
```

**Edge Cases:**
- Section fails 3 times -> Raises `AssemblyError("Failed to generate section_X after 3 attempts")`.
- `completed_sections` already contains all template sections -> Immediately skips LLM calls and performs mechanical concatenation.

## 6. Change Instructions

### 6.1 `assemblyzero/nodes/document_assembler.py` (Add)

**Complete file contents:**

```python
"""Mechanical document assembly utilities.

Issue #607: Mechanical Document Assembly Node
"""
import re

class AssemblyError(Exception):
    """Raised when document assembly fails critical constraints."""
    pass

def strip_hallucinated_headers(content: str, expected_header: str) -> str:
    """
    Removes hallucinated markdown headers from LLM output.
    Handles extra whitespace, multiple # signs, and bold asterisks.
    """
    if not content or not expected_header:
        return content

    # Clean the expected header of any markdown for the regex matching base
    clean_expected = re.sub(r'^#+\s*', '', expected_header).replace('*', '').strip()
    
    # Regex breakdown:
    # ^\s*                - Leading whitespace
    # #*                  - Optional markdown hash symbols
    # \s*                 - Optional whitespace
    # (?:\*\*)?           - Optional bold markdown
    # {clean_expected}    - The actual text (escaped)
    # (?:\*\*)?           - Optional trailing bold markdown
    # \s*                 - Optional trailing whitespace
    # \n*                 - Any trailing newlines
    escaped_text = re.escape(clean_expected)
    pattern = re.compile(
        rf"^\s*#*\s*(?:\*\*)?{escaped_text}(?:\*\*)?\s*\n*",
        re.IGNORECASE
    )
    
    # Strip from the beginning of the string
    cleaned = re.sub(pattern, '', content.lstrip())
    return cleaned.strip()

def assemble_final_document(completed_sections: list[dict]) -> str:
    """Mechanically concatenates headers and cleaned contents."""
    parts = []
    for sec in completed_sections:
        parts.append(f"{sec['header']}\n\n{sec['content']}")
    return "\n\n".join(parts) + "\n"
```

### 6.2 `assemblyzero/workflows/lld/templates.py` (Add)

**Complete file contents:**

```python
"""LLD template structures for mechanical assembly.

Issue #607: Mechanical Document Assembly Node
"""
from typing import TypedDict

class SectionTemplate(TypedDict):
    id: str
    header: str
    prompt_instruction: str

LLD_TEMPLATE: list[SectionTemplate] = [
    {
        "id": "context",
        "header": "## 1. Context & Goal",
        "prompt_instruction": "Summarize the objective based on the issue description. Do NOT output the section header, just provide the content."
    },
    {
        "id": "changes",
        "header": "## 2. Proposed Changes",
        "prompt_instruction": "Describe exactly what will be built. Detail file changes and paths. Do NOT output the section header, just provide the content."
    },
    {
        "id": "requirements",
        "header": "## 3. Requirements",
        "prompt_instruction": "List the functional and non-functional requirements. Do NOT output the section header, just provide the content."
    }
]
```

### 6.3 `assemblyzero/workflows/lld/nodes/assembly_node.py` (Add)

**Complete file contents:**

```python
"""Assembly node for sequential LLD generation.

Issue #607: Mechanical Document Assembly Node
"""
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from assemblyzero.nodes.document_assembler import (
    strip_hallucinated_headers, 
    assemble_final_document,
    AssemblyError
)
from assemblyzero.workflows.lld.templates import LLD_TEMPLATE

def assemble_document_node(state: dict[str, Any]) -> dict[str, Any]:
    """Executes sequential mechanical document assembly."""
    issue_context = state.get("issue_context", "")
    completed_sections = state.get("completed_sections", [])
    
    # Create map for quick lookup
    completed_ids = {sec["id"]: sec for sec in completed_sections}
    new_completed = list(completed_sections)
    
    llm = ChatAnthropic(model="claude-3-7-sonnet-20250219", temperature=0.2)
    
    for section_tmpl in LLD_TEMPLATE:
        sec_id = section_tmpl["id"]
        if sec_id in completed_ids:
            continue
            
        attempts = 0
        success = False
        
        # Build context from previously completed sections
        prior_context = "\n\n".join(
            [f"{s['header']}\n{s['content']}" for s in new_completed]
        )
        
        while attempts < 3 and not success:
            attempts += 1
            try:
                sys_msg = SystemMessage(
                    content="You are a senior technical architect writing a Low-Level Design (LLD)."
                )
                human_msg = HumanMessage(
                    content=(
                        f"Issue Context:\n{issue_context}\n\n"
                        f"Previous Sections:\n{prior_context}\n\n"
                        f"Task: {section_tmpl['prompt_instruction']}\n"
                        f"Current Section: {section_tmpl['header']}\n"
                    )
                )
                
                response = llm.invoke([sys_msg, human_msg])
                raw_content = str(response.content)
                
                # Strip hallucinated headers mechanically
                cleaned_content = strip_hallucinated_headers(
                    raw_content, 
                    section_tmpl["header"]
                )
                
                new_completed.append({
                    "id": sec_id,
                    "header": section_tmpl["header"],
                    "content": cleaned_content,
                    "attempts": attempts
                })
                success = True
                print(f"[N_Assembly] Generated section: {sec_id} (Attempt {attempts})")
                
            except Exception as e:
                print(f"[N_Assembly] Error on {sec_id} attempt {attempts}: {e}")
                if attempts >= 3:
                    raise AssemblyError(f"Failed to generate {sec_id} after 3 attempts.") from e

    final_document = assemble_final_document(new_completed)
    
    return {
        "completed_sections": new_completed,
        "final_document": final_document,
        "error_message": ""
    }
```

### 6.4 `assemblyzero/workflows/lld/__init__.py` (Modify)

**Change 1:** Add import and export for the assembly node at lines 5-6.

```diff
 """LLD workflow with Librarian RAG augmentation.
 
 Issue #88: The Librarian - Automated Context Retrieval
 """
+
+from assemblyzero.workflows.lld.nodes.assembly_node import assemble_document_node
+
+__all__ = ["assemble_document_node"]
```

### 6.5 `tests/unit/test_document_assembler.py` (Add)

**Complete file contents:**

```python
"""Tests for mechanical document assembly.

Issue #607: Mechanical Document Assembly Node
"""
import pytest
from assemblyzero.nodes.document_assembler import (
    strip_hallucinated_headers,
    assemble_final_document,
    AssemblyError
)

def test_strip_hallucinated_headers_exact_match():
    """T040: Regex strips exact hallucinated headers."""
    content = "## 2. Proposed Changes\n\nThis is the content."
    expected = "## 2. Proposed Changes"
    result = strip_hallucinated_headers(content, expected)
    assert result == "This is the content."

def test_strip_hallucinated_headers_variations():
    """T040: Regex strips hallucinated headers with asterisks and whitespace."""
    content = "  ### **2. Proposed Changes**  \n\nContent here."
    expected = "## 2. Proposed Changes"
    result = strip_hallucinated_headers(content, expected)
    assert result == "Content here."

def test_strip_hallucinated_headers_no_match():
    """T040: Content without hallucinated header remains intact."""
    content = "This content starts directly without a header."
    expected = "## 2. Proposed Changes"
    result = strip_hallucinated_headers(content, expected)
    assert result == "This content starts directly without a header."

def test_assemble_final_document_no_drift():
    """T010: Assembled document exactly matches template headers without drift."""
    sections = [
        {"id": "1", "header": "## 1. Context", "content": "Context details."},
        {"id": "2", "header": "## 2. Changes", "content": "Change details."}
    ]
    result = assemble_final_document(sections)
    expected = "## 1. Context\n\nContext details.\n\n## 2. Changes\n\nChange details.\n"
    assert result == expected
```

## 7. Pattern References

### 7.1 Node Implementation Pattern

**File:** `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py` (lines 1-50)

```python
# Reference for State returning pattern and LLM invocation
def generate_spec(state: ImplementationState) -> dict[str, Any]:
    """Generates the implementation spec."""
    llm = ChatAnthropic(model="claude-3-7-sonnet-20250219")
    # State update dictionaries are returned
    return {"spec_draft": response.content, "error_message": ""}
```

**Relevance:** The `assemble_document_node` mirrors this pattern by retrieving LLM instances, passing structured messages, and returning a dictionary matching the state schema containing `completed_sections`, `final_document`, and `error_message`.

### 7.2 Mocking LLM responses for State Validation

**File:** `tests/e2e/test_lld_workflow_mock.py` (lines 1-80)

**Relevance:** Indicates the testing paradigm where the unit test covers the raw logic (string manipulation, assembly concatenation), isolating the Langchain LLM invocations to separate E2E or mock integrations.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import re` | stdlib | `document_assembler.py` |
| `from typing import Any, TypedDict` | stdlib | `templates.py`, `assembly_node.py` |
| `from langchain_core.messages import HumanMessage, SystemMessage` | `langchain-core` | `assembly_node.py` |
| `from langchain_anthropic import ChatAnthropic` | `langchain-anthropic` | `assembly_node.py` |
| `import pytest` | `pytest` | `test_document_assembler.py` |

**New Dependencies:** None (utilizes existing `langchain-anthropic` and standard library).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `assemble_final_document()` | `[{"header": "## 1", "content": "text"}]` | `"## 1\n\ntext\n"` |
| T020 | `assemble_document_node()` | Mocked 3x failure in `ChatAnthropic` | Raises `AssemblyError` |
| T030 | `assemble_document_node()` | `completed_sections=[...]` | Prior context included in prompt string |
| T040 | `strip_hallucinated_headers()` | `content="**2. Target**\nText"`, `header="2. Target"` | `"Text"` |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All node errors related to API or structural failures must be caught. If retries exhaust the max limit (`MAX_ITERATIONS = 3`), the node explicitly raises `AssemblyError` to fail securely and block the workflow from emitting malformed code.

### 11.2 Logging Convention

Use `print()` statements prefixed with `[N_Assembly]` to output retry statuses. Example: `print("[N_Assembly] Generated section: context (Attempt 1)")`.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `MAX_ATTEMPTS` | `3` | Balance between handling transient model refusals and preventing infinite loops in the LangGraph step. |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #607 |
| Verdict | APPROVED |
| Date | 2026-03-06 |
| Iterations | 0 |
| Finalized | 2026-03-06T07:58:47Z |

### Review Feedback Summary

The implementation spec is exceptionally well-prepared. It provides complete, copy-pasteable code implementations for all new files and precise diffs for modifications. The regex logic, test cases, and edge-case handling are explicitly defined, making it highly executable for an autonomous AI agent with a near 100% chance of first-try success.

## Suggestions
- Consider including the 'CompletedSection' TypedDict defined in Section 4.2 within the actual 'templates.py' or 'assembly_node.py' file i...


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
  hourglass/
  unleashed/
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero-607\tests\test_issue_607.py
"""Test file for Issue #607.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from assemblyzero.nodes.document_assembler import *  # noqa: F401, F403


# Fixtures for mocking
@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    # TODO: Implement mock
    yield None


# Unit Tests
# -----------

def test_t010():
    """
    `assemble_final_document()` | `[{"header": "## 1", "content":
    "text"}]` | `"## 1\n\ntext\n"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t010 works correctly
    assert False, 'TDD RED: test_t010 not implemented'


def test_t020(mock_external_service):
    """
    `assemble_document_node()` | Mocked 3x failure in `ChatAnthropic` |
    Raises `AssemblyError`
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
    `assemble_document_node()` | `completed_sections=[...]` | Prior
    context included in prompt string
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
    `strip_hallucinated_headers()` | `content="**2. Target**\nText"`,
    `header="2. Target"` | `"Text"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t040 works correctly
    assert False, 'TDD RED: test_t040 not implemented'




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
