# LLD Review: 199-Feature: Schema-driven project structure

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a solid, configuration-driven approach to project structure management using standard JSON. The architecture is sound, leveraging the standard library to avoid dependencies. However, the LLD fails the strict 95% Requirement Coverage threshold because one requirement (documentation consistency) lacks an automated test. Additionally, the "Open Questions" section contains stale items that contradict or duplicate the proposed design decisions, indicating the document needs a final cleanup.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | A JSON schema file exists at `docs/standards/0009-structure-schema.json` | Test 100 (Schema includes lineage dirs - implies loading production schema) | ✓ Covered |
| 2 | `new-repo-setup.py` reads directory structure from schema | Test 040, 060 | ✓ Covered |
| 3 | `new-repo-setup.py --audit` validates against schema | Test 070, 080, 090 | ✓ Covered |
| 4 | Standard 0009 markdown references schema as the authoritative source | - | **GAP** |
| 5 | Schema includes `docs/lineage/` structure with `active/` and `done/` | Test 100 | ✓ Covered |
| 6 | All existing functionality of `new-repo-setup.py` continues to work | Test 110 | ✓ Covered |

**Coverage Calculation:** 5 requirements covered / 6 total = **83.3%**

**Verdict:** **BLOCK** (Coverage < 95%)

**Missing Test Scenarios:**
*   **Req 4:** Add a test (e.g., `test_standard_references_schema`) that parses `docs/standards/0009-canonical-project-structure.md` and asserts it contains the string `0009-structure-schema.json`. This automates the check for drift between the standard text and the schema file location.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation regarding Cost, Safety, Security, and Legal.

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
- [ ] **Requirement Coverage:** 83% < 95%. See Analysis above. The missing test for Requirement 4 must be added to Section 10 to ensure the "Single Source of Truth" objective is mechanically enforced.
- [ ] **Stale Open Questions:** Section 1 "Open Questions" lists items that are resolved by the design in Section 2.
    *   "Should we include file content templates...?" -> Resolved by Data Structures (uses `template` reference).
    *   "What validation strictness...?" -> Resolved by Logic Flow (Audit Flow: Warning for optional).
    *   **Action:** Remove resolved questions or update the design if these are still undecided. An approved LLD must represent a finalized design.

## Tier 3: SUGGESTIONS
- **Schema Validation:** Consider explicitly testing for `..` traversal attempts in the "Invalid schema" test fixture (Test 030) to reinforce the Security mitigation mentioned in 7.1.
- **Documentation:** Explicitly state in Section 2.5 (Logic Flow) that `new-repo-setup.py` will default to the standard schema location if no argument is provided.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision