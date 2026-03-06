# 607 - Feature: Mechanical Document Assembly Node

<!-- Template Metadata
Last Updated: 2026-02-24
Updated By: User
Update Reason: Initial draft for Mechanical Document Assembly Node based on Issue #607
Previous: N/A
-->

## 1. Context & Goal
* **Issue:** #607
* **Objective:** Transition from LLM-generated documents to Code-assembled documents to eliminate "Section Number Drift" and ensure 100% template compliance.
* **Status:** Draft
* **Related Issues:** #600 (Triggering failure), Standard 0010 (Golden Schema)

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [x] Will sections be generated sequentially to allow the LLM to contextually reference earlier sections, or in parallel to reduce overall latency? **Resolved:** Sections MUST be generated sequentially to maintain document coherence and allow context references.
- [x] What is the exact retry budget per individual section before the entire node fails? **Resolved:** The retry budget MUST be strictly set to 3 attempts per individual section before throwing an `AssemblyError`.

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/nodes/document_assembler.py` | Add | Core utility and base classes for the mechanical document assembly pattern. |
| `assemblyzero/workflows/lld/templates.py` | Add | Hardcoded Python data structures defining the LLD structural sections and targeted prompts. |
| `assemblyzero/workflows/lld/nodes/assembly_node.py` | Add | LangGraph node implementation specific to LLD generation using the new mechanical assembler. |
| `assemblyzero/workflows/lld/__init__.py` | Modify | Export new assembly node. |
| `tests/unit/test_document_assembler.py` | Add | Unit tests for structural compliance, partial section retries, and REQ-3 prompt scoping (T050). |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

### 2.2 Dependencies

### 2.3 Data Structures

### 2.4 Function Signatures

### 2.5 Logic Flow (Pseudocode)

### 2.6 Technical Approach

* **Module:** `assemblyzero/nodes/` and `assemblyzero/workflows/lld/nodes/`
* **Pattern:** Structural Composition / Factory Pattern
* **Key Decisions:** The LLM will no longer be responsible for emitting `#` or `##` headers for core sections. The Python orchestrator will inject these headers and append the LLM's response. The LLM's prompt will explicitly state: *"Do not output the section header, just provide the content for..."* to prevent duplicate headers.

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| **Execution Flow** | Sequential Generation, Parallel Generation | **Sequential Generation** | LLDs are narrative. Section 3 (Requirements) depends on Section 2 (Proposed Changes). Parallel generation loses context coherence. |
| **Header Ownership** | LLM outputs headers via JSON schema, Python injects headers purely as strings | **Python injects headers purely as strings** | Eliminates LLM hallucination of headers, guarantees 100% template compliance and no "Section Number Drift". |
| **State Tracking** | Store full document string in state, Store list of section objects | **Store list of section objects** | Allows granular validation, retry of individual sections, and debugging of specific step failures without parsing markdown. |

**Architectural Constraints:**
- Must integrate smoothly with the existing LangGraph `StateGraph` architectures.
- Must not exceed standard API rate limits (sequential calls inherently mitigate rate limit spikes compared to parallel batching).
- Must enforce a strict retry budget of 3 attempts per individual section before throwing an `AssemblyError`.

## 3. Requirements

1. Output Markdown MUST have exactly the section headers defined in the `DocumentTemplate`, with correct numbering, impossible to drift.
2. If the LLM fails to generate a specific section properly, the system must only retry that section, not the entire document.
3. The prompt for each section must be scoped to the issue context and only the necessary previous sections, reducing input token bloat.
4. The Drafter LLM must not be instructed to manage section numbers (e.g., "Write section 2.1"). The mechanical assembly logic MUST use resilient string manipulation or regex to strip any hallucinated headers, ensuring it is resilient to minor variations (e.g., extra whitespace, bold markdown asterisks).

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **LLM Output via Strict JSON Schema** | Single API call, fast execution, theoretically enforced structure. | High failure rate for complex markdown inside JSON; models still hallucinate keys or drop mandatory fields. | **Rejected** |
| **Post-Generation Linting/Fixing** | Keeps existing single-pass generation architecture. | High token cost for retrying entire documents; regex parsing of hallucinated markdown is brittle. | **Rejected** |
| **Mechanical Assembly (Selected)** | 100% structural guarantee, highly debuggable, granular retries. | Higher latency due to multiple sequential API calls; slightly higher base prompt overhead. | **Selected** |

**Rationale:** The reliability and 100% template compliance heavily outweigh the latency cost of sequential calls. Reworking a broken LLD costs the user minutes; generating a correct one a few seconds slower is a massive net positive.

## 5. Data & Fixtures

### 5.1 Data Sources

### 5.2 Data Pipeline

### 5.3 Test Fixtures

### 5.4 Deployment Pipeline

## 6. Diagram

### 6.1 Mermaid Quality Gate

### 6.2 Diagram

```mermaid
sequenceDiagram
    participant Graph as LangGraph State
    participant Node as Assembly Node
    participant LLM as Claude/Anthropic API

    Graph->>Node: Execute lld_assembly_node
    Node->>Node: Load LLD Template Structure

    loop For Each Section
        Node->>Node: Format Prompt (Issue + Previous Context)
        Node->>LLM: Request Content for Section N
        LLM-->>Node: Return Section Content
        Node->>Node: Strip Hallucinated Headers
        Node->>Node: Store in completed_sections
    end

    Node->>Node: Mechanically Concatenate Headers + Content
    Node-->>Graph: Return final_document (100% Compliant)
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Prompt Injection from Issue Text | Issue text is treated as passive context in the section generation prompt, not executable instructions. | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Partial Document Generation Failure | Section-level retry logic. If a mandatory section fails 3 times, the node cleanly throws an `AssemblyError` and returns the error in state, preventing a malformed PR/commit. | Addressed |
| Infinite LLM Loops | Hardcoded retry maximum (`max_attempts=3`) per section strictly enforced before throwing an `AssemblyError`. | Addressed |
| API Rate Limiting | Sequential execution inherently paces requests. Tenacity retries handle HTTP 429s. | Addressed |

**Fail Mode:** Fail Closed - If a mandatory section cannot be generated within the strictly 3-attempt retry budget per section, the document assembly throws an `AssemblyError` rather than outputting a structurally incomplete LLD.

**Recovery Strategy:** The LangGraph state maintains `completed_sections`. Upon retry of the node, it can skip sections already successfully generated and resume from the failed section.

## 8. Performance & Cost Considerations

### 8.1 Performance

### 8.2 Cost Analysis

## 9. Legal & Compliance

## 10. Verification & Testing

### 10.0 Test Plan (TDD - Complete Before Implementation)

### 10.1 Test Scenarios

### 10.2 Test Commands

### 10.3 Manual Tests (Only If Unavoidable)

## 11. Risks & Mitigations

## 12. Definition of Done

### Code

### Tests

### Documentation

### Review

### 12.1 Traceability (Mechanical - Auto-Checked)

## Appendix: Review Log

### Review Summary