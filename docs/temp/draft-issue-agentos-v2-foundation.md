# Draft Issue: AssemblyZero v2 Foundation - Dependencies & State Definition

**For Gemini Review via 0701c (Issue Review Prompt)**

---

## User Story

As an **AssemblyZero developer**, I want to establish the foundational dependencies and state definition for LangGraph-based orchestration, so that subsequent issues can build governance nodes on a stable, typed foundation.

---

## Context

AssemblyZero is being refactored from a prompt-based orchestration system to a **LangGraph-based system** that enforces governance programmatically. This is Issue 1 of the v2 roadmap.

**Current State:** Prompt-based gates in CLAUDE.md (can be bypassed)
**Target State:** LangGraph state machines with enforced transitions (cannot be bypassed)

This issue establishes:
1. The Python dependencies required for LangGraph
2. The directory structure for the new architecture
3. The core state definition that all nodes will share

---

## Proposed Changes

### 1. Dependencies (pyproject.toml)

Add via Poetry:
```
langgraph >= 0.2.0
langchain >= 0.3.0
langchain-google-genai >= 2.0.0
langchain-anthropic >= 0.3.0
```

### 2. Directory Structure

```
assemblyzero/
├── __init__.py
├── core/
│   ├── __init__.py
│   └── state.py          # AgentState TypedDict
├── nodes/
│   └── __init__.py       # Future: LLD review, implementation review nodes
└── graphs/
    └── __init__.py       # Future: Compiled LangGraph workflows
```

### 3. State Definition (assemblyzero/core/state.py)

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    Core state shared across all AssemblyZero LangGraph nodes.

    This state travels through the governance pipeline:
    Issue -> LLD Review -> Implementation -> Code Review -> Merge
    """
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

---

## Acceptance Criteria

- [ ] `poetry install` runs cleanly with no dependency conflicts
- [ ] `assemblyzero/` directory structure exists with `__init__.py` files
- [ ] `AgentState` is defined in `assemblyzero/core/state.py`
- [ ] `AgentState` uses proper typing (`TypedDict`, `Annotated`, `Literal`)
- [ ] `messages` field uses LangGraph's `add_messages` annotation
- [ ] `lld_status` is constrained to valid enum values
- [ ] `iteration_count` exists for loop prevention
- [ ] Code passes `mypy` type checking (no errors)
- [ ] No business logic implemented (structure only)

---

## Definition of Done

- [ ] All acceptance criteria met
- [ ] `poetry install` succeeds on clean environment
- [ ] `python -c "from assemblyzero.core.state import AgentState"` succeeds
- [ ] `mypy assemblyzero/` passes with no errors
- [ ] PR created and approved
- [ ] Merged to main

---

## Dependencies

- **Blocked by:** None (this is Issue 1)
- **Blocks:** All subsequent LangGraph issues (nodes, graphs, governance enforcement)

---

## Risk Assessment

### Privacy & Data Residency
- **N/A** - This issue defines types only, no data processing

### Cost Impact
- **LOW** - Adding dependencies increases install size slightly
- No infrastructure costs
- No API calls in this issue

### Safety/Friction
- **N/A** - No new permission prompts introduced
- No agent behavior changes

### License Compliance
- `langgraph`: MIT License ✓
- `langchain`: MIT License ✓
- `langchain-google-genai`: MIT License ✓
- `langchain-anthropic`: MIT License ✓

---

## Effort Estimate

**T-Shirt Size:** S (Small)

- Straightforward dependency additions
- Simple directory creation
- Single TypedDict definition
- No complex logic

---

## Labels

- `foundation`
- `langgraph`
- `v2.0`
- `no-code-review` (structure only, no logic to review)

---

## Notes for Reviewer

This issue intentionally has **no business logic**. It establishes:
1. That we can import LangGraph
2. That our state is properly typed
3. That subsequent issues have a foundation to build on

The `AgentState` fields map to our Golden Schema gates:
- `lld_status` → 0702c LLD Review outcome
- `gemini_critique` → Feedback from Gemini verification layer
- `iteration_count` → Cost/Safety protection against runaway loops
