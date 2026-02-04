# LLD Review: 83-Feature: Structured Issue File Naming Scheme for Multi-Repo Workflows

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The design provides a robust mechanism for deterministic, human-readable issue identifiers in a multi-repo environment. However, there is a **Tier 1 Safety Block** regarding potential infinite loops during word generation if the vocabulary is exhausted, and the Requirement Coverage falls below the strict 95% threshold due to missing test scenarios for state persistence and directory naming.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | `get_repo_short_id()` returns ≤7 character capitalized repo identifier | Test 060, 010 | ✓ Covered |
| 2 | `get_repo_short_id()` sanitizes input to alphanumeric only via regex `[a-zA-Z0-9]+` | Test 020, 030, 040 | ✓ Covered |
| 3 | `get_repo_short_id()` follows priority order: `.audit-config` → git remote → directory name | Test 150 | ✓ Covered |
| 4 | `get_repo_short_id()` raises `ValueError` for empty result after sanitization | Test 050 | ✓ Covered |
| 5 | `generate_issue_word()` produces deterministic word from brief hash | Test 070 | ✓ Covered |
| 6 | Word selection detects and avoids collisions in `active/` and `done/` | Test 080 | ✓ Covered |
| 7 | `get_next_issue_number()` scopes counter to current Repo ID only | Test 090 | ✓ Covered |
| 8 | Slug format matches `{REPO}-{WORD}-{NUM}` pattern exactly | Test 110 | ✓ Covered |
| 9 | All new audit files use `{SLUG}-{TYPE}.md` naming | Test 120 | ✓ Covered |
| 10 | Audit directories named with full slug | - | **GAP** |
| 11 | Revision files append sequence number (draft2, verdict2) | Test 130 | ✓ Covered |
| 12 | Existing old-format issues continue to work unchanged | Test 160 | ✓ Covered |
| 13 | Wordlist contains 80+ curated vocabulary-expanding words | Static Check (Implicit) | ✓ Covered |
| 14 | `issue_word` tracked in workflow state | - | **GAP** |

**Coverage Calculation:** 12 requirements covered / 14 total = **85.7%**

**Verdict:** BLOCK (Must be ≥95%)

**Missing Test Scenarios:**
1.  **Req 10:** Test scenario verifying that when an issue is filed (moved to `done/`), the directory created (if any) matches the full slug. If no directory is created and files remain flat, Requirement 10 should be removed or clarified.
2.  **Req 14:** Test scenario explicitly verifying that `issue_word` is persisted to `IssueWorkflowState` after generation.

## Tier 1: BLOCKING Issues

### Cost
- [ ] **Unbounded Loop in Word Generation:** The pseudocode for `generate_issue_word` contains a `WHILE` loop checking for collisions: `WHILE word at index in existing_words`. If all 80+ words are in use (vocabulary exhaustion), this becomes an infinite loop.
    -   **Recommendation:** Add a guard clause before the loop to check `if len(existing_words) >= len(ISSUE_WORDS): raise VocabularyExhaustedError`. Alternatively, implement a loop counter limit.

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
- [ ] **Requirement Coverage Gap:** Coverage is 85.7%. Please add the missing test scenarios listed in the Requirement Coverage Analysis section or adjust the requirements if they are outdated (specifically Req 10 regarding directory naming).

## Tier 3: SUGGESTIONS
- **Maintainability:** Consider exposing `ISSUE_WORDS` in the `.audit-config` or an external file in the future to allow users to customize/expand the wordlist without code changes, though the current hardcoded approach is acceptable for MVP.
- **Resilience:** In `get_repo_short_id`, consider logging a warning when falling back from Git Remote to Directory Name, so the user is aware the ID might be less stable (e.g., if they rename the folder).

## Questions for Orchestrator
1. **Req 10 Clarification:** Does the "Filed" state involve moving files into a subdirectory named `{SLUG}` inside `done/`, or are files simply moved flat into `done/` with the `{SLUG}` prefix in the filename? The design supports flat filenames, but Req 10 implies directories.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision