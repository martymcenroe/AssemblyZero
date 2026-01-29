# Issue Review: The Scout: External Intelligence Gathering Workflow

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Technical Product Manager & Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The issue is well-defined in terms of user value and technical implementation logic (LangGraph nodes). However, it faces critical Tier 1 blockers regarding **Cost** (high context window usage without estimates) and **Legal/Privacy** (transmission of internal proprietary code to external LLM providers). These must be addressed before backlog entry.

## Tier 1: BLOCKING Issues

### Security
- [ ] No blocking issues found.

### Safety
- [ ] No blocking issues found.

### Cost
- [ ] **Missing Budget/Token Estimate:** This workflow involves reading external READMEs, code files, and internal source code. This implies a high-context window operation which can be expensive.
    - *Recommendation:* Provide an estimated token count or cost per run (e.g., "$0.20/run via Gemini 1.5 Flash"). Specify which model tier is required (Flash vs Pro) to balance cost/performance.
    - *Recommendation:* Add a `--max-tokens` or safety cap requirement to the CLI arguments to prevent runaways.

### Legal
- [ ] **Data Residency & Internal IP Protection:** The workflow specifically compares "internal code" against external patterns. This implies sending proprietary internal source code to the LLM API provider (via `gemini_client.py`).
    - *Recommendation:* Explicitly state that internal code is transmitted to the LLM provider.
    - *Recommendation:* Mandate a CLI warning/confirmation prompt when `--internal` is used: "Warning: Target file will be sent to external LLM provider for analysis."

## Tier 2: HIGH PRIORITY Issues

### Quality
- [ ] **Non-Automatable Acceptance Criteria:** The criterion "Generated brief includes accurate README summary (verified manually)" creates a manual bottleneck in CI.
    - *Recommendation:* Change to "Generated brief matches `tests/fixtures/golden-brief-summary.md` within 90% cosine similarity" or strictly rely on static fixtures for the "Happy Path" test.

### Architecture
- [ ] **License Scanning:** The issue mentions extracting code from external repos. While likely Fair Use for analysis, copying code into "Innovation Briefs" could introduce license contamination (e.g., GPL code).
    - *Recommendation:* Add a requirement for the "Extractor Node" to capture/display the external repository's license type in the Innovation Brief.

## Tier 3: SUGGESTIONS
- **Taxonomy:** Add labels `feature`, `agent`, `langgraph`, `research`.
- **Effort Estimate:** Size appears to be **Large (L)** due to 4 distinct graph nodes + CLI wrapper.
- **Output:** Consider adding a `--format json` requirement for future automation pipelines.

## Questions for Orchestrator
1. Does the current `gemini_client.py` implementation cover the data privacy requirements for sending internal source code to the model?

## Verdict
[ ] **APPROVED** - Ready to enter backlog
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision