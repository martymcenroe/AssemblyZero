# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `split_on_headers()`, `chunk_markdown_document()` | Markdown with H2 sections / fixture ADR | Correct section count and titles

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_doc_type()` | Paths from adrs/, standards/, LLDs/done/ | "adr", "standard", "lld"

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `split_on_headers()` | Plain text, no headers | 1 section, title="Untitled"

### test_t040
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `check_rag_dependencies()` | Mocked missing chromadb | `(False, "...pip install assemblyzero[rag]")`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `check_rag_dependencies()` | Mocked available imports | `(True, "RAG dependencies available")`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `VectorStoreManager.is_initialized()` | Non-existent path | `False`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `VectorStoreManager.add_chunks()` + `.query()` | Add 2 chunks, query similar | Top result matches, score > 0.5

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `VectorStoreManager.query()` | Empty collection | `[]`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `LibrarianNode.retrieve()` | 4 candidates, 2 above 0.7 | 2 results, all scores >= 0.7

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `LibrarianNode.retrieve()` | 5 above threshold, top_n=3 | 3 results

### test_t110
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `LibrarianNode.check_availability()` | Mocked deps unavailable | `(False, "deps_missing")`

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `LibrarianNode.check_availability()` | Deps OK, store missing | `(False, "unavailable")`

### test_t130
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `librarian_node()` | Mocked deps unavailable | `{"rag_status": "deps_missing"}`

### test_t140
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `librarian_node()` | Mocked deps OK, store missing | `{"rag_status": "unavailable"}`

### test_t150
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `librarian_node()` | Mocked retrieve returns [] | `{"rag_status": "no_results"}`

### test_t160
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `librarian_node()` | Mocked retrieve returns 2 docs | `{"rag_status": "success"}`, INFO log

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `merge_contexts()` | Overlapping RAG + manual paths | Deduplicated, manual kept

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `merge_contexts()` | 1 manual + 1 RAG | Manual at index 0

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `LibrarianNode.format_context_for_designer()` | 2 RetrievedDocuments | String with file paths, sections

### test_t200
- Type: integration
- Requirement: 
- Mock needed: False
- Description: `run_full_ingestion()` via integration | 3 fixture files | files_indexed >= 3

### test_t210
- Type: integration
- Requirement: 
- Mock needed: False
- Description: `run_incremental_ingestion()` via integration | After full, no changes | files_skipped >= 3

### test_t220
- Type: integration
- Requirement: 
- Mock needed: False
- Description: `librarian_node()` via integration | Real store + fixture data | rag_status in ("success", "no_results")

### test_t230
- Type: integration
- Requirement: 
- Mock needed: True
- Description: `librarian_node()` via integration | Mocked deps missing | rag_status = "deps_missing"

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `LocalEmbeddingProvider.embed_query()` | Single text string | 384-dim float list

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `LibrarianNode.retrieve()` performance | Warm store query | elapsed < 500ms

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: CLI spinner display | — | Deferred to manual verification or integration test

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_full_ingestion()` performance | 100 files | elapsed < 10s

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Core install check | — | Deferred to CI environment test

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `VectorStoreManager` persistence | Add, new instance, query | Previous data accessible

