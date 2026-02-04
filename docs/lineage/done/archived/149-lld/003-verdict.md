# LLD Review: 1149 - Fix: Rate-limit backoff not implemented in CredentialCoordinator

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a solid, lightweight solution for handling rate-limit backoffs using a lazy-evaluation strategy, avoiding unnecessary threading complexity. The logic is sound, and the test plan covers the requirements well. However, there is a critical logic error in the pseudocode regarding dictionary modification during iteration that will cause a runtime crash if implemented as written, and an administrative metadata mismatch that needs correction.

## Tier 1: BLOCKING Issues
No blocking issues found.

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
- [ ] **Runtime Error in Logic Flow:** The pseudocode for `_promote_expired_quarantine` suggests iterating over `_quarantine` while removing items from it (`FOR each ... in _quarantine: ... Remove from _quarantine`). In Python, this raises `RuntimeError: dictionary changed size during iteration`. **Recommendation:** Explicitly specify iterating over a snapshot of keys (e.g., `list(_quarantine.items())`) or collecting keys to remove in a separate step.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Issue ID Mismatch:** The document title references `#1149`, but the Context section references `#149`. This breaks traceability. **Recommendation:** Verify the correct issue ID and unify references.
- [ ] **Test Scenario 040 Ambiguity:** The "Pass Criteria" for Scenario 040 ("Correct ordering by expiry") is slightly vague. **Recommendation:** Update Pass Criteria to be explicit, e.g., "get_credential returns Credential A, then Credential B".

## Tier 3: SUGGESTIONS
- **Performance:** While O(n) scanning of the quarantine dict is acceptable for <100 credentials, consider checking `if not _quarantine: return` at the start of `_promote_expired_quarantine` to save CPU cycles when the quarantine is empty (the common case).
- **Type Hinting:** In `2.4 Function Signatures`, `release_credential` arguments should likely be keyword-only arguments (using `*`) to prevent swapping `rate_limited` and `backoff_seconds` accidentally.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision