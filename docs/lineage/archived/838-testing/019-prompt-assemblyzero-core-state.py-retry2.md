# Implementation Request: assemblyzero/core/state.py

## Task

Write the complete contents of `assemblyzero/core/state.py`.

Change type: Modify
Description: Add `workspace_ctx` field to `AgentState`

## Existing File Contents

The file currently contains:

```python
"""Core state definition for AssemblyZero LangGraph workflows.

This module defines the AgentState TypedDict that travels through
the governance pipeline: Issue -> LLD Review -> Implementation -> Code Review -> Merge
"""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Core state shared across all AssemblyZero LangGraph nodes.

    Attributes:
        messages: Standard LangGraph message accumulator with add_messages annotation.
        issue_id: GitHub issue number being worked on.
        worktree_path: Path to the git worktree for this issue.
        lld_content: Full content of the Low-Level Design document.
        lld_status: Current approval status of the LLD.
        lld_draft_path: Path to LLD draft file on disk (Designer Node output).
        design_status: Designer Node outcome status.
        gemini_critique: Feedback from Gemini verification layer.
        iteration_count: Safety counter for loop prevention.
    """

    # Standard LangGraph message accumulator
    messages: Annotated[list[BaseMessage], add_messages]

    # Issue tracking
    issue_id: int
    worktree_path: str

    # LLD governance
    lld_content: str
    lld_status: Literal["PENDING", "APPROVED", "BLOCKED"]

    # Designer Node output (Issue #56)
    lld_draft_path: str
    design_status: Literal["PENDING", "DRAFTED", "FAILED"]

    # Gemini feedback
    gemini_critique: str

    # Safety: loop prevention
    iteration_count: int


class TDDState(TypedDict):
    """State for TDD workflow tracking.

    Attributes:
        issue_number: Issue being worked on.
        phase: Current TDD phase.
        test_file_path: Canonical path to test file (Issue #311).
        test_file_history: Track if file was moved (Issue #311).
        implementation_file_path: Path to implementation.
        last_verification_result: Result of last verification run.
    """

    issue_number: int
    phase: Literal["scaffold", "red", "green", "refactor"]
    test_file_path: str | None
    test_file_history: list[str]
    implementation_file_path: str | None
    last_verification_result: dict | None


class _TestFileLocation(TypedDict):
    """Record of a test file location at a point in time.

    Attributes:
        path: Absolute or project-relative path.
        created_at: ISO timestamp.
        created_by_phase: Phase that created/moved to this location.
        moved_from: Previous path if relocated, None if initial creation.
    """

    path: str
    created_at: str
    created_by_phase: str
    moved_from: str | None
```

Modify this file according to the LLD specification.



## Previous Attempt Failed (Attempt 2/2)

Your previous response had an error:

```
Validation failed: Unresolvable imports: langchain_core.messages (line 9), langgraph.graph.message (line 10)
```

Please fix this issue and provide the corrected, complete file contents.
IMPORTANT: Output the ENTIRE file, not just the fix.

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
