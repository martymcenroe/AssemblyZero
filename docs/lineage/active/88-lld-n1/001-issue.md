# Issue #88: RAG Injection: Automated Context Retrieval ("The Librarian")

# RAG Injection: Automated Context Retrieval ("The Librarian")

## User Story
As an **LLD Designer Agent**,
I want **relevant ADRs and standards automatically retrieved and injected into my context**,
So that **I don't propose solutions that violate established architectural decisions**.

## Objective
Implement an automated RAG (Retrieval-Augmented Generation) node that queries a local vector store with the issue brief and injects the top-3 most relevant governance documents into the Designer's context.

## UX Flow

### Scenario 1: Happy Path - Relevant Documents Found
1. User runs `agentos lld create --brief "Implement distributed error logging"`
2. Librarian Node embeds the brief and queries the vector store
3. System retrieves `docs/LLDs/done/57-distributed-logging.md` (score: 0.89), `docs/standards/0002-coding-standards.md` (score: 0.82), `docs/adrs/0204-single-identity-orchestration.md` (score: 0.71)
4. Retrieved documents are silently appended to Designer context
5. Designer references these constraints in the generated LLD without user prompting
6. Result: LLD aligns with existing architecture

### Scenario 2: No Relevant Documents Found
1. User runs `agentos lld create --brief "Add support for Klingon language localization"`
2. Librarian Node queries the vector store
3. All results score below 0.7 threshold
4. System logs: `[Librarian] No relevant governance documents found (best score: 0.42)`
5. Workflow continues with only manual `--context` if provided
6. Result: Designer proceeds without RAG augmentation

### Scenario 3: Manual Context Override
1. User runs `agentos lld create --brief "..." --context docs/adrs/0199-special-case.md`
2. Librarian retrieves 3 documents automatically
3. System merges: manual context takes precedence, duplicates removed
4. Result: Final context = manual selections + RAG selections (deduplicated)

### Scenario 4: Vector Store Not Initialized
1. User runs `agentos lld create --brief "..."`
2. Librarian checks for `.agentos/vector_store/` â€” not found
3. System logs warning: `[Librarian] Vector store not found. Run 'tools/rebuild_knowledge_base.py' to enable RAG.`
4. Workflow continues without RAG augmentation
5. Result: Graceful degradation to manual-only context

### Scenario 5: Cold Boot with CLI Spinner
1. User runs `agentos lld create --brief "..."` for the first time in a session
2. Vector store/embedding model loading begins
3. CLI displays spinner: `[Librarian] Loading embedding model...`
4. If loading exceeds 500ms, spinner remains visible until complete
5. Result: User has feedback during potentially slow cold-boot operations

### Scenario 6: RAG Dependencies Not Installed
1. User runs `agentos lld create --brief "..."` without RAG optional dependencies
2. Librarian Node attempts to import `chromadb`/`sentence-transformers`
3. Import fails gracefully with friendly message: `[Librarian] RAG dependencies not installed. Run 'pip install agentos[rag]' to enable.`
4. Workflow continues without RAG augmentation
5. Result: Graceful degradation preserving lightweight installation

## Requirements

### Vector Infrastructure
1. Use ChromaDB for local, file-based vector storage (no external dependencies for default mode)
2. Store vector database in `.agentos/vector_store/`
3. Support embedding models: `all-MiniLM-L6-v2` (default/local) or OpenAI/Gemini if API key available
4. Index all markdown files in `docs/adrs/`, `docs/standards/`, and `docs/LLDs/done/`
5. Split documents by H1/H2 headers for granular retrieval

### Librarian Node
1. Accept `issue_brief` text as input
2. Query vector store for k=5 candidates, return top 3 after filtering
3. Apply similarity score threshold of 0.7 (configurable)
4. Return list of `{file_path, section, content_snippet, score}`
5. Complete retrieval in < 500ms for typical queries (after model warm-up)
6. Display CLI spinner during model/vector store loading on cold boot
7. Use conditional imports with graceful fallback when dependencies unavailable

### Workflow Integration
1. Insert Librarian Node between "Load Brief" and "Designer" nodes
2. Merge RAG results with manual `--context` (manual wins on conflicts)
3. Pass combined context to Designer node
4. Log retrieved documents at INFO level for transparency

### Ingestion Tool
1. Provide `tools/rebuild_knowledge_base.py` for manual reindexing
2. Support incremental updates (only reindex changed files)
3. Complete full reindex of ~100 files in < 10 seconds
4. Output summary: files indexed, chunks created, time elapsed

### Optional Dependencies
1. Add `chromadb` and `sentence-transformers` as **optional dependencies** via `project.optional-dependencies` under `[rag]` extra
2. Core installation remains lightweight â€” RAG features require explicit `pip install agentos[rag]`
3. Implement conditional imports in `LibrarianNode` with clear error messaging when extras not installed

### Technical Verification
1. Verify core `pyproject.toml` installation remains lightweight (no ML dependencies by default)
2. Test `[rag]` extra installation on standard CI environments (Linux/Mac/Windows)
3. Document known `chromadb` compatibility issues with `sqlite` versions and `pydantic` conflicts
4. Provide fallback instructions if dependency conflicts occur
5. Estimate and document CI duration/artifact size impact for RAG extra installation

### License Compliance
1. Verify `chromadb` (Apache 2.0) license compatibility
2. Verify `sentence-transformers` and transitive dependencies (`torch`, `huggingface-hub`, etc.) license compatibility
3. Verify `all-MiniLM-L6-v2` model license permits intended use
4. Document all license findings in ADR

## Technical Approach
- **ChromaDB:** Persistent local vector store with HNSW index for fast similarity search
- **Sentence Transformers:** `all-MiniLM-L6-v2` model (384 dimensions, ~80MB) for local embeddings
- **Document Chunking:** Split on H1/H2 headers, preserve metadata (file path, section title)
- **LangGraph Integration:** New node in `lld_workflow` graph with typed State updates
- **CLI UX:** Spinner feedback during cold-boot model loading
- **Conditional Imports:** Wrap heavy imports in try/except blocks; raise friendly error/instruction if user hasn't installed `[rag]` extra
- **Optional Dependencies:** Use `project.optional-dependencies` in `pyproject.toml` to keep core install lightweight

## Security Considerations
- Vector store contains only internal documentation (no secrets)
- **Default mode (local embeddings):** Embedding model runs locally â€” no data leaves the machine
- **External API mode:** If user configures OpenAI/Gemini embedding APIs via environment variables, document text **will be sent to external services** for embedding generation. Users must explicitly opt-in by providing API keys. This is a user choice that trades privacy for potentially higher-quality embeddings.
- `.agentos/vector_store/` should be gitignored (local cache, regenerable)
- Input sanitization will be verified during code review

## Files to Create/Modify
- `tools/rebuild_knowledge_base.py` â€” CLI tool to ingest docs into vector store
- `agentos/nodes/librarian.py` â€” RAG retrieval node implementation with conditional imports
- `agentos/workflows/lld/graph.py` â€” Wire Librarian into workflow graph
- `agentos/workflows/lld/state.py` â€” Add `retrieved_context` to State schema
- `pyproject.toml` â€” Add `chromadb`, `sentence-transformers` as **optional** dependencies under `[rag]` extra
- `.gitignore` â€” Add `.agentos/vector_store/`
- `docs/adrs/XXXX-rag-librarian.md` â€” Document architectural decision including license compliance findings

## Dependencies
- None â€” this is a standalone enhancement to the LLD workflow

## Out of Scope (Future)
- **Automatic reindexing on file change** â€” requires file watcher, deferred
- **Remote/shared vector store** â€” team sync use case, not MVP
- **Query refinement/reranking** â€” single-stage retrieval sufficient for now
- **Cross-repository RAG** â€” multi-repo context is a separate feature
- **Semantic caching** â€” cache similar queries, optimization for later
- **Lightweight alternatives (FAISS + pickle)** â€” evaluate if ChromaDB proves too heavy for optional install

## Acceptance Criteria
- [ ] `tools/rebuild_knowledge_base.py` indexes `docs/` in < 10 seconds for 100+ files
- [ ] Query "How do I log errors?" retrieves logging-related standards/LLDs
- [ ] Query "authentication flow" retrieves identity/auth ADRs
- [ ] Librarian Node completes retrieval in < 500ms (after warm-up)
- [ ] Generated LLD references retrieved ADRs in "Constraints" section without manual prompting
- [ ] Workflow gracefully degrades when vector store missing (warning, not error)
- [ ] Workflow gracefully degrades when `[rag]` extra not installed (friendly message, not error)
- [ ] Manual `--context` flag still works and takes precedence over RAG results
- [ ] Vector store persists between sessions (no re-embedding on every run)
- [ ] Core package installs without ML dependencies (`pip install agentos`)
- [ ] RAG extra installs cleanly on Linux/Mac/Windows CI environments (`pip install agentos[rag]`)
- [ ] CLI spinner displays during cold-boot model loading

## Definition of Done

### Implementation
- [ ] Core feature implemented with conditional imports
- [ ] Unit tests written and passing
- [ ] Integration test: end-to-end LLD generation with RAG
- [ ] Integration test: graceful degradation without `[rag]` extra

### Tools
- [ ] `tools/rebuild_knowledge_base.py` created with `--full` and `--incremental` modes
- [ ] Document tool usage in script header and `--help`

### Technical Verification
- [ ] Verify core `pyproject.toml` install remains lightweight (no torch/chromadb by default)
- [ ] Verify `[rag]` extra installs correctly on Linux/Mac/Windows CI
- [ ] Document any `chromadb`/`pydantic`/`sqlite` compatibility notes in README
- [ ] Document CI duration and artifact size impact for `[rag]` extra
- [ ] Confirm all transitive dependency licenses are compatible with project distribution

### Documentation
- [ ] Update LLD Workflow wiki page with Librarian Node
- [ ] Update README.md with RAG setup instructions (including data residency note for external APIs)
- [ ] Create `docs/adrs/XXXX-rag-librarian.md` (include license compliance findings)
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes

**To test RAG retrieval quality:**
```bash
# Install RAG dependencies
pip install -e ".[rag]"

# Rebuild knowledge base
python tools/rebuild_knowledge_base.py --full

# Test queries manually
python -c "
from agentos.nodes.librarian import query_knowledge_base
results = query_knowledge_base('How should I implement logging?')
for r in results:
    print(f'{r.score:.2f} | {r.file_path} | {r.section}')
"
```

**To test graceful degradation (no vector store):**
```bash
# Remove vector store
rm -rf .agentos/vector_store/

# Run LLD workflow â€” should warn but not fail
agentos lld create --brief "Test brief"
```

**To test graceful degradation (no RAG dependencies):**
```bash
# Fresh virtual environment without RAG extra
python -m venv test_env_core
source test_env_core/bin/activate
pip install -e .  # Core only, no [rag]

# Run LLD workflow â€” should show friendly message and continue
agentos lld create --brief "Test brief"
# Expected: "[Librarian] RAG dependencies not installed. Run 'pip install agentos[rag]' to enable."
```

**To test manual override precedence:**
```bash
# Provide conflicting manual context
agentos lld create \
  --brief "Implement logging" \
  --context docs/adrs/0001-unrelated.md

# Verify manual context appears first in Designer input
```

**To test dependency compatibility:**
```bash
# Fresh virtual environment test with RAG extra
python -m venv test_env_rag
source test_env_rag/bin/activate
pip install -e ".[rag]"
python -c "import chromadb; import sentence_transformers; print('OK')"
```

**To verify lightweight core install:**
```bash
# Fresh virtual environment â€” core only
python -m venv test_env_light
source test_env_light/bin/activate
pip install -e .
python -c "import agentos; print('Core OK')"
# Verify torch/chromadb NOT installed
pip list | grep -E "(torch|chromadb)" && echo "FAIL: Heavy deps in core" || echo "PASS: Core is lightweight"
```

## Labels
`feature:rag`, `workflow:lld`, `enhancement`, `dependencies`

## Effort Estimate
**Large (L)** â€” 5-8 story points due to integration testing complexity, dependency verification across platforms, and license compliance verification.