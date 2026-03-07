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

# Test Plan for Issue #642

## Requirements to Cover

- REQ-1: `build_retry_prompt()` with `retry_count=1` must produce output semantically equivalent to current behavior (full LLD minus completed files, plus target file and error).
- REQ-2: `build_retry_prompt()` with `retry_count>=2` must produce a prompt containing only the relevant LLD section, the error, and a truncated previous-attempt snippet — no full LLD.
- REQ-3: Tier 2 token count must be ≤50% of an equivalent Tier 1 prompt token count for a representative 80K-token LLD (verified by unit test with fixture).
- REQ-4: If `extract_file_spec_section()` returns `None`, `build_retry_prompt()` must fall back to Tier 1 behavior and emit a warning log; it must not raise an exception.
- REQ-5: `_truncate_snippet()` must cap output at `SNIPPET_MAX_LINES` (default 60) lines; if the input is shorter, it must be returned unchanged.
- REQ-6: All functions in `retry_prompt_builder.py` and `lld_section_extractor.py` must have complete type annotations (verified by mypy with no errors).
- REQ-7: `extract_file_spec_section()` must return confidence=1.0 when the target file's exact relative path appears in a section, and a lower score otherwise.
- REQ-8: Unit test coverage for new modules must be ≥95% (measured by pytest-cov).
- REQ-9: No new runtime dependencies may be added to `pyproject.toml`.
- REQ-10: The implementation workflow's call site must pass `retry_count` and `previous_attempt_snippet` from existing workflow state; if `retry_count` is not yet tracked in state, it must be added as an integer field defaulting to 0.

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

### test_id
- **Type:** unit
- **Requirement:** 
- **Description:** Test Description | Expected Behavior | Status
- **Mock needed:** False
- **Assertions:** 

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `build_retry_prompt` retry_count=1 returns full LLD minus completed files | Prompt contains full LLD text; tier=1 | RED
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `build_retry_prompt` retry_count=2 returns section-only prompt | Prompt does NOT contain full LLD; contains only relevant section; tier=2 | RED
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** Tier 2 prompt is ≤50% tokens of tier 1 prompt for same context | `estimated_tokens` in tier 2 ≤ 0.50 × tier 1 for full_lld.md fixture | RED
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** Tier 2 fallback when section not found | Falls back to tier 1 behavior; emits warning | RED
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `build_retry_prompt` raises ValueError when retry_count < 1 | ValueError raised | RED
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `build_retry_prompt` raises ValueError when retry_count=2 and snippet is None | ValueError raised | RED
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `_truncate_snippet` truncates to max_lines | Output has ≤max_lines lines; leading ellipsis present | RED
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `_truncate_snippet` returns unchanged when input ≤max_lines | Output equals input exactly | RED
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_file_spec_section` exact path match returns confidence=1.0 | confidence == 1.0; correct section body returned | RED
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_file_spec_section` stem match returns confidence<1.0 | 0.0 < confidence < 1.0 | RED
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_file_spec_section` no match returns None | Returns None | RED
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_file_spec_section` raises ValueError on empty lld_content | ValueError raised | RED
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `_estimate_tokens` returns positive int for non-empty string | Result > 0 | RED
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `_estimate_tokens` returns 0 or handles empty string gracefully | No exception; returns 0 | RED
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `build_retry_prompt` completed_files excluded from tier 1 prompt | Excluded file names absent from prompt text | RED
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** All functions in retry_prompt_builder have complete type annotations | mypy reports zero errors on the module | RED
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** All functions in lld_section_extractor have complete type annotations | mypy reports zero errors on the module | RED
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** pytest-cov reports ≥95% line coverage for retry_prompt_builder | Coverage report shows ≥95% | RED
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** pytest-cov reports ≥95% line coverage for lld_section_extractor | Coverage report shows ≥95% | RED
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** No new entries added to pyproject.toml dependencies section | pyproject.toml diff contains no new runtime dependency lines | RED
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** Workflow state TypedDict includes retry_count integer field defaulting to 0 | Field present in state definition; default value is 0 | RED
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** Workflow call site passes retry_count to build_retry_prompt | Integration test verifies retry_count flows from state into RetryContext | RED
- **Mock needed:** False
- **Assertions:** 

### test_010
- **Type:** unit
- **Requirement:** 
- **Description:** Happy path tier 1 (REQ-1) | Auto | `RetryContext(retry_count=1, lld=full_lld, ...)` | `PrunedRetryPrompt(tier=1)` | tier==1; prompt contains LLD text
- **Mock needed:** False
- **Assertions:** 

