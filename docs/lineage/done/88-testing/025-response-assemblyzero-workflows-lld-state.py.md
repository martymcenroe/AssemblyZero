

```python
"""LLD workflow State schema with RAG augmentation fields.

Issue #88: The Librarian - Automated Context Retrieval
"""

from __future__ import annotations

from typing import TypedDict


class LLDState(TypedDict):
    """State schema for the LLD workflow with RAG augmentation."""

    issue_brief: str
    manual_context_paths: list[str]
    retrieved_context: list[dict]
    rag_status: str
    designer_output: str
```
