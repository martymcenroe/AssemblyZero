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

# Test Plan for Issue #497

## Requirements to Cover



## Detected Test Types

- browser
- e2e
- integration
- mobile
- performance
- security
- terminal
- unit

## Required Tools

- appium
- bandit
- click.testing
- detox
- docker-compose
- locust
- pexpect
- playwright
- pytest
- pytest-benchmark
- safety
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Performance Tests:** Test against representative data volumes
**Security Tests:** Never use real credentials, test edge cases thoroughly
**Terminal/CLI Tests:** Use CliRunner or capture stdout/stderr
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_010
- **Type:** unit
- **Requirement:** 
- **Description:** `build_feedback_block()` | 5 large verdicts (~1500 tokens each), budget=4000 | `total_tokens <= 4000`
- **Mock needed:** False
- **Assertions:** 

### test_015
- **Type:** unit
- **Requirement:** 
- **Description:** `build_feedback_block()` | 5 large verdicts, budget=2000 | `total_tokens <= 2000`
- **Mock needed:** False
- **Assertions:** 

### test_020
- **Type:** unit
- **Requirement:** 
- **Description:** `build_feedback_block()` | `[v1]` (single JSON verdict fixture) | `latest_verdict_full == v1`, `prior_summaries == []`
- **Mock needed:** False
- **Assertions:** 

### test_025
- **Type:** unit
- **Requirement:** 
- **Description:** `build_feedback_block()` | `[v1, v2, v3]` (3 JSON verdict fixtures) | `latest_verdict_full == v3`
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** unit
- **Requirement:** 
- **Description:** `build_feedback_block()` | `[v1, v2, v3]` (3 JSON verdict fixtures) | 2 VerdictSummary in `prior_summaries`
- **Mock needed:** False
- **Assertions:** 

### test_035
- **Type:** unit
- **Requirement:** 
- **Description:** `format_summary_line()` | `VerdictSummary(iter=2, BLOCKED, 2 issues, 1 persist)` | Contains `"Iteration 2"`, `"BLOCKED"`, `"2 issues"`, persist desc
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** unit
- **Requirement:** 
- **Description:** `identify_persisting_issues()` | `current=["No rollback plan..."]`, `prior=["Missing error...", "No rollback plan..."]` | `(["No rollback plan..."], [])`
- **Mock needed:** False
- **Assertions:** 

### test_045
- **Type:** unit
- **Requirement:** 
- **Description:** `identify_persisting_issues()` | `current=["Missing rollback plan..."]`, `prior=["No rollback plan..."]` | Persisting detected (similarity > 0.8)
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** unit
- **Requirement:** 
- **Description:** `identify_persisting_issues()` | `current=["Test coverage..."]`, `prior=["Missing error..."]` | `([], ["Test coverage..."])`
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** unit
- **Requirement:** 
- **Description:** `build_feedback_block()` | `abs(t5 - t2) / t2 < 0.20`
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** unit
- **Requirement:** 
- **Description:** `build_feedback_block()` | `[]` | `FeedbackWindow(latest="", prior=[], tokens=0, truncated=False)`
- **Mock needed:** False
- **Assertions:** 

### test_075
- **Type:** unit
- **Requirement:** 
- **Description:** `render_feedback_markdown()` | Empty `FeedbackWindow` | `""`
- **Mock needed:** False
- **Assertions:** 

### test_080
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_blocking_issues()` | JSON verdict fixture string (3 issues) | `["Missing error handling...", "No rollback plan...", "Security section..."]`
- **Mock needed:** False
- **Assertions:** 

### test_085
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_blocking_issues()` | Text verdict with `**[BLOCKING]**` lines | `["Missing error handling...", "No rollback plan...", "Security section..."]`
- **Mock needed:** False
- **Assertions:** 

### test_090
- **Type:** unit
- **Requirement:** 
- **Description:** `build_feedback_block()` | `[text_verdict, json_verdict]` | Valid `FeedbackWindow`, `prior_summaries[0].verdict == "BLOCKED"`
- **Mock needed:** False
- **Assertions:** 

### test_095
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_blocking_issues()` | `'{invalid json\n- **[BLOCKING]** Fallback issue found'` | `["Fallback issue found"]`, `logger.warning` captured
- **Mock needed:** False
- **Assertions:** 

### test_100
- **Type:** unit
- **Requirement:** 
- **Description:** `build_feedback_block()` | 5 large verdicts, tight budget (2000) | `was_truncated=True`, counter incremented, warning logged
- **Mock needed:** False
- **Assertions:** 

### test_110
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_draft` import chain | Module-level mock patching | `build_feedback_block` and `render_feedback_markdown` importable and patchable
- **Mock needed:** True
- **Assertions:** 

### test_120
- **Type:** unit
- **Requirement:** 
- **Description:** `render_feedback_markdown()` | Single-verdict `FeedbackWindow` | Contains `"## Review Feedback"`, not `"Prior Review Summary"`
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| 010 | `build_feedback_block()` | 5 large verdicts (~1500 tokens each), budget=4000 | `total_tokens <= 4000` |
| 015 | `build_feedback_block()` | 5 large verdicts, budget=2000 | `total_tokens <= 2000` |
| 020 | `build_feedback_block()` | `[v1]` (single JSON verdict fixture) | `latest_verdict_full == v1`, `prior_summaries == []` |
| 025 | `build_feedback_block()` | `[v1, v2, v3]` (3 JSON verdict fixtures) | `latest_verdict_full == v3` |
| 030 | `build_feedback_block()` | `[v1, v2, v3]` (3 JSON verdict fixtures) | 2 VerdictSummary in `prior_summaries` |
| 035 | `format_summary_line()` | `VerdictSummary(iter=2, BLOCKED, 2 issues, 1 persist)` | Contains `"Iteration 2"`, `"BLOCKED"`, `"2 issues"`, persist desc |
| 040 | `identify_persisting_issues()` | `current=["No rollback plan..."]`, `prior=["Missing error...", "No rollback plan..."]` | `(["No rollback plan..."], [])` |
| 045 | `identify_persisting_issues()` | `current=["Missing rollback plan..."]`, `prior=["No rollback plan..."]` | Persisting detected (similarity > 0.8) |
| 050 | `identify_persisting_issues()` | `current=["Test coverage..."]`, `prior=["Missing error..."]` | `([], ["Test coverage..."])` |
| 060 | `build_feedback_block()` | 2-verdict vs 5-verdict history with identical base verdict | `abs(t5 - t2) / t2 < 0.20` |
| 070 | `build_feedback_block()` | `[]` | `FeedbackWindow(latest="", prior=[], tokens=0, truncated=False)` |
| 075 | `render_feedback_markdown()` | Empty `FeedbackWindow` | `""` |
| 080 | `extract_blocking_issues()` | JSON verdict fixture string (3 issues) | `["Missing error handling...", "No rollback plan...", "Security section..."]` |
| 085 | `extract_blocking_issues()` | Text verdict with `**[BLOCKING]**` lines | `["Missing error handling...", "No rollback plan...", "Security section..."]` |
| 090 | `build_feedback_block()` | `[text_verdict, json_verdict]` | Valid `FeedbackWindow`, `prior_summaries[0].verdict == "BLOCKED"` |
| 095 | `extract_blocking_issues()` | `'{invalid json\n- **[BLOCKING]** Fallback issue found'` | `["Fallback issue found"]`, `logger.warning` captured |
| 100 | `build_feedback_block()` | 5 large verdicts, tight budget (2000) | `was_truncated=True`, counter incremented, warning logged |
| 110 | `generate_draft` import chain | Module-level mock patching | `build_feedback_block` and `render_feedback_markdown` importable and patchable |
| 120 | `render_feedback_markdown()` | Single-verdict `FeedbackWindow` | Contains `"## Review Feedback"`, not `"Prior Review Summary"` |
