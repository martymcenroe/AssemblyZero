# ADR 0207: LLM Team Coverage Targets

**Status:** Accepted
**Date:** 2026-02-01
**Deciders:** Orchestrator
**Context:** Setting coverage thresholds for TDD Testing Workflow (Stage 3)

---

## Context

The TDD Testing Workflow (Issue #101, #102) enforces two coverage metrics:

1. **Requirement Coverage:** Percentage of LLD requirements that have corresponding tests
2. **Code Coverage:** Percentage of the lines a change adds or modifies that are executed by tests

Traditional guidance for human teams suggests 80-90% code coverage, with "diminishing returns" cited above that threshold. This reflects:
- Human time is expensive
- Edge cases are tedious to test
- Some code is genuinely hard to test
- Developer fatigue on test writing

**However, our team is primarily LLMs.** This changes the calculus:
- LLMs don't experience fatigue
- LLMs don't find tedious tests demotivating
- Token cost is orders of magnitude cheaper than human developer hours
- Quality gates can be strict without morale impact

The question: What coverage thresholds are appropriate for an LLM-driven development workflow?

---

## Decision

### Requirement Coverage: 100%

**Every requirement in the LLD MUST have at least one corresponding test.**

Rationale:
- If a requirement cannot be tested, the requirement is poorly defined
- This creates a forcing function for testable requirements in LLD authoring
- LLMs can generate tests for any well-defined requirement
- No "we'll test that manually" escape hatch

Implementation:
- N1 (review_test_plan) blocks if requirement coverage < 100%
- Gemini reviews test plan for complete requirement mapping

### Code Coverage: 95% of Changed Lines

**At least 95% of the executable lines a change adds or modifies must be executed by tests, for each test framework. A new file counts whole.**

Rationale:
- The remaining 5% accommodates genuinely untestable code:
  - Platform-specific branches that can't run in CI
  - Defensive code for "impossible" conditions
  - Some error handling paths
- 100% code coverage often leads to meaningless tests just to hit lines
- 95% is strict enough to catch most gaps while allowing pragmatism
- The number is about the change, not the file. A whole file's coverage says what its history did; a run can add ten fully tested lines to a large module and still read 25% (#4436). Graded on the whole file, that run can never pass, whatever it writes.

Implementation:
- N5 (`verify_green_phase`) judges the lines the run added or changed against its base commit, one framework at a time. The base is where the run's history left its integration branch, so a resumed run and a run on a seed branch are judged on their own changes.
- Line data comes from coverage.py's JSON report for pytest and Istanbul's `coverage-final.json` for Vitest and Jest. A line is executable when the tool says so: comments, blank lines, docstrings and type-only lines are in no denominator. A later line of a multi-line statement is judged as that statement.
- A test file is judged on nothing. A framework with no changed executable lines is not judged on coverage, and the log says so.
- Whole-file coverage is still reported, and decides nothing. N5 passes `--cov-fail-under=0` and switches off Vitest's and Jest's thresholds, so neither the gate nor a target's own configuration can fail a run on it.
- A measurement that cannot be taken halts: a report that is missing or unreadable, a changed file the report does not name, or a base commit that cannot be determined. It is never read as zero changed lines.
- A shortfall names the uncovered changed lines, and N4c writes tests for those lines only.
- The target is the LLD's when it declares one, and `--coverage-target` wins over the LLD on every load path. The run says which target it uses and where it came from.

---

## Consequences

### Positive

- **Higher quality:** More code paths verified automatically
- **Confidence in changes:** Refactors have strong safety net
- **Testable requirements:** LLD authors must think about testability
- **No "test debt" accumulation:** Can't defer testing indefinitely

### Negative

- **Longer iteration cycles:** More tests = more time to generate and run
- **Potential for low-value tests:** Hitting 95% might include trivial assertions
- **Strictness may block valid PRs:** Edge cases genuinely hard to test

### Mitigations

- **Iteration time:** LLMs are parallel; test generation is fast
- **Low-value tests:** Gemini review in N1 catches "assert True" style tests
- **Blocking:** Coverage target can be overridden via `--coverage-target` flag with justification; the flag wins over the LLD's target

---

## Alternatives Considered

### 1. Traditional 80/90 Targets

**Rejected.** Optimizes for human cost constraints we don't have.

### 2. 100% Code Coverage

**Rejected.** Leads to:
- Tests for unreachable defensive code
- Platform-specific code that can't run in CI
- Mocking so heavy it tests the mocks, not the code

### 3. No Hard Thresholds (Advisory Only)

**Rejected.** Without enforcement, coverage drifts downward over time. The TDD workflow's value comes from its gates being non-negotiable.

---

## Compliance

**For every PR generated by the TDD Testing Workflow:**

```
[x] Requirement coverage = 100%
    - Every REQ-X in LLD has ≥1 test scenario
[x] Code coverage ≥ 95% of changed lines
    - N5 reports at least 95% of the executable lines the run added or
      changed against its base commit, for each framework; a new file
      counts whole
    - Whole-file coverage is reported and decides nothing
    - If <95%, must specify --coverage-target with justification
```

---

## References

- ADR 0205 - Test-First Philosophy
- Issue #101 - Test Plan Reviewer
- Issue #102 - TDD Initialization
- Issue #4436 - The gate judges changed lines, not whole files
- `assemblyzero/workflows/testing/changed_lines.py` - What the run changed, and which of those lines its tests ran
- `assemblyzero/workflows/testing/` - Implementation
