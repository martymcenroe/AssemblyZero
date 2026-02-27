"""Codebase retrieval system for RAG injection.

Issue #92: Codebase Retrieval System (RAG Injection)

Provides AST-based Python code parsing, keyword extraction from LLD content,
ChromaDB-backed vector retrieval, token budget management, and context
formatting for injection into code generation prompts.

All functions follow a fail-open pattern: errors are logged and empty
results returned, never raised to callers.
"""

from __future__ import annotations

import ast
import collections
import logging
import re

from pathlib import Path
from typing import Any, TypedDict


logger = logging.getLogger(__name__)


# chromadb is an optional [rag] dependency. We set a module-level sentinel
# so tests can mock.patch("assemblyzero.rag.codebase_retrieval.chromadb").
# The actual import happens lazily in query_codebase_collection().
chromadb: Any = None


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class CodeChunk(TypedDict):
    """A single extracted code entity from AST parsing."""

    content: str
    module_path: str
    entity_name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int


class RetrievalResult(TypedDict):
    """A scored retrieval result from vector store query."""

    chunk: CodeChunk
    relevance_score: float
    token_count: int


class CodebaseContext(TypedDict):
    """Formatted context ready for prompt injection."""

    formatted_text: str
    total_tokens: int
    chunks_included: int
    chunks_dropped: int
    keywords_used: list[str]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOKEN_BUDGET = 4096
DEFAULT_MAX_KEYWORDS = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.75
DEFAULT_MAX_RESULTS = 10

_DOMAIN_STOPWORDS: set[str] | None = None


# ---------------------------------------------------------------------------
# AST Parsing
# ---------------------------------------------------------------------------

def parse_python_file(file_path: str) -> list[CodeChunk]:
    """Parse a single Python file using ast module.

    Extracts public classes and top-level functions. Skips entities whose
    names start with ``_``. Returns ``[]`` on any parse or I/O error.
    """
    try:
        path = Path(file_path)
        source = path.read_text(encoding="utf-8")
    except (OSError, IOError) as exc:
        logger.warning("Failed to read %s: %s", file_path, exc)
        return []

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        logger.warning("Failed to parse %s: %s", file_path, exc)
        return []

    module_path = file_path_to_module_path(file_path)
    chunks: list[CodeChunk] = []

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        if node.name.startswith("_"):
            continue

        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        content = extract_node_source(source, node)

        chunks.append(
            CodeChunk(
                content=content,
                module_path=module_path,
                entity_name=node.name,
                kind=kind,
                file_path=file_path,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
            )
        )

    return chunks


def extract_node_source(source: str, node: ast.AST) -> str:
    """Extract the full source text for an AST node including decorators."""
    lines = source.splitlines()

    # Include decorator lines if present
    start = node.lineno - 1  # 0-indexed
    if hasattr(node, "decorator_list") and node.decorator_list:
        first_decorator = node.decorator_list[0]
        start = first_decorator.lineno - 1

    end = (node.end_lineno or node.lineno)  # 1-indexed inclusive
    return "\n".join(lines[start:end])


def file_path_to_module_path(file_path: str) -> str:
    """Convert file path to dotted module path.

    ``assemblyzero/core/audit.py`` -> ``assemblyzero.core.audit``
    ``assemblyzero/rag/__init__.py`` -> ``assemblyzero.rag``
    """
    path = file_path.replace("\\", "/")
    if path.endswith(".py"):
        path = path[:-3]
    if path.endswith("/__init__"):
        path = path[: -len("/__init__")]
    return path.replace("/", ".")


def scan_codebase(
    directories: list[str],
    file_pattern: str = "**/*.py",
) -> list[CodeChunk]:
    """Recursively scan directories for Python files and parse each."""
    all_chunks: list[CodeChunk] = []

    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.is_dir():
            logger.warning("Directory not found: %s", directory)
            continue

        for py_file in sorted(dir_path.glob(file_pattern)):
            if not py_file.is_file():
                continue
            chunks = parse_python_file(str(py_file))
            all_chunks.extend(chunks)

    return all_chunks


# ---------------------------------------------------------------------------
# Keyword Extraction
# ---------------------------------------------------------------------------

def get_domain_stopwords() -> set[str]:
    """Return domain-specific stopwords extending standard English stopwords."""
    global _DOMAIN_STOPWORDS  # noqa: PLW0603
    if _DOMAIN_STOPWORDS is not None:
        return _DOMAIN_STOPWORDS

    _DOMAIN_STOPWORDS = {
        # Standard English
        "the", "and", "for", "are", "but", "not", "you", "all", "any",
        "can", "had", "her", "was", "one", "our", "out", "has", "his",
        "how", "its", "may", "new", "now", "old", "see", "way", "who",
        "did", "get", "let", "say", "she", "too", "use", "from", "have",
        "been", "each", "when", "also", "into", "than", "other", "which",
        "their", "about", "would", "make", "like", "just", "over", "such",
        "after", "this", "that", "with", "will", "them",
        # Domain-specific (Python / programming)
        "implement", "create", "using", "should", "must", "system",
        "feature", "function", "method", "class", "module", "import",
        "return", "none", "true", "false", "self", "def", "str", "int",
        "list", "dict", "type", "file", "path", "data", "value", "name",
        "based", "need", "provide", "support", "update", "change",
        "ensure", "include", "require", "follow", "existing", "current",
        "section", "note", "issue", "proposed", "description",
    }
    return _DOMAIN_STOPWORDS


def split_compound_terms(text: str) -> list[str]:
    """Split CamelCase and snake_case terms, preserving originals."""
    parts: list[str] = []

    # CamelCase split
    camel_parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+", text)
    if len(camel_parts) > 1:
        parts.extend(camel_parts)
        parts.append(text)
        return parts

    # snake_case split
    if "_" in text:
        snake_parts = [p for p in text.split("_") if p]
        if len(snake_parts) > 1:
            parts.extend(snake_parts)
            parts.append(text)
            return parts

    parts.append(text)
    return parts


