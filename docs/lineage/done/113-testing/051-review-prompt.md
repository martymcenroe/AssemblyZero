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

# Test Plan for Issue #113

## Requirements to Cover

- REQ-T020: VectorStore.is_initialized
- REQ-T030: VectorStore.initialize()
- REQ-T040: CollectionManager.create_collection()
- REQ-T050: CollectionManager.list_collections()
- REQ-T060: EmbeddingProvider.embed_query()
- REQ-T070: EmbeddingProvider.embed_texts()
- REQ-T080: EmbeddingProvider.is_loaded
- REQ-T110: VectorStore.initialize()
- REQ-T120: EmbeddingProvider.embed_texts()
- REQ-T130: All error classes
- REQ-T150: VectorStore.initialize()
- REQ-T160: QueryEngine.add_documents()
- REQ-T170: QueryEngine.query()
- REQ-T180: QueryEngine.delete_documents()
- REQ-T190: QueryEngine.query(where=...)
- REQ-T200: QueryEngine.get_document()
- REQ-T210: TextChunker.chunk_text()
- REQ-T220: TextChunker.chunk_text(metadata=...)
- REQ-T230: TextChunker.chunk_text("")
- REQ-T240: TextChunker.chunk_text("short")
- REQ-T250: TextChunker.chunk_file()
- REQ-T320: CollectionManager.collection_count()
- REQ-T330: RAGConfig()
- REQ-T340: QueryEngine.query("nonexistent", ...)
- REQ-T350: RAGConfig(chunk_overlap=chunk_size)
- REQ-T360: TextChunker.chunk_file(outside_path)

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
- **Description:** `VectorStore.__init__()` + `initialize()` | `VectorStore(config)` → `initialize()` | `is_initialized == True`, directory exists
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `VectorStore.is_initialized` | `VectorStore()` (no init) | `False`
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `VectorStore.initialize()` | Path points to a file | `StoreCorruptedError`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `CollectionManager.create_collection()` | `"documentation"`, `"codebase"` | Both accessible via `get_collection()`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `CollectionManager.list_collections()` | 3 collections created | List of 3 names
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `EmbeddingProvider.embed_query()` | `"hello world"` | `list[float]` of len 384
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `EmbeddingProvider.embed_texts()` | `["a", "b", "c"]` | 3 vectors of len 384
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `EmbeddingProvider.is_loaded` | Fresh `EmbeddingProvider()` | `False`
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `CollectionManager` isolation | Add to docs, check codebase | Codebase empty
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `QueryEngine.add_documents()` + `query()` | Both collections via one engine | Both return correct results
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `VectorStore.initialize()` | chromadb mocked absent | `ImportError("chromadb")`
- **Mock needed:** True
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `EmbeddingProvider.embed_texts()` | sentence-transformers mocked absent | `ImportError("sentence-transformers")`
- **Mock needed:** True
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** All error classes | Instantiate each | All `isinstance(err, RAGError)`
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `VectorStore` close + reopen | Add data → close → reopen → query | Data still present
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `VectorStore.initialize()` | Custom `persist_directory` | Directory exists at path
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `QueryEngine.add_documents()` | 2 documents | 2 SHA-256 IDs returned
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `QueryEngine.query()` | Query matching content | Results[0] most similar
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `QueryEngine.delete_documents()` | Add 3, delete 1 | Count == 2
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `QueryEngine.query(where=...)` | Filter on metadata key | Only matching docs
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `QueryEngine.get_document()` | Known ID | Correct doc + metadata
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `TextChunker.chunk_text()` | 10 tokens, size=4, overlap=1 | 3 chunks
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** `TextChunker.chunk_text(metadata=...)` | Text + metadata | All chunks have metadata
- **Mock needed:** False
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** `TextChunker.chunk_text("")` | Empty string | `[]`
- **Mock needed:** False
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `TextChunker.chunk_text("short")` | Short text | 1 chunk
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `TextChunker.chunk_file()` | Real file path | Chunks with `source_file` in metadata
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `get_query_engine()` x2 | Two calls | Same `id()`
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `get_store()` x2 | Two calls | Same `id()`
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `inspect.get_annotations()` on all public methods | All classes | All have return hints
- **Mock needed:** False
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `.__doc__` on all public methods | All classes | All non-empty
- **Mock needed:** False
- **Assertions:** 

### test_t300
- **Type:** unit
- **Requirement:** 
- **Description:** `QueryEngine.add_documents()` x2 same content | Same doc twice | Count == 1
- **Mock needed:** False
- **Assertions:** 

### test_t310
- **Type:** unit
- **Requirement:** 
- **Description:** `QueryEngine.query()` on empty collection | Empty collection | `total_results == 0`
- **Mock needed:** False
- **Assertions:** 

