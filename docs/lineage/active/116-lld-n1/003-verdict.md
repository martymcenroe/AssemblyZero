# LLD Review: 116-Feature: Add GitHub Actions CI Workflow for Automated Testing

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a solid foundation for a tiered CI/CD pipeline using GitHub Actions and pytest markers. The "Hybrid" strategy is well-chosen for balancing feedback loop speed with regression safety. However, the review is **BLOCKED** primarily due to strict Requirement Coverage gaps—specifically regarding performance constraints and documentation requirements which lack corresponding test verification steps in Section 10.

## Open Questions Resolved
- [x] ~~Which CI strategy to use?~~ **RESOLVED: Option D (Hybrid) as selected in the LLD.**
- [x] ~~Python version matrix: 3.10, 3.11, 3.12 or just 3.11?~~ **RESOLVED: Start with 3.11.** Align with the project's current lockfile to minimize initial CI variance. Expand matrix only after the workflow is stable.
- [x] ~~Coverage threshold for new code: 90% or different?~~ **RESOLVED: 90% for new code.** For the existing codebase, establish a baseline (e.g., maintain current level) and enforce 90% strictly on the diff of PRs using a tool like `diff-cover` or Codecov's patch settings.
- [x] ~~Should live tests require manual trigger or run on nightly schedule?~~ **RESOLVED: Both.** Keep the nightly schedule for regression safety and allow manual `workflow_dispatch` triggers for on-demand verification by developers.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Tests run automatically on every PR opened or updated | T010 | ✓ Covered |
| 2 | Tests run automatically on every push to main branch | T020 | ✓ Covered |
| 3 | Nightly workflow runs full test suite including live tests | T030 | ✓ Covered |
| 4 | Coverage report generated and visible on PRs | T050 | ✓ Covered |
| 5 | CI status badge displayed in README | T060, T080 | ✓ Covered |
| 6 | PR tests complete in under 5 minutes | - | **GAP** |
| 7 | Main branch tests complete in under 25 minutes | - | **GAP** |
| 8 | All existing tests continue to pass | T010, T020 | ✓ Covered |
| 9 | Clear documentation on how to add markers to new tests | - | **GAP** |

**Coverage Calculation:** 6 requirements covered / 9 total = **66.6%**

**Verdict:** BLOCK (Target ≥ 95%)

**Missing Test Scenarios:**
To proceed, please add the following test scenarios to Section 10:
*   **T090**: Verify PR workflow duration (Manual/Observation) - Assert time < 5 min.
*   **T100**: Verify Main workflow duration (Manual/Observation) - Assert time < 25 min.
*   **T110**: Verify Documentation - Check `README.md` or `CONTRIBUTING.md` for marker guide (Manual).

## Tier 1: BLOCKING Issues
No blocking issues found in Tier 1 categories. LLD is blocked by Tier 2 Quality issues (Requirement Coverage).

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
- [ ] **Requirement Coverage:** 66.6% < 95%. The LLD lists performance and documentation requirements in Section 3 but fails to define how these will be verified in Section 10. While these are "meta" requirements, the strict TDD protocol requires them to be accounted for in the Test Plan (even as manual verification steps).
- [ ] **TDD Test Plan Completeness:** The "Expected Behavior" for T010 ("Jobs complete") is slightly vague regarding the outcome. It should ideally be "Jobs complete successfully (Green)".

## Tier 3: SUGGESTIONS
- **Coverage Tooling:** Consider adding `diff-cover` to the PR workflow to enforce the 90% coverage requirement specifically on changed lines, preventing technical debt accumulation.
- **Workflow Dispatch Logic:** In `ci.yml`, the `test-fast` job has logic `if: ... || inputs.test_scope == 'fast'`. If a user manually triggers with `test_scope: all`, `test-fast` is skipped. Ensure `test-full` runs the fast tests as well (it seems to, via `-m "not live"`), but verify that this behavior is intentional and clear to users who might expect "all" to run the "fast" job specifically.
- **Badge Stability:** Ensure the badge URL in `README.md` points to the `CI` workflow specifically, not the Nightly one, to avoid confusion.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision