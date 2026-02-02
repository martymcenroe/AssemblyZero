# LLD Review: #1155-Fix Mock-Heavy Tests

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD presents a robust strategy for introducing integration and contract testing to a mock-heavy codebase. It effectively addresses previous feedback regarding filesystem safety and CI integration. The architectural approach using pytest markers and contract verification is sound and low-risk.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

### Cost
- [ ] No issues found. Loop bounds and API costs are managed via configuration and opt-in execution.

### Safety
- [ ] No issues found. The mandatory use of `tmp_path` and `cwd` isolation for CLI tests (Section 7.2) effectively mitigates worktree pollution risks.

### Security
- [ ] No issues found. Credentials managed via environment variables.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] No issues found.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Test Scenario Specificity (Section 10):** Requirement 7 explicitly lists three specific integration tests (`subprocess`, `GeminiClient`, `file path`) for `agentos.nodes.designer`. However, Test Scenario 020 ("Integration tests run with marker") is generic.
    *   **Recommendation:** Split Scenario 020 into specific scenarios (e.g., "021: Designer Subprocess Integration", "022: Designer Gemini Integration") to ensure traceability between Requirement 7 and the Verification Plan. (This does not block approval as the intent is clear).

## Tier 3: SUGGESTIONS
- **Contract Versioning:** Consider adding a version key to the contract JSON schema to handle future changes in contract structure.
- **Fixture Scope:** Ensure the `real_subprocess_runner` fixture has `function` scope (default) rather than `session` scope to prevent state leakage between tests.

## Questions for Orchestrator
1. None.

## Verdict
[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision