# Implementation Request: tests/fixtures/rag/sample_module.py

## Task

Write the complete contents of `tests/fixtures/rag/sample_module.py`.

Change type: Add
Description: Sample Python file for AST parsing tests

## LLD Specification

# Implementation Spec: Codebase Retrieval System (RAG Injection)

| Field | Value |
|-------|-------|
| Issue | #92 |
| LLD | `docs/lld/active/092-codebase-retrieval-rag-injection.md` |
| Generated | 2026-02-27 |
| Status | DRAFT |


## 1. Overview

**Objective:** Implement a codebase retrieval system that indexes Python code via AST parsing and injects relevant function signatures into the Coder Node's context before code generation, eliminating hallucinated imports and reinvented utilities.

**Success Criteria:** Python files are AST-parsed into code chunks, stored in a ChromaDB `codebase` collection with local embeddings, and relevant chunks are retrieved via keyword extraction from LLD content and injected into the N3_Coder prompt within a 4096-token budget. All operations fail open — retrieval failures never block code generation.


## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/fixtures/rag/sample_module.py` | Add | Sample Python file for AST parsing tests |
| 2 | `tests/fixtures/rag/sample_module_malformed.py` | Add | Malformed Python file for error handling tests |
| 3 | `tests/fixtures/rag/sample_lld_audit.md` | Add | Sample LLD mentioning audit logging for integration tests |
| 4 | `assemblyzero/rag/codebase_retrieval.py` | Add | Core module: AST parser, keyword extractor, retrieval engine, context formatter |
| 5 | `assemblyzero/rag/__init__.py` | Modify | Add codebase_retrieval exports to existing RAG package init |
| 6 | `assemblyzero/workflows/implementation_spec/nodes/coder_node.py` | Add | New node module providing `inject_codebase_context` for N3_Coder prompt construction |
| 7 | `tools/rebuild_knowledge_base.py` | Modify | Add `--collection codebase` support with AST-based Python code parsing |
| 8 | `tests/unit/test_rag/test_codebase_retrieval.py` | Add | Unit tests for all codebase retrieval functionality |

**Implementation Order Rationale:** Fixtures first (no deps), then the core module (no internal deps), then init exports (depends on core module), then the integration node (depends on core module), then CLI tool modifications (depends on core module), and finally tests (depend on everything).


## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/rag/__init__.py`

**Relevant excerpt** (full file):

```python
"""RAG (Retrieval-Augmented Generation) subsystem for AssemblyZero.

Issue #113: Vector Database Infrastructure (RAG Foundation)
Issue #88: The Librarian - Automated Context Retrieval

Public API:
    Foundation (#113):
        - get_store() — singleton VectorStore
        - get_query_engine() — singleton QueryEngine wired with store + embeddings
        - RAGConfig (config.py) — configuration dataclass
        - TextChunker, TextChunk — document chunking utilities
        - QueryEngine, QueryResult, QueryResponse — query interface
        - VectorStore — store lifecycle management
        - EmbeddingProvider — local embedding generation
        - CollectionManager — collection CRUD
        - Error classes — RAGError hierarchy

    Librarian (#88):
        - ChunkMetadata, IngestionSummary, RetrievedDocument — models
        - check_rag_dependencies, require_rag_dependencies — dependency checks

Install RAG dependencies: pip install assemblyzero[rag]
"""

from __future__ import annotations

import threading

from typing import TYPE_CHECKING

from assemblyzero.rag.config import RAGConfig

from assemblyzero.rag.errors import (
    CollectionNotFoundError,
    EmbeddingError,
    RAGError,
    StoreCorruptedError,
    StoreNotInitializedError,
)

from assemblyzero.rag.chunking import TextChunk, TextChunker

from assemblyzero.rag.models import (
    ChunkMetadata,
    IngestionSummary,
    RetrievedDocument,
)

from assemblyzero.rag.dependencies import check_rag_dependencies, require_rag_dependencies

def get_store(config: RAGConfig | None = None) -> VectorStore:
    """Get or create the singleton VectorStore instance.

Thread-safe. Returns existing instance if already created."""
    ...

def get_query_engine(config: RAGConfig | None = None) -> QueryEngine:
    """Get or create the singleton QueryEngine instance.

Thread-safe. Automatically creates VectorStore and EmbeddingProvider."""
    ...

def _reset_singletons() -> None:
    """Reset singleton state for test isolation.

Called by test fixtures after each test to prevent cross-test"""
    ...

_lock = threading.RLock()
```

**What changes:** Add `Issue #92` section to module docstring and add codebase_retrieval imports after the `from assemblyzero.rag.dependencies` import block.

### 3.2 `tools/rebuild_knowledge_base.py`

**Relevant excerpt** (full file structure):

```python
"""CLI tool: ingest docs into ChromaDB vector store.

Issue #88: The Librarian - Automated Context Retrieval

Usage:
    python tools/rebuild_knowledge_base.py                     # Incremental (default)
    python tools/rebuild_knowledge_base.py --full              # Full rebuild
    python tools/rebuild_knowledge_base.py --full --verbose    # Verbose full rebuild
    python tools/rebuild_knowledge_base.py --source-dirs docs/adrs docs/standards
"""

from __future__ import annotations

import argparse

import hashlib

import sys

import time

from pathlib import Path

from assemblyzero.rag.dependencies import check_rag_dependencies

from assemblyzero.rag.models import IngestionSummary, RAGConfig

def main() -> None:
    """CLI entry point for rebuilding the RAG knowledge base."""
    ...

def discover_documents(source_dirs: list[str]) -> list[Path]:
    """Find all markdown files in the specified source directories."""
    ...

def compute_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of file content for change detection."""
    ...

def run_full_ingestion(
    config: RAGConfig,
    verbose: bool = False,
) -> IngestionSummary:
    """Drop and rebuild the entire vector store."""
    ...

def run_incremental_ingestion(
    config: RAGConfig,
    verbose: bool = False,
) -> IngestionSummary:
    """Only reindex files that have changed since last ingestion."""
    ...
```

**What changes:** Update module docstring with `--collection codebase` usage examples, add `--collection` CLI argument to `main()`, add `index_codebase()` function after the existing functions, and add conditional dispatch in `main()` so `--collection codebase` calls `index_codebase()` instead of the existing documentation ingestion pipeline. The existing documentation path remains untouched.


## 4. Data Structures

### 4.1 CodeChunk

**Definition:**

```python
class CodeChunk(TypedDict):
    """A single extracted code entity from AST parsing."""
    content: str
    module_path: str
    entity_name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
```

**Concrete Example:**

```json
{
    "content": "class GovernanceAuditLog:\n    \"\"\"Audit logging for governance events.\"\"\"\n\n    def log_event(self, event: str, severity: str = \"info\") -> bool:\n        \"\"\"Log a governance event.\"\"\"\n        ...\n\n    def get_recent(self, count: int = 10) -> list[dict[str, str]]:\n        \"\"\"Get recent audit log entries.\"\"\"\n        ...",
    "module_path": "assemblyzero.core.audit",
    "entity_name": "GovernanceAuditLog",
    "kind": "class",
    "file_path": "assemblyzero/core/audit.py",
    "start_line": 15,
    "end_line": 42
}
```

**Second Example (function):**

```json
{
    "content": "def validate_config(config: dict[str, Any], schema: str = \"default\") -> bool:\n    \"\"\"Validate a configuration dictionary against a schema.\"\"\"\n    ...",
    "module_path": "assemblyzero.core.config_utils",
    "entity_name": "validate_config",
    "kind": "function",
    "file_path": "assemblyzero/core/config_utils.py",
    "start_line": 8,
    "end_line": 19
}
```

### 4.2 RetrievalResult

**Definition:**

```python
class RetrievalResult(TypedDict):
    """A scored retrieval result from vector store query."""
    chunk: CodeChunk
    relevance_score: float
    token_count: int
```

**Concrete Example:**

```json
{
    "chunk": {
        "content": "class GovernanceAuditLog:\n    \"\"\"Audit logging for governance events.\"\"\"\n\n    def log_event(self, event: str, severity: str = \"info\") -> bool:\n        ...",
        "module_path": "assemblyzero.core.audit",
        "entity_name": "GovernanceAuditLog",
        "kind": "class",
        "file_path": "assemblyzero/core/audit.py",
        "start_line": 15,
        "end_line": 42
    },
    "relevance_score": 0.87,
    "token_count": 156
}
```

### 4.3 CodebaseContext

**Definition:**

```python
class CodebaseContext(TypedDict):
    """Formatted context ready for prompt injection."""
    formatted_text: str
    total_tokens: int
    chunks_included: int
    chunks_dropped: int
    keywords_used: list[str]
```

**Concrete Example (with results):**

```json
{
    "formatted_text": "## Reference Codebase\nUse these existing utilities. DO NOT reinvent them.\n\n### [Source: assemblyzero/core/audit.py]\n```python\nclass GovernanceAuditLog:\n    \"\"\"Audit logging for governance events.\"\"\"\n\n    def log_event(self, event: str, severity: str = \"info\") -> bool:\n        ...\n```\n",
    "total_tokens": 156,
    "chunks_included": 1,
    "chunks_dropped": 0,
    "keywords_used": ["GovernanceAuditLog", "audit", "logging"]
}
```

**Concrete Example (empty):**

```json
{
    "formatted_text": "",
    "total_tokens": 0,
    "chunks_included": 0,
    "chunks_dropped": 0,
    "keywords_used": ["xyznonexistent"]
}
```


## 5. Function Specifications

### 5.1 `parse_python_file()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def parse_python_file(file_path: str) -> list[CodeChunk]:
    """Parse a single Python file using ast module, extracting public classes and top-level functions.

    Skips private entities (names starting with '_').
    Returns empty list if file cannot be parsed (SyntaxError, IOError, etc.).
    Logs warning on parse failure.
    """
    ...
```

**Input Example:**

```python
file_path = "assemblyzero/core/audit.py"
# File contains:
# class GovernanceAuditLog:
#     """Audit logging for governance events."""
#     def log_event(self, event: str, severity: str = "info") -> bool: ...
#     def get_recent(self, count: int = 10) -> list[dict[str, str]]: ...
# class _PrivateProcessor:
#     """Internal processor."""
#     ...
# def _internal_helper(): ...
```

**Output Example:**

```python
[
    {
        "content": "class GovernanceAuditLog:\n    \"\"\"Audit logging for governance events.\"\"\"\n\n    def log_event(self, event: str, severity: str = \"info\") -> bool:\n        ...\n\n    def get_recent(self, count: int = 10) -> list[dict[str, str]]:\n        ...",
        "module_path": "assemblyzero.core.audit",
        "entity_name": "GovernanceAuditLog",
        "kind": "class",
        "file_path": "assemblyzero/core/audit.py",
        "start_line": 1,
        "end_line": 10,
    }
]
# _PrivateProcessor and _internal_helper are excluded (leading underscore)
```

**Edge Cases:**
- File with `SyntaxError` (malformed) → returns `[]`, logs `logger.warning("Failed to parse %s: %s", file_path, error)`
- File with only `"""Package docstring."""` → returns `[]`
- File not found → returns `[]`, logs warning
- File with `_private` classes/functions → excluded from results

### 5.2 `extract_node_source()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def extract_node_source(source: str, node: ast.AST) -> str:
    """Extract the full source text for an AST node including decorators and docstring."""
    ...
```

**Input Example:**

```python
source = "class Foo:\n    \"\"\"A foo.\"\"\"\n    def bar(self) -> str:\n        return \"baz\"\n"
node = <ast.ClassDef object at line 1, end_line 4>
```

**Output Example:**

```python
"class Foo:\n    \"\"\"A foo.\"\"\"\n    def bar(self) -> str:\n        return \"baz\""
```

**Edge Cases:**
- Node with decorators → includes decorator lines
- Node at end of file without trailing newline → returns content up to EOF

### 5.3 `file_path_to_module_path()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def file_path_to_module_path(file_path: str) -> str:
    """Convert a file path to a dotted module path."""
    ...
```

**Input Example:**

```python
file_path = "assemblyzero/core/audit.py"
```

**Output Example:**

```python
"assemblyzero.core.audit"
```

**Additional Example:**

```python
file_path = "assemblyzero/rag/__init__.py"
# Output:
"assemblyzero.rag"
```

**Edge Cases:**
- `__init__.py` → strips `/__init__.py` (e.g., `"assemblyzero/rag/__init__.py"` → `"assemblyzero.rag"`)
- Paths with `.py` extension → stripped
- Forward slashes converted to dots

### 5.4 `scan_codebase()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def scan_codebase(
    directories: list[str],
    file_pattern: str = "**/*.py",
) -> list[CodeChunk]:
    """Recursively scan directories for Python files, parse each, return all code chunks.

    Skips __init__.py files that contain only package docstrings (no class/function defs).
    Logs warnings for files that fail to parse.
    """
    ...
```

**Input Example:**

```python
directories = ["assemblyzero/", "tools/"]
```

**Output Example:**

```python
[
    {"content": "class GovernanceAuditLog: ...", "module_path": "assemblyzero.core.audit", "entity_name": "GovernanceAuditLog", "kind": "class", "file_path": "assemblyzero/core/audit.py", "start_line": 15, "end_line": 42},
    {"content": "def validate_config(...) -> bool: ...", "module_path": "assemblyzero.core.config_utils", "entity_name": "validate_config", "kind": "function", "file_path": "assemblyzero/core/config_utils.py", "start_line": 8, "end_line": 19},
    # ... more chunks
]
```

**Edge Cases:**
- Empty directory → returns `[]`
- Non-existent directory → returns `[]`, logs warning
- Directory with only `__init__.py` files containing only docstrings → returns `[]`

### 5.5 `split_compound_terms()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def split_compound_terms(text: str) -> list[str]:
    """Split CamelCase and snake_case terms into constituent words, preserving originals."""
    ...
```

**Input Example 1:**

```python
text = "GovernanceAuditLog"
```

**Output Example 1:**

```python
["Governance", "Audit", "Log", "GovernanceAuditLog"]
```

**Input Example 2:**

```python
text = "audit_log_entry"
```

**Output Example 2:**

```python
["audit", "log", "entry", "audit_log_entry"]
```

**Edge Cases:**
- Single word `"audit"` → `["audit"]`
- Already split word → returned as-is
- Mixed case `"HTMLParser"` → `["HTML", "Parser", "HTMLParser"]`

### 5.6 `extract_keywords()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def extract_keywords(
    lld_content: str,
    max_keywords: int = 5,
    stopwords: set[str] | None = None,
) -> list[str]:
    """Extract top technical keywords from LLD content using Counter-based frequency analysis.

    Pipeline:
    1. Split compound terms (CamelCase/snake_case)
    2. Tokenize into words
    3. Filter stopwords (domain-specific + standard English)
    4. Count term frequency
    5. Return top N keywords by frequency
    6. Fallback to regex extraction if frequency yields < 2 terms
    """
    ...
```

**Input Example 1:**

```python
lld_content = "Implement audit logging using GovernanceAuditLog. The audit system tracks governance events and provides audit trail functionality."
max_keywords = 5
```

**Output Example 1:**

```python
["audit", "GovernanceAuditLog", "governance", "logging", "tracks"]
```

**Input Example 2:**

```python
lld_content = "Use FooBarBaz"
max_keywords = 5
```

**Output Example 2:**

```python
["FooBarBaz", "Foo", "Bar", "Baz"]
# Fallback regex finds "FooBarBaz" CamelCase identifier
```

**Input Example 3 (stopword-heavy):**

```python
lld_content = "Implement the feature using a new system that should create the module and return the value"
max_keywords = 5
```

**Output Example 3:**

```python
[]
# All terms are stopwords or too generic
```

**Edge Cases:**
- Empty string → returns `[]`
- All stopwords → returns `[]`
- `max_keywords=5` with 20+ terms → returns exactly 5

### 5.7 `get_domain_stopwords()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def get_domain_stopwords() -> set[str]:
    """Return domain-specific stopwords extending standard English stopwords."""
    ...
```

**Input Example:**

```python
# No input
```

**Output Example:**

```python
{
    "the", "and", "implement", "create", "using", "should", "must",
    "will", "system", "feature", "function", "method", "class", "module",
    "import", "return", "none", "true", "false", "self", "def", "str", "int",
    "list", "dict", "type", "file", "path", "data", "value", "name",
    "this", "that", "with", "from", "have", "been", "each", "when",
    "also", "into", "than", "other", "which", "their", "about",
    "would", "make", "like", "just", "over", "such", "after",
    "new", "use", "can", "may", "not", "are", "was", "for",
    # ... more stopwords
}
```

**Edge Cases:**
- Always returns the same frozen set (module-level constant)

### 5.8 `query_codebase_collection()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def query_codebase_collection(
    keywords: list[str],
    collection_name: str = "codebase",
    similarity_threshold: float = 0.75,
    max_results: int = 10,
) -> list[RetrievalResult]:
    """Query ChromaDB codebase collection with keywords, apply threshold and deduplication.

    1. Combine keywords into query text
    2. Query ChromaDB with embedding similarity
    3. Convert L2 distances to similarity: 1.0 / (1.0 + distance)
    4. Filter results below similarity_threshold
    5. Deduplicate by module_path (keep highest score)
    6. Sort by relevance_score descending
    7. Limit to max_results

    Returns empty list if collection doesn't exist (graceful degradation).
    """
    ...
```

**Input Example 1 (normal):**

```python
keywords = ["GovernanceAuditLog", "audit", "logging"]
collection_name = "codebase"
similarity_threshold = 0.75
max_results = 10
```

**Output Example 1:**

```python
[
    {
        "chunk": {
            "content": "class GovernanceAuditLog:\n    ...",
            "module_path": "assemblyzero.core.audit",
            "entity_name": "GovernanceAuditLog",
            "kind": "class",
            "file_path": "assemblyzero/core/audit.py",
            "start_line": 15,
            "end_line": 42,
        },
        "relevance_score": 0.87,
        "token_count": 156,
    }
]
```

**Input Example 2 (no matches):**

```python
keywords = ["xyznonexistent123"]
```

**Output Example 2:**

```python
[]
```

**Edge Cases:**
- Empty `keywords` → returns `[]`
- Missing collection → returns `[]`, logs `logger.warning("Codebase collection '%s' not found", collection_name)`
- `ImportError` for chromadb → returns `[]`, logs warning
- Two chunks from same module → only highest score kept

### 5.9 `estimate_token_count()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def estimate_token_count(text: str) -> int:
    """Estimate token count using tiktoken cl100k_base. Falls back to word_count * 1.3."""
    ...
```

**Input Example:**

```python
text = "class Foo:\n    \"\"\"A foo class.\"\"\"\n    def bar(self) -> str:\n        return \"baz\""
```

**Output Example:**

```python
22  # tiktoken cl100k_base encoding
```

**Edge Cases:**
- Empty string → returns `0`
- `tiktoken` unavailable → uses `int(len(text.split()) * 1.3)` fallback

### 5.10 `apply_token_budget()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def apply_token_budget(
    results: list[RetrievalResult],
    max_tokens: int = 4096,
) -> list[RetrievalResult]:
    """Apply token budget, dropping lowest-relevance whole chunks that exceed budget."""
    ...
```

**Input Example 1 (budget exceeded):**

```python
results = [
    {"chunk": {"content": "class A: ...", ...}, "relevance_score": 0.9, "token_count": 100},
    {"chunk": {"content": "class B: ...", ...}, "relevance_score": 0.85, "token_count": 100},
    {"chunk": {"content": "class C: ...", ...}, "relevance_score": 0.8, "token_count": 100},
]
max_tokens = 150
```

**Output Example 1:**

```python
[
    {"chunk": {"content": "class A: ...", ...}, "relevance_score": 0.9, "token_count": 100},
]
# Only first chunk fits; second would push to 200 > 150
```

**Input Example 2 (all fit):**

```python
results = [
    {"chunk": {"content": "class A: ...", ...}, "relevance_score": 0.9, "token_count": 100},
    {"chunk": {"content": "class B: ...", ...}, "relevance_score": 0.85, "token_count": 100},
    {"chunk": {"content": "class C: ...", ...}, "relevance_score": 0.8, "token_count": 100},
]
max_tokens = 500
```

**Output Example 2:**

```python
[
    {"chunk": {"content": "class A: ...", ...}, "relevance_score": 0.9, "token_count": 100},
    {"chunk": {"content": "class B: ...", ...}, "relevance_score": 0.85, "token_count": 100},
    {"chunk": {"content": "class C: ...", ...}, "relevance_score": 0.8, "token_count": 100},
]
# All 3 fit within budget (300 <= 500)
```

**Edge Cases:**
- Empty results → returns `[]`
- First chunk alone exceeds budget → returns `[first_chunk]` (always include at least one)

### 5.11 `format_codebase_context()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def format_codebase_context(results: list[RetrievalResult]) -> CodebaseContext:
    """Format retrieval results into markdown for prompt injection."""
    ...
```

**Input Example:**

```python
results = [
    {
        "chunk": {
            "content": "class GovernanceAuditLog:\n    \"\"\"Audit logging.\"\"\"\n    def log_event(self, event: str) -> bool: ...",
            "module_path": "assemblyzero.core.audit",
            "entity_name": "GovernanceAuditLog",
            "kind": "class",
            "file_path": "assemblyzero/core/audit.py",
            "start_line": 15,
            "end_line": 30,
        },
        "relevance_score": 0.87,
        "token_count": 45,
    },
    {
        "chunk": {
            "content": "def validate_config(config: dict[str, Any]) -> bool:\n    \"\"\"Validate config.\"\"\"\n    ...",
            "module_path": "assemblyzero.core.config_utils",
            "entity_name": "validate_config",
            "kind": "function",
            "file_path": "assemblyzero/core/config_utils.py",
            "start_line": 8,
            "end_line": 15,
        },
        "relevance_score": 0.79,
        "token_count": 28,
    },
]
```

**Output Example:**

```python
{
    "formatted_text": "## Reference Codebase\nUse these existing utilities. DO NOT reinvent them.\n\n### [Source: assemblyzero/core/audit.py]\n```python\nclass GovernanceAuditLog:\n    \"\"\"Audit logging.\"\"\"\n    def log_event(self, event: str) -> bool: ...\n```\n\n### [Source: assemblyzero/core/config_utils.py]\n```python\ndef validate_config(config: dict[str, Any]) -> bool:\n    \"\"\"Validate config.\"\"\"\n    ...\n```\n",
    "total_tokens": 73,
    "chunks_included": 2,
    "chunks_dropped": 0,
    "keywords_used": [],
}
```

**Edge Cases:**
- Empty `results` → returns `{"formatted_text": "", "total_tokens": 0, "chunks_included": 0, "chunks_dropped": 0, "keywords_used": []}`

### 5.12 `retrieve_codebase_context()`

**File:** `assemblyzero/rag/codebase_retrieval.py`

**Signature:**

```python
def retrieve_codebase_context(
    lld_content: str,
    max_keywords: int = 5,
    similarity_threshold: float = 0.75,
    max_results: int = 10,
    token_budget: int = 4096,
) -> CodebaseContext:
    """End-to-end: extract keywords from LLD, retrieve relevant code, format for injection."""
    ...
```

**Input Example:**

```python
lld_content = "# 92 - Feature\n## Objective\nImplement audit logging using GovernanceAuditLog to track governance events."
```

**Output Example:**

```python
{
    "formatted_text": "## Reference Codebase\nUse these existing utilities. DO NOT reinvent them.\n\n### [Source: assemblyzero/core/audit.py]\n```python\nclass GovernanceAuditLog:\n    ...\n```\n",
    "total_tokens": 45,
    "chunks_included": 1,
    "chunks_dropped": 0,
    "keywords_used": ["GovernanceAuditLog", "audit", "logging", "governance", "events"],
}
```

**Edge Cases:**
- Empty `lld_content` → returns empty context (no keywords extracted)
- No matching chunks → returns context with `formatted_text = ""`

### 5.13 `inject_codebase_context()`

**File:** `assemblyzero/workflows/implementation_spec/nodes/coder_node.py`

**Signature:**

```python
def inject_codebase_context(
    base_prompt: str,
    lld_content: str,
    token_budget: int = 4096,
) -> str:
    """Inject codebase context into N3_Coder's system prompt.

    Returns modified prompt with codebase context prepended, or original prompt on failure.
    """
    ...
```

**Input Example 1 (with matches):**

```python
base_prompt = "You are a code generation assistant. Generate Python code based on the following LLD."
lld_content = "# 92 - Feature\nImplement audit logging using GovernanceAuditLog."
token_budget = 4096
```

**Output Example 1:**

```python
"## Reference Codebase\nUse these existing utilities. DO NOT reinvent them.\n\n### [Source: assemblyzero/core/audit.py]\n```python\nclass GovernanceAuditLog:\n    ...\n```\n\nYou are a code generation assistant. Generate Python code based on the following LLD."
```

**Input Example 2 (no matches):**

```python
base_prompt = "You are a code generation assistant."
lld_content = "# 999 - Feature\nSomething completely unrelated to any existing code."
```

**Output Example 2:**

```python
"You are a code generation assistant."
# No context to inject, returns base_prompt unchanged
```

**Input Example 3 (exception during retrieval):**

```python
base_prompt = "You are a code generation assistant."
lld_content = "Any content"
# retrieve_codebase_context raises RuntimeError
```

**Output Example 3:**

```python
"You are a code generation assistant."
# Returns base_prompt unchanged, logs warning
```

**Edge Cases:**
- Any `Exception` during retrieval → returns `base_prompt` unchanged, logs `logger.warning("Codebase retrieval failed: %s", e)`

### 5.14 `index_codebase()`

**File:** `tools/rebuild_knowledge_base.py`

**Signature:**

```python
def index_codebase(
    directories: list[str] | None = None,
    collection_name: str = "codebase",
) -> dict[str, int]:
    """Index Python codebase into ChromaDB.

    Drops and recreates collection on each run (full rebuild).
    Returns statistics dict.
    """
    ...
```

**Input Example:**

```python
directories = ["assemblyzero/", "tools/"]
collection_name = "codebase"
```

**Output Example:**

```python
{"files_scanned": 52, "chunks_indexed": 347, "errors": 2}
```

**Edge Cases:**
- `directories=None` → defaults to `["assemblyzero/", "tools/"]`
- No Python files found → returns `{"files_scanned": 0, "chunks_indexed": 0, "errors": 0}`

### 5.15 `test_docstring_only_init()`

**File:** `tests/unit/test_rag/test_codebase_retrieval.py`

**Signature:**

```python
def test_docstring_only_init(self, tmp_path: Path) -> None:
    """T050: AST skips empty __init__.py with only docstring."""
    ...
```

**Input Example:**

```python
# Creates a temporary file at tmp_path / "__init__.py" with content:
content = '"""Package docstring."""\n'
# Then calls: parse_python_file(str(tmp_path / "__init__.py"))
```

**Output Example:**

```python
result = []  # Empty list, no chunks extracted from docstring-only init file
assert result == []
```

### 5.16 `test_empty_init()`

**File:** `tests/unit/test_rag/test_codebase_retrieval.py`

**Signature:**

```python
def test_empty_init(self, tmp_path: Path) -> None:
    """T050 variant: AST skips completely empty __init__.py."""
    ...
```

**Input Example:**

```python
# Creates a temporary file at tmp_path / "__init__.py" with content:
content = ""
# Then calls: parse_python_file(str(tmp_path / "__init__.py"))
```

**Output Example:**

```python
result = []  # Empty list, no chunks from empty file
assert result == []
```

### 5.17 `test_malformed_logs_warning()`

**File:** `tests/unit/test_rag/test_codebase_retrieval.py`

**Signature:**

```python
def test_malformed_logs_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """T040/T290: Malformed Python file returns [] and logs warning with file path."""
    ...
```

**Input Example:**

```python
# Creates a temporary file at tmp_path / "broken.py" with content:
content = "def broken(\n    # Missing closing paren and colon\n"
# Then calls: parse_python_file(str(tmp_path / "broken.py"))
```

**Output Example:**

```python
result = []  # Empty list, no exception raised
assert result == []
assert "broken.py" in caplog.text  # Warning log contains the file path
assert any(record.levelname == "WARNING" for record in caplog.records)
```


## 6. Change Instructions

### 6.1 `tests/fixtures/rag/sample_module.py` (Add)

**Complete file contents:**

```python
"""Sample module for codebase retrieval AST parsing tests.

Issue #92: Codebase Retrieval System (RAG Injection)

This fixture contains a variety of Python constructs to test AST extraction:
- Public class with docstring and typed methods
- Public top-level function with type hints
- Private class (should be skipped)
- Private function (should be skipped)
"""

from __future__ import annotations

from typing import Any


class GovernanceAuditLog:
    """Audit logging for governance events.

    Tracks all governance-related actions in the system
    for compliance and debugging purposes.
    """

    def log_event(self, event: str, severity: str = "info") -> bool:
        """Log a governance event.

        Args:
            event: Description of the event.
            severity: Event severity level.

        Returns:
            True if the event was logged successfully.
        """
        return True

    def get_recent(self, count: int = 10) -> list[dict[str, str]]:
        """Get recent audit log entries.

        Args:
            count: Number of entries to retrieve.

        Returns:
            List of audit log entry dictionaries.
        """
        return []


class ConfigValidator:
    """Validates configuration dictionaries against schemas."""

    def validate(self, config: dict[str, Any], schema: str = "default") -> bool:
        """Validate a configuration dictionary.

        Args:
            config: Configuration to validate.
            schema: Schema name to validate against.

        Returns:
            True if valid.
        """
        return True


def compute_file_hash(file_path: str, algorithm: str = "md5") -> str:
    """Compute hash of a file's content.

    Args:
        file_path: Path to the file.
        algorithm: Hash algorithm to use.

    Returns:
        Hex digest of the file hash.
    """
    return ""


def format_report(entries: list[dict[str, str]], title: str = "Report") -> str:
    """Format entries into a human-readable report.

    Args:
        entries: List of entry dictionaries.
        title: Report title.

    Returns:
        Formatted report string.
    """
    return ""


def parse_timestamps(raw: str) -> list[str]:
    """Parse ISO 8601 timestamps from raw text.

    Args:
        raw: Raw text containing timestamps.

    Returns:
        List of parsed timestamp strings.
    """
    return []


class _PrivateProcessor:
    """Internal processor - should NOT be indexed."""

    def process(self) -> None:
        """Process internally."""
        pass


def _internal_helper() -> None:
    """Internal helper - should NOT be indexed."""
    pass
```

### 6.2 `tests/fixtures/rag/sample_module_malformed.py` (Add)

**Complete file contents:**

```python
"""Malformed module for testing parse error handling.

Issue #92: Codebase Retrieval System (RAG Injection)

This file intentionally contains a syntax error.
"""

def broken(
    # Missing closing paren, colon, and body
```

### 6.3 `tests/fixtures/rag/sample_lld_audit.md` (Add)

**Complete file contents:**

```markdown
# 999 - Feature: Audit Logging Enhancement

## 1. Context & Goal

* **Issue:** #999
* **Objective:** Enhance the audit logging system using GovernanceAuditLog to track governance events with improved severity filtering and report generation.

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/core/audit.py` | Modify | Add severity filtering to GovernanceAuditLog |

### 2.2 Technical Approach

Use the existing GovernanceAuditLog class to add audit trail functionality. The audit system should leverage compute_file_hash for integrity verification and ConfigValidator for configuration validation.

The implementation should support governance event tracking with configurable severity levels and report formatting via format_report.
```

### 6.4 `assemblyzero/rag/codebase_retrieval.py` (Add)

**Complete file contents:**

```python
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

    ``assemblyzero/core/audit.py`` → ``assemblyzero.core.audit``
    ``assemblyzero/rag/__init__.py`` → ``assemblyzero.rag``
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

    try:
        import chromadb  # noqa: PLC0415
    except ImportError:
        logger.warning("chromadb not installed; codebase retrieval unavailable")
        return []

    try:
        client = chromadb.PersistentClient()
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

        # Deduplicate by module_path — keep highest score
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
```

### 6.5 `assemblyzero/rag/__init__.py` (Modify)

**Change 1:** Update module docstring to add Issue #92 section (after the `Librarian (#88):` section)

```diff
     Librarian (#88):
         - ChunkMetadata, IngestionSummary, RetrievedDocument — models
         - check_rag_dependencies, require_rag_dependencies — dependency checks
 
+    Codebase Retrieval (#92):
+        - CodeChunk, RetrievalResult, CodebaseContext — data structures
+        - parse_python_file, scan_codebase — AST-based code parsing
+        - extract_keywords, split_compound_terms — keyword extraction
+        - query_codebase_collection — vector similarity search
+        - retrieve_codebase_context — end-to-end retrieval pipeline
+        - format_codebase_context — markdown context formatting
+        - estimate_token_count, apply_token_budget — token management
+
 Install RAG dependencies: pip install assemblyzero[rag]
```

**Change 2:** Add codebase_retrieval imports after the `from assemblyzero.rag.dependencies` import block

```diff
 from assemblyzero.rag.dependencies import check_rag_dependencies, require_rag_dependencies
 
+from assemblyzero.rag.codebase_retrieval import (
+    CodebaseContext,
+    CodeChunk,
+    RetrievalResult,
+    apply_token_budget,
+    estimate_token_count,
+    extract_keywords,
+    format_codebase_context,
+    parse_python_file,
+    query_codebase_collection,
+    retrieve_codebase_context,
+    scan_codebase,
+    split_compound_terms,
+)
+
 def get_store(config: RAGConfig | None = None) -> VectorStore:
```

### 6.6 `assemblyzero/workflows/implementation_spec/nodes/coder_node.py` (Add)

**Complete file contents:**

```python
"""Coder node: codebase context injection for N3_Coder prompt construction.

Issue #92: Codebase Retrieval System (RAG Injection)

Provides a composable utility that retrieves relevant codebase context
from the RAG vector store and injects it into the code generation prompt.
Designed to be called from whichever workflow node constructs the N3_Coder
system prompt.

Fail-open: if retrieval fails for any reason, the original prompt is
returned unchanged and a warning is logged.
"""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


def inject_codebase_context(
    base_prompt: str,
    lld_content: str,
    token_budget: int = 4096,
) -> str:
    """Inject codebase context into N3_Coder's system prompt.

    1. Call retrieve_codebase_context(lld_content)
    2. If context is non-empty, prepend to base_prompt
    3. If retrieval fails (exception), log warning and return base_prompt unchanged

    Args:
        base_prompt: The original system prompt for code generation.
        lld_content: The LLD content to extract keywords from.
        token_budget: Maximum tokens for the codebase context section.

    Returns:
        Modified prompt with codebase context prepended, or original prompt
        on failure or no matches.
    """
    try:
        from assemblyzero.rag.codebase_retrieval import retrieve_codebase_context  # noqa: PLC0415

        context = retrieve_codebase_context(
            lld_content,
            token_budget=token_budget,
        )

        if context["formatted_text"]:
            return context["formatted_text"] + "\n" + base_prompt

    except Exception as exc:
        logger.warning("Codebase retrieval failed: %s", exc)

    return base_prompt
```

### 6.7 `tools/rebuild_knowledge_base.py` (Modify)

**Change 1:** Update module docstring to add `--collection codebase` usage

```diff
 """CLI tool: ingest docs into ChromaDB vector store.
 
 Issue #88: The Librarian - Automated Context Retrieval
+Issue #92: Codebase Retrieval System (RAG Injection)
 
 Usage:
     python tools/rebuild_knowledge_base.py                     # Incremental (default)
     python tools/rebuild_knowledge_base.py --full              # Full rebuild
     python tools/rebuild_knowledge_base.py --full --verbose    # Verbose full rebuild
     python tools/rebuild_knowledge_base.py --source-dirs docs/adrs docs/standards
+    python tools/rebuild_knowledge_base.py --collection codebase  # Index Python codebase
 """
```

**Change 2:** Add `--collection` argument inside `main()` function's argparse setup. Locate the `parser = argparse.ArgumentParser(...)` call and add after the last existing `parser.add_argument`:

```diff
+    parser.add_argument(
+        "--collection",
+        choices=["documentation", "codebase"],
+        default="documentation",
+        help="Which collection to rebuild (default: documentation)",
+    )
```

**Change 3:** Add conditional dispatch in `main()` before the existing documentation ingestion path. Locate the line where `main()` begins its ingestion logic (after argument parsing and dependency check) and add:

```diff
     args = parser.parse_args()
 
     if not check_rag_dependencies():
         print("[ERROR] RAG dependencies not installed. Run: pip install assemblyzero[rag]")
         sys.exit(1)
 
+    if args.collection == "codebase":
+        print("[codebase] Starting codebase indexing...")
+        stats = index_codebase()
+        print(f"[codebase] Files scanned: {stats['files_scanned']}")
+        print(f"[codebase] Chunks indexed: {stats['chunks_indexed']}")
+        print(f"[codebase] Errors: {stats['errors']}")
+        print("[codebase] Done.")
+        return
+
     # Existing documentation ingestion path continues below...
```

**Change 4:** Add `index_codebase()` function at the end of the file, after `run_incremental_ingestion()`:

```python
def index_codebase(
    directories: list[str] | None = None,
    collection_name: str = "codebase",
) -> dict[str, int]:
    """Index Python codebase into ChromaDB.

    Issue #92: Codebase Retrieval System (RAG Injection)

    Drops and recreates the codebase collection on each run (full rebuild).
    Uses sentence-transformers for local embedding generation.

    Args:
        directories: Directories to scan. Defaults to ["assemblyzero/", "tools/"].
        collection_name: ChromaDB collection name. Defaults to "codebase".

    Returns:
        Statistics dict with keys: files_scanned, chunks_indexed, errors.
    """
    from assemblyzero.rag.codebase_retrieval import scan_codebase, estimate_token_count  # noqa: PLC0415

    if directories is None:
        directories = ["assemblyzero/", "tools/"]

    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    BATCH_SIZE = 500

    # Scan and parse
    print(f"[codebase] Scanning directories: {directories}")
    chunks = scan_codebase(directories)

    # Count unique files
    files_scanned = len({c["file_path"] for c in chunks})
    errors = 0  # Errors are already logged by scan_codebase; count from chunks vs expected

    if not chunks:
        print("[codebase] No code chunks found.")
        return {"files_scanned": files_scanned, "chunks_indexed": 0, "errors": errors}

    print(f"[codebase] Found {len(chunks)} code chunks from {files_scanned} files")

    # Generate embeddings
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
    except ImportError:
        print("[ERROR] sentence-transformers not installed. Run: pip install assemblyzero[rag]")
        sys.exit(1)

    print(f"[codebase] Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    contents = [c["content"] for c in chunks]
    print(f"[codebase] Generating embeddings for {len(contents)} chunks...")
    embeddings = model.encode(contents, show_progress_bar=True, batch_size=BATCH_SIZE)

    # Upsert into ChromaDB
    import chromadb  # noqa: PLC0415

    client = chromadb.PersistentClient()

    # Drop existing collection
    try:
        client.delete_collection(name=collection_name)
        print(f"[codebase] Dropped existing '{collection_name}' collection")
    except Exception:
        pass  # Collection didn't exist

    collection = client.create_collection(name=collection_name)

    # Batch upsert
    total_indexed = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch_chunks = chunks[i : i + BATCH_SIZE]
        batch_embeddings = embeddings[i : i + BATCH_SIZE].tolist()
        batch_ids = [
            f"{c['module_path']}.{c['entity_name']}" for c in batch_chunks
        ]
        batch_documents = [c["content"] for c in batch_chunks]
        batch_metadatas = [
            {
                "module_path": c["module_path"],
                "entity_name": c["entity_name"],
                "kind": c["kind"],
                "file_path": c["file_path"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "type": "code",
            }
            for c in batch_chunks
        ]

        collection.upsert(
            ids=batch_ids,
            documents=batch_documents,
            embeddings=batch_embeddings,
            metadatas=batch_metadatas,
        )
        total_indexed += len(batch_chunks)
        print(f"[codebase] Indexed {total_indexed}/{len(chunks)} chunks")

    return {"files_scanned": files_scanned, "chunks_indexed": total_indexed, "errors": errors}
```

### 6.8 `tests/unit/test_rag/test_codebase_retrieval.py` (Add)

**Complete file contents:**

```python
"""Tests for codebase retrieval system.

Issue #92: Codebase Retrieval System (RAG Injection)
"""

from __future__ import annotations

import logging

from pathlib import Path
from unittest import mock

import pytest

from assemblyzero.rag.codebase_retrieval import (
    CodeChunk,
    CodebaseContext,
    RetrievalResult,
    apply_token_budget,
    estimate_token_count,
    extract_keywords,
    file_path_to_module_path,
    format_codebase_context,
    get_domain_stopwords,
    parse_python_file,
    query_codebase_collection,
    retrieve_codebase_context,
    split_compound_terms,
)


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "rag"


# ---------------------------------------------------------------------------
# AST Parsing Tests
# ---------------------------------------------------------------------------


class TestParseFile:
    """Tests for parse_python_file() — T010, T020, T030, T040, T050, T260."""

    def test_class_extraction_with_docstring(self) -> None:
        """T010: AST extracts class with docstring and methods."""
        chunks = parse_python_file(str(FIXTURES_DIR / "sample_module.py"))
        class_chunks = [c for c in chunks if c["entity_name"] == "GovernanceAuditLog"]
        assert len(class_chunks) == 1
        chunk = class_chunks[0]
        assert chunk["kind"] == "class"
        assert "GovernanceAuditLog" in chunk["content"]
        assert "Audit logging for governance events" in chunk["content"]
        assert chunk["module_path"].endswith("sample_module")

    def test_function_extraction_with_type_hints(self) -> None:
        """T020: AST extracts top-level function with type hints."""
        chunks = parse_python_file(str(FIXTURES_DIR / "sample_module.py"))
        func_chunks = [c for c in chunks if c["kind"] == "function"]
        assert len(func_chunks) >= 1
        # Check that at least one function has type hints in content
        has_type_hints = any("str" in c["content"] for c in func_chunks)
        assert has_type_hints

    def test_private_entity_skip(self) -> None:
        """T030: AST skips private entities."""
        chunks = parse_python_file(str(FIXTURES_DIR / "sample_module.py"))
        names = [c["entity_name"] for c in chunks]
        assert "_internal_helper" not in names
        assert "_PrivateProcessor" not in names

    def test_malformed_file_returns_empty(self) -> None:
        """T040: AST handles malformed Python file."""
        chunks = parse_python_file(str(FIXTURES_DIR / "sample_module_malformed.py"))
        assert chunks == []

    def test_malformed_logs_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """T040/T290: Malformed Python file returns [] and logs warning with file path."""
        broken_file = tmp_path / "broken.py"
        broken_file.write_text("def broken(\n    # Missing closing paren\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = parse_python_file(str(broken_file))

        assert result == []
        assert "broken.py" in caplog.text
        assert any(record.levelname == "WARNING" for record in caplog.records)

    def test_docstring_only_init(self, tmp_path: Path) -> None:
        """T050: AST skips __init__.py with only docstring."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text('"""Package docstring."""\n', encoding="utf-8")

        result = parse_python_file(str(init_file))

        assert result == []

    def test_empty_init(self, tmp_path: Path) -> None:
        """T050 variant: AST skips completely empty __init__.py."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text("", encoding="utf-8")

        result = parse_python_file(str(init_file))

        assert result == []

    def test_type_hints_preserved(self) -> None:
        """T260: AST extracts ClassDef with type hints preserved in content."""
        chunks = parse_python_file(str(FIXTURES_DIR / "sample_module.py"))
        class_chunks = [c for c in chunks if c["entity_name"] == "GovernanceAuditLog"]
        assert len(class_chunks) == 1
        content = class_chunks[0]["content"]
        assert "str" in content
        assert "bool" in content
        assert "list[dict[str, str]]" in content


class TestFilePathToModulePath:
    """Tests for file_path_to_module_path() — T060."""

    def test_standard_path(self) -> None:
        """T060: Convert standard file path to module path."""
        assert file_path_to_module_path("assemblyzero/core/audit.py") == "assemblyzero.core.audit"

    def test_init_path(self) -> None:
        """T060 variant: Convert __init__.py path."""
        assert file_path_to_module_path("assemblyzero/rag/__init__.py") == "assemblyzero.rag"


# ---------------------------------------------------------------------------
# Keyword Extraction Tests
# ---------------------------------------------------------------------------


class TestSplitCompoundTerms:
    """Tests for split_compound_terms() — T070, T080."""

    def test_camel_case(self) -> None:
        """T070: CamelCase splitting."""
        parts = split_compound_terms("GovernanceAuditLog")
        assert "Governance" in parts
        assert "Audit" in parts
        assert "Log" in parts
        assert "GovernanceAuditLog" in parts

    def test_snake_case(self) -> None:
        """T080: snake_case splitting."""
        parts = split_compound_terms("audit_log_entry")
        assert "audit" in parts
        assert "log" in parts
        assert "entry" in parts
        assert "audit_log_entry" in parts


class TestExtractKeywords:
    """Tests for extract_keywords() — T090, T100, T110."""

    def test_stopword_filtering(self) -> None:
        """T090: Stopwords are filtered out."""
        keywords = extract_keywords(
            "Implement the feature using a new system that should create"
        )
        stopwords = get_domain_stopwords()
        for kw in keywords:
            assert kw.lower() not in stopwords

    def test_max_keywords_limit(self) -> None:
        """T100: Keyword extraction limits to top N."""
        # Text with many distinct technical terms
        text = (
            "GovernanceAuditLog ConfigValidator TextChunker VectorStore "
            "EmbeddingProvider CollectionManager QueryEngine RAGConfig "
            "ChunkMetadata IngestionSummary RetrievedDocument SecurityAudit "
            "WorkflowState GraphBuilder NodeRegistry TaskScheduler "
            "CacheManager ConnectionPool EventDispatcher MetricsCollector "
            "LogAggregator AlertSystem HealthChecker"
        )
        keywords = extract_keywords(text, max_keywords=5)
        assert len(keywords) <= 5

    def test_fallback_on_sparse_input(self) -> None:
        """T110: Keyword extraction fallback on sparse CamelCase input."""
        keywords = extract_keywords("Use FooBarBaz")
        assert "FooBarBaz" in keywords


class TestDomainStopwords:
    """Tests for get_domain_stopwords() — T250."""

    def test_contains_expected_terms(self) -> None:
        """T250: Domain stopwords are comprehensive."""
        stopwords = get_domain_stopwords()
        for expected in ["def", "class", "implement", "the", "return", "self"]:
            assert expected in stopwords


# ---------------------------------------------------------------------------
# Retrieval Tests
# ---------------------------------------------------------------------------


class TestQueryCodebaseCollection:
    """Tests for query_codebase_collection() — T120, T130, T140, T150, T280."""

    def test_threshold_filtering(self) -> None:
        """T120: Nonsense query returns empty results with mocked low scores."""
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_collection = mock.MagicMock()
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection
            # Return results with very high distances (low similarity)
            mock_collection.query.return_value = {
                "documents": [["class X: pass"]],
                "metadatas": [[{"module_path": "mod.x", "entity_name": "X", "kind": "class", "file_path": "mod/x.py", "start_line": 1, "end_line": 1}]],
                "distances": [[10.0]],  # similarity = 1/(1+10) = 0.09 < 0.75
            }

            results = query_codebase_collection(["xyznonexistent123"])
            assert results == []

    def test_module_deduplication(self) -> None:
        """T130: Two chunks from same module keeps only highest score."""
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_collection = mock.MagicMock()
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection
            # distance 0.111 → similarity ≈ 0.9;  distance 0.25 → similarity = 0.8
            mock_collection.query.return_value = {
                "documents": [["class A: pass", "def b(): pass"]],
                "metadatas": [[
                    {"module_path": "assemblyzero.core.audit", "entity_name": "A", "kind": "class", "file_path": "assemblyzero/core/audit.py", "start_line": 1, "end_line": 1},
                    {"module_path": "assemblyzero.core.audit", "entity_name": "b", "kind": "function", "file_path": "assemblyzero/core/audit.py", "start_line": 5, "end_line": 5},
                ]],
                "distances": [[0.111, 0.25]],
            }

            results = query_codebase_collection(["audit"])
            assert len(results) == 1
            # Should keep the higher similarity one
            assert results[0]["relevance_score"] > 0.85

    def test_max_results_limit(self) -> None:
        """T140: Query returns at most max_results."""
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_collection = mock.MagicMock()
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection

            # 15 results from different modules, all high similarity
            docs = [f"class C{i}: pass" for i in range(15)]
            metas = [{"module_path": f"mod.c{i}", "entity_name": f"C{i}", "kind": "class", "file_path": f"mod/c{i}.py", "start_line": 1, "end_line": 1} for i in range(15)]
            dists = [0.1] * 15  # similarity ≈ 0.91

            mock_collection.query.return_value = {
                "documents": [docs],
                "metadatas": [metas],
                "distances": [dists],
            }

            results = query_codebase_collection(["test"], max_results=10)
            assert len(results) == 10

    def test_missing_collection_graceful(self, caplog: pytest.LogCaptureFixture) -> None:
        """T150: Missing collection returns empty list with warning."""
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.side_effect = Exception("Collection not found")

            with caplog.at_level(logging.WARNING):
                results = query_codebase_collection(["audit"])

            assert results == []
            assert "codebase" in caplog.text.lower() or "not found" in caplog.text.lower()

    def test_similarity_threshold_boundary(self) -> None:
        """T280: Results at boundary — 0.76 passes, 0.74 fails."""
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_collection = mock.MagicMock()
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection

            # distance for similarity 0.76: 1/0.76 - 1 ≈ 0.3158
            # distance for similarity 0.74: 1/0.74 - 1 ≈ 0.3514
            mock_collection.query.return_value = {
                "documents": [["class A: pass", "class B: pass"]],
                "metadatas": [[
                    {"module_path": "mod.a", "entity_name": "A", "kind": "class", "file_path": "mod/a.py", "start_line": 1, "end_line": 1},
                    {"module_path": "mod.b", "entity_name": "B", "kind": "class", "file_path": "mod/b.py", "start_line": 1, "end_line": 1},
                ]],
                "distances": [[0.3158, 0.3514]],
            }

            results = query_codebase_collection(["test"], similarity_threshold=0.75)
            assert len(results) == 1
            assert results[0]["chunk"]["entity_name"] == "A"


# ---------------------------------------------------------------------------
# Token Budget Tests
# ---------------------------------------------------------------------------


class TestApplyTokenBudget:
    """Tests for apply_token_budget() — T160, T170."""

    def _make_result(self, name: str, score: float, tokens: int) -> RetrievalResult:
        return RetrievalResult(
            chunk=CodeChunk(
                content=f"class {name}: pass",
                module_path=f"mod.{name.lower()}",
                entity_name=name,
                kind="class",
                file_path=f"mod/{name.lower()}.py",
                start_line=1,
                end_line=1,
            ),
            relevance_score=score,
            token_count=tokens,
        )

    def test_budget_drops_lowest(self) -> None:
        """T160: Budget for 1.5 chunks keeps only top 1."""
        results = [
            self._make_result("A", 0.9, 100),
            self._make_result("B", 0.85, 100),
            self._make_result("C", 0.8, 100),
        ]
        trimmed = apply_token_budget(results, max_tokens=150)
        assert len(trimmed) == 1
        assert trimmed[0]["chunk"]["entity_name"] == "A"

    def test_budget_keeps_all(self) -> None:
        """T170: All chunks within budget returns all."""
        results = [
            self._make_result("A", 0.9, 100),
            self._make_result("B", 0.85, 100),
            self._make_result("C", 0.8, 100),
        ]
        trimmed = apply_token_budget(results, max_tokens=500)
        assert len(trimmed) == 3


# ---------------------------------------------------------------------------
# Context Formatting Tests
# ---------------------------------------------------------------------------


class TestFormatCodebaseContext:
    """Tests for format_codebase_context() — T180, T190."""

    def test_markdown_formatting(self) -> None:
        """T180: Output has header, instruction, and code blocks."""
        results = [
            RetrievalResult(
                chunk=CodeChunk(
                    content="class GovernanceAuditLog:\n    pass",
                    module_path="assemblyzero.core.audit",
                    entity_name="GovernanceAuditLog",
                    kind="class",
                    file_path="assemblyzero/core/audit.py",
                    start_line=1,
                    end_line=2,
                ),
                relevance_score=0.87,
                token_count=10,
            ),
            RetrievalResult(
                chunk=CodeChunk(
                    content="def validate_config(): pass",
                    module_path="assemblyzero.core.config",
                    entity_name="validate_config",
                    kind="function",
                    file_path="assemblyzero/core/config.py",
                    start_line=1,
                    end_line=1,
                ),
                relevance_score=0.79,
                token_count=8,
            ),
        ]
        context = format_codebase_context(results)
        assert "## Reference Codebase" in context["formatted_text"]
        assert "DO NOT reinvent" in context["formatted_text"]
        assert "```python" in context["formatted_text"]
        assert context["chunks_included"] == 2

    def test_empty_results(self) -> None:
        """T190: Empty results produces empty formatted_text."""
        context = format_codebase_context([])
        assert context["formatted_text"] == ""
        assert context["total_tokens"] == 0
        assert context["chunks_included"] == 0


# ---------------------------------------------------------------------------
# Token Count Tests
# ---------------------------------------------------------------------------


class TestEstimateTokenCount:
    """Tests for estimate_token_count() — T240."""

    def test_returns_positive(self) -> None:
        """T240: Token count is positive for non-empty text."""
        count = estimate_token_count("class Foo: pass")
        assert count > 0

    def test_no_network_calls(self) -> None:
        """T240: No network calls during token estimation."""
        with mock.patch("urllib3.PoolManager.request") as mock_request:
            count = estimate_token_count("class Foo: pass")
            assert count > 0
            mock_request.assert_not_called()


# ---------------------------------------------------------------------------
# End-to-End & Integration Tests
# ---------------------------------------------------------------------------


class TestRetrieveCodebaseContext:
    """Tests for retrieve_codebase_context() — T200."""

    def test_audit_lld_retrieves_governance(self) -> None:
        """T200: LLD with 'audit logging' retrieves GovernanceAuditLog."""
        lld_content = (FIXTURES_DIR / "sample_lld_audit.md").read_text(encoding="utf-8")

        # Mock the collection query to return GovernanceAuditLog
        with mock.patch("assemblyzero.rag.codebase_retrieval.chromadb") as mock_chromadb:
            mock_collection = mock.MagicMock()
            mock_client = mock.MagicMock()
            mock_chromadb.PersistentClient.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection
            mock_collection.query.return_value = {
                "documents": [["class GovernanceAuditLog:\n    \"\"\"Audit logging.\"\"\"\n    def log_event(self, event: str) -> bool: ..."]],
                "metadatas": [[{"module_path": "assemblyzero.core.audit", "entity_name": "GovernanceAuditLog", "kind": "class", "file_path": "assemblyzero/core/audit.py", "start_line": 15, "end_line": 30}]],
                "distances": [[0.1]],  # similarity ≈ 0.91
            }

            context = retrieve_codebase_context(lld_content)
            assert "GovernanceAuditLog" in context["formatted_text"]


class TestInjectCodebaseContext:
    """Tests for inject_codebase_context() — T210, T220, T230."""

    def test_inject_on_match(self) -> None:
        """T210: Modified prompt contains 'Reference Codebase' section."""
        from assemblyzero.workflows.implementation_spec.nodes.coder_node import (
            inject_codebase_context,
        )

        base_prompt = "You are a code generation assistant."
        lld_content = "Implement audit logging using GovernanceAuditLog."

        mock_context = CodebaseContext(
            formatted_text="## Reference Codebase\nUse these existing utilities. DO NOT reinvent them.\n\n```python\nclass GovernanceAuditLog: ...\n```\n",
            total_tokens=20,
            chunks_included=1,
            chunks_dropped=0,
            keywords_used=["GovernanceAuditLog", "audit"],
        )

        with mock.patch(
            "assemblyzero.workflows.implementation_spec.nodes.coder_node.retrieve_codebase_context",
            return_value=mock_context,
        ):
            result = inject_codebase_context(base_prompt, lld_content)
            assert "Reference Codebase" in result
            assert base_prompt in result

    def test_passthrough_on_no_match(self) -> None:
        """T220: Original prompt unchanged when no matches."""
        from assemblyzero.workflows.implementation_spec.nodes.coder_node import (
            inject_codebase_context,
        )

        base_prompt = "You are a code generation assistant."
        lld_content = "Something completely unrelated."

        mock_context = CodebaseContext(
            formatted_text="",
            total_tokens=0,
            chunks_included=0,
            chunks_dropped=0,
            keywords_used=[],
        )

        with mock.patch(
            "assemblyzero.workflows.implementation_spec.nodes.coder_node.retrieve_codebase_context",
            return_value=mock_context,
        ):
            result = inject_codebase_context(base_prompt, lld_content)
            assert result == base_prompt

    def test_exception_handling(self, caplog: pytest.LogCaptureFixture) -> None:
        """T230: Exception during retrieval logs warning, returns original prompt."""
        from assemblyzero.workflows.implementation_spec.nodes.coder_node import (
            inject_codebase_context,
        )

        base_prompt = "You are a code generation assistant."
        lld_content = "Any content."

        with mock.patch(
            "assemblyzero.workflows.implementation_spec.nodes.coder_node.retrieve_codebase_context",
            side_effect=RuntimeError("Connection failed"),
        ):
            with caplog.at_level(logging.WARNING):
                result = inject_codebase_context(base_prompt, lld_content)

            assert result == base_prompt
            assert "Codebase retrieval failed" in caplog.text


# ---------------------------------------------------------------------------
# Embedding Tests
# ---------------------------------------------------------------------------


class TestEmbeddings:
    """Tests for embedding generation — T270."""

    @pytest.mark.rag
    def test_local_embedding_dimensions(self) -> None:
        """T270: SentenceTransformer generates 384-dim embeddings locally."""
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode(["class Foo: pass"])
        assert embeddings.shape[1] == 384
```


## 7. Pattern References

### 7.1 Existing Node Implementation Pattern

**File:** `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py` (lines 1-50)

**Relevance:** This is an existing node in the same `implementation_spec/nodes/` directory where `coder_node.py` will be added. Follow the same module structure: module docstring with issue reference, `from __future__ import annotations`, logging setup, and function-based node implementation. The `coder_node.py` should match this pattern for consistency.

### 7.2 Existing CLI Tool Pattern

**File:** `tools/rebuild_knowledge_base.py` (lines 1-60)

**Relevance:** The modifications to this file must follow its existing patterns: `argparse`-based CLI, print statements for user feedback (prefixed with `[codebase]` for the new collection), `check_rag_dependencies()` guard at entry, and `sys.exit(1)` on missing dependencies. The `index_codebase()` function follows the same signature pattern as `run_full_ingestion()`.

### 7.3 RAG Module Init Pattern

**File:** `assemblyzero/rag/__init__.py` (lines 1-40)

**Relevance:** The existing init file groups imports by feature/issue. The new codebase_retrieval imports should follow the same grouping pattern, with a comment block in the docstring for Issue #92.

### 7.4 Test Pattern

**File:** `tests/unit/test_rag/` (existing test directory)

**Relevance:** Tests should follow the existing pytest patterns in the project: class-based test grouping, `pytest.mark.rag` for optional dependency tests, `caplog` fixture for log verification, `tmp_path` for temporary file creation, and `mock.patch` for external dependency isolation.


## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `import ast` | stdlib | `codebase_retrieval.py` |
| `import collections` | stdlib | `codebase_retrieval.py` |
| `import logging` | stdlib | `codebase_retrieval.py`, `coder_node.py` |
| `import re` | stdlib | `codebase_retrieval.py` |
| `from pathlib import Path` | stdlib | `codebase_retrieval.py`, test file |
| `from typing import Any, TypedDict` | stdlib | `codebase_retrieval.py` |
| `import tiktoken` | core dependency | `codebase_retrieval.py` (lazy import in `estimate_token_count`) |
| `import chromadb` | optional `[rag]` | `codebase_retrieval.py` (lazy import in `query_codebase_collection`) |
| `from sentence_transformers import SentenceTransformer` | optional `[rag]` | `rebuild_knowledge_base.py` (lazy import in `index_codebase`) |
| `from assemblyzero.rag.codebase_retrieval import retrieve_codebase_context` | internal | `coder_node.py` (lazy import inside function) |
| `from assemblyzero.rag.codebase_retrieval import scan_codebase, estimate_token_count` | internal | `rebuild_knowledge_base.py` (in `index_codebase`) |
| `import pytest` | dev dependency | test file |
| `from unittest import mock` | stdlib | test file |

**New Dependencies:** None. All required packages (`chromadb`, `sentence-transformers`, `tiktoken`) are already declared in `pyproject.toml`.


## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `parse_python_file()` | `sample_module.py` fixture path | Chunks contain `GovernanceAuditLog` with docstring |
| T020 | `parse_python_file()` | `sample_module.py` fixture path | Function chunks with `kind="function"` and type hints |
| T030 | `parse_python_file()` | `sample_module.py` fixture path | No `_internal_helper` or `_PrivateProcessor` in results |
| T040 | `parse_python_file()` | `sample_module_malformed.py` path | `[]`, no exception |
| T050 | `parse_python_file()` | tmp `__init__.py` with only docstring `'"""Package docstring."""\n'` | `[]` |
| T060 | `file_path_to_module_path()` | `"assemblyzero/core/audit.py"` | `"assemblyzero.core.audit"` |
| T070 | `split_compound_terms()` | `"GovernanceAuditLog"` | Parts include `"Governance"`, `"Audit"`, `"Log"`, `"GovernanceAuditLog"` |
| T080 | `split_compound_terms()` | `"audit_log_entry"` | Parts include `"audit"`, `"log"`, `"entry"`, `"audit_log_entry"` |
| T090 | `extract_keywords()` | `"Implement the feature using a new system that should create"` | No stopwords in result |
| T100 | `extract_keywords(max_keywords=5)` | Text with 20+ distinct CamelCase terms | `len(result) <= 5` |
| T110 | `extract_keywords()` | `"Use FooBarBaz"` | `"FooBarBaz"` in result |
| T120 | `query_codebase_collection()` | `["xyznonexistent123"]` + mocked high-distance results | `[]` |
| T130 | `query_codebase_collection()` | Two same-module chunks at distances 0.111 and 0.25 | Single highest-score result |
| T140 | `query_codebase_collection(max_results=10)` | 15 mocked results from different modules | `len(result) == 10` |
| T150 | `query_codebase_collection()` | Mocked `Exception("Collection not found")` | `[]` + warning in log |
| T160 | `apply_token_budget(max_tokens=150)` | 3 results at 100 tokens each | `[first_result]` |
| T170 | `apply_token_budget(max_tokens=500)` | 3 results at 100 tokens each | All 3 results |
| T180 | `format_codebase_context()` | 2 `RetrievalResult` objects | Markdown with `"## Reference Codebase"` + 2 code blocks |
| T190 | `format_codebase_context()` | `[]` | `{"formatted_text": "", "total_tokens": 0, ...}` |
| T200 | `retrieve_codebase_context()` | `sample_lld_audit.md` content + mocked collection | `"GovernanceAuditLog"` in `formatted_text` |
| T210 | `inject_codebase_context()` | Base prompt + LLD + mocked context with match | `"Reference Codebase"` in result |
| T220 | `inject_codebase_context()` | Base prompt + LLD + mocked empty context | `result == base_prompt` |
| T230 | `inject_codebase_context()` | Mocked `RuntimeError("Connection failed")` during retrieval | `result == base_prompt` + warning logged |
| T240 | `estimate_token_count()` | `"class Foo: pass"` + mocked urllib3 | `count > 0` + `mock_request.assert_not_called()` |
| T250 | `get_domain_stopwords()` | No input | Set contains `"def"`, `"class"`, `"implement"`, `"the"`, `"return"`, `"self"` |
| T260 | `parse_python_file()` | `sample_module.py` fixture path | `"str"`, `"bool"`, `"list[dict[str, str]]"` in chunk content |
| T270 | `SentenceTransformer.encode()` | `["class Foo: pass"]` | `shape[1] == 384` |
| T280 | `query_codebase_collection()` | Mocked results at distances 0.3158 and 0.3514 (sim ≈ 0.76, 0.74) | Only first result returned |
| T290 | `parse_python_file()` | tmp `broken.py` with `"def broken(\n"` + caplog | `[]` + file path in warning |


## 10. Implementation Notes

### 10.1 Error Handling Convention

All functions in `codebase_retrieval.py` follow a **fail-open** pattern:
- `parse_python_file()`: catches `SyntaxError`/`IOError`, returns `[]`, logs warning
- `query_codebase_collection()`: catches missing collection/import errors, returns `[]`, logs warning
- `inject_codebase_context()`: catches **any** `Exception`, returns `base_prompt` unchanged, logs warning
- No function in this module should ever raise an exception to the caller

### 10.2 Logging Convention

Use `logging.getLogger(__name__)` in each module:
- `logger.warning()` — for recoverable errors (parse failures, missing collections, import errors)
- `logger.info()` — for successful context injection (chunk count, token count)
- `logger.debug()` — for no-match situations
- `print()` with `[codebase]` prefix — only in `rebuild_knowledge_base.py` for CLI user feedback

### 10.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `DEFAULT_TOKEN_BUDGET` | `4096` | Function parameter default; balances context richness vs. prompt length |
| `DEFAULT_MAX_KEYWORDS` | `5` | Function parameter default; prevents over-querying |
| `DEFAULT_SIMILARITY_THRESHOLD` | `0.75` | Function parameter default; filters noise |
| `DEFAULT_MAX_RESULTS` | `10` | Function parameter default; sufficient context without overwhelming |
| `EMBEDDING_MODEL` | `"all-MiniLM-L6-v2"` | String in `index_codebase()` only; 384-dim, CPU-optimized |
| `BATCH_SIZE` | `500` | ChromaDB upsert batch limit in `index_codebase()` |

### 10.4 ChromaDB Distance to Similarity Conversion

ChromaDB returns L2 (Euclidean) distances by default. The conversion to a [0, 1] similarity score is:

```python
similarity = 1.0 / (1.0 + distance)
```

This means:
- `distance = 0.0` → `similarity = 1.0` (perfect match)
- `distance = 0.333` → `similarity = 0.75` (threshold)
- `distance = 10.0` → `similarity = 0.09` (very poor match)

### 10.5 Lazy Imports for Optional Dependencies

Both `chromadb` and `sentence-transformers` are optional `[rag]` dependencies. They must be imported lazily (inside function bodies, not at module top-level) to avoid `ImportError` when the optional dependencies are not installed. The `tiktoken` import in `estimate_token_count()` also uses a try/except for resilience.

---


## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 9)

---


## Review Log

| Field | Value |
|-------|-------|
| Issue | #92 |
| Verdict | DRAFT |
| Date | 2026-02-27 |
| Iterations | 2 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #92 |
| Verdict | APPROVED |
| Date | 2026-02-27 |
| Iterations | 1 |
| Finalized | 2026-02-27T12:11:32Z |

### Review Feedback Summary

Approved with suggestions:
*   **CLI UX:** In `tools/rebuild_knowledge_base.py`, the success message for `index_codebase` prints `Errors: {stats['errors']}`. Ensure that the logic in `scan_codebase` (which logs warnings but doesn't return an error count in the list of chunks) aligns with how `index_codebase` calculates errors. Currently, `index_codebase` sets `errors = 0` hardcoded (comment says "Errors are already logged..."). This is acceptable for MVP but could be refined later to return erro...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:

- `assemblyzero/core/audit.py`

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
    issue_workflow/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
    test_metrics/
    test_rag/
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
  telemetry/
  utils/
  workflow/
  workflows/
    implementation_spec/
      nodes/
    issue/
      nodes/
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
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_92.py
"""Test file for Issue #92.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from assemblyzero.rag.codebase_retrieval import *  # noqa: F401, F403


# Fixtures for mocking
@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    # TODO: Implement mock
    yield None


# Unit Tests
# -----------

def test_class_extraction_with_docstring():
    """
    T010: AST extracts class with docstring and methods. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_class_extraction_with_docstring works correctly
    assert False, 'TDD RED: test_class_extraction_with_docstring not implemented'


def test_function_extraction_with_type_hints():
    """
    T020: AST extracts top-level function with type hints. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_function_extraction_with_type_hints works correctly
    assert False, 'TDD RED: test_function_extraction_with_type_hints not implemented'


def test_private_entity_skip():
    """
    T030: AST skips private entities. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_private_entity_skip works correctly
    assert False, 'TDD RED: test_private_entity_skip not implemented'


def test_malformed_file_returns_empty():
    """
    T040: AST handles malformed Python file. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_malformed_file_returns_empty works correctly
    assert False, 'TDD RED: test_malformed_file_returns_empty not implemented'


def test_malformed_logs_warning():
    """
    T040/T290: Malformed Python file returns [] and logs warning with
    file path. | unit | tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_malformed_logs_warning works correctly
    assert False, 'TDD RED: test_malformed_logs_warning not implemented'


def test_docstring_only_init():
    """
    T050: AST skips __init__.py with only docstring. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_docstring_only_init works correctly
    assert False, 'TDD RED: test_docstring_only_init not implemented'


def test_empty_init():
    """
    T050 variant: AST skips completely empty __init__.py. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_empty_init works correctly
    assert False, 'TDD RED: test_empty_init not implemented'


def test_type_hints_preserved():
    """
    T260: AST extracts ClassDef with type hints preserved in content. |
    unit | tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_type_hints_preserved works correctly
    assert False, 'TDD RED: test_type_hints_preserved not implemented'


def test_standard_path():
    """
    T060: Convert standard file path to module path. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_standard_path works correctly
    assert False, 'TDD RED: test_standard_path not implemented'


def test_init_path():
    """
    T060 variant: Convert __init__.py path. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_init_path works correctly
    assert False, 'TDD RED: test_init_path not implemented'


def test_camel_case():
    """
    T070: CamelCase splitting. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_camel_case works correctly
    assert False, 'TDD RED: test_camel_case not implemented'


def test_snake_case():
    """
    T080: snake_case splitting. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_snake_case works correctly
    assert False, 'TDD RED: test_snake_case not implemented'


def test_stopword_filtering():
    """
    T090: Stopwords are filtered out. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_stopword_filtering works correctly
    assert False, 'TDD RED: test_stopword_filtering not implemented'


def test_max_keywords_limit():
    """
    T100: Keyword extraction limits to top N. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_max_keywords_limit works correctly
    assert False, 'TDD RED: test_max_keywords_limit not implemented'


def test_fallback_on_sparse_input():
    """
    T110: Keyword extraction fallback on sparse CamelCase input. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_fallback_on_sparse_input works correctly
    assert False, 'TDD RED: test_fallback_on_sparse_input not implemented'


def test_contains_expected_terms():
    """
    T250: Domain stopwords are comprehensive. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_contains_expected_terms works correctly
    assert False, 'TDD RED: test_contains_expected_terms not implemented'


def test_threshold_filtering(mock_external_service):
    """
    T120: Nonsense query returns empty results with mocked low scores. |
    unit | tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_threshold_filtering works correctly
    assert False, 'TDD RED: test_threshold_filtering not implemented'


def test_module_deduplication():
    """
    T130: Two chunks from same module keeps only highest score. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_module_deduplication works correctly
    assert False, 'TDD RED: test_module_deduplication not implemented'


def test_max_results_limit():
    """
    T140: Query returns at most max_results. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_max_results_limit works correctly
    assert False, 'TDD RED: test_max_results_limit not implemented'


def test_missing_collection_graceful():
    """
    T150: Missing collection returns empty list with warning. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_missing_collection_graceful works correctly
    assert False, 'TDD RED: test_missing_collection_graceful not implemented'


def test_similarity_threshold_boundary():
    """
    T280: Results at boundary — 0.76 passes, 0.74 fails. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_similarity_threshold_boundary works correctly
    assert False, 'TDD RED: test_similarity_threshold_boundary not implemented'


def test_budget_drops_lowest():
    """
    T160: Budget for 1.5 chunks keeps only top 1. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_budget_drops_lowest works correctly
    assert False, 'TDD RED: test_budget_drops_lowest not implemented'


def test_budget_keeps_all():
    """
    T170: All chunks within budget returns all. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_budget_keeps_all works correctly
    assert False, 'TDD RED: test_budget_keeps_all not implemented'


def test_markdown_formatting():
    """
    T180: Output has header, instruction, and code blocks. | unit |
    tests/unit/test_rag/test_codebase_retrieval.py
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_markdown_formatting works correctly
    assert False, 'TDD RED: test_markdown_formatting not implemented'




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
