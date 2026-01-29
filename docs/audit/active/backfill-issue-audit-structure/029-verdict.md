# Issue Review: Backfill Audit Directory Structure for Existing GitHub Issues

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Technical Product Manager & Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
This is an exceptionally well-specified issue that handles complex edge cases (rate limits, injection attacks, slug collisions) with precision. However, a specific ambiguity regarding the GitHub API payload for "timeline events" exists, which poses a risk to performance and implementation clarity. This should be defined before work begins to meet the Definition of Ready.

## Tier 1: BLOCKING Issues
No blocking issues found. Issue is actionable.

### Security
- [ ] No issues found. Input sanitization for `subprocess` is explicitly defined.

### Safety
- [ ] No issues found. Fail-fast and fail-open strategies are correctly applied to different error types.

### Cost
- [ ] No issues found. Local execution uses existing API quotas.

### Legal
- [ ] No issues found. Data residency (Local-Only) is explicitly mandated.

## Tier 2: HIGH PRIORITY Issues

### Quality
- [ ] No issues found. Acceptance Criteria are binary and comprehensive.

### Architecture
- [ ] **Ambiguous API Contract for Linked PRs:**
    - **Issue:** Data Fetching requirement #4 states: "Include linked PR detection from timeline events". However, requirement #2 specifies "Use `gh issue view` with JSON output". By default, `gh issue view` does not return timeline events (which contain PR links) unless explicitly requested via `--json timelineItems`. Requesting the full timeline for old issues can result in massive payloads, parsing overhead, and potential timeouts.
    - **Recommendation:** Explicitly list the exact fields to be passed to the `--json` flag in the "Data Fetching" section (e.g., `--json number,title,body,comments,timelineItems`). If `timelineItems` is deemed too heavy, restrict PR detection to parsing the issue body/comments and update the scope accordingly.

## Tier 3: SUGGESTIONS
- **Usability:** Consider adding a `--force` flag to explicitly overwrite existing directories if needed (distinct from skipping).
- **Testing:** In "Testing Notes", explicitly suggest testing a scenario where an issue has a "closed" state but no closing event in the timeline (migrated issues sometimes exhibit this).
- **UX:** The dry-run output format isn't defined; suggest specifying a simple diff-like or tree-like output for clarity.

## Questions for Orchestrator
1. Is the strict requirement to forbid runtime `sys.path` manipulation (and force `pip install -e .`) aligned with the team's developer experience standards for standalone scripts? (The fallback handling in Scenario 11 mitigates this, but it remains a high barrier for casual contributors).

## Verdict
[ ] **APPROVED** - Ready to enter backlog
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision