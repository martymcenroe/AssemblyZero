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

# Test Plan for Issue #607

## Requirements to Cover

- REQ-T010: assemble_final_document()
- REQ-T020: assemble_document_node()
- REQ-T030: assemble_document_node()
- REQ-T040: strip_hallucinated_headers()

## Detected Test Types

- browser
- e2e
- integration
- mobile
- unit

## Required Tools

- appium
- detox
- docker-compose
- playwright
- pytest
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `assemble_final_document()` | `[{"header": "## 1", "content": "text"}]` | `"## 1\n\ntext\n"`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `assemble_document_node()` | Mocked 3x failure in `ChatAnthropic` | Raises `AssemblyError`
- **Mock needed:** True
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `assemble_document_node()` | `completed_sections=[...]` | Prior context included in prompt string
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `strip_hallucinated_headers()` | `content="**2. Target**\nText"`, `header="2. Target"` | `"Text"`
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `assemble_final_document()` | `[{"header": "## 1", "content": "text"}]` | `"## 1\n\ntext\n"` |
| T020 | `assemble_document_node()` | Mocked 3x failure in `ChatAnthropic` | Raises `AssemblyError` |
| T030 | `assemble_document_node()` | `completed_sections=[...]` | Prior context included in prompt string |
| T040 | `strip_hallucinated_headers()` | `content="**2. Target**\nText"`, `header="2. Target"` | `"Text"` |
