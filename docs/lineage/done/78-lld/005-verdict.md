# LLD Review: 0178-Feature: Per-Repo Workflow Database

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a solid architectural change to improve workflow isolation and safety by moving the checkpoint database to the repository root. The design correctly handles fail-closed scenarios and environment variable overrides. However, the Testing Strategy (Section 10) fails the strict quality gate regarding automated testing and requirement coverage.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation logic, pending test plan fixes.

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
- [ ] No issues found.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Manual Test Delegation (CRITICAL):** Section 10.3 defines M010 as a "Manual Test". The protocol strictly requires **ALL** tests to be fully automated. Concurrency checks can and must be automated using Python's `subprocess` or `multiprocessing` modules to spawn workflows in separate temporary directories. Remove Section 10.3 and convert M010 to an automated integration test.
- [ ] **Requirement Coverage Gap:** Requirement 7 (".agentos/ pattern is added to .gitignore") is not mapped to a test scenario. Current coverage is 8/9 (88%), which is below the 95% threshold. Add a test case (e.g., Test 011) to parse `.gitignore` and assert the entry exists to ensure the database is not accidentally committed.

## Tier 3: SUGGESTIONS
- **Migration Helper:** Consider adding a momentary log warning if a global `~/.agentos/issue_workflow.db` exists but is being ignored in favor of the new per-repo DB, just to alert users their old context is not visible (unless they intended this).
- **Test 070:** Ensure the "Nested repo detection" test explicitly covers running from a deep subdirectory (e.g., `repo/src/lib/`) to verify `git rev-parse --show-toplevel` works as expected.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision