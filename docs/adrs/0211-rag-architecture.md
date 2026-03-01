# ADR-0211: RAG Architecture (Brutha Foundation)

**Status:** Accepted
**Date:** 2026-03-01
**Issue:** #114
**Related:** ADR-0205 (RAG Librarian), ADR-0212 (Local-Only Embeddings)

## 1. Context

AssemblyZero's workflows need contextual awareness — an LLD draft should reference relevant ADRs, a duplicate check should recall past issues, and implementation specs should understand the existing codebase. Manually curating context for each LLM invocation doesn't scale.

Issues #113 (Brutha), #88 (Librarian), #92 (Hex), and #91 (Historian) collectively built a RAG subsystem that serves multiple consumers. This ADR documents the overall architecture that emerged from those implementations.

## 2. Decision

### Architecture: Shared Foundation, Specialized Consumers

```
                    ┌─────────────────────────┐
                    │     Brutha Foundation    │
                    │    (assemblyzero/rag/)   │
                    │                         │
                    │  ChromaDB Vector Store   │
                    │  Local Embeddings        │
                    │  Chunking Pipeline       │
                    │  Query Engine            │
                    └────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼──────┐ ┌────▼──────┐ ┌─────▼───────┐
     │  Librarian    │ │   Hex     │ │  Historian   │
     │  (docs RAG)   │ │(code RAG) │ │(history RAG) │
     │  #88          │ │ #92       │ │ #91          │
     └───────────────┘ └───────────┘ └──────────────┘
```

**Brutha** (`assemblyzero/rag/`) is the shared infrastructure layer:
- `config.py` — Immutable `RAGConfig` dataclass (persist dir, model name, chunk size, thresholds)
- `store.py` / `vector_store.py` — ChromaDB persistent client, thread-safe singleton
- `embeddings.py` — `LocalEmbeddingProvider` wrapping `all-MiniLM-L6-v2`
- `chunking.py` / `chunker.py` — Document splitting (512 tokens, 50-token overlap)
- `query.py` — `QueryEngine` with top-k retrieval and similarity filtering
- `collections.py` — Collection CRUD operations
- `models.py` — `ChunkMetadata`, `RetrievedDocument`, `IngestionSummary`
- `errors.py` — `RAGError` hierarchy
- `dependencies.py` — Optional dependency checking (`pip install assemblyzero[rag]`)

**The Librarian** (`assemblyzero/rag/librarian.py` + `assemblyzero/nodes/librarian.py`):
- LangGraph node that embeds an issue brief and retrieves relevant governance documents
- Source directories: `docs/adrs/`, `docs/standards/`, `docs/LLDs/done/`, `docs/lineage/done/`
- Returns top-3 results above 0.7 cosine similarity threshold
- Graceful degradation: `deps_missing`, `unavailable`, `no_results`, `success`

**Hex** (`assemblyzero/rag/codebase_retrieval.py`):
- AST-based Python code indexing (classes, functions, methods)
- Keyword extraction from LLD content
- Token-budget-aware retrieval (drops lowest-scoring chunks to fit budget)
- Formats results as markdown for LLM prompt injection

**The Historian** (`assemblyzero/workflows/issue/nodes/historian.py`):
- Queries RAG store with issue brief before drafting
- Detects potential duplicates by finding similar past issues
- Injects historical context into the draft prompt

### Data Flow

```
Source Documents                     Consumer Workflows
─────────────────                    ──────────────────
docs/adrs/*.md        ─┐
docs/standards/*.md    ─┤  rebuild_knowledge_base.py   ┌─ Requirements (LLD)
docs/LLDs/done/*.md    ─┼──────────────────────────────┤─ Issue (draft)
docs/lineage/done/*.md ─┘         │                    └─ Implementation Spec
                              ChromaDB                         │
*.py (AST parsed)     ──── codebase indexing ──────────── TDD Implementation
```

### Key Design Decisions

1. **Optional dependency.** RAG requires ~2GB (PyTorch + model). Install via `pip install assemblyzero[rag]`. All workflows gracefully degrade if RAG is absent.
2. **Single vector store.** One ChromaDB instance with multiple collections, not separate databases per consumer.
3. **Thread-safe singletons.** `get_store()` and `get_query_engine()` provide process-wide shared instances with lazy initialization.
4. **Rebuild, don't incrementally update.** `tools/rebuild_knowledge_base.py` does full re-indexing. Incremental updates add complexity without proportional benefit at current scale.

## 3. Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| FAISS + serialized state | No built-in persistence or metadata management |
| SQLite FTS5 | No semantic search — only keyword matching |
| LangChain vector store | Extra abstraction layer without benefit |
| Cloud-hosted embeddings (OpenAI) | Violates local-only policy (see ADR-0212) |
| Separate vector stores per consumer | Unnecessary complexity; collections provide isolation |

## 4. Consequences

### Positive
- Workflows automatically receive relevant context without manual curation
- Single shared infrastructure reduces maintenance burden
- Local-first: no data leaves the developer machine
- Zero ongoing cost (local model, local storage)

### Negative
- ~2GB optional dependency size
- Requires manual knowledge base rebuild when docs change significantly
- Cold-boot latency (~5-10s for model loading on first query)

## 5. References

- ADR-0205: RAG Librarian (original Librarian-specific decision)
- ADR-0212: Local-Only Embeddings Policy
- Issue #113: Vector Database Foundation (Brutha)
- Issue #88: The Librarian (RAG Injection)
- Issue #92: Hex (Codebase Retrieval)
- Issue #91: The Historian (History Check)
