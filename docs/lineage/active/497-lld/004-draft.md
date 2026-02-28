# 497 - Feature: Bounded Verdict History in LLD Revision Loop

<!-- Template Metadata
Last Updated: 2026-02-28
Updated By: Issue #497
Update Reason: Revised per Gemini Review #1 — resolved open questions, incorporated logging and observability suggestions
-->


## 1. Context & Goal
* **Issue:** #497
* **Objective:** Replace unbounded cumulative verdict history in the LLD revision prompt with a bounded rolling-window strategy that keeps prompt size within ~20% of iteration 2 regardless of iteration count.
* **Status:** Draft
* **Related Issues:** #494 (JSON review output — decoupled; this LLD handles both formats), #489 (section-level revision), #491 (diff-aware review)

**Gemini Review Resolutions Applied:**
* **Logging:** All warning-level events (e.g., budget truncation, format detection fallback) use the project's standard `logging` library (`logger.warning()`) — never `print`.
* **Observability:** A `feedback_window_truncation_count` metric is tracked to monitor how often the token budget triggers summarization in production.
* **Iteration cap:** A `MAX_REVISIONS = 5` hard cap is recommended for the workflow control logic (in `generate_draft.py` or graph definition), but is *out of scope* for this LLD — this LLD only bounds the *feedback content*, not the loop count.


### Open Questions

*All questions resolved per Gemini Review #1.*

- [x] **Does #494 (JSON migration) land before or after this?** — **Resolved:** Proceed with hybrid implementation. The `extract_blocking_issues` function handles both text-format and JSON-format verdicts. This decouples deployment timelines — #494 can land before, after, or concurrently without affecting this work.
- [x] **What is the maximum number of revision iterations allowed before the loop aborts?** — **Resolved:** A hard cap (`MAX_REVISIONS = 5`) should be enforced in the workflow control logic (e.g., `generate_draft.py` or the LangGraph graph definition) as a cost safety net. This is a separate concern from prompt bounding and should be tracked as a follow-up task if not already present.


## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describes exactly what will be built.*


### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/workflows/requirements/nodes/generate_draft.py` | Modify | Replace cumulative verdict insertion (lines ~256-259) with rolling-window feedback builder; add `logger.warning()` for truncation events |
| `assemblyzero/workflows/requirements/verdict_summarizer.py` | Add | New module: summarizes prior verdicts into structured one-line summaries; uses `logging` for format detection fallback |
| `assemblyzero/workflows/requirements/feedback_window.py` | Add | New module: assembles bounded feedback block from verdict history; tracks `feedback_window_truncation_count` metric |
| `tests/unit/test_verdict_summarizer.py` | Add | Unit tests for verdict summarization logic |
| `tests/unit/test_feedback_window.py` | Add | Unit tests for feedback window assembly and token budget enforcement |
| `tests/unit/test_generate_draft_feedback.py` | Add | Integration-style unit tests verifying generate_draft uses bounded feedback |
| `tests/fixtures/verdict_analyzer/sample_verdict_iteration_1.json` | Add | Fixture: sample verdict from iteration 1 (blocked, 3 issues) |
| `tests/fixtures/verdict_analyzer/sample_verdict_iteration_2.json` | Add | Fixture: sample verdict from iteration 2 (blocked, 2 issues) |
| `tests/fixtures/verdict_analyzer/sample_verdict_iteration_3.json` | Add | Fixture: sample verdict from iteration 3 (approved) |


### 2.1.1 Path Validation (Mechanical - Auto-Checked)
<!-- UNCHANGED -->


### 2.2 Dependencies
<!-- UNCHANGED -->


### 2.3 Data Structures
<!-- UNCHANGED -->


### 2.4 Function Signatures
<!-- UNCHANGED -->


### 2.5 Logic Flow (Pseudocode)
<!-- UNCHANGED -->


### 2.6 Technical Approach
<!-- UNCHANGED -->


### 2.7 Architecture Decisions
<!-- UNCHANGED -->


## 3. Requirements

1. **Bounded feedback size:** The feedback section of the revision prompt must not exceed `token_budget` (default 4,000) tokens regardless of iteration count.
2. **Latest verdict always full:** The most recent verdict is included verbatim (up to budget).
3. **Prior verdicts summarized:** All prior verdicts are represented as structured one-line summaries showing iteration number, verdict, issue count, and persisting issue descriptions.
4. **Persistent issue visibility:** Issues that appear in multiple consecutive verdicts are explicitly flagged as "persists" in summaries so the LLM knows they haven't been addressed.
5. **Token cost stability:** Iteration 5 prompt token count is within 20% of iteration 2 prompt token count.
6. **Backward compatibility:** Empty verdict history produces the same prompt as the current initial draft behavior.
7. **Format agnostic:** Works with both current text-format verdicts and future #494 JSON-format verdicts.


## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| A: Latest verdict + prior summaries (rolling window) | Works with both text and JSON; clear signal; bounded cost; simple to implement; decouples from #494 timeline | Loses some detail from intermediate verdicts | **Selected** |
| B: Diff-only feedback | Minimal token usage; precise delta | Requires #494 JSON format to be practical; complex diff logic; loses context of overall progress trajectory | Rejected (future enhancement after #494 lands) |
| C: Token budget with progressive summarization | Most flexible; adapts dynamically to any budget | More complex; summarization quality varies by model; harder to test deterministically; over-engineered for 1–5 iteration range | Rejected (over-engineered for current need) |
| D: Keep cumulative, add truncation safeguard | Minimal code change; quick to implement | Doesn't solve the core problem — stale feedback still dominates prompt; truncation point is arbitrary and may cut mid-issue; no persistent-issue tracking | Rejected |

**Rationale:** Option A provides the best balance of implementation simplicity, independence from other issues (#494), and prompt quality. It directly addresses the root cause (stale feedback accumulation) rather than working around it (truncation). The rolling summary gives the LLM a clear picture of what has been tried and what persists, without overwhelming it with redundant detail. Critically, it works with both text and JSON verdict formats, so deployment is not blocked by #494's timeline.


## 5. Data & Fixtures


### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Verdict history list from LangGraph workflow state |
| Format | List of strings (text or JSON, depending on #494 status); `extract_blocking_issues` auto-detects format |
| Size | 1-5 entries typically; each ~2,000 tokens |
| Refresh | One new entry added per review iteration |
| Copyright/License | N/A — internally generated |


### 5.2 Data Pipeline
<!-- UNCHANGED -->


### 5.3 Test Fixtures
<!-- UNCHANGED -->


### 5.4 Deployment Pipeline
<!-- UNCHANGED -->


## 6. Diagram
<!-- UNCHANGED -->


### 6.1 Mermaid Quality Gate
<!-- UNCHANGED -->


### 6.2 Diagram
<!-- UNCHANGED -->


## 7. Security & Safety Considerations
<!-- UNCHANGED -->


### 7.1 Security
<!-- UNCHANGED -->


### 7.2 Safety
<!-- UNCHANGED -->


## 8. Performance & Cost Considerations
<!-- UNCHANGED -->


### 8.1 Performance
<!-- UNCHANGED -->


### 8.2 Cost Analysis
<!-- UNCHANGED -->


## 9. Legal & Compliance
<!-- UNCHANGED -->


## 10. Verification & Testing
<!-- UNCHANGED -->


### 10.0 Test Plan (TDD - Complete Before Implementation)
<!-- UNCHANGED -->


### 10.1 Test Scenarios
<!-- UNCHANGED -->


### 10.2 Test Commands
<!-- UNCHANGED -->


### 10.3 Manual Tests (Only If Unavoidable)
<!-- UNCHANGED -->


## 11. Risks & Mitigations
<!-- UNCHANGED -->


## 12. Definition of Done
<!-- UNCHANGED -->


### Code
<!-- UNCHANGED -->


### Tests
<!-- UNCHANGED -->


### Documentation
<!-- UNCHANGED -->


### Review
<!-- UNCHANGED -->


### 12.1 Traceability (Mechanical - Auto-Checked)
<!-- UNCHANGED -->


## Appendix: Review Log
<!-- UNCHANGED -->


### Review Summary
<!-- UNCHANGED -->