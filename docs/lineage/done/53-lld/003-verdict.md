# LLD Review: #51 - Migrate from google.generativeai to google.genai

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD follows the correct structure and clearly defines the migration scope. However, it is not yet ready for implementation because the "Open Questions" section contains critical architectural unknowns (specifically regarding credential rotation support and response structures). These questions must be answered and incorporated into the design (Section 2) before the LLD can be approved.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is conditionally approved pending Tier 2 resolutions.

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
- [ ] **Unresolved Open Questions:** Section 1 lists "Does the new SDK support the same credential rotation pattern?" and "Are there any breaking changes in response object structure?" as open questions.
    - **Recommendation:** You must verify these *now* (check documentation or run a script) and update the LLD. Specifically, Section 2.5 (Logic Flow) must identify exactly which Exception classes the new SDK raises for Rate Limits (e.g., is it still `google.api_core.exceptions.ResourceExhausted` or a new `google.genai.errors` type?). Without this, the rotation logic cannot be implemented reliably.
- [ ] **Response Structure Definitions:** Section 2.3 uses pseudocode `NewResponse`.
    - **Recommendation:** Replace this with the concrete attribute paths. For example, verify if `response.text` exists or if it changes to `response.candidates[0].content.parts[0].text`. The "Data Structures" section should allow the developer to code without guessing.

### Observability
- [ ] **Missing Tracing/Logging Specs:** The migration does not mention updates to observability.
    - **Recommendation:** Explicitly state if LangSmith tracing needs to be re-hooked or if the new SDK client exposes different callbacks/hooks for logging raw requests/responses.

### Quality
- [ ] **Test Strategy Precision:** Section 11.1 (Test Scenarios) is good, but Scenario 040 (Rotation on rate limit) requires the specific Exception type to be mocked correctly.
    - **Recommendation:** Update the fixture definition in Section 5.3 to specify the exact Exception class being mocked for the new SDK.

## Tier 3: SUGGESTIONS
- **Async Support:** The new SDK often prioritizes async/await patterns. While "Sync only" is acceptable for backward compatibility, consider if this is the right time to introduce an `invoke_async` method to future-proof the client.
- **Dependency Pinning:** In `pyproject.toml`, consider pinning to a specific minor version (e.g., `google-genai = "~1.0.0"`) rather than `^1.0.0` if the SDK is very new, to prevent breakage from rapid updates.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision