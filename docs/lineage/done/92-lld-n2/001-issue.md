# Issue #92: Hex: Codebase Retrieval System (RAG Injection)

# RAG Injection: Codebase Retrieval System (The Smart Engineer)

## User Story
As a **Developer using AgentOS workflows**,
I want the **Coder Node to automatically receive context about existing utilities and patterns**,
So that **generated code uses actual project imports and avoids reinventing existing functionality**.

## Objective
Implement a codebase retrieval system that indexes Python code via AST parsing and injects relevant function signatures into the Coder Node's context before code generation.

## UX Flow

### Scenario 1: Happy Path - Coder Uses Existing Utility
1. User submits an LLD that mentions "audit logging"
2. System extracts keywords: ["audit", "logging", "GovernanceAuditLog"]
3. System queries vector store with keywords, retrieves `GovernanceAuditLog` class definition
4. System injects reference code into Coder's system prompt
5. Coder generates implementation using `from agentos.core.audit import GovernanceAuditLog`
6. Result: Code passes lint/audit gates on first attempt

### Scenario 2: No Relevant Codebase Match
1. User submits an LLD for a genuinely new feature with no existing utilities
2. System extracts keywords but vector store returns no matches above threshold (0.75)
3. System proceeds without injecting reference code
4. Coder generates implementation from scratch
5. Result: Normal workflow continues, no false positives injected

### Scenario 3: Multiple Relevant Utilities Found
1. User submits an LLD mentioning "Gemini API" and "configuration"
2. System extracts keywords: ["Gemini", "API", "config", "GeminiClient"]
3. System retrieves both `GeminiClient` and `Config` class definitions
4. System injects both under "Reference Codebase" section
5. Coder uses both utilities correctly
6. Result: No wheel reinvention, proper client wrapper used

### Scenario 4: Codebase Index Stale/Missing
1. User runs implementation workflow
2. System checks for codebase collection in vector store
3. Collection is missing or outdated
4. System logs warning and proceeds without codebase context
5. Result: Graceful degradation, workflow completes with warning

## Requirements

### Codebase Indexing
1. Parse Python files using `ast` module (not line-based chunking)
2. Extract chunks by **Class** and **Top-Level Function** boundaries
3. Index files from `agentos/**/*.py` and `tools/**/*.py`
4. Store metadata: `type: code`, `module: <full.module.path>`, `kind: class|function`
5. Include docstrings and type hints in indexed content
6. Store in dedicated collection `codebase` (separate from `documentation`)

### Embedding Model Specification
1. **Model:** Use local `sentence-transformers/all-MiniLM-L6-v2` via SentenceTransformers library
2. **Execution:** All embeddings generated locally—no source code transmitted to external APIs
3. **Rationale:** Ensures zero data egress, no per-token costs, and full compliance with code confidentiality requirements

### Keyword Extraction
1. Extract technical nouns from LLD content using `collections.Counter` with term frequency analysis
2. Apply CamelCase and snake_case term splitting via regex preprocessing
3. Filter common words using domain-specific stopword list (extending standard English stopwords)
4. Limit to top 5 keywords to avoid over-retrieval
5. Fallback to pure regex extraction if frequency analysis yields insufficient terms
6. **Rationale:** Lightweight approach avoids heavy `scikit-learn` dependency (~100MB+) while achieving equivalent results for short LLD text inputs

### Retrieval Logic
1. Query vector store with extracted keywords
2. Apply strict similarity threshold (> 0.75)
3. Deduplicate results by module path
4. Limit to 10 most relevant chunks maximum
5. Sort by relevance score descending

### Context Injection
1. Format retrieved code in markdown code blocks
2. Include source file path for each snippet
3. Add clear instruction header: "Use these existing utilities. DO NOT reinvent them."
4. Inject before the main implementation prompt
5. **Token Budget Strategy:** If total retrieved content exceeds token budget, drop lowest-relevance chunks entirely (do NOT truncate mid-function). Iterate from lowest relevance upward until within budget.

## Technical Approach
- **AST Parsing:** Use `ast.parse()` to walk Python files, extract `ClassDef` and `FunctionDef` nodes with their docstrings and signatures
- **Vector Store:** Extend existing ChromaDB integration with new `codebase` collection
- **Embedding Model:** Local `sentence-transformers/all-MiniLM-L6-v2` (384-dim vectors, ~80MB model, no API calls)
- **Keyword Extraction:** `collections.Counter` with term frequency + CamelCase/snake_case regex preprocessing + domain stopword filtering. Lightweight alternative to TF-IDF that avoids heavy dependencies while performing equivalently on short text inputs.
- **Retrieval:** ChromaDB similarity search with metadata filtering for `type: code`
- **Injection Point:** Modify `N3_Coder` prompt construction in `run_implementation_workflow.py`
- **Token Management:** Count tokens per chunk, sum in relevance order, drop lowest-scoring whole chunks when budget exceeded

## Cost & Infrastructure Impact
| Item | Cost | Notes |
|------|------|-------|
| Embedding Model | $0 | Local SentenceTransformers, no API calls |
| ChromaDB Storage | ~50MB per 10k functions | Local SQLite backend |
| Index Rebuild Time | ~30s for 5k LOC | Single-threaded AST parsing |
| **Total Recurring Cost** | **$0** | Fully local execution |

## Privacy Considerations
- **Embedding Generation:** Performed entirely locally using SentenceTransformers. No source code is transmitted to any external service.
- **Data Storage:** All vectors stored in local ChromaDB instance
- **No Telemetry:** Indexing and retrieval operations do not phone home
- **No Code Egress:** Source code snippets never leave the local machine

## Security Considerations
- Only indexes local codebase files (no external sources)
- No sensitive data in code signatures (API keys should never be in function signatures)
- Read-only access to codebase during indexing
- No execution of indexed code, purely text extraction
- Embeddings generated locally—no code egress

## Files to Create/Modify
- `tools/rebuild_knowledge_base.py` — Add AST-based Python code parsing, new `codebase` collection
- `agentos/core/codebase_retrieval.py` — New module for keyword extraction (Counter-based) and retrieval logic
- `agentos/workflows/run_implementation_workflow.py` — Integrate codebase context injection into N3_Coder with token budget management
- `tests/test_codebase_retrieval.py` — Unit tests for new retrieval functionality

## Dependencies
- Issue #DN-002 (Librarian) should be completed first for vector store infrastructure
- ChromaDB must be configured and operational
- `sentence-transformers` package (Apache 2.0 License - compatible with project MIT license)

### Dependency License Compliance
| Package | License | Compatibility |
|---------|---------|---------------|
| `sentence-transformers` | Apache 2.0 | ✅ Compatible with MIT |
| `chromadb` | Apache 2.0 | ✅ Compatible with MIT |

**Note:** `scikit-learn` (BSD-3) was evaluated but rejected due to dependency weight (~100MB) for marginal keyword extraction improvement on short text inputs.

## Out of Scope (Future)
- **Cross-language support** — Only Python indexed in MVP
- **Incremental indexing** — Full rebuild each time for MVP
- **Vector Cache** — No caching layer for embeddings in MVP (mitigates rebuild cost concern since embeddings are local/free)
- **Semantic code search** — Keyword-based only, no code2vec embeddings
- **Private method indexing** — Only public APIs (no `_private` methods)
- **Usage examples retrieval** — Only signatures, not example usages

## Acceptance Criteria
- [ ] `tools/rebuild_knowledge_base.py --collection codebase` successfully indexes Python files
- [ ] Vector store contains chunks for `agentos/core/audit.py` with `GovernanceAuditLog` class
- [ ] Vector store contains chunks for `agentos/core/gemini_client.py` with `GeminiClient` class
- [ ] Keyword extraction correctly identifies "GovernanceAuditLog" from LLD text mentioning "audit logging"
- [ ] Retrieval returns `GovernanceAuditLog` definition when queried with "audit" keyword
- [ ] N3_Coder prompt includes "Reference Codebase" section when relevant utilities found
- [ ] Generated code uses `from agentos.core.audit import GovernanceAuditLog` (correct import path)
- [ ] No `ImportError` failures from hallucinated module paths in generated code
- [ ] Workflow completes gracefully when codebase collection is empty/missing
- [ ] Token budget exceeded scenario drops whole chunks (not mid-function truncation)
- [ ] No network calls made during embedding generation (verified via network monitor)

## Definition of Done

### Implementation
- [ ] AST-based code indexer implemented in `rebuild_knowledge_base.py`
- [ ] Codebase retrieval module created with Counter-based keyword extraction
- [ ] N3_Coder integration complete with context injection and token budget management
- [ ] Unit tests written and passing (>80% coverage on new code)

### Tools
- [ ] `tools/rebuild_knowledge_base.py` updated with `--collection codebase` option
- [ ] Document tool usage for codebase indexing

### Documentation
- [ ] Update wiki with codebase retrieval architecture
- [ ] Update README.md with new indexing command
- [ ] Create ADR for AST-based chunking decision
- [ ] Create ADR for local embedding model selection (SentenceTransformers)
- [ ] Create ADR for lightweight keyword extraction (Counter vs TF-IDF trade-off)
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/DN-003/implementation-report.md` created
- [ ] `docs/reports/DN-003/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes

### Manual Testing
1. Run `python tools/rebuild_knowledge_base.py --collection codebase`
2. Verify chunks exist: query ChromaDB for `type: code` documents
3. Create test LLD mentioning "audit logging"
4. Run implementation workflow
5. Inspect generated code for correct imports
6. Verify no outbound network requests during indexing (use `tcpdump` or similar)

### Forcing Error States
- **Empty collection:** Delete `codebase` collection before running workflow
- **No matches:** Use LLD with nonsense technical terms
- **Parse error:** Add malformed Python file to indexed directory
- **Token budget exceeded:** Create LLD that matches 20+ utilities, verify graceful chunk dropping

### Key Test Cases
```python
# Test AST extraction captures class with docstring
def test_ast_extracts_class_definition():
    code = '''
    class MyClass:
        """A test class."""
        def method(self, x: int) -> str: ...
    '''
    chunks = extract_code_chunks(code)
    assert len(chunks) == 1
    assert "MyClass" in chunks[0].content
    assert "A test class" in chunks[0].content

# Test keyword extraction from LLD using Counter-based frequency
def test_keyword_extraction_counter():
    lld = "Implement audit logging using GovernanceAuditLog"
    keywords = extract_keywords(lld)
    assert "GovernanceAuditLog" in keywords
    assert "audit" in keywords

# Test retrieval threshold
def test_retrieval_respects_threshold():
    results = retrieve_codebase_context(["xyznonexistent"], threshold=0.75)
    assert len(results) == 0

# Test token budget drops whole chunks
def test_token_budget_drops_whole_chunks():
    chunks = [
        {"content": "class A: ...", "relevance": 0.9, "tokens": 100},
        {"content": "class B: ...", "relevance": 0.8, "tokens": 100},
        {"content": "class C: ...", "relevance": 0.7, "tokens": 100},
    ]
    result = apply_token_budget(chunks, max_tokens=150)
    assert len(result) == 1  # Only highest relevance chunk
    assert "class A" in result[0]["content"]

# Test no network calls during embedding
def test_embeddings_are_local(mocker):
    mock_request = mocker.patch("urllib3.PoolManager.request")
    generate_embeddings(["test code"])
    mock_request.assert_not_called()
```

## Labels
`rag-pipeline`, `enhancement`, `backend`

## T-Shirt Size
**L** (Due to AST parsing complexity and integration testing)

## Original Brief
# RAG Injection: Implementation Context (The Smart Engineer)

**Context:** We have designed the "Librarian" (#DN-002) to inject architectural standards into LLDs, and "The Historian" to check for duplicate issues. Now we need to solve the **Engineering Context** problem.

## Problem

**The "Hallucinating Junior Engineer" Failure Mode:**
When the Coder Node (`N3_Coder`) implements a feature, it often:

1. **Reinvents Wheels:** Writes a new `log_to_file` function because it doesn't know `agentos.core.audit` exists.
2. **Hallucinates Imports:** Guesses `from agentos.utils import logger` (which doesn't exist) instead of the correct path.
3. **Ignores Patterns:** Uses `requests` directly instead of your `GeminiClient` wrapper, bypassing rotation and logging logic.

**Result:** The code fails "Lint/Audit" gates or requires heavy human refactoring.

## Goal

Implement a **Codebase Retrieval System** that gives the Coder Node access to the *actual* project utilities and patterns before it writes a single line of code.

1. **Index:** Expand `tools/rebuild_knowledge_base.py` to parse and chunk Python code (`.py` files).
2. **Retrieve:** Analyze the **LLD** (Low Level Design) to extract technical keywords (e.g., "Audit", "Gemini", "Config").
3. **Inject:** Fetch the actual function signatures/classes from the codebase and inject them into the Coder's system prompt.

## Proposed Architecture

### 1. Codebase Indexing (AST-Based)

Enhance `tools/rebuild_knowledge_base.py`.

* **Target:** Scan `agentos/**/*.py` and `tools/**/*.py`.
* **Strategy:** Don't just chunk by lines. Use Python's `ast` module to chunk by **Class** and **Top-Level Function**.
* **Metadata:** Tag chunks with `type: code` and `module: agentos.core.audit` (for example).

### 2. The "Tech Lead" Logic (in `run_implementation_workflow.py`)

Modify the prompt construction for `N3_Coder`.

* **Step A: Keyword Extraction**
    * *Input:* The Approved LLD content.
    * *Action:* Extract top 5 technical nouns (e.g., "GovernanceAuditLog", "GeminiClient", "SqliteSaver").

* **Step B: Retrieval**
    * *Action:* Query the Vector Store (`collection='codebase'`) for these keywords.
    * *Threshold:* High strictness (> 0.75) to avoid noise.

* **Step C: Context Injection**
    * *Action:* Append the retrieved code snippets to the prompt under a new section:
    ```markdown
    ## Reference Codebase
    Use these existing utilities. DO NOT reinvent them.

    [Source: agentos/core/audit.py]
    class GovernanceAuditLog:
        def log(self, entry: dict): ...
    ```

### 3. Integration Point

This sits inside the **N3_Coder** node of the `Implementation Workflow` (from the previous brief). It runs *before* the prompt is sent to the LLM.

## Success Criteria

* [ ] The Vector Store contains chunks for `agentos/core/audit.py` and `agentos/core/gemini_client.py`.
* [ ] When an LLD mentions "logging", the Coder context automatically receives the `GovernanceAuditLog` class definition.
* [ ] The generated implementation uses `from agentos.core.audit import GovernanceAuditLog` correctly on the first try.
* [ ] Zero `ImportError` failures caused by hallucinated module paths.