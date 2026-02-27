

```python
"""LLD workflow graph with Librarian RAG node.

Issue #88: The Librarian - Automated Context Retrieval

Graph topology:
    START -> check_rag -> librarian_node (if available) -> END
                       -> skip_rag (if unavailable) -> END

This is a focused sub-workflow for RAG context retrieval.
It can be composed into larger LLD generation workflows.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from assemblyzero.nodes.librarian import librarian_node
from assemblyzero.rag.dependencies import check_rag_dependencies
from assemblyzero.workflows.lld.state import LLDState


def _check_rag_available(state: dict) -> str:
    """Conditional edge: check if RAG is available."""
    available, _ = check_rag_dependencies()
    if not available:
        return "skip_rag"
    return "librarian"


def _skip_rag_node(state: dict) -> dict:
    """No-op node when RAG is unavailable. Sets status for downstream."""
    return {
        "retrieved_context": [],
        "rag_status": "deps_missing",
    }


def build_lld_graph() -> StateGraph:
    """Build the LLD workflow graph with Librarian RAG node.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(LLDState)

    # Add nodes
    graph.add_node("librarian", librarian_node)
    graph.add_node("skip_rag", _skip_rag_node)

    # Set entry point with conditional routing
    graph.set_conditional_entry_point(
        _check_rag_available,
        {
            "librarian": "librarian",
            "skip_rag": "skip_rag",
        },
    )

    # Both paths lead to END
    graph.add_edge("librarian", END)
    graph.add_edge("skip_rag", END)

    return graph.compile()
```
