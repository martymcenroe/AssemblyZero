# LLD Review: 1247 - Feature: Two-tier commit validation with hourly orphan issue detection

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a solid dual-layer validation strategy. The separation of concerns (blocking shell script vs. non-blocking Python detector) is architecturally sound. However, the Testing Strategy (Section 10) falls slightly short on Requirement Coverage, specifically missing integration tests for the negative cases (Requirement 6) and infrastructure validation (Requirement 3).

## Open Questions Resolved
- [x] ~~Should the orphan detector also check for issues referenced only with `Ref #N` that have been open for extended periods (e.g., 30+ days)?~~ **RESOLVED: No. Keep the scope strictly limited to "Orphaned Implementations" (code merged, issue open). Stale issue management is a separate concern/feature.**
- [x] ~~What notification mechanism is preferred for orphan reports: GitHub Issues, Slack, or email?~~ **RESOLVED: Stdout (for logs) + creation of a summary GitHub Issue if orphans are found. Avoid adding Slack/Email secrets for this MVP.**
- [x] ~~Should the hourly job run on a schedule or only on PR merge events?~~ **RESOLVED: Hourly schedule as proposed. This handles batch processing efficiently and avoids API rate limit bursts from rapid-fire PR merges.**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Pre-commit hook rejects commits without any issue reference pattern | T050 | ✓ Covered |
| 2 | Pre-commit hook accepts commits with `Ref`, `fixes`, `closes`, or `resolves` | T010, T020, T030, T040, T060 | ✓ Covered |
| 3 | Orphan detector runs hourly via GitHub Actions | - | **GAP** |
| 4 | Detector correctly identifies implementation PRs vs. LLD/docs PRs | T070, T080 | ✓ Covered |
| 5 | Detector generates actionable report listing orphan issues | T110 | ✓ Covered |
| 6 | System does not generate false positives for legitimate `Ref #N` usage on LLD commits | T080 (Partial) | **GAP** |

**Coverage Calculation:** 4 requirements covered / 6 total = **66%**

**Verdict:** BLOCK

### Missing Test Scenarios
1.  **Requirement 3:** Need a test (e.g., `T130`) that parses `.github/workflows/orphan-detection.yml` to verify the `cron` schedule is present and valid.
2.  **Requirement 6:** `T080` only tests the `is_implementation_pr` helper. You need an integration test (e.g., `T140`) where `detect_orphan_issues` is called with a mocked LLD PR (ref only) and asserts that the returned orphan list is **empty**. The current plan tests the helper, but not the decision logic in the main loop.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation pending Tier 2 fixes.

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
- [ ] **Requirement Coverage:** 66% (Threshold 95%). The test plan is missing verification for the workflow schedule and a full integration test for the false-positive suppression logic.
- [ ] **Test Data Hygiene:** Ensure the "Mock PR objects" in Section 5.3 explicitly include examples of "LLD-only" PRs (only .md files) to support the missing T140.

## Tier 3: SUGGESTIONS
- **Performance:** The pseudocode logic (Loop open issues -> Search all merged PRs) is O(N*M). For larger repos, consider inverting this: Fetch merged PRs in lookback period once, extract their issue refs, and then check those specific issues.
- **Maintainability:** In `is_implementation_pr`, verify that the list of "implementation extensions" is configurable or comprehensive (e.g., include `.sh`, `.yml`, `.toml` as implementation changes?).

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision