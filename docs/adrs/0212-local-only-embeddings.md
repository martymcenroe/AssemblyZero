# ADR-0212: Local-Only Embeddings Policy

**Status:** Accepted
**Date:** 2026-03-01
**Issue:** #114
**Related:** ADR-0211 (RAG Architecture)

## 1. Context

The RAG subsystem (ADR-0211) requires an embedding model to convert documents and queries into vectors for similarity search. Two approaches exist:

1. **Cloud-hosted embeddings** (OpenAI `text-embedding-3-small`, Cohere, etc.) — send text to an API, receive vectors back
2. **Local embeddings** (SentenceTransformers `all-MiniLM-L6-v2`) — run the model on the developer's machine

AssemblyZero already sends code context to Claude and Gemini for generation and review. The question is whether the RAG indexing pipeline should also send data externally.

## 2. Decision

**All embeddings run locally. No document content leaves the developer machine for vectorization.**

### Implementation

- **Model:** `all-MiniLM-L6-v2` via SentenceTransformers
- **Dimension:** 384-dimensional vectors
- **Storage:** ChromaDB with local persistent storage (`.assemblyzero/vector_store/`)
- **Provider:** `LocalEmbeddingProvider` in `assemblyzero/rag/embeddings.py`

### Why Local-Only

1. **Data scope is different.** Claude/Gemini see targeted code snippets and briefs during active work. RAG indexing processes the *entire* governance corpus — every ADR, every standard, every completed LLD, every archived lineage file. Sending all of that to an embedding API creates a comprehensive map of the project's decision history.

2. **Indexing is passive.** When a developer runs `rebuild_knowledge_base.py`, they expect a local operation. Silent network calls to an embedding API violate the principle of least surprise.

3. **Cost control.** OpenAI embedding API costs are low per-call but accumulate across full re-indexes. Local embeddings have zero marginal cost after the initial model download.

4. **Offline capability.** Developers working on planes, trains, or restricted networks can still use RAG features.

5. **No API key dependency.** The RAG subsystem has no external credentials to manage, rotate, or protect.

### Model Selection: Why all-MiniLM-L6-v2

| Criterion | all-MiniLM-L6-v2 | OpenAI text-embedding-3-small |
|-----------|-------------------|-------------------------------|
| Latency | ~5ms/document (local) | ~100ms/document (network) |
| Cost | Free | $0.02/1M tokens |
| Offline | Yes | No |
| Dimension | 384 | 1536 |
| Quality | Good for documentation search | Better for general-purpose |
| License | Apache 2.0 | Proprietary API |
| Privacy | No data egress | Full text sent to OpenAI |

The 384-dimension model is sufficient for documentation retrieval where queries are semantically similar to source material (issue briefs matching ADRs and standards). The higher dimensionality of cloud models provides marginal benefit for this use case.

## 3. Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| OpenAI embeddings | Data egress, API dependency, cost accumulation |
| Cohere embeddings | Same data egress concerns as OpenAI |
| Larger local model (e.g., `all-mpnet-base-v2`) | 2x slower, marginal quality improvement for our use case |
| Hybrid (local for indexing, cloud for queries) | Inconsistent — if we trust local for indexing, use it for queries too |

## 4. Consequences

### Positive
- Zero data egress for the RAG pipeline
- No API keys to manage for embeddings
- Works offline
- Zero ongoing cost
- Consistent with AssemblyZero's privacy posture

### Negative
- Model download is ~90MB (one-time)
- PyTorch dependency is ~2GB (shared with other ML tools if present)
- Lower embedding quality than cloud models (acceptable for our use case)
- Cold-start latency (~5-10s) on first query of a session

## 5. Compliance Note

All RAG dependencies use permissive open-source licenses:

| Dependency | License |
|------------|---------|
| chromadb | Apache 2.0 |
| sentence-transformers | Apache 2.0 |
| torch (transitive) | BSD-3-Clause |
| all-MiniLM-L6-v2 (model) | Apache 2.0 |

All compatible with AssemblyZero's PolyForm-Noncommercial-1.0.0 license.

## 6. References

- ADR-0211: RAG Architecture (Brutha Foundation)
- ADR-0205: RAG Librarian
- [SentenceTransformers documentation](https://www.sbert.net/)
- [all-MiniLM-L6-v2 model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
