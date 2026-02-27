# LLD Review: #88 - Feature: RAG Injection - Automated Context Retrieval ("The Librarian")

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate: PASSED
All required elements (Issue Link, Context, Proposed Changes) are present.

## Review Summary
The LLD is exceptionally well-structured and addresses the architectural challenge of adding heavy dependencies (ML libraries) to a lightweight core via a well-designed conditional import strategy. The decision to isolate the RAG workflow in `assemblyzero/workflows/lld/` rather than modifying the stable orchestrator graph is prudent. The test plan is comprehensive with 100% requirement coverage.

## Open Questions Resolved
- [x] ~~Should the similarity threshold (0.7) be configurable via CLI flag (`--rag-threshold`) or only via config file?~~ **RESOLVED: Implement both. Config file defines the default; CLI flag overrides it. This allows for rapid experimentation during tuning.**
- [x] ~~What is the maximum combined token budget for injected RAG context to avoid exceeding Designer prompt limits?~~ **RESOLVED: Set a soft limit of 2,000 tokens. With ~500 tokens per chunk, this comfortably fits the top-3 chunks plus protocol overhead within standard context windows (8k-32k).**
- [x] ~~Should `rebuild_knowledge_base.py` be invocable as a subcommand (`assemblyzero rag rebuild`) in addition to standalone script?~~ **RESOLVED: Yes. Register it as a subcommand for developer ergonomics, but keep the standalone script entry point for CI/scripting usage.**
- [x] ~~Which existing workflow graph... or should a new `lld` workflow directory be created?~~ **RESOLVED: Proceed with the proposed `assemblyzero/workflows/lld/` directory. Do not modify `assemblyzero/workflows/orchestrator/graph.py` yet. This isolation prevents regression in the core workflow while RAG is experimental.**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | ChromaDB stores vectors in .assemblyzero/vector_store/ with persistent HNSW index | T060, T070, T080, T290 | ✓ Covered |
| 2 | Default embedding model is all-MiniLM-L6-v2 (local); external APIs opt-in | T240 | ✓ Covered |
| 3 | Documents in docs/adrs/, standards/, LLDs/done/ indexed by H1/H2 splitting | T010, T020, T030 | ✓ Covered |
| 4 | Librarian queries k=5, filters 0.7, returns top 3 | T090, T100, T150 | ✓ Covered |
| 5 | Retrieval completes in < 500ms after warm-up | T250 | ✓ Covered |
| 6 | CLI spinner displays during cold-boot loading | T260 | ✓ Covered |
| 7 | Manual --context takes precedence over RAG results with deduplication | T170, T180 | ✓ Covered |
| 8 | Workflow degrades when vector store is missing (warning, continues) | T120, T140 | ✓ Covered |
| 9 | Workflow degrades when [rag] extra is not installed (message, continues) | T040, T050, T110, T130, T230 | ✓ Covered |
| 10 | tools/rebuild_knowledge_base.py supports --full and --incremental modes | T200, T210 | ✓ Covered |
| 11 | Full reindex of ~100 files completes in < 10 seconds | T270 | ✓ Covered |
| 12 | Core pip install does not install chromadb or sentence-transformers | T280 | ✓ Covered |
| 13 | Vector store persists between sessions | T290 | ✓ Covered |
| 14 | Retrieved documents are logged at INFO level | T160, T190 | ✓ Covered |

**Coverage Calculation:** 14 requirements covered / 14 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

### Cost
- [ ] No issues found. Local-first design ($0) is excellent.

### Safety
- [ ] No issues found. Destructive operations are limited to the `.assemblyzero/vector_store/` cache directory, which is safe.

### Security
- [ ] No issues found. Input sanitization relies on the embedding model (standard practice). No execution of retrieved content occurs.

### Legal
- [ ] No issues found. Dependency licenses are compatible.

## Tier 2: HIGH PRIORITY Issues
No high-priority issues found.

### Architecture
- [ ] **Semantic Path Check:** The use of `assemblyzero/` (root package) instead of `src/` matches the project structure. The new `rag` module and `workflows/lld` directory are correctly placed.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** PASS (100%).

## Tier 3: SUGGESTIONS
- **DoS Protection:** In `chunk_markdown`, consider adding a hard limit to the number of chunks processed per file (e.g., 50 chunks) to prevent a malicious or accidental massive markdown file from hanging the ingestion process.
- **Cache Invalidation:** In `incremental` mode, ensure that if a file is *deleted* from the source directories, its chunks are also removed from ChromaDB. The current logic describes updating changed files, but handling deletions is a common edge case in sync logic.

## Questions for Orchestrator
1. None.

## Verdict
[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision