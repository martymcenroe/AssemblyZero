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

### Keyword Extraction
1. Extract technical nouns from LLD content
2. Filter common words, keep domain-specific terms
3. Limit to top 5 keywords to avoid over-retrieval
4. Handle CamelCase and snake_case term splitting

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
5. Respect token budget (truncate if necessary)

## Technical Approach
- **AST Parsing:** Use `ast.parse()` to walk Python files, extract `ClassDef` and `FunctionDef` nodes with their docstrings and signatures
- **Vector Store:** Extend existing ChromaDB integration with new `codebase` collection
- **Keyword Extraction:** Simple NLP approach using regex for CamelCase/snake_case + stopword filtering
- **Retrieval:** ChromaDB similarity search with metadata filtering for `type: code`
- **Injection Point:** Modify `N3_Coder` prompt construction in `run_implementation_workflow.py`

## Security Considerations
- Only indexes local codebase files (no external sources)
- No sensitive data in code signatures (API keys should never be in function signatures)
- Read-only access to codebase during indexing
- No execution of indexed code, purely text extraction

## Files to Create/Modify
- `tools/rebuild_knowledge_base.py` — Add AST-based Python code parsing, new `codebase` collection
- `agentos/core/codebase_retrieval.py` — New module for keyword extraction and retrieval logic
- `agentos/workflows/run_implementation_workflow.py` — Integrate codebase context injection into N3_Coder
- `tests/test_codebase_retrieval.py` — Unit tests for new retrieval functionality

## Dependencies
- Issue #DN-002 (Librarian) should be completed first for vector store infrastructure
- ChromaDB must be configured and operational

## Out of Scope (Future)
- **Cross-language support** — Only Python indexed in MVP
- **Incremental indexing** — Full rebuild each time for MVP
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

## Definition of Done

### Implementation
- [ ] AST-based code indexer implemented in `rebuild_knowledge_base.py`
- [ ] Codebase retrieval module created with keyword extraction
- [ ] N3_Coder integration complete with context injection
- [ ] Unit tests written and passing (>80% coverage on new code)

### Tools
- [ ] `tools/rebuild_knowledge_base.py` updated with `--collection codebase` option
- [ ] Document tool usage for codebase indexing

### Documentation
- [ ] Update wiki with codebase retrieval architecture
- [ ] Update README.md with new indexing command
- [ ] Create ADR for AST-based chunking decision
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

### Forcing Error States
- **Empty collection:** Delete `codebase` collection before running workflow
- **No matches:** Use LLD with nonsense technical terms
- **Parse error:** Add malformed Python file to indexed directory

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

# Test keyword extraction from LLD
def test_keyword_extraction():
    lld = "Implement audit logging using GovernanceAuditLog"
    keywords = extract_keywords(lld)
    assert "GovernanceAuditLog" in keywords
    assert "audit" in keywords

# Test retrieval threshold
def test_retrieval_respects_threshold():
    results = retrieve_codebase_context(["xyznonexistent"], threshold=0.75)
    assert len(results) == 0
```