### test_020
- **Type:** unit
- **Requirement:** 
- **Description:** Happy path tier 2 (REQ-2) | Auto | `RetryContext(retry_count=2, lld=full_lld, snippet="...", ...)` | `PrunedRetryPrompt(tier=2)` | tier==2; prompt lacks bulk of LLD; contains relevant section, error, 
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** unit
- **Requirement:** 
- **Description:** Token reduction ≥50% (REQ-3) | Auto | Same context; compare tier 1 vs tier 2 token estimates | tier2.estimated_tokens ≤ 0.5 × tier1.estimated_tokens | Numeric assertion passes
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** unit
- **Requirement:** 
- **Description:** Fallback on no section (REQ-4) | Auto | LLD with no mention of target_file; retry_count=2 | tier==1 fallback; warning logged | tier==1; no exception
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** unit
- **Requirement:** 
- **Description:** Invalid retry_count=0 (REQ-1) | Auto | `RetryContext(retry_count=0, ...)` | `ValueError` | Exception raised with descriptive message
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** unit
- **Requirement:** 
- **Description:** Tier 2, snippet None (REQ-2) | Auto | `RetryContext(retry_count=2, previous_attempt_snippet=None, ...)` | `ValueError` | Exception raised
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** unit
- **Requirement:** 
- **Description:** Snippet longer than max_lines (REQ-5) | Auto | snippet with 200 lines | Truncated to SNIPPET_MAX_LINES; starts with "..." | len(output.splitlines()) ≤ SNIPPET_MAX_LINES
- **Mock needed:** False
- **Assertions:** 

### test_080
- **Type:** unit
- **Requirement:** 
- **Description:** Snippet shorter than max_lines (REQ-5) | Auto | snippet with 5 lines | Unchanged | output == input
- **Mock needed:** False
- **Assertions:** 

### test_090
- **Type:** unit
- **Requirement:** 
- **Description:** Section extraction exact match (REQ-7) | Auto | LLD containing `assemblyzero/foo/bar.py`; target=`assemblyzero/foo/bar.py` | confidence==1.0 | Assertion passes
- **Mock needed:** False
- **Assertions:** 

### test_100
- **Type:** unit
- **Requirement:** 
- **Description:** Section extraction stem match (REQ-7) | Auto | LLD containing `bar.py` but not full path; target=`assemblyzero/foo/bar.py` | 0.0 < confidence < 1.0 | Assertion passes
- **Mock needed:** False
- **Assertions:** 

### test_110
- **Type:** unit
- **Requirement:** 
- **Description:** Section extraction no match (REQ-7) | Auto | LLD with no mention of target file or stem | None | Returns None
- **Mock needed:** False
- **Assertions:** 

### test_120
- **Type:** unit
- **Requirement:** 
- **Description:** Empty LLD raises ValueError (REQ-7) | Auto | `lld_content=""` | `ValueError` | Exception raised
- **Mock needed:** False
- **Assertions:** 

### test_130
- **Type:** unit
- **Requirement:** 
- **Description:** Token estimate positive (REQ-3) | Auto | `"Hello world"` | int > 0 | Assertion passes
- **Mock needed:** False
- **Assertions:** 

### test_140
- **Type:** unit
- **Requirement:** 
- **Description:** Token estimate empty string (REQ-3) | Auto | `""` | 0 or no exception | No crash; result ≥ 0
- **Mock needed:** False
- **Assertions:** 

### test_150
- **Type:** unit
- **Requirement:** 
- **Description:** Completed files excluded tier 1 (REQ-1) | Auto | `completed_files=["assemblyzero/done.py"]`; retry_count=1 | `"done.py"` not in prompt_text | String search passes
- **Mock needed:** False
- **Assertions:** 

### test_160
- **Type:** unit
- **Requirement:** 
- **Description:** Type annotations complete — retry_prompt_builder (REQ-6) | Auto | Run `mypy assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py --strict` | Exit code 0; zero errors reported | myp
- **Mock needed:** False
- **Assertions:** 

### test_170
- **Type:** unit
- **Requirement:** 
- **Description:** Type annotations complete — lld_section_extractor (REQ-6) | Auto | Run `mypy assemblyzero/utils/lld_section_extractor.py --strict` | Exit code 0; zero errors reported | mypy passes with no errors
- **Mock needed:** False
- **Assertions:** 

### test_180
- **Type:** unit
- **Requirement:** 
- **Description:** Coverage ≥95% retry_prompt_builder (REQ-8) | Auto | Run pytest-cov on retry_prompt_builder module | Coverage report line% ≥ 95 | pytest-cov assertion passes
- **Mock needed:** False
- **Assertions:** 

### test_190
- **Type:** unit
- **Requirement:** 
- **Description:** Coverage ≥95% lld_section_extractor (REQ-8) | Auto | Run pytest-cov on lld_section_extractor module | Coverage report line% ≥ 95 | pytest-cov assertion passes
- **Mock needed:** False
- **Assertions:** 

### test_200
- **Type:** unit
- **Requirement:** 
- **Description:** No new runtime dependencies added (REQ-9) | Auto | Read `pyproject.toml` dependencies section before and after; diff | Diff is empty (no new lines in `[project.dependencies]`) | Automated diff asserti
- **Mock needed:** False
- **Assertions:** 

### test_210
- **Type:** unit
- **Requirement:** 
- **Description:** Workflow state includes retry_count field (REQ-10) | Auto | Inspect workflow state TypedDict definition; verify field presence and default | `retry_count: int` present with default `0` | AST/import as
- **Mock needed:** False
- **Assertions:** 

### test_220
- **Type:** unit
- **Requirement:** 
- **Description:** Workflow call site passes retry_count and previous_attempt_snippet (REQ-10) | Auto | Unit test that constructs a minimal workflow state with retry_count=2 and invokes the call site wrapper; assert Ret
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

### 10.0 Test Plan (TDD - Complete Before Implementation)

**TDD Requirement:** Tests MUST be written and failing BEFORE implementation begins.

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | `build_retry_prompt` retry_count=1 returns full LLD minus completed files | Prompt contains full LLD text; tier=1 | RED |
| T020 | `build_retry_prompt` retry_count=2 returns section-only prompt | Prompt does NOT contain full LLD; contains only relevant section; tier=2 | RED |
| T030 | Tier 2 prompt is ≤50% tokens of tier 1 prompt for same context | `estimated_tokens` in tier 2 ≤ 0.50 × tier 1 for full_lld.md fixture | RED |
| T040 | Tier 2 fallback when section not found | Falls back to tier 1 behavior; emits warning | RED |
| T050 | `build_retry_prompt` raises ValueError when retry_count < 1 | ValueError raised | RED |
| T060 | `build_retry_prompt` raises ValueError when retry_count=2 and snippet is None | ValueError raised | RED |
| T070 | `_truncate_snippet` truncates to max_lines | Output has ≤max_lines lines; leading ellipsis present | RED |
| T080 | `_truncate_snippet` returns unchanged when input ≤max_lines | Output equals input exactly | RED |
| T090 | `extract_file_spec_section` exact path match returns confidence=1.0 | confidence == 1.0; correct section body returned | RED |
| T100 | `extract_file_spec_section` stem match returns confidence<1.0 | 0.0 < confidence < 1.0 | RED |
| T110 | `extract_file_spec_section` no match returns None | Returns None | RED |
| T120 | `extract_file_spec_section` raises ValueError on empty lld_content | ValueError raised | RED |
| T130 | `_estimate_tokens` returns positive int for non-empty string | Result > 0 | RED |
| T140 | `_estimate_tokens` returns 0 or handles empty string gracefully | No exception; returns 0 | RED |
| T150 | `build_retry_prompt` completed_files excluded from tier 1 prompt | Excluded file names absent from prompt text | RED |
| T160 | All functions in retry_prompt_builder have complete type annotations | mypy reports zero errors on the module | RED |
| T170 | All functions in lld_section_extractor have complete type annotations | mypy reports zero errors on the module | RED |
| T180 | pytest-cov reports ≥95% line coverage for retry_prompt_builder | Coverage report shows ≥95% | RED |
| T190 | pytest-cov reports ≥95% line coverage for lld_section_extractor | Coverage report shows ≥95% | RED |
| T200 | No new entries added to pyproject.toml dependencies section | pyproject.toml diff contains no new runtime dependency lines | RED |
| T210 | Workflow state TypedDict includes retry_count integer field defaulting to 0 | Field present in state definition; default value is 0 | RED |
| T220 | Workflow call site passes retry_count to build_retry_prompt | Integration test verifies retry_count flows from state into RetryContext | RED |

**Coverage Target:** ≥95% for all new code

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_retry_prompt_builder.py`
- [ ] Test file created at: `tests/unit/test_lld_section_extractor.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Happy path tier 1 (REQ-1) | Auto | `RetryContext(retry_count=1, lld=full_lld, ...)` | `PrunedRetryPrompt(tier=1)` | tier==1; prompt contains LLD text |
| 020 | Happy path tier 2 (REQ-2) | Auto | `RetryContext(retry_count=2, lld=full_lld, snippet="...", ...)` | `PrunedRetryPrompt(tier=2)` | tier==2; prompt lacks bulk of LLD; contains relevant section, error, and snippet |
| 030 | Token reduction ≥50% (REQ-3) | Auto | Same context; compare tier 1 vs tier 2 token estimates | tier2.estimated_tokens ≤ 0.5 × tier1.estimated_tokens | Numeric assertion passes |
| 040 | Fallback on no section (REQ-4) | Auto | LLD with no mention of target_file; retry_count=2 | tier==1 fallback; warning logged | tier==1; no exception |
| 050 | Invalid retry_count=0 (REQ-1) | Auto | `RetryContext(retry_count=0, ...)` | `ValueError` | Exception raised with descriptive message |
| 060 | Tier 2, snippet None (REQ-2) | Auto | `RetryContext(retry_count=2, previous_attempt_snippet=None, ...)` | `ValueError` | Exception raised |
| 070 | Snippet longer than max_lines (REQ-5) | Auto | snippet with 200 lines | Truncated to SNIPPET_MAX_LINES; starts with "..." | len(output.splitlines()) ≤ SNIPPET_MAX_LINES |
| 080 | Snippet shorter than max_lines (REQ-5) | Auto | snippet with 5 lines | Unchanged | output == input |
| 090 | Section extraction exact match (REQ-7) | Auto | LLD containing `assemblyzero/foo/bar.py`; target=`assemblyzero/foo/bar.py` | confidence==1.0 | Assertion passes |
| 100 | Section extraction stem match (REQ-7) | Auto | LLD containing `bar.py` but not full path; target=`assemblyzero/foo/bar.py` | 0.0 < confidence < 1.0 | Assertion passes |
| 110 | Section extraction no match (REQ-7) | Auto | LLD with no mention of target file or stem | None | Returns None |
| 120 | Empty LLD raises ValueError (REQ-7) | Auto | `lld_content=""` | `ValueError` | Exception raised |
| 130 | Token estimate positive (REQ-3) | Auto | `"Hello world"` | int > 0 | Assertion passes |
| 140 | Token estimate empty string (REQ-3) | Auto | `""` | 0 or no exception | No crash; result ≥ 0 |
| 150 | Completed files excluded tier 1 (REQ-1) | Auto | `completed_files=["assemblyzero/done.py"]`; retry_count=1 | `"done.py"` not in prompt_text | String search passes |
| 160 | Type annotations complete — retry_prompt_builder (REQ-6) | Auto | Run `mypy assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py --strict` | Exit code 0; zero errors reported | mypy passes with no errors |
| 170 | Type annotations complete — lld_section_extractor (REQ-6) | Auto | Run `mypy assemblyzero/utils/lld_section_extractor.py --strict` | Exit code 0; zero errors reported | mypy passes with no errors |
| 180 | Coverage ≥95% retry_prompt_builder (REQ-8) | Auto | Run pytest-cov on retry_prompt_builder module | Coverage report line% ≥ 95 | pytest-cov assertion passes |
| 190 | Coverage ≥95% lld_section_extractor (REQ-8) | Auto | Run pytest-cov on lld_section_extractor module | Coverage report line% ≥ 95 | pytest-cov assertion passes |
| 200 | No new runtime dependencies added (REQ-9) | Auto | Read `pyproject.toml` dependencies section before and after; diff | Diff is empty (no new lines in `[project.dependencies]`) | Automated diff assertion passes |
| 210 | Workflow state includes retry_count field (REQ-10) | Auto | Inspect workflow state TypedDict definition; verify field presence and default | `retry_count: int` present with default `0` | AST/import assertion passes |
| 220 | Workflow call site passes retry_count and previous_attempt_snippet (REQ-10) | Auto | Unit test that constructs a minimal workflow state with retry_count=2 and invokes the call site wrapper; assert RetryContext fields populated | `RetryContext.retry_count == state.retry_count`; `RetryContext.previous_attempt_snippet == state.previous_attempt_snippet` | Field-equality assertions pass |

### 10.2 Test Commands

```bash

# Run all new unit tests
poetry run pytest tests/unit/test_retry_prompt_builder.py tests/unit/test_lld_section_extractor.py -v

# Run with coverage
poetry run pytest tests/unit/test_retry_prompt_builder.py tests/unit/test_lld_section_extractor.py -v \
  --cov=assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder \
  --cov=assemblyzero/utils/lld_section_extractor \
  --cov-report=term-missing

# Type-check new modules (REQ-6)
poetry run mypy assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py \
  assemblyzero/utils/lld_section_extractor.py --strict

# Verify no new runtime dependencies added (REQ-9)
git diff pyproject.toml | grep '^\+' | grep -v 'dev\|test\|pytest\|mypy' | grep -v '^+++' || echo "PASS: no new runtime deps"

# Run full unit suite (confirm no regressions)
poetry run pytest tests/unit/ -v -m "not integration and not e2e and not adversarial"
```

### 10.3 Manual Tests (Only If Unavoidable)

**N/A - All scenarios automated.**

---
