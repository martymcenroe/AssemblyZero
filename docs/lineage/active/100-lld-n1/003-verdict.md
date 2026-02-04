# LLD Review: 1100 - Feature: Lineage Workflow Integration

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The design for standardizing design review artifacts is sound, leveraging the existing filesystem-based pattern effectively. The choice of flat JSON and markdown artifacts ensures long-term auditability without database dependencies. However, the LLD fails the strict **Requirement Coverage** gate (77%) due to missing test scenarios for setup scripts and inter-process communication in the structured test table.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Issue workflow creates `docs/lineage/active/{id}-{slug}/` folder at workflow start | 010 | ✓ Covered |
| 2 | All briefs saved as `001-brief.md` in lineage folder | 020 | ✓ Covered |
| 3 | All LLD drafts saved as `{NNN}-draft.md` with incrementing sequence | 030 | ✓ Covered |
| 4 | All Gemini verdicts saved as `{NNN}-verdict.md` with incrementing sequence | 040 | ✓ Covered |
| 5 | Filing metadata saved as final `{NNN}-filed.json` | 060 | ✓ Covered |
| 6 | Folder moves from `active/` to `done/` on successful filing | 060 | ✓ Covered |
| 7 | LLD workflow accepts lineage path when called as subprocess | - | **GAP** |
| 8 | `new-repo-setup.py` creates both `docs/lineage/active/` and `docs/lineage/done/` | - | **GAP** |
| 9 | Existing workflows continue functioning if lineage directories don't exist | 090 | ✓ Covered |

**Coverage Calculation:** 7 requirements covered / 9 total = **77.7%**

**Verdict:** **BLOCK** (< 95%)

**Missing Test Scenarios:**
1.  **Req 7**: Need a specific test scenario (e.g., ID 100) verifying the CLI argument parsing: `LLD workflow accepts --lineage-path argument`. (Current tests 030/040 test the save *logic*, but not the subprocess interface/argument passing).
2.  **Req 8**: Need a specific test scenario (e.g., ID 110) in Table 10.1 for `new-repo-setup.py` execution. (Note: Section 10.2 lists a command, but the requirement is for a structured test scenario in Section 10.1).

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation regarding Cost, Safety, Security, and Legal tiers.

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
- [ ] **Requirement Coverage:** **BLOCK**. Coverage is 77.7% (Threshold 95%). Please add specific test scenarios to Section 10.1 for Requirements 7 (subprocess CLI args) and 8 (setup script).

## Tier 3: SUGGESTIONS
- **Scenario 080**: This test ("Error on done/ exists") is excellent for safety but doesn't explicitly map to a numbered requirement in Section 3. Consider adding a requirement like "Prevent modification of already-filed issues" to make this coverage explicit.
- **Recovery**: The "Recovery Strategy" mentions manual inspection. Consider adding a `tools/lineage-repair.py` in a future iteration if corruption becomes common, though not needed for MVP.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision