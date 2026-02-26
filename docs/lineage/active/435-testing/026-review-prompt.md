# Test Plan Review Prompt

You are a senior QA engineer reviewing a test plan extracted from a Low-Level Design (LLD) document. Your goal is to ensure the test plan provides adequate coverage and uses real, executable tests.

## Pre-Flight Check

Before reviewing, verify these fundamentals:
- [ ] Test plan section exists and is not empty
- [ ] At least one test scenario is defined
- [ ] Test scenarios have names and descriptions

If any pre-flight check fails, immediately return BLOCKED with the specific issue.

## Review Criteria

### 1. Coverage Analysis (CRITICAL - 100% threshold per ADR 0207)

Calculate coverage by mapping test scenarios to requirements:

```
Coverage = (Requirements with tests / Total requirements) * 100
```

For each requirement, identify:
- Which test(s) cover it
- If no test covers it, flag as a gap

**BLOCKING if:** Coverage < 95%

### 2. Test Reality Check (CRITICAL)

Every test MUST be an executable automated test. Flag any test that:
- Delegates to "manual verification" or "human review"
- Says "verify by inspection" or "visual check"
- Has no clear assertions or expected outcomes
- Is vague like "test that it works"

**BLOCKING if:** Any test is not executable

### 3. No Human Delegation

Tests must NOT require human intervention. Flag any test that:
- Requires someone to "observe" behavior
- Needs "judgment" to determine pass/fail
- Says "ask the user" or "get feedback"

**BLOCKING if:** Any test delegates to humans

### 4. Test Type Appropriateness

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
## Pre-Flight Gate

- [x] PASSED / [ ] FAILED: Test plan exists
- [x] PASSED / [ ] FAILED: Scenarios defined
- [x] PASSED / [ ] FAILED: Scenarios have names

## Coverage Analysis

| Requirement | Test(s) | Status |
|-------------|---------|--------|
| REQ-1       | test_x  | Covered |
| REQ-2       | -       | GAP |

**Coverage: X/Y requirements (Z%)**

## Test Reality Check

| Test | Issue | Status |
|------|-------|--------|
| test_x | None | OK |
| test_y | "Manual check" | FAIL |

## Human Delegation Check

- [ ] PASSED: No human delegation found
- [ ] FAILED: [list tests that delegate to humans]

## Test Type Review

| Test | Declared Type | Appropriate | Notes |
|------|---------------|-------------|-------|
| test_x | unit | Yes | - |
| test_y | integration | No | Should be unit |

## Edge Cases

- [ ] Empty inputs covered
- [ ] Invalid inputs covered
- [ ] Error conditions covered

## Verdict

[x] **APPROVED** - Test plan is ready for implementation

OR

[x] **BLOCKED** - Test plan needs revision

## Required Changes (if BLOCKED)

1. [Specific, actionable change needed]
2. [Specific, actionable change needed]
```

## Important Notes

- Be strict on coverage (95% threshold)
- Be strict on test reality (no manual tests)
- Provide specific, actionable feedback
- Reference specific tests and requirements by name


---

# Test Plan for Issue #435

## Requirements to Cover

- REQ-1: Example requirement

## Detected Test Types

- browser
- e2e
- integration
- mobile
- performance
- security
- unit

## Required Tools

- appium
- bandit
- detox
- docker-compose
- locust
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
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_gemini_review()` | Fixture `sample_lld_with_review.md` content (contains `### Gemini Review` heading) | `True`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_gemini_review()` | Fixture `sample_lld_no_review.md` content (ends with `*No reviews yet.*`) | `False`
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_gemini_review()` | `""` | `False`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_gemini_review()` | `"# 400 - Example\n\n## Appendix: Review Log\n\n### Gemini Revi"` (truncated marker) | `False`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_gemini_review()` | Fixture with_review content + `"\n\n### Gemini Review\n\n | Field | Value | ..."` appended | `True`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `embed_review_evidence()` | String containing `"APPROVED"`, `"Gemini"`, `"2026-02-25T10:00:00Z"`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `embed_review_evidence()` | Result of T060 + same evidence dict | Verdict count equals T060 verdict count (no duplication)
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `embed_review_evidence()` | `ValueError`/`KeyError`/`TypeError` raised, OR returns original content unchanged
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `embed_review_evidence()` | `""` + valid evidence dict | `ValueError`/`TypeError` raised, OR returns string containing verdict
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `embed_review_evidence()` | Output contains `"## 1. Context & Goal"` and `"## 2. Proposed Changes"`
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `embed_review_evidence()` | Output contains `"Gemini"`, `"APPROVED"`, `"2026-02-25T10:00:00Z"`, `"gemini-2.5-pro"`, `"Design is sound"`
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking.json")` | Dict with key `"100"`, entry `{"issue_id": 100, "status": "approved", ...}`
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `load_lld_tracking()` | `tmp_path / "does_not_exist.json"` | `FileNotFoundError` raised OR `{}`
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking_corrupt.json")` | `json.JSONDecodeError` raised OR `{}`
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `load_lld_tracking()` | `tmp_path / "empty.json"` (0 bytes) | `{}` OR `json.JSONDecodeError`
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking.json")` | Dict with keys `{"100", "200", "300"}`
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `update_lld_status()` | File with 3 entries, `issue_id=100, status="rejected"` | File re-read: entry 100 has `status="rejected"`, `lld_path` unchanged
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `update_lld_status()` | File with 3 entries (100, 200, 300), `issue_id=999, status="draft"` | File re-read: new entry 999 with `status="draft"`, keys 100/200/300 still present
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `update_lld_status()` | Non-existent file path, `issue_id=500, status="draft"` | File created, re-read: entry 500 with `status="draft"`
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `update_lld_status()` | File with 3 entries, `issue_id=200, status="reviewed", gemini_reviewed=True, review_verdict="APPROVED", review_timestamp="2026-02-25T12:00:00Z"` | Entry 200 has all kwargs merg
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `update_lld_status()` | File with 3 entries, `issue_id=100, status="invalid_value"` | `ValueError` raised OR graceful handling (entry stored)
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** N/A (meta-test) | `Path(__file__)` introspection + `inspect.getmembers()` | File in `tests/unit/`, name `test_lld_tracking.py`, ≥5 `Test*` classes
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `detect_gemini_review()` | Fixture `sample_lld_with_review.md` content (contains `### Gemini Review` heading) | `True` |
| T020 | `detect_gemini_review()` | Fixture `sample_lld_no_review.md` content (ends with `*No reviews yet.*`) | `False` |
| T030 | `detect_gemini_review()` | `""` | `False` |
| T040 | `detect_gemini_review()` | `"# 400 - Example\n\n## Appendix: Review Log\n\n### Gemini Revi"` (truncated marker) | `False` |
| T050 | `detect_gemini_review()` | Fixture with_review content + `"\n\n### Gemini Review\n\n| Field | Value |..."` appended | `True` |
| T060 | `embed_review_evidence()` | No-review fixture + `{"reviewer": "Gemini", "verdict": "APPROVED", "comments": ["Design is sound"], "timestamp": "2026-02-25T10:00:00Z", "model": "gemini-2.5-pro"}` | String containing `"APPROVED"`, `"Gemini"`, `"2026-02-25T10:00:00Z"` |
| T070 | `embed_review_evidence()` | Result of T060 + same evidence dict | Verdict count equals T060 verdict count (no duplication) |
| T080 | `embed_review_evidence()` | No-review fixture + `{}` | `ValueError`/`KeyError`/`TypeError` raised, OR returns original content unchanged |
| T090 | `embed_review_evidence()` | `""` + valid evidence dict | `ValueError`/`TypeError` raised, OR returns string containing verdict |
| T100 | `embed_review_evidence()` | No-review fixture + valid evidence | Output contains `"## 1. Context & Goal"` and `"## 2. Proposed Changes"` |
| T110 | `embed_review_evidence()` | No-review fixture + valid evidence (all fields) | Output contains `"Gemini"`, `"APPROVED"`, `"2026-02-25T10:00:00Z"`, `"gemini-2.5-pro"`, `"Design is sound"` |
| T120 | `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking.json")` | Dict with key `"100"`, entry `{"issue_id": 100, "status": "approved", ...}` |
| T130 | `load_lld_tracking()` | `tmp_path / "does_not_exist.json"` | `FileNotFoundError` raised OR `{}` |
| T140 | `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking_corrupt.json")` | `json.JSONDecodeError` raised OR `{}` |
| T150 | `load_lld_tracking()` | `tmp_path / "empty.json"` (0 bytes) | `{}` OR `json.JSONDecodeError` |
| T160 | `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking.json")` | Dict with keys `{"100", "200", "300"}` |
| T170 | `update_lld_status()` | File with 3 entries, `issue_id=100, status="rejected"` | File re-read: entry 100 has `status="rejected"`, `lld_path` unchanged |
| T180 | `update_lld_status()` | File with 3 entries (100, 200, 300), `issue_id=999, status="draft"` | File re-read: new entry 999 with `status="draft"`, keys 100/200/300 still present |
| T190 | `update_lld_status()` | Non-existent file path, `issue_id=500, status="draft"` | File created, re-read: entry 500 with `status="draft"` |
| T200 | `update_lld_status()` | File with 3 entries, `issue_id=200, status="reviewed", gemini_reviewed=True, review_verdict="APPROVED", review_timestamp="2026-02-25T12:00:00Z"` | Entry 200 has all kwargs merged: `gemini_reviewed=True`, `review_verdict="APPROVED"` |
| T210 | `update_lld_status()` | File with 3 entries, `issue_id=100, status="invalid_value"` | `ValueError` raised OR graceful handling (entry stored) |
| T220 | N/A (meta-test) | `Path(__file__)` introspection + `inspect.getmembers()` | File in `tests/unit/`, name `test_lld_tracking.py`, ≥5 `Test*` classes |
