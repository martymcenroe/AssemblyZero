# LLD Review: 188-Feature: RAG Injection: Automated Context Retrieval ("The Librarian")

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The design for "The Librarian" is architecturally sound, choosing appropriate local-first technologies (ChromaDB, SentenceTransformers) that align with the project's privacy and license constraints. The optional dependency model is well-structured. However, the Testing Plan currently lacks coverage for performance and UI requirements specified in Section 3, resulting in a coverage check failure.

## Open Questions Resolved
- [x] ~~Should vector store be per-project or shared across projects in a workspace?~~ **RESOLVED: Per-project (`.agentos/vector_store/`).** This ensures project isolation, prevents context leakage between unrelated efforts, and simplifies file path resolution relative to the project root.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| R1 | Indexing < 10s for 100+ files | T130 (checks count only) | **GAP** - No timing assertion |
| R2 | Query "log errors" > 0.7 | T060 | ✓ Covered |
| R3 | Query "auth flow" > 0.7 | T060 (generic happy path) | ✓ Covered |
| R4 | Retrieval < 500ms | - | **GAP** - No latency test |
| R5 | Generated LLD refs ADRs | T150 | ✓ Covered |
| R6 | Degrade: Store missing | T090 | ✓ Covered |
| R7 | Degrade: Deps missing | T080 | ✓ Covered |
| R8 | Manual context precedence | T110 | ✓ Covered |
| R9 | Store persistence | T030, T130 | ✓ Covered |
| R10 | Core installs w/o ML deps | T020 (logic check) | ✓ Covered |
| R11 | RAG extra installs on CI | T150, T160 (integration) | ✓ Covered |
| R12 | CLI spinner displays | - | **GAP** - No UI interaction test |

**Coverage Calculation:** 9 requirements covered / 12 total = **75%**

**Verdict:** **BLOCK** (Requires ≥95%)

**Missing Test Scenarios:**
1. `test_indexing_performance`: benchmark test asserting indexing time is within limits for a generated dataset.
2. `test_query_latency`: benchmark test asserting query time < 500ms (after warmup).
3. `test_cli_spinner`: unit test mocking stdout/stderr to verify spinner invocation during model load.

## Tier 1: BLOCKING Issues
No blocking issues found in Cost, Safety, Security, or Legal categories.

### Cost
- No issues found. Local inference costs $0.

### Safety
- No issues found. Operations are read-only or scoped to project directory.

### Security
- No issues found.

### Legal
- No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- No issues found.

### Observability
- No issues found.

### Quality
- [ ] **Requirement Coverage Gap:** The Test Plan (Section 10) misses specific scenarios for performance constraints (R1, R4) and UI feedback (R12). While functional logic is tested, the acceptance criteria explicitly list performance budgets which must be asserted in the automated suite (marked as "performance" or "benchmark" tests).
- [ ] **Test Assertions:** T130 "test_build_knowledge_base_full" verifies the vector store is created, but does not strictly verify R1 (time limit). Add an assertion or a specific performance test case.

## Tier 3: SUGGESTIONS
- **Performance:** Consider adding a "warm-up" step in `librarian_node` initialization if the workflow is long-running, to hide the 3-5s model load time before the user reaches that step.
- **Maintainability:** The `chunk_document` function relying on H1/H2 headers is a good start, but consider a fallback for documents that use different structure (e.g., only bold text) to ensure content isn't lost.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision