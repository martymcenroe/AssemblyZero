# Issue Review: Parallel Workflow Execution for LLD and Issue Processing

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Technical Product Manager & Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The draft is technically robust, demonstrating strong foresight regarding concurrency challenges (SQLite locking, output interleaving, and graceful shutdown). However, the distinction between "Credential Availability" and "API Rate Limiting" (TPM/RPM) is ambiguous and poses a risk to the parallel execution success. Additionally, the performance Acceptance Criteria is too vague for verification.

## Tier 1: BLOCKING Issues
No blocking issues found. Issue is actionable.

### Security
- [ ] No issues found.

### Safety
- [ ] No issues found.

### Cost
- [ ] No issues found. Budget impact is neutral (same total work, just faster), and pool limits prevent runaway resource usage.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Quality
- [ ] **Vague Performance AC:** The criterion `Total execution time... is ~N/P times sequential` is difficult to verify strictly due to network variance and overhead.
    *   **Recommendation:** Define a specific tolerance. Example: "Total execution time for 6 items with `--parallel 3` is less than 50% of the sequential execution time (allowing for 15% coordination overhead)."
- [ ] **Ambiguous "Exhaustion" Definition:** The scenario `Scenario 2: Credential Pool Exhaustion` handles running out of *keys*. However, with `parallel 10`, it is highly likely to hit **Rate Limits (HTTP 429)** or **TPM (Tokens Per Minute)** limits on the keys before the keys themselves are "exhausted" (reserved).
    *   **Recommendation:** Explicitly add behavior for Rate Limit encounters. Should the worker backoff individually? Should the coordinator throttle *all* workers if one hits a 429?

### Architecture
- [ ] **Handling 429s in Parallel:** If `parallel 3` triggers a rate limit on the shared pool, simply "pausing" might not be enough.
    *   **Recommendation:** Ensure the `CredentialCoordinator` logic distinguishes between "No keys available to reserve" and "Key is reserved but API is rejecting requests due to rate limits."

## Tier 3: SUGGESTIONS
- Add label `core-workflow` and `performance`.
- Add T-Shirt Size: L (due to complexity of subprocess state management).
- Consider adding a `--dry-run` flag to verify which LLDs would be picked up without executing them.

## Questions for Orchestrator
1. Does the current Credential Pool implementation expose TPM (Tokens Per Minute) remaining, or just a binary "Key Available" state? This impacts how smart the parallel scheduler can be.

## Verdict
[ ] **APPROVED** - Ready to enter backlog
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision