---
repo: martymcenroe/AgentOS
issue: 113
url: https://github.com/martymcenroe/AgentOS/issues/113
fetched: 2026-02-04T14:47:33.820124Z
---

# Issue #113: Brutha: Vector Database Infrastructure (RAG Foundation)

# Brutha: Vector Database Infrastructure (RAG Foundation)

**Persona:** Brutha (*Small Gods*)
> *"The turtle moves. And I remember everything."*

## User Story
As a **workflow developer**,
I want a **shared vector database infrastructure with perfect recall**,
So that **The Librarian (docs), Hex (code), and future agents can all query the same memory layer**.

## Objective
Implement the foundational RAG infrastructure that other personas (Librarian, Hex) consume. Brutha is the memory itself—he does not hallucinate, he only recalls what was stored.

## Responsibilities
- ChromaDB (or equivalent) vector store setup
- Embedding model configuration (local SentenceTransformers)
- Collection management API
- Shared infrastructure for:
  - Issue #88 (The Librarian - documentation retrieval)
  - Issue #92 (Hex - codebase retrieval)

## Technical Approach
- Local vector store (no external API calls for embeddings)
- Collection-per-domain architecture (`documentation`, `codebase`, etc.)
- Unified query interface
- Persistence in `.agentos/vector_store/`

## Acceptance Criteria
- [ ] Vector store initializes on first use
- [ ] Multiple collections supported (docs, code, etc.)
- [ ] Embedding generation is fully local (no data egress)
- [ ] The Librarian (#88) and Hex (#92) can both query their respective collections
- [ ] Graceful degradation when vector store not initialized

## Dependencies
- This is a foundation issue - #88 and #92 depend on it
- `sentence-transformers` package
- `chromadb` package

## Philosophy
Brutha was a simple novice with eidetic memory. He remembered every word, every page, every conversation—perfectly and without embellishment. 

In AgentOS, Brutha is the RAG layer. He does not invent. He does not guess. He only recalls exactly what was stored.