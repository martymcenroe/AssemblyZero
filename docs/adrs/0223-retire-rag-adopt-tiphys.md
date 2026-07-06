# ADR 0223: Retire the RAG Librarian; adopt Tiphys (structural interface-map) for LLD grounding

**Status:** Accepted
**Date:** 2026-07-06
**Supersedes:** ADR-0205 (RAG Librarian), ADR-0211 (RAG Architecture / Brutha), ADR-0212 (Local-Only Embeddings)
**Related:** #1687 (the chronically-red CI this closes), #1688 (Tiphys build), #88 (the original Librarian)

---

## 1. Context

The LLD (design) stage hallucinates *interfacing function names that don't exist*. The intended fix (#88) was **RAG — "the Librarian"**: a local ChromaDB vector store + `sentence-transformers` embeddings meant to retrieve relevant codebase/doc context for the design. Three ADRs codified it — 0205 (the Librarian node), 0211 (the Brutha RAG foundation), 0212 (local-only embeddings).

It never became load-bearing:

- The RAG-wired LLD graph (`assemblyzero/workflows/lld/graph.py`: `check_rag → librarian / skip_rag → END`) is **vestigial** — zero production callers. The live LLD runs through the requirements workflow (`workflow_type="lld"`), whose pre-drafter node `N0b_analyze_codebase` contains no RAG.
- The `[rag]` extra (chromadb, sentence-transformers) is **not installed by default or in CI**, so the Librarian was gated off everywhere. RAG was **dormant**.
- Its dormant integration tests are why **main CI had been red for days (#1687)** — they run only on main-push and fail with `ImportError: Missing: chromadb, sentence-transformers`.
- The documentation even **contradicts itself** about whether RAG was ever live (some pages describe shipped ChromaDB embeddings; others insist embeddings are "not used / only planned"). That contradiction is the fingerprint of a feature half-built and abandoned.

## 2. Decision

**Retire RAG entirely. Ground the LLD with Tiphys instead — a deterministic node that reads the real public interface surface (AST signatures) of the modules a change touches, and feeds it into the drafter.**

The core reason RAG was the wrong tool: **RAG is a similarity engine; interface-grounding is a ground-truth lookup.** RAG returns the *most similar* function — which is exactly how you retrieve a plausible-but-wrong name and make the interface-hallucination *worse*. A design doesn't need something *like* the real interface; it needs *the* real interface. That is `ast`-level signature extraction, not vector search.

Retired in this ADR's PR (`Closes #1687`): `assemblyzero/rag/` (14 modules), `assemblyzero/nodes/librarian.py`, the vestigial `workflows/lld/graph.py`, the orphaned `implementation_spec/nodes/coder_node.py`, `tools/rebuild_knowledge_base.py`, all RAG tests, and the `[rag]` optional extra. This supersedes ADR-0205 / 0211 / 0212.

Tiphys (build tracked in #1688) reuses extractors that **already exist** at the spec stage (`implementation_spec/nodes/analyze_codebase.py`'s AST summarizers; the reactive `check_api_symbols_exist` gate). No vector store, no embeddings, no torch. It is the first "channel marker" in a code-awareness funnel that narrows LLD → spec → impl ("red, right, returning").

## 3. Consequences

- **Main CI goes green** — the RAG integration tests that failed on every main-push are gone (#1687 closed).
- The `[rag]` extra (chromadb, sentence-transformers, and their transitive torch) leaves the dependency surface. `tiktoken` **stays** — it has non-RAG users (`retry_prompt_builder`, `feedback_window`, `scout/budget`).
- **ADR-0205 / 0211 / 0212 are Superseded but preserved** — the story of what was tried and why it was wrong is kept for depth: this ADR plus the untouched build lineage in `docs/lineage/`.
- The `assemblyzero/workflows/lld/` package survives minus its RAG graph; its two now-unused `LLDState` fields (`retrieved_context`, `rag_status`) are harmless dead fields, left for a trivial follow-up.
- Naming: the **Librarian** (Pratchett) is retired; the replacement is **Tiphys** (helmsman of the Argo), inscribed in the fleet's Well of Names.

## 4. Alternatives considered

- **Install `[rag]` in CI and keep it** — rejected. Commits to maintaining and testing a similarity tool for a ground-truth job, and pulls torch into CI. The wrong tool, kept for the wrong reason.
- **`pytest.importorskip` the RAG tests** — rejected. Greens CI by hiding, not fixing: RAG would ship untested and be rediscovered only in an audit. A skip is invisible debt.
- **Keep the Librarian name, swap the mechanism underneath** — rejected. The name carried the retrieval identity (a library, L-space); the new mechanism is navigation to ground truth. New identity, new name.
