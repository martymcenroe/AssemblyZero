# LLD Review: 1285-Bug: Integration Tests Run by Default

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD is well-structured and directly addresses the objective of preventing accidental API calls during default test runs. The proposed solution using `pyproject.toml` configuration and `pytest` markers is standard and effective. The testing strategy (meta-testing via subprocess) is robust and correctly automates verification of the configuration itself, addressing previous governance feedback.

## Open Questions Resolved
No open questions found in Section 1 (all were resolved/marked in the draft).

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | `pytest tests/` runs without making any real API calls by default | T010, T040 | ✓ Covered |
| 2 | `pytest tests/ -m integration` runs only integration-marked tests | T020 | ✓ Covered |
| 3 | `pytest tests/ -m "integration or e2e"` runs all external-service tests | T050 | ✓ Covered |
| 4 | Test markers are documented in pyproject.toml | T030 | ✓ Covered |
| 5 | Deselected test count is visible in pytest output | T010 | ✓ Covered |

**Coverage Calculation:** 5 requirements covered / 5 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

### Cost
- [ ] No issues found. The design actively reduces cost by preventing accidental API calls.

### Safety
- [ ] No issues found.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues
No high-priority issues found.

### Architecture
- [ ] No issues found. Design follows standard Python/Pytest patterns.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** PASS (100%).
- [ ] The move to automated meta-tests (checking subprocess output) instead of manual verification is excellent and compliant with governance standards.

## Tier 3: SUGGESTIONS
- **CI Integration:** Ensure the CI pipeline (GitHub Actions) is updated to explicitly call `pytest -m "not integration and not e2e"` (or rely on the new default) for the PR checks, and `pytest -m "integration or e2e"` for the scheduled/release checks.
- **Documentation:** Consider adding a comment in `pyproject.toml` pointing to the meta-tests so future developers understand that the configuration is actively tested.

## Questions for Orchestrator
None.

## Verdict
[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision