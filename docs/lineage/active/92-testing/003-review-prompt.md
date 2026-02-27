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

# Test Plan for Issue #92

## Requirements to Cover

- REQ-T010: parse_python_file()
- REQ-T020: parse_python_file()
- REQ-T030: parse_python_file()
- REQ-T040: parse_python_file()
- REQ-T050: parse_python_file()
- REQ-T060: file_path_to_module_path()
- REQ-T070: split_compound_terms()
- REQ-T080: split_compound_terms()
- REQ-T090: extract_keywords()
- REQ-T100: extract_keywords(max_keywords=5)
- REQ-T110: extract_keywords()
- REQ-T120: query_codebase_collection()
- REQ-T130: query_codebase_collection()
- REQ-T140: query_codebase_collection(max_results=10)
- REQ-T150: query_codebase_collection()
- REQ-T160: apply_token_budget(max_tokens=150)
- REQ-T170: apply_token_budget(max_tokens=500)
- REQ-T180: format_codebase_context()
- REQ-T190: format_codebase_context()
- REQ-T200: retrieve_codebase_context()
- REQ-T210: inject_codebase_context()
- REQ-T220: inject_codebase_context()
- REQ-T230: inject_codebase_context()
- REQ-T240: estimate_token_count()
- REQ-T250: get_domain_stopwords()
- REQ-T260: parse_python_file()
- REQ-T270: SentenceTransformer.encode()
- REQ-T280: query_codebase_collection()
- REQ-T290: parse_python_file()

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

### test_class_extraction_with_docstring
- **Type:** unit
- **Requirement:** 
- **Description:** T010: AST extracts class with docstring and methods. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_function_extraction_with_type_hints
- **Type:** unit
- **Requirement:** 
- **Description:** T020: AST extracts top-level function with type hints. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_private_entity_skip
- **Type:** unit
- **Requirement:** 
- **Description:** T030: AST skips private entities. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_malformed_file_returns_empty
- **Type:** unit
- **Requirement:** 
- **Description:** T040: AST handles malformed Python file. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_malformed_logs_warning
- **Type:** unit
- **Requirement:** 
- **Description:** T040/T290: Malformed Python file returns [] and logs warning with file path. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_docstring_only_init
- **Type:** unit
- **Requirement:** 
- **Description:** T050: AST skips __init__.py with only docstring. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_empty_init
- **Type:** unit
- **Requirement:** 
- **Description:** T050 variant: AST skips completely empty __init__.py. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_type_hints_preserved
- **Type:** unit
- **Requirement:** 
- **Description:** T260: AST extracts ClassDef with type hints preserved in content. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_standard_path
- **Type:** unit
- **Requirement:** 
- **Description:** T060: Convert standard file path to module path. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_init_path
- **Type:** unit
- **Requirement:** 
- **Description:** T060 variant: Convert __init__.py path. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_camel_case
- **Type:** unit
- **Requirement:** 
- **Description:** T070: CamelCase splitting. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_snake_case
- **Type:** unit
- **Requirement:** 
- **Description:** T080: snake_case splitting. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_stopword_filtering
- **Type:** unit
- **Requirement:** 
- **Description:** T090: Stopwords are filtered out. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_max_keywords_limit
- **Type:** unit
- **Requirement:** 
- **Description:** T100: Keyword extraction limits to top N. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_fallback_on_sparse_input
- **Type:** unit
- **Requirement:** 
- **Description:** T110: Keyword extraction fallback on sparse CamelCase input. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_contains_expected_terms
- **Type:** unit
- **Requirement:** 
- **Description:** T250: Domain stopwords are comprehensive. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_threshold_filtering
- **Type:** unit
- **Requirement:** 
- **Description:** T120: Nonsense query returns empty results with mocked low scores. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** True
- **Assertions:** 

### test_module_deduplication
- **Type:** unit
- **Requirement:** 
- **Description:** T130: Two chunks from same module keeps only highest score. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_max_results_limit
- **Type:** unit
- **Requirement:** 
- **Description:** T140: Query returns at most max_results. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_missing_collection_graceful
- **Type:** unit
- **Requirement:** 
- **Description:** T150: Missing collection returns empty list with warning. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_similarity_threshold_boundary
- **Type:** unit
- **Requirement:** 
- **Description:** T280: Results at boundary — 0.76 passes, 0.74 fails. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_budget_drops_lowest
- **Type:** unit
- **Requirement:** 
- **Description:** T160: Budget for 1.5 chunks keeps only top 1. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_budget_keeps_all
- **Type:** unit
- **Requirement:** 
- **Description:** T170: All chunks within budget returns all. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

### test_markdown_formatting
- **Type:** unit
- **Requirement:** 
- **Description:** T180: Output has header, instruction, and code blocks. | unit | tests/unit/test_rag/test_codebase_retrieval.py
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Scenario | Type | Source |
|---------|----------|------|--------|
| test_class_extraction_with_docstring | T010: AST extracts class with docstring and methods. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_function_extraction_with_type_hints | T020: AST extracts top-level function with type hints. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_private_entity_skip | T030: AST skips private entities. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_malformed_file_returns_empty | T040: AST handles malformed Python file. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_malformed_logs_warning | T040/T290: Malformed Python file returns [] and logs warning with file path. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_docstring_only_init | T050: AST skips __init__.py with only docstring. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_empty_init | T050 variant: AST skips completely empty __init__.py. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_type_hints_preserved | T260: AST extracts ClassDef with type hints preserved in content. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_standard_path | T060: Convert standard file path to module path. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_init_path | T060 variant: Convert __init__.py path. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_camel_case | T070: CamelCase splitting. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_snake_case | T080: snake_case splitting. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_stopword_filtering | T090: Stopwords are filtered out. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_max_keywords_limit | T100: Keyword extraction limits to top N. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_fallback_on_sparse_input | T110: Keyword extraction fallback on sparse CamelCase input. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_contains_expected_terms | T250: Domain stopwords are comprehensive. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_threshold_filtering | T120: Nonsense query returns empty results with mocked low scores. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_module_deduplication | T130: Two chunks from same module keeps only highest score. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_max_results_limit | T140: Query returns at most max_results. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_missing_collection_graceful | T150: Missing collection returns empty list with warning. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_similarity_threshold_boundary | T280: Results at boundary — 0.76 passes, 0.74 fails. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_budget_drops_lowest | T160: Budget for 1.5 chunks keeps only top 1. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_budget_keeps_all | T170: All chunks within budget returns all. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
| test_markdown_formatting | T180: Output has header, instruction, and code blocks. | unit | tests/unit/test_rag/test_codebase_retrieval.py |
