

```python
"""Conditional import checker for RAG optional dependencies.

Issue #88: The Librarian - Automated Context Retrieval

Provides friendly error messages when chromadb or sentence-transformers
are not installed. This module itself has zero external dependencies.
"""

from __future__ import annotations

_INSTALL_MSG = "RAG dependencies not installed. Install with: pip install assemblyzero[rag]"


def check_rag_dependencies() -> tuple[bool, str]:
    """Check if RAG optional dependencies (chromadb, sentence-transformers) are installed.

    Returns:
        Tuple of (available: bool, message: str). If not available,
        message contains user-friendly installation instructions.
    """
    missing = []

    try:
        import chromadb  # noqa: F401
    except ImportError:
        missing.append("chromadb")

    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        missing.append("sentence-transformers")

    if missing:
        names = ", ".join(missing)
        return (
            False,
            f"Missing: {names}. Install with: pip install assemblyzero[rag]",
        )

    return (True, "RAG dependencies available")


def require_rag_dependencies() -> None:
    """Raise ImportError with friendly message if RAG dependencies unavailable."""
    available, message = check_rag_dependencies()
    if not available:
        raise ImportError(message)
```
