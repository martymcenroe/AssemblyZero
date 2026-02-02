# LLD Review: 184 - Feature: Add [F]ile Option to Issue Workflow Exit

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a secure and well-structured approach for integrating the `gh` CLI into the issue workflow. The use of list arguments for subprocess calls effectively mitigates shell injection risks. However, the design is **BLOCKED** due to insufficient automated test coverage (<95%) for the menu interface changes and a potential edge case regarding GitHub API pagination for labels.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | `[F]ile` option appears in workflow exit menu alongside existing options | - | **GAP** |
| 2 | Draft parsing extracts title from first H1, body from content, labels from backtick list | 030, 040, 050 | ✓ Covered |
| 3 | Missing labels are created with category-appropriate colors before filing | 020, 100, 110, 120 | ✓ Covered |
| 4 | Issue is filed via `gh issue create` with extracted content | 010, 020 | ✓ Covered |
| 5 | `003-metadata.json` is updated with issue URL and filing timestamp | 130, 140 | ✓ Covered |
| 6 | Unauthenticated `gh` CLI produces clear error without crashing workflow | 060 | ✓ Covered |
| 7 | Missing title produces clear error and keeps user in workflow | 070 | ✓ Covered |
| 8 | Malformed labels line produces warning and files issue without labels | 080 | ✓ Covered |
| 9 | All subprocess calls use list arguments (not `shell=True`) | 090 | ✓ Covered |
| 10 | Shell special characters in draft content are handled safely | 090 | ✓ Covered |

**Coverage Calculation:** 9 requirements covered / 10 total = **90%**

**Verdict:** BLOCK (Threshold is 95%)

**Missing Test Scenarios:**
*   **Req 1:** Needs an automated unit test verifying `run_issue_workflow.py` adds the 'F' option to the returned menu choices list. (Cannot rely on Manual Test M01 for coverage).

## Tier 1: BLOCKING Issues
No blocking issues found in Cost, Safety, Security, or Legal categories. LLD is approved for implementation pending Tier 2 fixes.

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
- [ ] **GitHub CLI Pagination limit:** The design "Fetches all labels once" using `gh label list`. By default, `gh` limits this to 30 items. If a repo has >30 labels and the target label is distinct but exists (e.g., item #31), the check `if label doesn't exist` will return True. The subsequent `gh label create` will fail because the label *does* exist, causing the workflow to "Fail Closed" (exit).
    *   **Recommendation:** Update `ensure_labels_exist` logic to use `gh label list --limit 100` (or higher) to minimize this risk.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** 90%. Must reach 95%. Add an automated test case for the menu option presence.
- [ ] **Path Validation:** While `run_issue_workflow` likely handles path selection, `parse_draft_for_filing` takes a `Path` argument directly. For robustness, ensure the implementation validates that `draft_path` is strictly within the project worktree to prevent arbitrary file reading if the calling logic changes.

## Tier 3: SUGGESTIONS
- Consider using the project's standard logger instead of `Display:` (print) statements for better debugging of user issues.
- In `file_issue.py`, consider adding a `--dry-run` parameter to the filing function to facilitate testing without mocking `gh` entirely in all scenarios.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision