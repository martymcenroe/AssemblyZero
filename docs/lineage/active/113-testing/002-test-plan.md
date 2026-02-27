# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `VectorStore.__init__()` + `initialize()` | `VectorStore(config)` → `initialize()` | `is_initialized == True`, directory exists

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `VectorStore.is_initialized` | `VectorStore()` (no init) | `False`

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `VectorStore.initialize()` | Path points to a file | `StoreCorruptedError`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `CollectionManager.create_collection()` | `"documentation"`, `"codebase"` | Both accessible via `get_collection()`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `CollectionManager.list_collections()` | 3 collections created | List of 3 names

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `EmbeddingProvider.embed_query()` | `"hello world"` | `list[float]` of len 384

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `EmbeddingProvider.embed_texts()` | `["a", "b", "c"]` | 3 vectors of len 384

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `EmbeddingProvider.is_loaded` | Fresh `EmbeddingProvider()` | `False`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `CollectionManager` isolation | Add to docs, check codebase | Codebase empty

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `QueryEngine.add_documents()` + `query()` | Both collections via one engine | Both return correct results

### test_t110
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `VectorStore.initialize()` | chromadb mocked absent | `ImportError("chromadb")`

### test_t120
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `EmbeddingProvider.embed_texts()` | sentence-transformers mocked absent | `ImportError("sentence-transformers")`

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: All error classes | Instantiate each | All `isinstance(err, RAGError)`

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `VectorStore` close + reopen | Add data → close → reopen → query | Data still present

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `VectorStore.initialize()` | Custom `persist_directory` | Directory exists at path

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `QueryEngine.add_documents()` | 2 documents | 2 SHA-256 IDs returned

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `QueryEngine.query()` | Query matching content | Results[0] most similar

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `QueryEngine.delete_documents()` | Add 3, delete 1 | Count == 2

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `QueryEngine.query(where=...)` | Filter on metadata key | Only matching docs

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `QueryEngine.get_document()` | Known ID | Correct doc + metadata

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `TextChunker.chunk_text()` | 10 tokens, size=4, overlap=1 | 3 chunks

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `TextChunker.chunk_text(metadata=...)` | Text + metadata | All chunks have metadata

### test_t230
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `TextChunker.chunk_text("")` | Empty string | `[]`

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `TextChunker.chunk_text("short")` | Short text | 1 chunk

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `TextChunker.chunk_file()` | Real file path | Chunks with `source_file` in metadata

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `get_query_engine()` x2 | Two calls | Same `id()`

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `get_store()` x2 | Two calls | Same `id()`

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `inspect.get_annotations()` on all public methods | All classes | All have return hints

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `.__doc__` on all public methods | All classes | All non-empty

### test_t300
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `QueryEngine.add_documents()` x2 same content | Same doc twice | Count == 1

### test_t310
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `QueryEngine.query()` on empty collection | Empty collection | `total_results == 0`

### test_t320
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `CollectionManager.collection_count()` | 5 docs added | Returns 5

### test_t330
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `RAGConfig()` | Default constructor | All defaults match spec

### test_t340
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `QueryEngine.query("nonexistent", ...)` | Non-existent collection | `CollectionNotFoundError`

### test_t350
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `RAGConfig(chunk_overlap=chunk_size)` | overlap == size | `ValueError`

### test_t360
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `TextChunker.chunk_file(outside_path)` | Path outside project root | `ValueError("Path traversal")`

