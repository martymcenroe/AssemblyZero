# Issue Review: RAG Injection: Codebase Retrieval System (The Smart Engineer)

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Technical Product Manager & Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
This is a well-structured technical specification with clear User Stories and Acceptance Criteria. However, it fails Tier 1 checks regarding the **Cost** and **Legal/Privacy** implications of the embedding strategy. The "Full rebuild each time" approach combined with undefined embedding model usage creates potential budget and data residency risks that must be defined before approval.

## Tier 1: BLOCKING Issues

### Security
- [ ] No blocking issues found.

### Safety
- [ ] No blocking issues found.

### Cost
- [ ] **Missing Budget/Infrastructure Impact:** The issue specifies "Full rebuild each time for MVP" for the index. It does not specify *which* embedding model is used (e.g., OpenAI `text-embedding-3`, Gemini, or a local HuggingFace model). If using a remote API, re-indexing the entire codebase on every run incurs recurring token costs.
    *   **Requirement:** Specify the embedding model. If remote, provide a cost estimate per 1k lines of code and total budget cap.

### Legal
- [ ] **Data Residency Ambiguity:** The Security section states "Only indexes local codebase files (no external sources)," which refers to *ingestion*. It does not specify if code snippets are sent to a third-party API for *embedding generation*.
    *   **Requirement:** Explicitly state: "Embeddings generated Locally (e.g., SentenceTransformers)" OR "Code snippets transmitted to [Provider] for embedding." If transmitted, update the Privacy section to acknowledge source code egress.

## Tier 2: HIGH PRIORITY Issues

### Quality
- [ ] **Fragile Keyword Logic:** The Requirement "Simple NLP approach using regex" is risky and likely to produce poor retrieval results (e.g., missing synonyms or semantic matches).
    *   **Recommendation:** Clarify the "Simple NLP" spec. Either define the exact Regex patterns in the Technical Approach or switch to a lightweight local keyword extractor (e.g., TF-IDF or KeyBERT) to ensure the Acceptance Criteria can be met reliably.

### Architecture
- [ ] **Missing Token limit strategy for Injection:** The "Context Injection" requirement mentions "Respect token budget (truncate if necessary)" but does not define *how*. Truncating code mid-function causes hallucinations.
    *   **Recommendation:** Define the truncation strategy (e.g., "Drop lowest relevance chunks entirely if context window full" rather than "Cut off text mid-stream").

## Tier 3: SUGGESTIONS
- Add label `rag-pipeline`.
- Consider T-Shirt size: **L** (Due to AST parsing complexity and integration testing).
- In "Out of Scope", consider adding "Vector Cache" to mitigate the "Full rebuild" cost if using remote embeddings.

## Questions for Orchestrator
1. Does the current project license/NDA allow for full source code transmission to the embedding provider (if not local)?

## Verdict
[ ] **APPROVED** - Ready to enter backlog
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision