# Issue Review: Add Logging to Draft Node

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Technical Product Manager & Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The issue is structurally sound and clearly scoped. However, there is a significant Architectural risk regarding the use of `print()` (stdout pollution) which could break downstream consumption of the workflow's output. Additionally, a dependency on the State schema needs verification.

## Tier 1: BLOCKING Issues
No blocking issues found. Issue is actionable.

### Security
- [ ] No issues found.

### Safety
- [ ] No issues found.

### Cost
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Quality
- [ ] **Stdout Pollution Risk:** The "Technical Approach" specifies using `print()`. If this CLI/workflow's output is intended to be piped or consumed programmatically (e.g., JSON output), writing debug logs to `stdout` will corrupt the data.
    - **Recommendation:** Change requirement to use `sys.stderr` or Python's standard `logging` module (configured to stream to stderr), or explicitly confirm that `stdout` is reserved solely for human-readable logs.

### Architecture
- [ ] **State Schema Dependency:** The issue requires reading `iteration` from the state object.
    - **Question:** Is `iteration` a guaranteed key in the existing state schema?
    - **Recommendation:** If the `iteration` key is not guaranteed, the implementation must handle the missing key safely (e.g., `.get('iteration', 1)`) to prevent `KeyError` crashes, or this issue needs a dependency link to the issue that adds `iteration` to the State.

## Tier 3: SUGGESTIONS
- **Taxonomy:** Add label `type:instrumentation` or `type:dx` (Developer Experience).
- **Effort Estimate:** Recommended Size: XS (0.5 - 1 Story Point).
- **Future Proofing:** Even if structured logging is out of scope, using `logging.info()` now makes the future transition easier than refactoring `print()` statements later.

## Questions for Orchestrator
1. Does the current workflow State schema already include an `iteration` counter, or does that need to be added as part of this implementation?

## Verdict
[ ] **APPROVED** - Ready to enter backlog
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision