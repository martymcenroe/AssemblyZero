# 148 - Feature: AssemblyZero v2 Foundation - Dependencies & State Definition

## 1. Context & Goal
* **Issue:** #48
* **Objective:** Establish foundational dependencies and state definition for LangGraph-based orchestration
* **Status:** Draft
* **Related Issues:** None (this is Issue 1 of v2 roadmap)

### Open Questions
*None - this is a straightforward foundation ticket.*

## 2. Proposed Changes

### 2.1 Dependencies (pyproject.toml)

Add via Poetry:
```toml
[tool.poetry.dependencies]
langgraph = "^0.2.0"
langchain = "^0.3.0"
langchain-google-genai = "^2.0.0"
langchain-anthropic = "^0.3.0"
```

### 2.2 Directory Structure

```
assemblyzero/
├── __init__.py
├── core/
│   ├── __init__.py
│   └── state.py          # AgentState TypedDict
├── nodes/
│   └── __init__.py       # Future: governance nodes
└── graphs/
    └── __init__.py       # Future: compiled workflows
```

### 2.3 State Definition (assemblyzero/core/state.py)

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """Core state shared across all AssemblyZero LangGraph nodes."""

    # Standard LangGraph message accumulator
    messages: Annotated[list[BaseMessage], add_messages]

    # Issue tracking
    issue_id: int
    worktree_path: str

    # LLD governance
    lld_content: str
    lld_status: Literal["PENDING", "APPROVED", "BLOCKED"]

    # Gemini feedback
    gemini_critique: str

    # Safety: loop prevention
    iteration_count: int
```

## 3. Requirements

1. LangGraph and LangChain dependencies installed via Poetry
2. Directory structure for `assemblyzero/` module created
3. `AgentState` TypedDict defined with governance-relevant fields
4. Code passes mypy type checking
5. No business logic - structure only

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| TypedDict state | Type-safe, LangGraph native, IDE support | Less flexible than dict | **Selected** |
| Plain dict state | Flexible, no typing overhead | No type safety, easy to introduce bugs | Rejected |
| Pydantic model | Validation, serialization | Heavier dependency, not LangGraph native | Rejected |

**Rationale:** TypedDict is the LangGraph standard and provides type safety without runtime overhead.

## 5. Data & Fixtures

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | N/A - this issue defines types only |
| Format | N/A |
| Size | N/A |
| Refresh | N/A |
| Copyright/License | N/A |

### 5.2 Data Pipeline

N/A - no data processing in this issue.

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| N/A | N/A | No test fixtures needed - mypy validates types |

### 5.4 Deployment Pipeline

N/A - this is a library module, not a deployed service.

## 6. Diagram

### 6.1 Mermaid Quality Gate

N/A - simple module structure doesn't require a diagram.

### 6.2 Diagram

```
assemblyzero/
├── __init__.py
├── core/
│   ├── __init__.py
│   └── state.py          # AgentState TypedDict
├── nodes/
│   └── __init__.py       # Future: governance nodes
└── graphs/
    └── __init__.py       # Future: compiled workflows
```

## 7. Technical Approach

* **Module:** `assemblyzero/`
* **Dependencies:** langgraph, langchain, langchain-google-genai, langchain-anthropic
* **Pattern:** LangGraph state machine with TypedDict state

## 8. Interface Specification

### 8.1 Data Structures

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """Core state shared across all AssemblyZero LangGraph nodes."""

    # Standard LangGraph message accumulator
    messages: Annotated[list[BaseMessage], add_messages]

    # Issue tracking
    issue_id: int
    worktree_path: str

    # LLD governance
    lld_content: str
    lld_status: Literal["PENDING", "APPROVED", "BLOCKED"]

    # Gemini feedback
    gemini_critique: str

    # Safety: loop prevention
    iteration_count: int
```

### 8.2 Function Signatures

N/A - this issue defines types only, no functions.

### 8.3 Logic Flow (Pseudocode)

N/A - no business logic in this issue.

## 9. Security Considerations

| Concern | Mitigation | Status |
|---------|------------|--------|
| N/A | N/A | N/A |

**Fail Mode:** N/A - this issue defines types only.

## 10. Performance Considerations

| Metric | Budget | Approach |
|--------|--------|----------|
| N/A | N/A | N/A |

**Bottlenecks:** None - TypedDict has zero runtime overhead.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Dependency version conflicts | Med | Low | Use Poetry lock file, test install on clean env |
| State schema needs changes later | Low | Med | TypedDict is easy to extend, document schema versioning strategy |

## 12. Verification & Testing

### 12.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Import state module | Auto | `from assemblyzero.core.state import AgentState` | No import error | Import succeeds |
| 020 | mypy type check | Auto | `mypy assemblyzero/` | Exit code 0 | No type errors |
| 030 | Poetry install clean | Auto | `poetry install` on clean env | Exit code 0 | No dependency conflicts |

### 12.2 Test Commands

```bash
# Verify import works
python -c "from assemblyzero.core.state import AgentState; print('OK')"

# Run mypy
poetry run mypy assemblyzero/

# Clean install test (in CI or fresh venv)
poetry install
```

### 12.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.

## 13. Definition of Done

### Code
- [ ] `assemblyzero/` directory structure created
- [ ] `assemblyzero/core/state.py` contains AgentState TypedDict
- [ ] All `__init__.py` files present

### Tests
- [ ] `mypy assemblyzero/` passes with no errors
- [ ] Import test passes

### Documentation
- [ ] LLD approved (this document)
- [ ] Implementation Report completed

### Review
- [ ] Code review completed (via PR)
- [ ] Merged to main

---

## Appendix: Review Log

### Gemini Review #1 (APPROVED)

**Timestamp:** 2026-01-22 14:30 CT
**Reviewer:** Gemini 3 Pro
**Verdict:** APPROVED

#### Comments

| ID | Comment | Implemented? |
|----|---------|--------------|
| G1.1 | "Consider adding a `metadata: dict` field to `AgentState` for future proofing" | PENDING - Tier 3 suggestion, will evaluate |
| G1.2 | "Ensure `poetry.lock` is committed" | PENDING - will commit during implementation |

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Gemini #1 | 2026-01-22 | APPROVED | No blocking issues |

**Final Status:** APPROVED
