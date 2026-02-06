# RAG Injection: Architectural Consistency (The Librarian)

**Context:** We have implemented manual context injection via the `--context` CLI flag in the LLD Workflow (#DN-001). While useful, this relies entirely on the user remembering which ADRs or Standards are relevant. As the documentation grows (currently 100+ files), human memory becomes the bottleneck.

## Problem

**The "Amnesiac Designer" Failure Mode:**
When the Designer Node creates an LLD, it often proposes solutions that violate established architectural decisions because it cannot "see" the `docs/adrs/` folder.

* *Example:* Designer proposes a new logging library, ignoring `docs/LLDs/done/57-distributed-logging.md`.
* *Example:* Designer suggests direct SQL queries, ignoring `docs/adrs/0204-single-identity-orchestration.md`.

## Goal

Implement an **Automated Retrieval Node ("The Librarian")** at the start of the LLD Workflow.

1. **Index:** Automatically ingest `docs/adrs/`, `docs/standards/`, and `docs/LLDs/done/` into a local vector store.
2. **Retrieve:** Before the Designer starts, query the store with the Issue Brief.
3. **Inject:** Silently append the Top-3 most relevant governance documents to the context.

## Proposed Architecture

### 1. Local Vector Infrastructure

We will use **ChromaDB** (local, file-based) or **FAISS** to avoid external dependencies/infrastructure costs.

* **Storage Location:** `.assemblyzero/vector_store/`
* **Ingestion Tool:** `tools/rebuild_knowledge_base.py`
* Scans `docs/` for markdown files.
* Splits by header (H1/H2).
* Generates embeddings (using a small local model like `all-MiniLM-L6-v2` or OpenAI/Gemini embeddings if API key available).



### 2. The Librarian Node (`assemblyzero/nodes/librarian.py`)

A new node for the `lld_workflow` graph.

* **Input:** `issue_brief` (text)
* **Process:**
1. Embed the brief.
2. Query Vector Store for `k=3` nearest neighbors from `docs/adrs/` and `docs/standards/`.
3. Filter results (score threshold > 0.7).


* **Output:** `retrieved_context` (List of file paths + content snippets).

### 3. Workflow Integration

Modify `assemblyzero/workflows/lld/graph.py`:

**Current:**
`Load Brief -> [Manual Context] -> Designer -> ...`

**New:**
`Load Brief -> [Librarian Node] -> [Manual Context Merge] -> Designer -> ...`

* The Librarian *augments* the manual `--context` flag, it does not replace it. User manual overrides always win.

## Implementation Steps

1. **Dependencies:** Add `chromadb` and `sentence-transformers` to `pyproject.toml`.
2. **Ingestion Script:** Create `tools/rebuild_knowledge_base.py`.
3. **Node Logic:** Implement `assemblyzero/nodes/librarian.py`.
4. **Graph Update:** Wire the node into `run_lld_workflow.py`.

## Success Criteria

* [ ] `tools/rebuild_knowledge_base.py` runs in < 10 seconds for current docset.
* [ ] Querying "How do I log errors?" retrieves `docs/standards/0002-coding-standards.md` or `assemblyzero/core/audit.py`.
* [ ] The generated LLD references the retrieved ADRs in its "Constraints" section without human prompting.