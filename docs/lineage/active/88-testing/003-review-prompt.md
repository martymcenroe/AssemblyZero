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

# Test Plan for Issue #88

## Requirements to Cover

- REQ-1: All tests run in under 5 minutes
- REQ-2: Test results reported as PR checks
- REQ-3: Coverage report generated automatically

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

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `split_on_headers()`, `chunk_markdown_document()` | Markdown with H2 sections / fixture ADR | Correct section count and titles
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_doc_type()` | Paths from adrs/, standards/, LLDs/done/ | "adr", "standard", "lld"
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `split_on_headers()` | Plain text, no headers | 1 section, title="Untitled"
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `check_rag_dependencies()` | Mocked missing chromadb | `(False, "...pip install assemblyzero[rag]")`
- **Mock needed:** True
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `check_rag_dependencies()` | Mocked available imports | `(True, "RAG dependencies available")`
- **Mock needed:** True
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `VectorStoreManager.is_initialized()` | Non-existent path | `False`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `VectorStoreManager.add_chunks()` + `.query()` | Add 2 chunks, query similar | Top result matches, score > 0.5
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `VectorStoreManager.query()` | Empty collection | `[]`
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `LibrarianNode.retrieve()` | 4 candidates, 2 above 0.7 | 2 results, all scores >= 0.7
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `LibrarianNode.retrieve()` | 5 above threshold, top_n=3 | 3 results
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `LibrarianNode.check_availability()` | Mocked deps unavailable | `(False, "deps_missing")`
- **Mock needed:** True
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `LibrarianNode.check_availability()` | Deps OK, store missing | `(False, "unavailable")`
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `librarian_node()` | Mocked deps unavailable | `{"rag_status": "deps_missing"}`
- **Mock needed:** True
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `librarian_node()` | Mocked deps OK, store missing | `{"rag_status": "unavailable"}`
- **Mock needed:** True
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `librarian_node()` | Mocked retrieve returns [] | `{"rag_status": "no_results"}`
- **Mock needed:** True
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `librarian_node()` | Mocked retrieve returns 2 docs | `{"rag_status": "success"}`, INFO log
- **Mock needed:** True
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `merge_contexts()` | Overlapping RAG + manual paths | Deduplicated, manual kept
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `merge_contexts()` | 1 manual + 1 RAG | Manual at index 0
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `LibrarianNode.format_context_for_designer()` | 2 RetrievedDocuments | String with file paths, sections
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** integration
- **Requirement:** 
- **Description:** `run_full_ingestion()` via integration | 3 fixture files | files_indexed >= 3
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** integration
- **Requirement:** 
- **Description:** `run_incremental_ingestion()` via integration | After full, no changes | files_skipped >= 3
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** integration
- **Requirement:** 
- **Description:** `librarian_node()` via integration | Real store + fixture data | rag_status in ("success", "no_results")
- **Mock needed:** False
- **Assertions:** 

### test_t230
- **Type:** integration
- **Requirement:** 
- **Description:** `librarian_node()` via integration | Mocked deps missing | rag_status = "deps_missing"
- **Mock needed:** True
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `LocalEmbeddingProvider.embed_query()` | Single text string | 384-dim float list
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `LibrarianNode.retrieve()` performance | Warm store query | elapsed < 500ms
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** CLI spinner display | — | Deferred to manual verification or integration test
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `run_full_ingestion()` performance | 100 files | elapsed < 10s
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** Core install check | — | Deferred to CI environment test
- **Mock needed:** False
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `VectorStoreManager` persistence | Add, new instance, query | Previous data accessible
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `split_on_headers()`, `chunk_markdown_document()` | Markdown with H2 sections / fixture ADR | Correct section count and titles |
| T020 | `detect_doc_type()` | Paths from adrs/, standards/, LLDs/done/ | "adr", "standard", "lld" |
| T030 | `split_on_headers()` | Plain text, no headers | 1 section, title="Untitled" |
| T040 | `check_rag_dependencies()` | Mocked missing chromadb | `(False, "...pip install assemblyzero[rag]")` |
| T050 | `check_rag_dependencies()` | Mocked available imports | `(True, "RAG dependencies available")` |
| T060 | `VectorStoreManager.is_initialized()` | Non-existent path | `False` |
| T070 | `VectorStoreManager.add_chunks()` + `.query()` | Add 2 chunks, query similar | Top result matches, score > 0.5 |
| T080 | `VectorStoreManager.query()` | Empty collection | `[]` |
| T090 | `LibrarianNode.retrieve()` | 4 candidates, 2 above 0.7 | 2 results, all scores >= 0.7 |
| T100 | `LibrarianNode.retrieve()` | 5 above threshold, top_n=3 | 3 results |
| T110 | `LibrarianNode.check_availability()` | Mocked deps unavailable | `(False, "deps_missing")` |
| T120 | `LibrarianNode.check_availability()` | Deps OK, store missing | `(False, "unavailable")` |
| T130 | `librarian_node()` | Mocked deps unavailable | `{"rag_status": "deps_missing"}` |
| T140 | `librarian_node()` | Mocked deps OK, store missing | `{"rag_status": "unavailable"}` |
| T150 | `librarian_node()` | Mocked retrieve returns [] | `{"rag_status": "no_results"}` |
| T160 | `librarian_node()` | Mocked retrieve returns 2 docs | `{"rag_status": "success"}`, INFO log |
| T170 | `merge_contexts()` | Overlapping RAG + manual paths | Deduplicated, manual kept |
| T180 | `merge_contexts()` | 1 manual + 1 RAG | Manual at index 0 |
| T190 | `LibrarianNode.format_context_for_designer()` | 2 RetrievedDocuments | String with file paths, sections |
| T200 | `run_full_ingestion()` via integration | 3 fixture files | files_indexed >= 3 |
| T210 | `run_incremental_ingestion()` via integration | After full, no changes | files_skipped >= 3 |
| T220 | `librarian_node()` via integration | Real store + fixture data | rag_status in ("success", "no_results") |
| T230 | `librarian_node()` via integration | Mocked deps missing | rag_status = "deps_missing" |
| T240 | `LocalEmbeddingProvider.embed_query()` | Single text string | 384-dim float list |
| T250 | `LibrarianNode.retrieve()` performance | Warm store query | elapsed < 500ms |
| T260 | CLI spinner display | — | Deferred to manual verification or integration test |
| T270 | `run_full_ingestion()` performance | 100 files | elapsed < 10s |
| T280 | Core install check | — | Deferred to CI environment test |
| T290 | `VectorStoreManager` persistence | Add, new instance, query | Previous data accessible |

**Notes on T250, T260, T270, T280:**
- T250 (latency) and T270 (reindex timing) are best tested in integration tests with `@pytest.mark.rag` since they require real model loading.
- T260 (spinner) requires terminal interaction — covered by the implementation logging pattern rather than automated assertion.
- T280 (core install) is a CI-level check verified by the dependency isolation approach.
