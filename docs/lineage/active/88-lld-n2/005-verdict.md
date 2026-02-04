# LLD Review: 188 - Feature: RAG Injection: Automated Context Retrieval ("The Librarian")

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a robust, local-first RAG architecture with excellent attention to privacy, licensing, and graceful degradation. The document structure is sound, and the testing strategy is comprehensive for the local workflow. However, the review is **BLOCKED** due to a Requirement Coverage violation (90% < 95% threshold) regarding the optional external API support claimed in Section 3.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Vector Infrastructure: ChromaDB-based local vector store | 030, 070, 080 | ✓ Covered |
| 2 | Embedding Model: Default `all-MiniLM-L6-v2` with optional external API support | 060, 090 (Default only) | **GAP** |
| 3 | Document Indexing: Index `docs/adrs/`, `docs/standards/`, `docs/LLDs/done/` | 070 | ✓ Covered |
| 4 | Chunking: Split documents by H1/H2 headers | 010 (Content verification) | ✓ Covered |
| 5 | Query Performance: <500ms after warm-up | 090 | ✓ Covered |
| 6 | Graceful Degradation: Workflow continues if missing store/deps | 030, 040 | ✓ Covered |
| 7 | Manual Override: `--context` flag takes precedence | 050 | ✓ Covered |
| 8 | Transparency: Log retrieved documents at INFO level | 115 | ✓ Covered |
| 9 | CLI Feedback: Display spinner during cold-boot | 060 | ✓ Covered |
| 10 | Lightweight Core: Core package installs without ML dependencies | 10.2 (pip check) | ✓ Covered |

**Coverage Calculation:** 9 requirements covered / 10 total = **90%**

**Verdict:** **BLOCK**

**Missing Test Scenarios:**
*   **Req 2 (External API Support):** The requirement states "optional external API support". There is no test scenario (e.g., "Test 120") that configures the librarian to use an external provider (like OpenAI or Azure) to verify that the system correctly handles API keys and network calls instead of the local model. If this is out of scope for this MVP, remove the requirement. If it is in scope, it must be tested.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation regarding Cost, Safety, Security, and Legal tiers.

### Cost
- [ ] No issues found. Local inference minimizes cost.

### Safety
- [ ] No issues found. Worktree scope and fail-open strategies are well-defined.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found. License compliance is thorough.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] **Design/Requirement Mismatch (Req 2):** Section 3 requires "optional external API support", but Section 2.5 (Logic Flow) and 2.4 (Function Signatures) do not describe how this is implemented. `load_embedding_model` implies loading a local model. There is no logic shown for "If model is OpenAI, verify API key, instantiate remote client." You must either detail the design for the external API adapter or remove it from the requirements.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** **FAILED (90%)**. See Analysis above. The external API support is a stated requirement but is untested and effectively undesigned in the logic flow.

## Tier 3: SUGGESTIONS
- **Unit Test for Splitter:** While Test 010 covers the happy path, adding a specific unit test for `index_document` to verify H1/H2 splitting logic on edge-case Markdown (e.g., headers inside code blocks, nested headers) would be beneficial.
- **External API Configuration:** If keeping Req 2, explicitly define the environment variable naming convention (e.g., `AGENTOS_RAG_API_KEY`) in the design.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision