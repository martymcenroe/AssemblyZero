# LLD Review: 1247-Two-tier Commit Validation with Hourly Orphan Issue Detection

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a solid dual-layer approach to issue tracking hygiene, combining immediate developer feedback (git hook) with asynchronous safety nets (orphan detector). The logic for distinguishing implementation PRs is sound. However, the **Requirement Coverage Analysis** indicates significant gaps in the test plan, specifically regarding output formatting and infrastructure setup verification. These must be addressed before approval.

## Open Questions Resolved
- [x] ~~Should the orphan detection report go to Slack, GitHub Issues, or both?~~ **RESOLVED: Output to Stdout and GitHub Actions Job Summary (Markdown). Avoid Slack integration to minimize secrets management complexity.**
- [x] ~~What is the threshold for "implementation PR" - just file extensions or also minimum lines changed?~~ **RESOLVED: Use file extensions + PR title/branch conventions (as defined in 2.5). Do not use line counts, as small bug fixes are valid implementations.**
- [x] ~~Should we create auto-fix functionality that closes orphan issues automatically or just report them?~~ **RESOLVED: Report only. Auto-closing introduces risk of false positives; human review is required.**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Pre-commit hook rejects commits without issue reference | T030 (Scenario 050, 060) | ✓ Covered |
| 2 | Pre-commit hook accepts valid commits with supported formats | T010, T020 (Scenario 010, 020, 030, 040) | ✓ Covered |
| 3 | Pre-commit hook provides clear error message | T030 (Scenario 050 implicit) | ✓ Covered |
| 4 | Orphan detector identifies open issues with merged impl PRs | T040 (Scenario 070) | ✓ Covered |
| 5 | Orphan detector distinguishes impl PRs from docs/LLD PRs | T050, T060 (Scenario 080, 100-130) | ✓ Covered |
| 6 | Orphan detector runs hourly via GitHub Actions | - | **GAP** |
| 7 | Orphan detector outputs machine-readable (JSON) and human-readable (MD) | - | **GAP** |
| 8 | Setup script installs git hook correctly on dev machines | - | **GAP** |

**Coverage Calculation:** 5 requirements covered / 8 total = **62.5%**

**Verdict:** **BLOCK** (Threshold < 95%)

**Missing Test Scenarios:**
1.  **For Req 6:** A test verifying the workflow file (`.github/workflows/orphan-detection.yml`) exists and contains the correct cron schedule `0 * * * *`.
2.  **For Req 7:** Unit tests for `generate_report` verifying it produces valid JSON structure and Markdown syntax matching the schema defined in 2.3.
3.  **For Req 8:** A shell or integration test verifying `tools/setup_hooks.sh` correctly copies the file to `.git/hooks/commit-msg` and sets executable permissions.

## Tier 1: BLOCKING Issues
No blocking issues found in Cost, Safety, Security, or Legal categories. LLD is blocked primarily on Requirement Coverage.

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
- [ ] **Requirement Coverage Failure:** The Test Plan (Section 10) misses tests for report generation formatting, workflow scheduling configuration, and the installation script. These are core requirements listed in Section 3. Add scenarios to Section 10.1 to cover these (e.g., `T140: Generate JSON report`, `T150: Setup script installs hook`).

## Tier 3: SUGGESTIONS
- **Setup Script Safety:** Consider checking if a hook already exists in `setup_hooks.sh` before overwriting it, or prompt the user.
- **Pagination:** Ensure `tools/orphan_issue_detector.py` handles GitHub API pagination correctly when fetching "all open issues" (Logic Flow 2.5), as noted in 2.6.
- **Breaking Changes:** Consider adding logic to the commit hook to validate `BREAKING CHANGE:` footer format if that is part of the project's convention.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision