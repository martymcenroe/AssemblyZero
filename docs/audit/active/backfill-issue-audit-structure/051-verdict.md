# Issue Review: Backfill Audit Directory Structure for Existing GitHub Issues

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Technical Product Manager & Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
This is an exceptionally detailed and well-structured specification. The inclusion of specific "Fail Fast" vs "Fail Open" strategies, rate limit handling, and distinct UX scenarios sets a high standard. However, there is a critical **Safety (Data Loss)** conflict regarding how renamed issues are handled when using the `--force` flag, which prevents immediate approval.

## Tier 1: BLOCKING Issues

### Security
- [ ] No blocking issues found.

### Safety
- [ ] **Data Loss Risk (Renaming Strategy):** In "Scenario 17" and "Overwrite Behavior," the spec states that if an issue is renamed and `--force` is used, the tool "removes the entire old directory." This is a **Destructive Action** that will permanently delete manual sidecar files (e.g., `004-analysis.md`) which the spec explicitly aims to preserve in other scenarios.
    *   **Recommendation:** Change the logic for renamed issues. The tool must either:
        1.  **Migrate:** Move non-generated files (sidecars) from the old directory to the new directory before deleting the old one.
        2.  **Abort:** Refuse to auto-delete the old directory if it contains non-generated files, even with `--force`, requiring manual cleanup.

### Cost
- [ ] No blocking issues found.

### Legal
- [ ] No blocking issues found.

## Tier 2: HIGH PRIORITY Issues

### Quality
- [ ] **Ambiguity in "TimelineItems" Fetching:** In "Data Fetching," the spec suggests fetching `timelineItems` via the REST API to find linked PRs. For old/active issues, this payload can be massive, potentially causing timeouts or memory issues.
    *   **Recommendation:** Explicitly cap the `timelineItems` (e.g., `--limit` on the nested field if possible, or accept that this might fail on massive issues). Ensure the "Fail Open" logic applies specifically to the PR-linking sub-task if the timeline fetch fails, preserving the core issue backup.

### Architecture
- [ ] No blocking issues found.

## Tier 3: SUGGESTIONS
- **Output:** In "Scenario 12" (Emoji Titles), consider logging a specific "Warning" to stdout so the user knows `77-untitled` refers to the emoji issue.
- **Performance:** For "Scenario 4" (All Registered), consider adding a slight default delay (e.g., 0.1s) even without the flag to be a "good citizen" to the API, although `gh` CLI handles this well usually.
- **Fixture Management:** Add a `tools/fixtures/schema.json` to programmatically validate the fixtures themselves in the future.

## Questions for Orchestrator
1. **Sidecar Migration:** Do we have a reliable way to distinguish "tool-managed" files from "manual sidecars" other than the filename whitelist (`001`, `002`, `003`)? (Assumption is yes, whitelist is sufficient).

## Verdict
[ ] **APPROVED** - Ready to enter backlog
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision