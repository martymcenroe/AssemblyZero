# 605 - Feature: Systemic Model Version Refresh (Gemini 3.1 & Claude 4.6+)

<!-- Template Metadata
Last Updated: 2026-02-04
Updated By: Issue #605 LLD generation
Update Reason: Model identifiers refresh for Gemini 3.1 and Claude 4.6+
Previous: Added sections based on 80 blocking issues from 164 governance verdicts (2026-02-01)
-->

## 1. Context & Goal
* **Issue:** #605
* **Objective:** Refresh all hardcoded model identifiers across the codebase to ensure we are using the latest stable versions (`gemini-3.1-pro-preview` and Claude 4.6+ variants), strictly removing legacy fallbacks to enforce a fail-closed governance posture.
* **Status:** Draft
* **Related Issues:** #600

### Open Questions
- [x] Should we use `gemini-3.1-pro-preview` or `gemini-3.1-pro` as the absolute default if both are available? **Resolved:** `gemini-3.1-pro-preview` is the absolute default until the stable non-preview version is fully rolled out.
- [x] Do we need to retain backwards compatibility mappings for `gemini-3-pro` in the fallback logic, or strictly replace them? **Resolved:** Strictly replace. Retaining old mappings violates strict governance and fail-closed security posture.

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*
The system will undergo a strict cutover to `gemini-3.1-pro-preview` and `claude-4-6-opus-latest`/`claude-4-6-sonnet-latest`. Legacy `gemini-3-pro` identifiers will be completely purged from the codebase to enforce fail-closed security.

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/core/config.py` | Modify | Update default model constants for Gemini and Claude. |
| `assemblyzero/core/llm_provider.py` | Modify | Update `MODEL_MAP` dictionary to point to `claude-4-6-opus-latest`, `claude-4-6-sonnet-latest`, and `gemini-3.1-pro-preview`. |
| `tools/gemini-rotate.py` | Modify | Update argparse defaults and fallback logic to use `gemini-3.1-pro-preview`. |
| `tools/gemini-model-check.sh` | Add | Create/re-establish script with downgrade detection logic strictly verifying `gemini-3.1-pro`. |
| `tests/test_assemblyzero_config.py` | Modify | Update unit test assertions to match the new 3.1 and 4.6 default strings. |
| `tests/test_gemini_client.py` | Modify | Update mock assertions to expect the new model identifiers. |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

### 2.2 Dependencies

### 2.3 Data Structures

### 2.4 Function Signatures

### 2.5 Logic Flow (Pseudocode)

### 2.6 Technical Approach

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Downgrade Detection strictness | Exact match vs Prefix match (`gemini-3.1`) | Prefix match (`gemini-3.1-pro`) | Allows minor Google-side revisions (`-001`, `-preview`) while strictly preventing `flash` or `3.0` downgrades. |
| Configuration | ENV vars vs Hardcoded config | Hardcoded `config.py` | AssemblyZero relies on explicit infrastructure-as-code mappings to enforce governance. Env vars allow bypassing. |

**Architectural Constraints:**
- Must maintain the adversarial verification pattern (Claude acts, Gemini checks).
- Model identifiers must perfectly match Anthropic/Google exact API string requirements to avoid 400 Bad Request errors.

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. `assemblyzero/core/config.py` exports `gemini-3.1-pro-preview` and `claude-4-6-opus-latest` as defaults.
2. `MODEL_MAP` maps internal canonical names to the new 3.1/4.6 exact model strings, with NO backwards compatibility mappings for `gemini-3-pro`.
3. CLI tools default to `gemini-3.1-pro-preview` when invoked without explicit model flags.
4. `tools/gemini-model-check.sh` successfully detects and rejects downgrades from `gemini-3.1-pro` to `gemini-3.1-flash` or `gemini-3.0-pro`.
5. All unit tests pass with the new model string assertions.
6. A runbook entry/release note is added documenting the strict removal of `gemini-3-pro` fallbacks, instructing operators to check API key permissions if 403/404 errors spike post-deployment.

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Retain backward compat layers | Safer if API keys lack access | Adds technical debt; violates fail-closed security posture; delays catching quota/access issues | **Rejected** |
| Hard systemic update (String replace) | Clean break, ensures 100% adoption, strict governance | Immediate failure (403/404) if API access is missing | **Selected** |

**Rationale:** The platform operates under a strict governance model. If the environment does not support Gemini 3.1 or Claude 4.6, it should fail closed (loudly) rather than silently falling back to less capable, outdated models that may miss security audit vulnerabilities. This is mitigated by adding a runbook entry for operators to quickly identify permission issues.

## 5. Data & Fixtures

*Per [0108-lld-pre-implementation-review.md](0108-lld-pre-implementation-review.md) - complete this section BEFORE implementation.*

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Hardcoded constants & internal config |
| Format | Python / Bash Strings |
| Size | < 1 KB |
| Refresh | Manual codebase update |
| Copyright/License | N/A |

### 5.2 Data Pipeline

### 5.3 Test Fixtures

### 5.4 Deployment Pipeline

## 6. Diagram

### 6.1 Mermaid Quality Gate

### 6.2 Diagram

## 7. Security & Safety Considerations

### 7.1 Security

### 7.2 Safety

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
- [x] LLD updated with any deviations
- [ ] Implementation Report (0103) completed

### Review
- [x] Code review completed
- [x] User approval before closing issue

### 12.1 Traceability (Mechanical - Auto-Checked)

Mechanical validation automatically checks:
- Every file mentioned in this section must appear in Section 2.1
- Every risk mitigation in Section 11 should have a corresponding function in Section 2.4 (warning if not)

**If files are missing from Section 2.1, the LLD is BLOCKED.**

---

## Appendix: Review Log

### Orchestrator Review #1 (APPROVED)

**Reviewer:** Orchestrator
**Verdict:** APPROVED

#### Comments

| ID | Comment | Implemented? |
|----|---------|--------------|
| O1.1 | "Proceed with 'gemini-3.1-pro-preview' as the absolute default." | YES - Updated Section 1 and Requirements |
| O1.2 | "Strictly replace backwards compatibility mappings for 'gemini-3-pro'." | YES - Updated Section 1 and Requirements |
| O1.3 | "Consider adding a small operational runbook entry or release note regarding the strict removal of 'gemini-3-pro' fallbacks." | YES - Added REQ-6 to add runbook entry |

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Orchestrator #1 | (auto) | APPROVED | Resolve open questions and finalize fail-closed approach |

**Final Status:** APPROVED

## Original GitHub Issue #605

## Template (REQUIRED STRUCTURE)