

```markdown
# ADR-0205: RAG Librarian for Automated Context Retrieval

**Status:** Accepted
**Date:** 2026-02-27
**Issue:** #88

## 1. Context

The Designer node in the LLD workflow requires relevant governance documents (ADRs, standards, completed LLDs) as context to produce high-quality designs. Currently, context is provided manually via the `--context` CLI flag, which requires the user to know which documents are relevant.

## 2. Decision

Implement an automated RAG (Retrieval-Augmented Generation) system — "The Librarian" — that:
- Indexes governance documents in a local ChromaDB vector store
- Embeds issue briefs using `all-MiniLM-L6-v2` (local, no external API)
- Retrieves top-3 most relevant document chunks above a 0.7 similarity threshold
- Injects retrieved context into the Designer's prompt

The system is entirely optional via `pip install assemblyzero[rag]`.

## 3. Consequences

### Positive
- Designers automatically receive relevant context without manual curation
- Local-first: no data leaves the developer machine
- Zero ongoing cost (local model, local storage)
- Graceful degradation: workflow continues if RAG is unavailable

### Negative
- Optional dependency size: ~2GB (PyTorch) + ~200MB (model + ChromaDB)
- Requires manual knowledge base rebuild when docs change
- Initial cold-boot latency (~5-10s for model loading)

## 4. License Compliance

| Dependency | License | Compatible with PolyForm-NC-1.0.0? |
|------------|---------|--------------------------------------|
| chromadb | Apache 2.0 | ✅ Yes |
| sentence-transformers | Apache 2.0 | ✅ Yes |
| torch (transitive) | BSD-3-Clause | ✅ Yes |
| all-MiniLM-L6-v2 (model) | Apache 2.0 | ✅ Yes |

All dependencies use permissive open-source licenses compatible with our PolyForm-Noncommercial-1.0.0 project license.

## 5. Alternatives Considered

See LLD #88 Section 4 for full analysis. Key alternatives rejected:
- **FAISS + pickle:** No built-in persistence or metadata management
- **SQLite FTS5:** No semantic search capability
- **LangChain vector store:** Extra abstraction without benefit
```