### test_t320
- **Type:** unit
- **Requirement:** 
- **Description:** `CollectionManager.collection_count()` | 5 docs added | Returns 5
- **Mock needed:** False
- **Assertions:** 

### test_t330
- **Type:** unit
- **Requirement:** 
- **Description:** `RAGConfig()` | Default constructor | All defaults match spec
- **Mock needed:** False
- **Assertions:** 

### test_t340
- **Type:** unit
- **Requirement:** 
- **Description:** `QueryEngine.query("nonexistent", ...)` | Non-existent collection | `CollectionNotFoundError`
- **Mock needed:** False
- **Assertions:** 

### test_t350
- **Type:** unit
- **Requirement:** 
- **Description:** `RAGConfig(chunk_overlap=chunk_size)` | overlap == size | `ValueError`
- **Mock needed:** False
- **Assertions:** 

### test_t360
- **Type:** unit
- **Requirement:** 
- **Description:** `TextChunker.chunk_file(outside_path)` | Path outside project root | `ValueError("Path traversal")`
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `VectorStore.__init__()` + `initialize()` | `VectorStore(config)` → `initialize()` | `is_initialized == True`, directory exists |
| T020 | `VectorStore.is_initialized` | `VectorStore()` (no init) | `False` |
| T030 | `VectorStore.initialize()` | Path points to a file | `StoreCorruptedError` |
| T040 | `CollectionManager.create_collection()` | `"documentation"`, `"codebase"` | Both accessible via `get_collection()` |
| T050 | `CollectionManager.list_collections()` | 3 collections created | List of 3 names |
| T060 | `EmbeddingProvider.embed_query()` | `"hello world"` | `list[float]` of len 384 |
| T070 | `EmbeddingProvider.embed_texts()` | `["a", "b", "c"]` | 3 vectors of len 384 |
| T080 | `EmbeddingProvider.is_loaded` | Fresh `EmbeddingProvider()` | `False` |
| T090 | `CollectionManager` isolation | Add to docs, check codebase | Codebase empty |
| T100 | `QueryEngine.add_documents()` + `query()` | Both collections via one engine | Both return correct results |
| T110 | `VectorStore.initialize()` | chromadb mocked absent | `ImportError("chromadb")` |
| T120 | `EmbeddingProvider.embed_texts()` | sentence-transformers mocked absent | `ImportError("sentence-transformers")` |
| T130 | All error classes | Instantiate each | All `isinstance(err, RAGError)` |
| T140 | `VectorStore` close + reopen | Add data → close → reopen → query | Data still present |
| T150 | `VectorStore.initialize()` | Custom `persist_directory` | Directory exists at path |
| T160 | `QueryEngine.add_documents()` | 2 documents | 2 SHA-256 IDs returned |
| T170 | `QueryEngine.query()` | Query matching content | Results[0] most similar |
| T180 | `QueryEngine.delete_documents()` | Add 3, delete 1 | Count == 2 |
| T190 | `QueryEngine.query(where=...)` | Filter on metadata key | Only matching docs |
| T200 | `QueryEngine.get_document()` | Known ID | Correct doc + metadata |
| T210 | `TextChunker.chunk_text()` | 10 tokens, size=4, overlap=1 | 3 chunks |
| T220 | `TextChunker.chunk_text(metadata=...)` | Text + metadata | All chunks have metadata |
| T230 | `TextChunker.chunk_text("")` | Empty string | `[]` |
| T240 | `TextChunker.chunk_text("short")` | Short text | 1 chunk |
| T250 | `TextChunker.chunk_file()` | Real file path | Chunks with `source_file` in metadata |
| T260 | `get_query_engine()` x2 | Two calls | Same `id()` |
| T270 | `get_store()` x2 | Two calls | Same `id()` |
| T280 | `inspect.get_annotations()` on all public methods | All classes | All have return hints |
| T290 | `.__doc__` on all public methods | All classes | All non-empty |
| T300 | `QueryEngine.add_documents()` x2 same content | Same doc twice | Count == 1 |
| T310 | `QueryEngine.query()` on empty collection | Empty collection | `total_results == 0` |
| T320 | `CollectionManager.collection_count()` | 5 docs added | Returns 5 |
| T330 | `RAGConfig()` | Default constructor | All defaults match spec |
| T340 | `QueryEngine.query("nonexistent", ...)` | Non-existent collection | `CollectionNotFoundError` |
| T350 | `RAGConfig(chunk_overlap=chunk_size)` | overlap == size | `ValueError` |
| T360 | `TextChunker.chunk_file(outside_path)` | Path outside project root | `ValueError("Path traversal")` |
