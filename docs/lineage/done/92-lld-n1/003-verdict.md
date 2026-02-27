# LLD Review: 192 - Feature: Hex - Codebase Retrieval System (RAG Injection)

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The design for the Codebase Retrieval System is technically sound, utilizing a standard RAG pattern with appropriate privacy controls (local embeddings). However, the Test Plan (Section 10) has gaps in requirement coverage, specifically regarding the integration into the workflow and the verification of import paths. Implementation is blocked until these test scenarios are added to ensure the system actually modifies the prompt as intended.

## Open Questions Resolved
- [x] ~~Should we cache embeddings between index rebuilds to speed up incremental updates?~~ **RESOLVED: No. For the MVP target of ~20k LOC, rebuild times should remain <60s. Keep architecture simple; add caching only if latency becomes an issue later.**
- [x] ~~What token budget should we allocate for injected codebase context?~~ **RESOLVED: 2000 tokens. This leaves sufficient room for the system prompt and generation output. Define this as a configurable constant (e.g., `MAX_CODEBASE_CONTEXT_TOKENS`).**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | R1: `rebuild_knowledge_base.py` indexes agentos/tools files | T140, T010-030 | ✓ Covered |
| 2 | R2: Vector store contains chunks with correct metadata | T010, T020 | ✓ Covered |
| 3 | R3: Keyword extraction identifies technical terms | T040, T050, T060 | ✓ Covered |
| 4 | R4: Retrieval returns relevant chunks (>0.75 threshold) | T070, T080 | ✓ Covered |
| 5 | R5: N3_Coder prompt includes "Reference Codebase" section | T130 (Format only) | **GAP** |
| 6 | R6: Generated code uses correct import paths | - | **GAP** |
| 7 | R7: Workflow completes gracefully when collection missing | T120 | ✓ Covered |
| 8 | R8: Token budget drops whole chunks | T090 | ✓ Covered |
| 9 | R9: No network calls made during embedding generation | T110 | ✓ Covered |
| 10 | R10: All embeddings generated locally | T110 | ✓ Covered |

**Coverage Calculation:** 8 requirements covered / 10 total = **80%**

**Verdict:** BLOCK (Coverage < 95%)

**Missing Test Scenarios:**
1.  **For R5 (Workflow Integration):** T130 tests the *formatting helper*, but no test confirms that `run_implementation_workflow.py` actually *calls* this logic and injects it into the prompt. Add a test scenario: `T150 | Workflow injects context | Mock retrieval returns chunks -> Verify prompt contains "Reference Codebase"`.
2.  **For R6 (Import Paths):** While we cannot deterministically test LLM output, we must verify the input to the LLM contains the necessary data. Update T130 or add a new test to assert that the formatted context string *explicitly includes* the `module_path` for the retrieved chunks.

## Tier 1: BLOCKING Issues
No blocking issues found in Cost, Safety, Security, or Legal categories.

### Cost
- [ ] No issues found.

### Safety
- [ ] No issues found.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] No issues found.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** 80%. Two critical requirements (R5, R6) lack sufficient test coverage. R5 is the core value delivery (injection into the prompt), and R6 is the specific objective (correct imports). These must be explicitly covered in the Test Plan.

## Tier 3: SUGGESTIONS
- **Performance:** Consider adding a `--dry-run` flag to the CLI tool to see what *would* be indexed without writing to ChromaDB.
- **Maintainability:** In `extract_keywords`, consider referencing a shared `STOPWORDS` constant if one exists in the project, rather than hardcoding.
- **Documentation:** The `Dependency License Compliance` table lists `chromadb` as "Already in project", but verify the version compatibility if `sentence-transformers` requires specific numpy versions.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision