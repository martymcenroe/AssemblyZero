# ADR 0215: Test-First Philosophy

**Status:** Accepted
**Date:** 2026-01-09
**Deciders:** Orchestrator, Agent Team
**Context:** Observation that testing is often perfunctory; desire to systematize test improvement

---

## Context

Multiple incidents have revealed gaps in our testing approach:

1. **Reactive testing:** Tests are written after code, often as an afterthought
2. **Coverage gaps:** `popup.js` has 484 lines with zero unit tests (discovered in code review)
3. **Manual testing debt:** Implementation reports show patterns like "manual testing only" and "deferred to E2E"
4. **Risky refactors:** Changes like innerHTML removal (Issue #194) were made without regression tests
5. **Perfunctory validation:** Test reports sometimes verify happy paths without edge cases

The current state creates anxiety around changes because we lack confidence that modifications won't break existing functionality.

---

## Decision

### Principle 1: Tests Before Risky Changes

**Before modifying existing code, write tests that verify current behavior.**

This creates a safety net: if tests pass before AND after the change, behavior is preserved.

```
WRONG ORDER:
1. Modify code
2. Manual test
3. Hope nothing broke

RIGHT ORDER:
1. Write tests for current behavior
2. Verify tests pass
3. Modify code
4. Verify tests still pass
```

**When to apply:**
- Any refactor (e.g., innerHTML → DOM methods)
- Bug fixes (test should fail before fix, pass after)
- Performance optimizations
- Security hardening

**Exception:** Net-new code with no existing behavior to preserve.

### Principle 2: Test Pyramid Enforcement

```
        /\
       /  \        E2E Tests (few, slow, brittle)
      /----\
     /      \      Integration Tests (moderate)
    /--------\
   /          \    Unit Tests (many, fast, focused)
  --------------
```

**Current gap:** We have E2E (Playwright) but no unit tests for extension code.

**Action required:** Add Jest/Vitest for unit testing. Every module should have corresponding unit tests.

### Principle 3: Continuous Test Mining

Implementation reports and test reports contain untapped intelligence about testing gaps:

- "Manual testing only" → Automation opportunity
- "Not tested" / "Deferred" → Known gap to address
- "Works on my machine" → Environment-specific test needed
- "Edge case not covered" → Explicit test case to add

**Process:**
1. Periodically review `docs/reports/*/test-report.md`
2. Extract patterns indicating test debt
3. Create issues for high-value automation opportunities
4. Prioritize by risk (security > data integrity > UX)

### Principle 4: Test Reports Must Be Actionable

A test report is not complete if it only says "tests pass." It must include:

1. **What was tested** (specific scenarios)
2. **How it was tested** (automated vs manual)
3. **What was NOT tested** (explicit gaps)
4. **Evidence** (logs, screenshots, test output)

This ensures future agents can identify automation opportunities.

---

## Consequences

### Positive

- **Confidence in changes:** Refactors become low-risk with test coverage
- **Documentation of behavior:** Tests serve as executable specification
- **Regression prevention:** Bugs, once fixed, stay fixed
- **Faster iteration:** Automated tests are faster than manual verification
- **Knowledge capture:** Test gaps are explicitly tracked, not forgotten

### Negative

- **Initial slowdown:** Writing tests before changes adds upfront time
- **Infrastructure investment:** Need to set up Jest/Vitest, mocks, CI integration
- **Maintenance burden:** Tests must be maintained alongside code

### Mitigations

- Start with highest-risk code (security-sensitive, frequently modified)
- Create reusable mocks (Chrome API, AWS SDK) to reduce per-test effort
- Automate test gap detection via `/test-gaps` skill

---

## Implementation

### Phase 1: Unit Test Infrastructure (Immediate)
- Add Vitest to `package.json`
- Create Chrome API mocks in `tests/mocks/`
- Add `npm run test:unit` script
- Write tests for `popup.js` as proof of concept

### Phase 2: Test Mining Skill (Short-term)
- Create `/test-gaps` skill that:
  - Reads all `docs/reports/*/test-report.md`
  - Finds patterns: "manual", "not tested", "deferred", "skipped"
  - Cross-references with code coverage
  - Generates prioritized list of automation opportunities

### Phase 3: Coverage Gates (Medium-term)
- Add coverage reporting to CI
- Establish minimum thresholds per module
- Block PRs that reduce coverage without justification

---

## Compliance

**Before any PR that modifies existing code:**

```
[ ] Tests exist for the code being modified
    - If NO: Write tests first, verify they pass, then proceed
    - If YES: Verify tests pass before AND after change
[ ] Test report documents what was/wasn't tested
[ ] Any "manual only" testing is logged as future automation opportunity
```

---

## References

- [Test-Driven Development by Example](https://www.oreilly.com/library/view/test-driven-development/0321146530/) - Kent Beck
- ADR 0212 - Unified V3 & Secure DOM (motivated by innerHTML testing gap)
- Issue #194 - innerHTML removal without regression tests
- docs/0004-orchestration-protocol.md §8.6 - Test report requirements