def extract_keywords(
    lld_content: str,
    max_keywords: int = DEFAULT_MAX_KEYWORDS,
    stopwords: set[str] | None = None,
) -> list[str]:
    """Extract top technical keywords from LLD content."""
    if not lld_content.strip():
        return []

    if stopwords is None:
        stopwords = get_domain_stopwords()

    # Tokenize
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", lld_content)

    # Expand compound terms
    expanded: list[str] = []
    for token in tokens:
        expanded.extend(split_compound_terms(token))

    # Filter stopwords and count
    counter: collections.Counter[str] = collections.Counter()
    for term in expanded:
        lower = term.lower()
        if lower not in stopwords and len(lower) > 2:
            # Preserve original case for CamelCase terms
            counter[term] += 1

    # Deduplicate by lowercase (keep first-seen casing)
    seen_lower: set[str] = set()
    unique_terms: list[tuple[str, int]] = []
    for term, count in counter.most_common():
        if term.lower() not in seen_lower:
            seen_lower.add(term.lower())
            unique_terms.append((term, count))

    if len(unique_terms) >= 2:
        return [term for term, _count in unique_terms[:max_keywords]]

    # Fallback: extract CamelCase identifiers
    camel_matches = re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", lld_content)
    if camel_matches:
        result: list[str] = []
        for match in camel_matches:
            if match not in result:
                result.append(match)
            # Also add split parts
            for part in re.findall(r"[A-Z][a-z]+", match):
                if part not in result and part.lower() not in stopwords:
                    result.append(part)
        return result[:max_keywords]

    return [term for term, _count in unique_terms[:max_keywords]]


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def query_codebase_collection(
    keywords: list[str],
    collection_name: str = "codebase",
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> list[RetrievalResult]:
    """Query ChromaDB codebase collection with keywords."""
    if not keywords:
        return []

    # Use the module-level chromadb attribute (may be set by mock.patch in tests)
    # or lazily import the real package.
    global chromadb  # noqa: PLW0603
    _chromadb = chromadb
    if _chromadb is None:
        try:
            import chromadb as _real_chromadb  # noqa: PLC0415

            chromadb = _real_chromadb
            _chromadb = _real_chromadb
        except ImportError:
            logger.warning("chromadb not installed; codebase retrieval unavailable")
            return []

    try:
        client = _chromadb.PersistentClient()
        collection = client.get_collection(name=collection_name)
    except Exception:
        logger.warning("Codebase collection '%s' not found", collection_name)
        return []

    query_text = " ".join(keywords)

    try:
        query_result = collection.query(
            query_texts=[query_text],
            n_results=max_results * 2,  # over-fetch for post-filtering
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.warning("ChromaDB query failed: %s", exc)
        return []

    documents = query_result.get("documents", [[]])[0]
    metadatas = query_result.get("metadatas", [[]])[0]
    distances = query_result.get("distances", [[]])[0]

    results: list[RetrievalResult] = []
    seen_modules: dict[str, int] = {}  # module_path -> index in results

    for doc, meta, dist in zip(documents, metadatas, distances):
        similarity = 1.0 / (1.0 + dist)
        if similarity < similarity_threshold:
            continue

        module_path = meta.get("module_path", "")
        token_count = estimate_token_count(doc)

        chunk = CodeChunk(
            content=doc,
            module_path=module_path,
            entity_name=meta.get("entity_name", ""),
            kind=meta.get("kind", ""),
            file_path=meta.get("file_path", ""),
            start_line=int(meta.get("start_line", 0)),
            end_line=int(meta.get("end_line", 0)),
        )

        result = RetrievalResult(
            chunk=chunk,
            relevance_score=similarity,
            token_count=token_count,
        )

        # Deduplicate by module_path -- keep highest score
        if module_path in seen_modules:
            existing_idx = seen_modules[module_path]
            if similarity > results[existing_idx]["relevance_score"]:
                results[existing_idx] = result
        else:
            seen_modules[module_path] = len(results)
            results.append(result)

    # Sort by relevance descending
    results.sort(key=lambda r: r["relevance_score"], reverse=True)

    return results[:max_results]


def estimate_token_count(text: str) -> int:
    """Estimate token count using tiktoken. Falls back to heuristic."""
    if not text:
        return 0

    try:
        import tiktoken  # noqa: PLC0415

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return int(len(text.split()) * 1.3)


# ---------------------------------------------------------------------------
# Token Budget Management
# ---------------------------------------------------------------------------

def apply_token_budget(
    results: list[RetrievalResult],
    max_tokens: int = DEFAULT_TOKEN_BUDGET,
) -> list[RetrievalResult]:
    """Apply token budget, dropping lowest-relevance whole chunks."""
    if not results:
        return []

    kept: list[RetrievalResult] = []
    accumulated = 0

    for result in results:
        cost = result["token_count"]
        if accumulated + cost > max_tokens and kept:
            # Budget exceeded and we already have at least one result
            break
        kept.append(result)
        accumulated += cost

    return kept


# ---------------------------------------------------------------------------
# Context Formatting
# ---------------------------------------------------------------------------

def format_codebase_context(
    results: list[RetrievalResult],
    keywords_used: list[str] | None = None,
) -> CodebaseContext:
    """Format retrieval results into markdown for prompt injection."""
    if not results:
        return CodebaseContext(
            formatted_text="",
            total_tokens=0,
            chunks_included=0,
            chunks_dropped=0,
            keywords_used=keywords_used or [],
        )

    sections: list[str] = [
        "## Reference Codebase",
        "Use these existing utilities. DO NOT reinvent them.",
        "",
    ]

    total_tokens = 0
    for result in results:
        chunk = result["chunk"]
        sections.append(f"### [Source: {chunk['file_path']}]")
        sections.append("```python")
        sections.append(chunk["content"])
        sections.append("```")
        sections.append("")
        total_tokens += result["token_count"]

    formatted_text = "\n".join(sections)

    return CodebaseContext(
        formatted_text=formatted_text,
        total_tokens=total_tokens,
        chunks_included=len(results),
        chunks_dropped=0,
        keywords_used=keywords_used or [],
    )


# ---------------------------------------------------------------------------
# Top-Level Orchestration
# ---------------------------------------------------------------------------

def retrieve_codebase_context(
    lld_content: str,
    max_keywords: int = DEFAULT_MAX_KEYWORDS,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_results: int = DEFAULT_MAX_RESULTS,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> CodebaseContext:
    """End-to-end: extract keywords, retrieve code, format for injection."""
    keywords = extract_keywords(lld_content, max_keywords=max_keywords)

    if not keywords:
        logger.debug("No keywords extracted from LLD content")
        return CodebaseContext(
            formatted_text="",
            total_tokens=0,
            chunks_included=0,
            chunks_dropped=0,
            keywords_used=[],
        )

    results = query_codebase_collection(
        keywords,
        similarity_threshold=similarity_threshold,
        max_results=max_results,
    )

    total_before = len(results)
    results = apply_token_budget(results, max_tokens=token_budget)
    dropped = total_before - len(results)

    context = format_codebase_context(results, keywords_used=keywords)
    # Override chunks_dropped with actual count
    context["chunks_dropped"] = dropped

    if context["chunks_included"] > 0:
        logger.info(
            "Codebase context: %d chunks, %d tokens, keywords=%s",
            context["chunks_included"],
            context["total_tokens"],
            keywords,
        )
    else:
        logger.debug("No codebase matches for keywords: %s", keywords)

    return context
