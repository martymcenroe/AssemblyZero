# LLD Review: 116-Feature: Add GitHub Actions CI Workflow for Automated Testing

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a solid foundation for the CI implementation with a logical hybrid strategy. However, it fails the strict "No Human Delegation" criteria in the Test Plan (Section 10). Several tests (Nightly triggers, Durations, Documentation) are marked as Manual with steps like "Wait for 6 AM" or "Measure duration," which implies human observation. These must be converted to automated scripts using the GitHub CLI (`gh`) to verify workflow behavior and metrics programmatically.

## Open Questions Resolved
- [x] ~~Which CI strategy to use?~~ **RESOLVED: Option D: Hybrid (tiered by trigger + markers)**
- [x] ~~Python version matrix: 3.10, 3.11, 3.12 or just 3.11?~~ **RESOLVED: Start with 3.11, align with project lockfile**
- [x] ~~Coverage threshold for new code: 90% or different?~~ **RESOLVED: 90% for new code, baseline for existing**
- [x] ~~Should live tests require manual trigger or run on nightly schedule?~~ **RESOLVED: Both: nightly schedule + manual workflow_dispatch**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Tests run automatically on every PR opened or updated | T010, Scen 010 | ✓ Covered |
| 2 | Tests run automatically on every push to main branch | T020, Scen 020 | ✓ Covered |
| 3 | Nightly workflow runs full test suite including live tests | T030, Scen 030 | ✓ Covered |
| 4 | Coverage report generated and visible on PRs | T050, Scen 050 | ✓ Covered |
| 5 | CI status badge displayed in README | T060, Scen 060 | ✓ Covered |
| 6 | PR tests complete in under 5 minutes | T090, Scen 090 | ✓ Covered |
| 7 | Main branch tests complete in under 25 minutes | T100, Scen 100 | ✓ Covered |
| 8 | All existing tests continue to pass | T010, T020 (implicit in passing status) | ✓ Covered |
| 9 | Clear documentation on how to add markers to new tests | T110, Scen 110 | ✓ Covered |

**Coverage Calculation:** 9 requirements covered / 9 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues
No blocking issues found in Tier 1 categories. LLD is approved for Cost, Safety, Security, and Legal.

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
- [ ] **Path Structure Mismatch Risk:** The command `poetry run pytest ... --cov=src` assumes the source code is located in a `src/` directory.
    - **Issue:** If the project uses a flat layout (source in root or package folder in root), this command will fail or report 0% coverage.
    - **Recommendation:** Verify project structure. If using flat layout, change to `--cov=.` or `--cov=<package_name>`. If using `src` layout, ensure `pyproject.toml` is configured to find packages in `src`.

### Observability
- [ ] No issues found.

### Quality
- [ ] **No Human Delegation (CRITICAL):** Section 10.3 lists tests T030, T090, T100, and T110 as "Manual". The strict protocol requires ALL tests to be fully automated.
    - **T030 (Nightly):** "Wait for 6 AM" is not a valid test step.
        - **Recommendation:** Automate by triggering the workflow via API (`gh workflow run nightly.yml`), polling for completion, and asserting that "live" tests executed. We trust GitHub's scheduler; we verify the workflow configuration works when triggered.
    - **T090 & T100 (Performance):** "Measure duration" requires human calculation.
        - **Recommendation:** Automate using `gh run view <run-id> --json jobs` and `jq` to parse start/end times and assert duration < X minutes in a script.
    - **T110 (Docs):** "Verify instructions are clear" involves judgment.
        - **Recommendation:** Change test scope to verify *existence* of documentation via `grep`. "Clarity" is a Code Review (human) concern, but the TDD test must be binary/automated (e.g., `grep -q "pytest.mark" CONTRIBUTING.md`).
- [ ] **Test Plan Status:** Section 10.0 correctly identifies tests as RED, but the "Type" column in 10.1 must be updated to "Automated (Scripted)" for the tests mentioned above once the scripts are defined.

## Tier 3: SUGGESTIONS
- **Concurrency:** Add `concurrency` group with `cancel-in-progress: true` to the PR workflow to save CI minutes when developers push multiple commits in rapid succession.
- **Diff-Cover:** Implementation of `diff-cover` is listed as optional; highly recommended to enforce the 90% threshold strictly on *new* code as planned.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision