# Issue Review: Backfill Audit Directory Structure for Existing GitHub Issues

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Technical Product Manager & Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
This is an exceptionally well-specified issue with high-quality acceptance criteria and thorough edge case coverage (emojis, rate limits, shell injection). However, a significant logic gap regarding issue renames requires clarification to prevent data hygiene issues (duplicate directories) before execution.

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
- [ ] **Data Hygiene / Duplicate Detection:** The current slug logic (`{number}-{slug}`) and existence check imply that if a GitHub issue is renamed, the tool will generate a new directory (e.g., `12-new-title`) while leaving the old one (`12-old-title`) as an orphan.
    - **Recommendation:** Update Requirements to specify if the tool should scan for `{number}-*` to detect existing directories for that ID and rename/update them, or explicitly list "Cleanup of renamed issues" in "Out of Scope".

### Architecture
- [ ] No issues found.

## Tier 3: SUGGESTIONS
- **Python Version:** Since the tool relies on `datetime` for ISO parsing, explicitly state the minimum Python version (e.g., 3.11+) if relying on `fromisoformat` handling of 'Z' timezones, or use `dateutil`.
- **Version Check:** The Acceptance Criteria mentions "Tool validates gh CLI version," but doesn't specify the mechanism. Suggest adding a specific check for `gh version >= 2.0`.
- **Test Scenarios:** Consider adding a test case for "Issue with description larger than filesystem block size" (though unlikely to break, good for robustness).

## Questions for Orchestrator
1. Should this tool be responsible for cleaning up "stale" audit directories if an issue title changes, or is that a manual governance task?

## Verdict
[ ] **APPROVED** - Ready to enter backlog
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision