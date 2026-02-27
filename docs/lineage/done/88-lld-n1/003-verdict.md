# LLD Review: 188-Feature: RAG Injection: Automated Context Retrieval ("The Librarian")

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The design for "The Librarian" is robust, featuring a well-structured local RAG implementation with careful attention to fallback mechanisms and optional dependencies. The architecture using ChromaDB and `sentence-transformers` is appropriate for the scale. However, the LLD currently fails the Requirement Coverage check (<95%) due to missing tests for performance budgets and the final output requirement. These must be addressed before implementation.

## Open Questions Resolved
- [x] ~~Should the similarity threshold (0.7) be configurable via environment variable or CLI flag?~~ **RESOLVED: Yes. Use an environment variable (e.g., `AGENTOS_RAG_THRESHOLD`) with a default of 0.7 to allow tuning without code changes.**
- [x] ~~What is the expected cold-boot time budget for embedding model loading (currently specified as spinner at 500ms)?~~ **RESOLVED: Allocate a 5-10s budget for model loading. 500ms is unrealistic for loading PyTorch/weights. The spinner is mandatory.**
- [x] ~~Should we support hybrid search (keyword + semantic) for edge cases where semantic similarity misses exact terminology matches?~~ **RESOLVED: No. Stick to semantic search for this MVP to minimize complexity. Hybrid search can be a future enhancement if recall issues are proven.**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | `tools/rebuild_knowledge_base.py` indexes 100+ files in < 10 seconds | - | **GAP** |
| 2 | Queries complete in < 500ms after model warm-up | - | **GAP** |
| 3 | Query "How do I log errors?" retrieves logging-related documents | T150 | ✓ Covered |
| 4 | Query "authentication flow" retrieves identity/auth ADRs | T160 | ✓ Covered |
| 5 | Workflow gracefully degrades when vector store is missing | T040, T110 | ✓ Covered |
| 6 | Workflow gracefully degrades when `[rag]` extra not installed | T020, T100 | ✓ Covered |
| 7 | Manual `--context` takes precedence over RAG results | T080 | ✓ Covered |
| 8 | Vector store persists between sessions | T030, T150 | ✓ Covered |
| 9 | Core `pip install agentos` does not pull torch/chromadb | T180 | ✓ Covered |
| 10 | `pip install agentos[rag]` works cleanly | T190 | ✓ Covered |
| 11 | CLI spinner displays during cold-boot model loading | T170 | ✓ Covered |
| 12 | Generated LLDs reference retrieved ADRs in Constraints section automatically | - | **GAP** |

**Coverage Calculation:** 9 requirements covered / 12 total = **75%**

**Verdict:** BLOCK

**Missing Test Scenarios:**
1.  **Performance Test (Indexing):** A test measuring execution time of `rebuild_knowledge_base.py` on a fixture of 100 small files.
2.  **Performance Test (Query):** A benchmark test asserting `query_knowledge_base` takes <500ms on a warmed-up model.
3.  **E2E Output Verification:** An integration test verifying that when RAG context is injected, the resulting LLD (or a mock Designer step) actually includes the referenced material in its output.

## Tier 1: BLOCKING Issues
No Tier 1 blocking issues found. Cost, Safety, Security, and Legal sections are well-handled.

## Tier 2: HIGH PRIORITY Issues

### Quality
- [ ] **Requirement Coverage Gap (75%):** The test plan misses critical performance constraints and the final functional output requirement.
    *   **Recommendation:** Add scenarios T200 (Indexing Perf), T210 (Query Perf), and T220 (E2E Content Verification) to Section 10.1 and the TDD checklist.
- [ ] **Performance Testing Strategy:** Requirements 1 and 2 specify strict timing (<10s, <500ms) but no automated tests enforce these budgets.
    *   **Recommendation:** Add specific performance assertions using `time.perf_counter()` in the new test scenarios.

## Tier 3: SUGGESTIONS
- **Configuration:** Add `AGENTOS_RAG_THRESHOLD` and `AGENTOS_RAG_MODEL` to the `LibrarianConfig` definition to support the resolution of Open Question #1.
- **CLI UX:** Ensure `rebuild_knowledge_base.py` provides a progress bar (e.g., `tqdm`) as 100+ files might feel slow even if <10s.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision