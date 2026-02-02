# LLD Review: 10098 - Feature: Brief Structure and Placement Standard

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a clear standard for "Briefs" and integrates well with the existing project structure tooling. The file modifications and automation scripts are safe and low-risk. However, the test plan has gaps regarding the content verification of the documentation updates (Requirements 6 and 7), falling below the mandatory coverage threshold.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | `ideas/` directory structure documented in canonical structure standard | Test 040 | ✓ Covered |
| 2 | `new-repo-setup.py` creates `ideas/active/` and `ideas/backlog/` directories | Test 010, Test 030 | ✓ Covered |
| 3 | Brief template exists at `docs/templates/0110-brief-template.md` | Test 020, Test 050 | ✓ Covered |
| 4 | Template includes all required frontmatter fields (Status, Effort, Value) | Test 025 | ✓ Covered |
| 5 | Template includes Problem and Proposal sections | Test 026 | ✓ Covered |
| 6 | Lifecycle rules documented with clear state transitions | - | **GAP** |
| 7 | "What Goes Where" reference included distinguishing briefs from issues | - | **GAP** |

**Coverage Calculation:** 5 requirements covered / 7 total = **71%**

**Verdict:** BLOCK (Threshold is 95%)

**Missing Test Scenarios:**
To address the gaps, add automated checks (likely extensions of Test 040 or new tests) that scan the documentation content for:
1.  Keywords related to lifecycle rules (e.g., "Lifecycle", "Promote", "Archive") in `0009-canonical-project-structure.md`.
2.  The presence of the "What Goes Where" reference table (or unique headers/keywords from it) in the target documentation file.

## Tier 1: BLOCKING Issues
No blocking issues found in Cost, Safety, Security, or Legal categories.

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
- [ ] **Requirement Coverage:** BLOCK (71%). The test plan verifies the existence of files and directories, but fails to verify that the specific documentation content required by Req 6 (Lifecycle rules) and Req 7 ("What Goes Where" table) is actually written to the files. Since this is a documentation standard feature, verifying the content text exists is critical.

## Tier 3: SUGGESTIONS
- **Verification:** For documentation tests, checking for specific unique phrases (like table headers) is more robust than just checking for directory keywords.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision