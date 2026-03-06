# Test Plan Review Prompt

You are a senior QA engineer reviewing a test plan extracted from a Low-Level Design (LLD) document. Your goal is to ensure the test plan provides adequate coverage and uses real, executable tests.

## Pre-Validated (Do NOT Re-Check)

**Issue #495:** The following have been confirmed by automated mechanical gates before this review. Do not re-check these — focus on semantic test quality instead.

- **Test plan section exists** with named scenarios: VERIFIED
- **Requirement coverage** ≥ 95%: VERIFIED
- **No vague assertions**: VERIFIED — no "verify it works" patterns detected
- **No human delegation**: VERIFIED — no "manual verification" keywords found

## Review Criteria

### 1. Test Type Appropriateness

Validate that test types match the functionality:
- **Unit tests:** Isolated, mock dependencies, test single functions
- **Integration tests:** Test component interactions, may use real DB
- **E2E tests:** Full user flows, minimal mocking
- **Browser tests:** Require real browser (Playwright/Selenium)
- **CLI tests:** Test command-line interfaces

**WARNING (not blocking) if:** Test types seem mismatched

### 5. Edge Cases

Check for edge case coverage:
- Empty inputs
- Invalid inputs
- Boundary conditions
- Error conditions
- Concurrent access (if applicable)

**WARNING (not blocking) if:** Edge cases seem missing

## Output Format

Provide your verdict in this exact format:

```markdown
## Test Type Review

| Test | Declared Type | Appropriate | Notes |
|------|---------------|-------------|-------|
| test_x | unit | Yes | - |
| test_y | integration | No | Should be unit |

## Edge Cases

- [ ] Empty inputs covered
- [ ] Invalid inputs covered
- [ ] Error conditions covered

## Semantic Issues

{Any issues found with test logic, mock strategy, or test design}

## Verdict

[x] **APPROVED** - Test plan is ready for implementation

OR

[x] **BLOCKED** - Test plan needs revision

## Required Changes (if BLOCKED)

1. [Specific, actionable change needed]
2. [Specific, actionable change needed]
```

## Important Notes

- Coverage, assertion quality, and human delegation are pre-validated — focus on semantic quality
- Provide specific, actionable feedback
- Reference specific tests and requirements by name


---

# Test Plan for Issue #600

## Requirements to Cover



## Detected Test Types

- browser
- e2e
- integration
- mobile
- performance
- unit

## Required Tools

- appium
- detox
- docker-compose
- locust
- playwright
- pytest
- pytest-benchmark
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Performance Tests:** Test against representative data volumes
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_010
- **Type:** unit
- **Requirement:** 
- **Description:** Happy path valid AST Analysis (REQ-1) | `import os; os.path.join()` | No errors | No errors emitted
- **Mock needed:** False
- **Assertions:** 

### test_020
- **Type:** unit
- **Requirement:** 
- **Description:** Missing import verified (REQ-2) | `json.dumps({})` | `SentinelError` | Error for 'json'
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** unit
- **Requirement:** 
- **Description:** Feedback to stderr (REQ-3) | `json.dumps({})` | Error in stderr | Exact string in stderr
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** unit
- **Requirement:** 
- **Description:** Mechanical validation fail (REQ-4) | Bad file | `sys.exit(1)` | Exit code 1
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** unit
- **Requirement:** 
- **Description:** Local scope resilience (REQ-5) | `def foo(a): b = a; return b` | No errors | Args/locals recognized
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** unit
- **Requirement:** 
- **Description:** Comprehensions (REQ-5) | `[x for x in y]` | No errors | 'x' isolated
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** unit
- **Requirement:** 
- **Description:** Walrus Operators (REQ-5) | `if (n := len(a)) > 1: print(n)` | No errors | 'n' recognized
- **Mock needed:** False
- **Assertions:** 

### test_080
- **Type:** unit
- **Requirement:** 
- **Description:** Star imports banned (REQ-6) | `from typing import *` | "Star imports are not allowed" | REQ-6 failure
- **Mock needed:** False
- **Assertions:** 

### test_090
- **Type:** unit
- **Requirement:** 
- **Description:** Global/Nonlocal tracking (REQ-5) | `global x; x = 1` | No errors | No false positives
- **Mock needed:** False
- **Assertions:** 

### test_100
- **Type:** unit
- **Requirement:** 
- **Description:** TYPE_CHECKING support (REQ-7) | `if TYPE_CHECKING: from x import y` | No errors | 'y' registered
- **Mock needed:** False
- **Assertions:** 

### test_110
- **Type:** unit
- **Requirement:** 
- **Description:** Ignore comments (REQ-8) | `var # sentinel: disable-line` | No errors | Symbol ignored
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

### 9.1 Test Scenarios
| ID | Scenario | Input | Expected | Pass Criteria |
|----|----------|-------|----------|---------------|
| 010 | Happy path valid AST Analysis (REQ-1) | `import os; os.path.join()` | No errors | No errors emitted |
| 020 | Missing import verified (REQ-2) | `json.dumps({})` | `SentinelError` | Error for 'json' |
| 030 | Feedback to stderr (REQ-3) | `json.dumps({})` | Error in stderr | Exact string in stderr |
| 040 | Mechanical validation fail (REQ-4) | Bad file | `sys.exit(1)` | Exit code 1 |
| 050 | Local scope resilience (REQ-5) | `def foo(a): b = a; return b` | No errors | Args/locals recognized |
| 060 | Comprehensions (REQ-5) | `[x for x in y]` | No errors | 'x' isolated |
| 070 | Walrus Operators (REQ-5) | `if (n := len(a)) > 1: print(n)` | No errors | 'n' recognized |
| 080 | Star imports banned (REQ-6) | `from typing import *` | "Star imports are not allowed" | REQ-6 failure |
| 090 | Global/Nonlocal tracking (REQ-5) | `global x; x = 1` | No errors | No false positives |
| 100 | TYPE_CHECKING support (REQ-7) | `if TYPE_CHECKING: from x import y` | No errors | 'y' registered |
| 110 | Ignore comments (REQ-8) | `var # sentinel: disable-line` | No errors | Symbol ignored |

**Final Status:** APPROVED (Manually Patched)
