# Implementation Request: assemblyzero/rag/store.py

## Task

Write the complete contents of `assemblyzero/rag/store.py`.

Change type: Add
Description: VectorStore — ChromaDB lifecycle management

## LLD Specification

# Implementation Spec: Vector Database Infrastructure (RAG Foundation)

| Field | Value |
|-------|-------|
| Issue | #113 |
| LLD | `docs/lld/active/113-vector-database-infrastructure.md` |
| Generated | 2026-02-27 |
| Status | DRAFT |


## 1. Overview

**Objective:** Implement foundational RAG infrastructure (vector database + embedding generation) that downstream personas (The Librarian #88, Hex #92) consume for document and codebase retrieval.

**Success Criteria:**
- Vector store initializes lazily with zero startup cost
- Multiple named collections supported (documentation, codebase)
- Local-only embeddings via SentenceTransformers (zero network calls)
- Persistent storage survives process restarts
- Unified QueryEngine API for add/query/delete operations
- Text chunking utility with overlap validation and path traversal protection
- Thread-safe singleton store
- All public functions have type hints and docstrings


## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `pyproject.toml` | Modify | Add chromadb, sentence-transformers dependencies |
| 2 | `assemblyzero/rag/__init__.py` | Add | Package init, public API exports, singleton factories |
| 3 | `assemblyzero/rag/errors.py` | Add | Custom exception hierarchy for RAG layer |
| 4 | `assemblyzero/rag/config.py` | Add | RAGConfig frozen dataclass with validation |
| 5 | `assemblyzero/rag/store.py` | Add | VectorStore — ChromaDB lifecycle management |
| 6 | `assemblyzero/rag/embeddings.py` | Add | EmbeddingProvider — local SentenceTransformers wrapper |
| 7 | `assemblyzero/rag/collections.py` | Add | CollectionManager — CRUD for named collections |
| 8 | `assemblyzero/rag/chunking.py` | Add | TextChunker — document splitting for embedding |
| 9 | `assemblyzero/rag/query.py` | Add | QueryEngine — unified query interface |
| 10 | `tests/fixtures/rag/sample_docs.json` | Add | Sample documentation fixtures |
| 11 | `tests/fixtures/rag/sample_code.json` | Add | Sample code chunk fixtures |
| 12 | `tests/unit/test_rag/__init__.py` | Add | Test package init |
| 13 | `tests/unit/test_rag/test_errors.py` | Add | Tests for error hierarchy |
| 14 | `tests/unit/test_rag/test_config.py` | Add | Tests for RAGConfig validation |
| 15 | `tests/unit/test_rag/test_store.py` | Add | Tests for VectorStore lifecycle |
| 16 | `tests/unit/test_rag/test_embeddings.py` | Add | Tests for EmbeddingProvider |
| 17 | `tests/unit/test_rag/test_collections.py` | Add | Tests for CollectionManager |
| 18 | `tests/unit/test_rag/test_chunking.py` | Add | Tests for TextChunker |
| 19 | `tests/unit/test_rag/test_query.py` | Add | Tests for QueryEngine |

**Implementation Order Rationale:** Dependencies flow bottom-up: errors → config → store → embeddings → collections → chunking → query → __init__. Tests depend on all source modules. `pyproject.toml` must be modified first to install dependencies.


## 3. Current State (for Modify/Delete files)

### 3.1 `pyproject.toml`

**Relevant excerpt** (lines 1–60):

```toml
[project]
name = "assemblyzero-tools"
version = "0.1.0"
description = "AssemblyZero configuration and tooling"
authors = [{name = "Marty McEnroe"}]
readme = "README.md"
license = "PolyForm-Noncommercial-1.0.0"
requires-python = "^3.10"
dependencies = [
    "keyring (>=25.7.0,<26.0.0)",
    "anthropic (>=0.78.0,<0.79.0)",
    "langgraph (>=1.0.7,<2.0.0)",
    "langgraph-checkpoint-sqlite (>=3.0.3,<4.0.0)",
    "langchain (>=1.2.8,<2.0.0)",
    "langchain-google-genai (>=4.2.0,<5.0.0)",
    "langchain-anthropic (>=1.3.1,<2.0.0)",
    "watchdog (>=6.0.0,<7.0.0)",
    "google-genai (>=1.60.0,<2.0.0)",
    "pygithub (>=2.8.1,<3.0.0)",
    "tiktoken (>=0.9.0,<1.0.0)",
    "langchain-core (>=1.2.9,<2.0.0)",
    "cryptography (>=46.0.4,<47.0.0)",
    "tenacity (>=9.1.3,<10.0.0)",
    "packaging (>=26.0,<27.0)",
    "pathspec (>=1.0.4,<2.0.0)",
    "aiosqlite (>=0.22.1,<0.23.0)",
    "jiter (>=0.13.0,<0.14.0)",
    "orjson (>=3.11.7,<4.0.0)",
    "langsmith (>=0.6.9,<0.7.0)",
    "google-auth (>=2.48.0,<3.0.0)",
    "pycparser (>=3.0,<4.0)",
    "boto3 (>=1.35.0,<2.0.0)"
]

[tool.pytest.ini_options]
addopts = "-m 'not integration and not e2e'"
markers = [
    "integration: tests that call real external services (deselect with '-m \"not integration\"')",
    "e2e: end-to-end workflow tests requiring sandbox repo",
    "expensive: tests that use significant API quota",
]

[tool.poetry]
packages = [{include = "assemblyzero"}]

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"

[dependency-groups]
dev = [
    "pytest (>=9.0.2,<10.0.0)",
    "mypy (>=1.0.0,<2.0.0)",
    "pytest-cov (>=7.0.0,<8.0.0)"
]

[tool.coverage.run]
source = ["assemblyzero"]

[tool.coverage.report]
show_missing = true
```

**What changes:** Add `chromadb` and `sentence-transformers` to the `dependencies` list, after the existing `boto3` entry.


## 4. Data Structures

### 4.1 RAGConfig

**Definition:**

```python
@dataclass(frozen=True)
class RAGConfig:
    persist_directory: Path = field(default_factory=lambda: Path(".assemblyzero/vector_store"))
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunk_size: int = 512
    chunk_overlap: int = 50
    default_n_results: int = 5
    distance_metric: str = "cosine"
```

**Concrete Example:**

```json
{
    "persist_directory": ".assemblyzero/vector_store",
    "embedding_model_name": "all-MiniLM-L6-v2",
    "embedding_dimension": 384,
    "chunk_size": 512,
    "chunk_overlap": 50,
    "default_n_results": 5,
    "distance_metric": "cosine"
}
```

### 4.2 TextChunk

**Definition:**

```python
@dataclass(frozen=True)
class TextChunk:
    text: str
    metadata: dict
    chunk_index: int
```

**Concrete Example:**

```json
{
    "text": "The VectorStore class manages ChromaDB lifecycle and provides persistence across process restarts.",
    "metadata": {
        "source_file": "docs/api-reference.md",
        "start_line": 10,
        "end_line": 25
    },
    "chunk_index": 0
}
```

### 4.3 QueryResult

**Definition:**

```python
@dataclass(frozen=True)
class QueryResult:
    document: str
    metadata: dict
    distance: float
    collection_name: str
    chunk_id: str
```

**Concrete Example:**

```json
{
    "document": "The VectorStore class manages ChromaDB lifecycle and provides persistence across process restarts.",
    "metadata": {
        "source_file": "docs/api-reference.md",
        "section": "VectorStore"
    },
    "distance": 0.1234,
    "collection_name": "documentation",
    "chunk_id": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
}
```

### 4.4 QueryResponse

**Definition:**

```python
@dataclass(frozen=True)
class QueryResponse:
    results: list[QueryResult]
    query_text: str
    collection_name: str
    total_results: int
```

**Concrete Example:**

```json
{
    "results": [
        {
            "document": "The VectorStore class manages ChromaDB lifecycle...",
            "metadata": {"source_file": "docs/api-reference.md"},
            "distance": 0.1234,
            "collection_name": "documentation",
            "chunk_id": "a1b2c3d4..."
        }
    ],
    "query_text": "How does the vector store work?",
    "collection_name": "documentation",
    "total_results": 1
}
```

### 4.5 Error Hierarchy

**Definition:**

```python
class RAGError(Exception): ...
class StoreNotInitializedError(RAGError): ...
class CollectionNotFoundError(RAGError): ...
class EmbeddingError(RAGError): ...
class StoreCorruptedError(RAGError): ...
```

**Concrete Example:**

```python
# Instantiation examples
err1 = RAGError("Something went wrong")
err2 = StoreNotInitializedError("Store not initialized - call initialize() first")
err3 = CollectionNotFoundError("nonexistent")  # stores collection_name attr
err4 = EmbeddingError("Model failed to encode text")
err5 = StoreCorruptedError("Store at /tmp/store is corrupted")
```

### 4.6 Test Fixture: sample_docs.json

**Concrete Example:**

```json
{
    "chunks": [
        {
            "text": "The VectorStore class manages ChromaDB lifecycle and provides persistence across process restarts. It uses a PersistentClient that writes to the .assemblyzero/vector_store/ directory.",
            "metadata": {
                "source_file": "docs/api-reference.md",
                "section": "VectorStore",
                "start_line": 10,
                "end_line": 25
            }
        },
        {
            "text": "The EmbeddingProvider generates local embeddings using SentenceTransformers with the all-MiniLM-L6-v2 model. No network calls are made.",
            "metadata": {
                "source_file": "docs/api-reference.md",
                "section": "EmbeddingProvider",
                "start_line": 30,
                "end_line": 45
            }
        },
        {
            "text": "Collections provide isolated namespaces for different document types. The documentation collection stores parsed markdown files. The codebase collection stores source code chunks.",
            "metadata": {
                "source_file": "docs/architecture.md",
                "section": "Collections",
                "start_line": 1,
                "end_line": 15
            }
        },
        {
            "text": "The QueryEngine provides a unified interface for adding, querying, and deleting documents across any collection. It automatically generates embeddings for incoming documents.",
            "metadata": {
                "source_file": "docs/api-reference.md",
                "section": "QueryEngine",
                "start_line": 50,
                "end_line": 65
            }
        },
        {
            "text": "Text chunking splits large documents into overlapping windows of configurable size. The default chunk size is 512 tokens with a 50-token overlap for context continuity.",
            "metadata": {
                "source_file": "docs/api-reference.md",
                "section": "TextChunker",
                "start_line": 70,
                "end_line": 85
            }
        }
    ]
}
```

### 4.7 Test Fixture: sample_code.json

**Concrete Example:**

```json
{
    "chunks": [
        {
            "text": "class VectorStore:\n    \"\"\"Manages ChromaDB lifecycle and persistence.\"\"\"\n\n    def __init__(self, config=None):\n        self._config = config or RAGConfig()\n        self._client = None",
            "metadata": {
                "source_file": "assemblyzero/rag/store.py",
                "language": "python",
                "start_line": 1,
                "end_line": 6
            }
        },
        {
            "text": "class EmbeddingProvider:\n    \"\"\"Local embedding generation using SentenceTransformers.\"\"\"\n\n    def __init__(self, model_name='all-MiniLM-L6-v2'):\n        self._model_name = model_name\n        self._model = None",
            "metadata": {
                "source_file": "assemblyzero/rag/embeddings.py",
                "language": "python",
                "start_line": 1,
                "end_line": 6
            }
        },
        {
            "text": "def get_query_engine(config=None):\n    \"\"\"Get or create the singleton QueryEngine.\"\"\"\n    global _query_engine\n    if _query_engine is None:\n        store = get_store(config)\n        provider = EmbeddingProvider()",
            "metadata": {
                "source_file": "assemblyzero/rag/__init__.py",
                "language": "python",
                "start_line": 20,
                "end_line": 25
            }
        },
        {
            "text": "def chunk_text(self, text, metadata=None):\n    if not text or not text.strip():\n        return []\n    tokens = text.split()\n    chunks = []\n    stride = self._chunk_size - self._chunk_overlap",
            "metadata": {
                "source_file": "assemblyzero/rag/chunking.py",
                "language": "python",
                "start_line": 30,
                "end_line": 35
            }
        },
        {
            "text": "class CollectionNotFoundError(RAGError):\n    def __init__(self, collection_name):\n        self.collection_name = collection_name\n        super().__init__(f\"Collection '{collection_name}' not found\")",
            "metadata": {
                "source_file": "assemblyzero/rag/errors.py",
                "language": "python",
                "start_line": 15,
                "end_line": 18
            }
        }
    ]
}
```


## 5. Function Specifications

### 5.1 `RAGConfig.__post_init__()`

**File:** `assemblyzero/rag/config.py`

**Signature:**

```python
def __post_init__(self) -> None:
    """Validate configuration invariants."""
```

**Input Example:**

```python
config = RAGConfig(chunk_size=100, chunk_overlap=100)
```

**Output Example:**

```python
# Raises ValueError("chunk_overlap (100) must be strictly less than chunk_size (100) to ensure forward progress in the chunking loop")
```

**Edge Cases:**
- `chunk_size=0` → `ValueError("chunk_size must be positive, got 0")`
- `chunk_overlap=-1` → `ValueError("chunk_overlap must be non-negative, got -1")`
- `chunk_overlap=0, chunk_size=512` → Valid, no error
- Default constructor `RAGConfig()` → Valid, all defaults pass validation

### 5.2 `VectorStore.__init__()`

**File:** `assemblyzero/rag/store.py`

**Signature:**

```python
def __init__(self, config: RAGConfig | None = None) -> None:
    """Initialize with optional config. Does NOT connect yet (lazy init)."""
```

**Input Example:**

```python
store = VectorStore()  # uses default RAGConfig
store = VectorStore(RAGConfig(persist_directory=Path("/tmp/test_store")))
```

**Output Example:**

```python
# store._config = RAGConfig(...)
# store._client = None
# store.is_initialized == False
```

**Edge Cases:**
- `None` config → uses `RAGConfig()` defaults

### 5.3 `VectorStore.initialize()`

**File:** `assemblyzero/rag/store.py`

**Signature:**

```python
def initialize(self) -> None:
    """Create or open the persistent ChromaDB client."""
```

**Input Example:**

```python
store = VectorStore(RAGConfig(persist_directory=Path("/tmp/test_store")))
store.initialize()
```

**Output Example:**

```python
# store.is_initialized == True
# Path("/tmp/test_store").exists() == True
# store._client is a chromadb.ClientAPI instance
```

**Edge Cases:**
- Path is a file (not directory) → `StoreCorruptedError("Store path /tmp/test_store exists but is not a directory")`
- chromadb not installed → `ImportError("chromadb is required for RAG infrastructure. Install with: pip install chromadb")`
- Already initialized → no-op (idempotent)

### 5.4 `VectorStore.is_initialized` (property)

**File:** `assemblyzero/rag/store.py`

**Signature:**

```python
@property
def is_initialized(self) -> bool:
    """Whether the store has been initialized and is ready."""
```

**Input Example:**

```python
store = VectorStore()
result_before = store.is_initialized  # False
store.initialize()
result_after = store.is_initialized   # True
```

**Output Example:**

```python
result_before = False
result_after = True
```

### 5.5 `VectorStore.get_client()`

**File:** `assemblyzero/rag/store.py`

**Signature:**

```python
def get_client(self) -> "chromadb.ClientAPI":
    """Return the underlying ChromaDB client."""
```

**Input Example:**

```python
store = VectorStore()
store.initialize()
client = store.get_client()
```

**Output Example:**

```python
# client is a chromadb.PersistentClient instance
```

**Edge Cases:**
- Not initialized → `StoreNotInitializedError("Store not initialized - call initialize() first")`

### 5.6 `VectorStore.reset()`

**File:** `assemblyzero/rag/store.py`

**Signature:**

```python
def reset(self) -> None:
    """Delete all data and reinitialize. DESTRUCTIVE."""
```

**Input Example:**

```python
store = VectorStore(RAGConfig(persist_directory=Path("/tmp/test_store")))
store.initialize()
# ... add data ...
store.reset()
```

**Output Example:**

```python
# All collections and data deleted
# store.is_initialized == True (re-initialized)
# Path("/tmp/test_store") exists but is empty
```

### 5.7 `VectorStore.close()`

**File:** `assemblyzero/rag/store.py`

**Signature:**

```python
def close(self) -> None:
    """Clean shutdown of the store."""
```

**Input Example:**

```python
store = VectorStore()
store.initialize()
store.close()
```

**Output Example:**

```python
# store._client = None
# store.is_initialized == False
```

### 5.8 `EmbeddingProvider.__init__()`

**File:** `assemblyzero/rag/embeddings.py`

**Signature:**

```python
def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
    """Initialize with model name. Model loaded lazily on first use."""
```

**Input Example:**

```python
provider = EmbeddingProvider()
provider = EmbeddingProvider(model_name="all-MiniLM-L6-v2")
```

**Output Example:**

```python
# provider._model_name = "all-MiniLM-L6-v2"
# provider._model = None
# provider.is_loaded == False
```

### 5.9 `EmbeddingProvider.embed_texts()`

**File:** `assemblyzero/rag/embeddings.py`

**Signature:**

```python
def embed_texts(self, texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
```

**Input Example:**

```python
provider = EmbeddingProvider()
vectors = provider.embed_texts(["hello world", "vector database", "chromadb"])
```

**Output Example:**

```python
# vectors = [
#     [0.0231, -0.0456, 0.0892, ...],  # 384 floats
#     [0.0112, -0.0789, 0.0345, ...],  # 384 floats
#     [0.0567, -0.0123, 0.0678, ...],  # 384 floats
# ]
# len(vectors) == 3
# len(vectors[0]) == 384
# all(isinstance(v, float) for v in vectors[0])
```

**Edge Cases:**
- sentence-transformers not installed → `ImportError("sentence-transformers is required for RAG infrastructure. Install with: pip install sentence-transformers")`
- Model failure → `EmbeddingError("Failed to encode texts: ...")`

### 5.10 `EmbeddingProvider.embed_query()`

**File:** `assemblyzero/rag/embeddings.py`

**Signature:**

```python
def embed_query(self, query: str) -> list[float]:
    """Generate embedding for a single query string."""
```

**Input Example:**

```python
provider = EmbeddingProvider()
vector = provider.embed_query("hello world")
```

**Output Example:**

```python
# vector = [0.0231, -0.0456, 0.0892, ...]  # 384 floats
# len(vector) == 384
```

### 5.11 `EmbeddingProvider.dimension` (property)

**File:** `assemblyzero/rag/embeddings.py`

**Signature:**

```python
@property
def dimension(self) -> int:
    """Return the embedding dimension for the loaded model."""
```

**Input Example:**

```python
provider = EmbeddingProvider()
dim = provider.dimension
```

**Output Example:**

```python
dim = 384
```

### 5.12 `EmbeddingProvider.is_loaded` (property)

**File:** `assemblyzero/rag/embeddings.py`

**Signature:**

```python
@property
def is_loaded(self) -> bool:
    """Whether the model has been loaded into memory."""
```

**Input Example:**

```python
provider = EmbeddingProvider()
before = provider.is_loaded  # False
provider.embed_query("trigger load")
after = provider.is_loaded   # True
```

**Output Example:**

```python
before = False
after = True
```

### 5.13 `CollectionManager.__init__()`

**File:** `assemblyzero/rag/collections.py`

**Signature:**

```python
def __init__(self, store: VectorStore) -> None:
    """Initialize with a VectorStore instance."""
```

**Input Example:**

```python
store = VectorStore()
store.initialize()
cm = CollectionManager(store)
```

**Output Example:**

```python
# cm._store = store
```

### 5.14 `CollectionManager.create_collection()`

**File:** `assemblyzero/rag/collections.py`

**Signature:**

```python
def create_collection(self, name: str, metadata: dict | None = None) -> "chromadb.Collection":
    """Create a new collection."""
```

**Input Example:**

```python
cm = CollectionManager(store)
col = cm.create_collection("documentation", metadata={"description": "Project docs"})
```

**Output Example:**

```python
# col is a chromadb.Collection instance
# col.name == "documentation"
```

**Edge Cases:**
- Already exists → `RAGError("Collection 'documentation' already exists")`

### 5.15 `CollectionManager.get_collection()`

**File:** `assemblyzero/rag/collections.py`

**Signature:**

```python
def get_collection(self, name: str) -> "chromadb.Collection":
    """Get existing collection by name."""
```

**Input Example:**

```python
col = cm.get_collection("documentation")
```

**Output Example:**

```python
# col is a chromadb.Collection instance with name "documentation"
```

**Edge Cases:**
- Not found → `CollectionNotFoundError("documentation")`

### 5.16 `CollectionManager.get_or_create_collection()`

**File:** `assemblyzero/rag/collections.py`

**Signature:**

```python
def get_or_create_collection(self, name: str, metadata: dict | None = None) -> "chromadb.Collection":
    """Get existing or create new collection."""
```

**Input Example:**

```python
col = cm.get_or_create_collection("codebase")
```

**Output Example:**

```python
# col is a chromadb.Collection instance
# col.name == "codebase"
```

### 5.17 `CollectionManager.delete_collection()`

**File:** `assemblyzero/rag/collections.py`

**Signature:**

```python
def delete_collection(self, name: str) -> None:
    """Delete a collection by name."""
```

**Input Example:**

```python
cm.delete_collection("old_collection")
```

**Output Example:**

```python
# Collection removed, cm.collection_exists("old_collection") == False
```

**Edge Cases:**
- Not found → `CollectionNotFoundError("old_collection")`

### 5.18 `CollectionManager.list_collections()`

**File:** `assemblyzero/rag/collections.py`

**Signature:**

```python
def list_collections(self) -> list[str]:
    """Return names of all existing collections."""
```

**Input Example:**

```python
# After creating "documentation", "codebase", "custom"
names = cm.list_collections()
```

**Output Example:**

```python
names = ["codebase", "custom", "documentation"]  # sorted or unsorted
```

### 5.19 `CollectionManager.collection_exists()`

**File:** `assemblyzero/rag/collections.py`

**Signature:**

```python
def collection_exists(self, name: str) -> bool:
    """Check if a collection exists."""
```

**Input Example:**

```python
exists = cm.collection_exists("documentation")
```

**Output Example:**

```python
exists = True  # if created
exists = False  # if not created
```

### 5.20 `CollectionManager.collection_count()`

**File:** `assemblyzero/rag/collections.py`

**Signature:**

```python
def collection_count(self, name: str) -> int:
    """Return number of documents in a collection."""
```

**Input Example:**

```python
count = cm.collection_count("documentation")
```

**Output Example:**

```python
count = 5  # after adding 5 documents
```

**Edge Cases:**
- Not found → `CollectionNotFoundError("documentation")`

### 5.21 `TextChunker.__init__()`

**File:** `assemblyzero/rag/chunking.py`

**Signature:**

```python
def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50) -> None:
    """Initialize with chunk size (tokens) and overlap."""
```

**Input Example:**

```python
chunker = TextChunker(chunk_size=200, chunk_overlap=50)
```

**Output Example:**

```python
# chunker._chunk_size = 200
# chunker._chunk_overlap = 50
```

**Edge Cases:**
- `chunk_overlap >= chunk_size` → `ValueError("chunk_overlap (200) must be strictly less than chunk_size (200) to ensure forward progress in the chunking loop")`
- `chunk_size <= 0` → `ValueError("chunk_size must be positive, got 0")`
- `chunk_overlap < 0` → `ValueError("chunk_overlap must be non-negative, got -1")`

### 5.22 `TextChunker.chunk_text()`

**File:** `assemblyzero/rag/chunking.py`

**Signature:**

```python
def chunk_text(self, text: str, metadata: dict | None = None) -> list[TextChunk]:
    """Split text into overlapping chunks with metadata propagation."""
```

**Input Example:**

```python
chunker = TextChunker(chunk_size=4, chunk_overlap=1)
chunks = chunker.chunk_text(
    "one two three four five six seven eight nine ten",
    metadata={"source": "test.md"}
)
```

**Output Example:**

```python
chunks = [
    TextChunk(text="one two three four", metadata={"source": "test.md"}, chunk_index=0),
    TextChunk(text="four five six seven", metadata={"source": "test.md"}, chunk_index=1),
    TextChunk(text="seven eight nine ten", metadata={"source": "test.md"}, chunk_index=2),
]
# len(chunks) == 3
```

**Edge Cases:**
- Empty string `""` → `[]`
- Short text (`"hello"` with chunk_size=512) → `[TextChunk(text="hello", metadata={}, chunk_index=0)]`
- `metadata=None` → each chunk gets `metadata={}`

### 5.23 `TextChunker.chunk_file()`

**File:** `assemblyzero/rag/chunking.py`

**Signature:**

```python
def chunk_file(
    self,
    file_path: Path,
    additional_metadata: dict | None = None,
    project_root: Path | None = None,
) -> list[TextChunk]:
    """Read file and chunk contents. Adds file path to metadata."""
```

**Input Example:**

```python
chunker = TextChunker(chunk_size=200, chunk_overlap=50)
chunks = chunker.chunk_file(
    Path("docs/api-reference.md"),
    additional_metadata={"section": "API"},
    project_root=Path("/home/user/project"),
)
```

**Output Example:**

```python
# chunks = [
#     TextChunk(
#         text="The VectorStore class manages ...",
#         metadata={"source_file": "docs/api-reference.md", "section": "API"},
#         chunk_index=0
#     ),
#     ...
# ]
```

**Edge Cases:**
- File doesn't exist → `FileNotFoundError`
- Path outside project root → `ValueError("Path traversal: /tmp/outside.txt is outside /home/user/project")`
- `project_root=None` → defaults to `Path.cwd()`

### 5.24 `QueryEngine.__init__()`

**File:** `assemblyzero/rag/query.py`

**Signature:**

```python
def __init__(
    self,
    store: VectorStore,
    embedding_provider: EmbeddingProvider,
    config: RAGConfig | None = None,
) -> None:
    """Initialize with store and embedding provider."""
```

**Input Example:**

```python
engine = QueryEngine(store, embedding_provider, config)
```

**Output Example:**

```python
# engine._store = store
# engine._embedding_provider = embedding_provider
# engine._config = config or RAGConfig()
# engine._collection_manager = CollectionManager(store)
```

### 5.25 `QueryEngine.add_documents()`

**File:** `assemblyzero/rag/query.py`

**Signature:**

```python
def add_documents(
    self,
    collection_name: str,
    documents: list[str],
    metadatas: list[dict] | None = None,
    ids: list[str] | None = None,
) -> list[str]:
    """Add documents to a collection with auto-generated embeddings."""
```

**Input Example:**

```python
ids = engine.add_documents(
    collection_name="documentation",
    documents=[
        "The VectorStore manages ChromaDB lifecycle.",
        "The EmbeddingProvider generates local embeddings."
    ],
    metadatas=[
        {"source_file": "docs/store.md"},
        {"source_file": "docs/embed.md"},
    ]
)
```

**Output Example:**

```python
ids = [
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # SHA-256 of doc 1
    "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592",  # SHA-256 of doc 2
]
```

**Edge Cases:**
- Collection doesn't exist → auto-creates via `get_or_create_collection()`
- Duplicate content → same ID, `upsert()` is idempotent, count unchanged
- `metadatas=None` → no metadata attached

### 5.26 `QueryEngine.query()`

**File:** `assemblyzero/rag/query.py`

**Signature:**

```python
def query(
    self,
    collection_name: str,
    query_text: str,
    n_results: int | None = None,
    where: dict | None = None,
) -> QueryResponse:
    """Query a collection with natural language text."""
```

**Input Example:**

```python
response = engine.query(
    collection_name="documentation",
    query_text="How does the vector store work?",
    n_results=3,
)
```

**Output Example:**

```python
response = QueryResponse(
    results=[
        QueryResult(
            document="The VectorStore manages ChromaDB lifecycle.",
            metadata={"source_file": "docs/store.md"},
            distance=0.1234,
            collection_name="documentation",
            chunk_id="e3b0c44298fc1c..."
        ),
        # ... more results
    ],
    query_text="How does the vector store work?",
    collection_name="documentation",
    total_results=3,
)
```

**Edge Cases:**
- Collection doesn't exist → `CollectionNotFoundError("documentation")`
- Empty collection → `QueryResponse(results=[], query_text=..., collection_name=..., total_results=0)`
- `n_results=None` → uses `config.default_n_results` (5)
- `where={"source_file": "docs/store.md"}` → filters results by metadata

### 5.27 `QueryEngine.delete_documents()`

**File:** `assemblyzero/rag/query.py`

**Signature:**

```python
def delete_documents(self, collection_name: str, ids: list[str]) -> None:
    """Remove documents by ID from a collection."""
```

**Input Example:**

```python
engine.delete_documents("documentation", ["e3b0c44298fc1c..."])
```

**Output Example:**

```python
# Document removed. collection_count("documentation") decremented by 1.
```

### 5.28 `QueryEngine.get_document()`

**File:** `assemblyzero/rag/query.py`

**Signature:**

```python
def get_document(self, collection_name: str, doc_id: str) -> QueryResult | None:
    """Retrieve a specific document by ID. Returns None if not found."""
```

**Input Example:**

```python
result = engine.get_document("documentation", "e3b0c44298fc1c...")
```

**Output Example:**

```python
result = QueryResult(
    document="The VectorStore manages ChromaDB lifecycle.",
    metadata={"source_file": "docs/store.md"},
    distance=0.0,
    collection_name="documentation",
    chunk_id="e3b0c44298fc1c..."
)
# Or None if ID not found
```

### 5.29 `get_store()`

**File:** `assemblyzero/rag/__init__.py`

**Signature:**

```python
def get_store(config: RAGConfig | None = None) -> VectorStore:
    """Get or create the singleton VectorStore instance."""
```

**Input Example:**

```python
store1 = get_store()
store2 = get_store()
```

**Output Example:**

```python
# id(store1) == id(store2)  # Same instance
# store1.is_initialized == True
```

### 5.30 `get_query_engine()`

**File:** `assemblyzero/rag/__init__.py`

**Signature:**

```python
def get_query_engine(config: RAGConfig | None = None) -> QueryEngine:
    """Get a fully wired QueryEngine with store + embeddings."""
```

**Input Example:**

```python
engine1 = get_query_engine()
engine2 = get_query_engine()
```

**Output Example:**

```python
# id(engine1) == id(engine2)  # Same instance
```

### 5.31 `_reset_singletons()`

**File:** `assemblyzero/rag/__init__.py`

**Signature:**

```python
def _reset_singletons() -> None:
    """Reset singleton instances. For testing only."""
```

**Input Example:**

```python
_reset_singletons()
```

**Output Example:**

```python
# _store_instance = None
# _query_engine_instance = None
```


## 6. Change Instructions

### 6.1 `pyproject.toml` (Modify)

**Change 1:** Add two dependencies after the `boto3` line (line 32):

```diff
     "pycparser (>=3.0,<4.0)",
-    "boto3 (>=1.35.0,<2.0.0)"
+    "boto3 (>=1.35.0,<2.0.0)",
+    "chromadb (>=0.5.0,<1.0.0)",
+    "sentence-transformers (>=3.0.0,<4.0.0)"
 ]
```

### 6.2 `assemblyzero/rag/__init__.py` (Add)

**Complete file contents:**

```python
"""RAG infrastructure for vector-based document retrieval.

Issue #113: Vector Database Infrastructure (RAG Foundation)

Public API:
    - get_store() — singleton VectorStore
    - get_query_engine() — singleton QueryEngine wired with store + embeddings
    - RAGConfig — configuration dataclass
    - TextChunker, TextChunk — document chunking utilities
    - QueryEngine, QueryResult, QueryResponse — query interface
    - VectorStore — store lifecycle management
    - EmbeddingProvider — local embedding generation
    - CollectionManager — collection CRUD
    - Error classes — RAGError hierarchy
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import (
    CollectionNotFoundError,
    EmbeddingError,
    RAGError,
    StoreCorruptedError,
    StoreNotInitializedError,
)
from assemblyzero.rag.chunking import TextChunk, TextChunker

if TYPE_CHECKING:
    from assemblyzero.rag.store import VectorStore
    from assemblyzero.rag.embeddings import EmbeddingProvider
    from assemblyzero.rag.collections import CollectionManager
    from assemblyzero.rag.query import QueryEngine, QueryResult, QueryResponse

__all__ = [
    "get_store",
    "get_query_engine",
    "RAGConfig",
    "TextChunker",
    "TextChunk",
    "RAGError",
    "StoreNotInitializedError",
    "CollectionNotFoundError",
    "EmbeddingError",
    "StoreCorruptedError",
]

_lock = threading.Lock()
_store_instance: VectorStore | None = None
_query_engine_instance: QueryEngine | None = None


def get_store(config: RAGConfig | None = None) -> VectorStore:
    """Get or create the singleton VectorStore instance.

    Thread-safe. Returns existing instance if already created.
    Initializes the store on first call.

    Args:
        config: Optional RAG configuration. Uses defaults if None.

    Returns:
        The singleton VectorStore instance, initialized and ready.
    """
    global _store_instance
    if _store_instance is not None:
        return _store_instance
    with _lock:
        if _store_instance is not None:
            return _store_instance
        from assemblyzero.rag.store import VectorStore as _VectorStore

        cfg = config or RAGConfig()
        store = _VectorStore(cfg)
        store.initialize()
        _store_instance = store
        return _store_instance


def get_query_engine(config: RAGConfig | None = None) -> QueryEngine:
    """Get a fully wired QueryEngine with store + embeddings.

    Convenience factory for consumers (#88, #92).
    Initializes store and creates embedding provider on first call.
    Thread-safe singleton.

    Args:
        config: Optional RAG configuration. Uses defaults if None.

    Returns:
        The singleton QueryEngine instance, ready for add/query operations.
    """
    global _query_engine_instance
    if _query_engine_instance is not None:
        return _query_engine_instance
    with _lock:
        if _query_engine_instance is not None:
            return _query_engine_instance
        from assemblyzero.rag.embeddings import EmbeddingProvider as _EmbeddingProvider
        from assemblyzero.rag.query import QueryEngine as _QueryEngine

        cfg = config or RAGConfig()
        store = get_store(cfg)
        provider = _EmbeddingProvider(cfg.embedding_model_name)
        engine = _QueryEngine(store, provider, cfg)
        _query_engine_instance = engine
        return _query_engine_instance


def _reset_singletons() -> None:
    """Reset singleton instances. For testing only.

    Not included in __all__. Tests must call this in try/finally
    to avoid polluting other test runs.
    """
    global _store_instance, _query_engine_instance
    with _lock:
        if _store_instance is not None:
            try:
                _store_instance.close()
            except Exception:
                pass
        _store_instance = None
        _query_engine_instance = None
```

### 6.3 `assemblyzero/rag/errors.py` (Add)

**Complete file contents:**

```python
"""Custom exception hierarchy for RAG infrastructure.

Issue #113: Vector Database Infrastructure (RAG Foundation)

All RAG errors inherit from RAGError. Consumers catch RAGError
for unified fallback behavior.
"""
from __future__ import annotations


class RAGError(Exception):
    """Base exception for all RAG infrastructure errors."""

    pass


class StoreNotInitializedError(RAGError):
    """Raised when operations attempted on uninitialized store."""

    pass


class CollectionNotFoundError(RAGError):
    """Raised when referencing a non-existent collection.

    Attributes:
        collection_name: The name of the collection that was not found.
    """

    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        super().__init__(f"Collection '{collection_name}' not found")


class EmbeddingError(RAGError):
    """Raised when embedding generation fails."""

    pass


class StoreCorruptedError(RAGError):
    """Raised when the persistent store is corrupted or unreadable."""

    pass
```

### 6.4 `assemblyzero/rag/config.py` (Add)

**Complete file contents:**

```python
"""RAG configuration dataclass and defaults.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RAGConfig:
    """Immutable configuration for the RAG infrastructure.

    Attributes:
        persist_directory: Path for ChromaDB persistent storage.
        embedding_model_name: SentenceTransformers model name.
        embedding_dimension: Vector dimension (must match model).
        chunk_size: Maximum tokens per chunk.
        chunk_overlap: Overlap tokens between consecutive chunks.
        default_n_results: Default number of query results.
        distance_metric: ChromaDB distance function.
    """

    persist_directory: Path = field(
        default_factory=lambda: Path(".assemblyzero/vector_store")
    )
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunk_size: int = 512
    chunk_overlap: int = 50
    default_n_results: int = 5
    distance_metric: str = "cosine"

    def __post_init__(self) -> None:
        """Validate configuration invariants.

        Raises:
            ValueError: If chunk_overlap >= chunk_size (would cause infinite
                loop in sliding window chunker) or if either value is <= 0.
        """
        if self.chunk_size <= 0:
            raise ValueError(
                f"chunk_size must be positive, got {self.chunk_size}"
            )
        if self.chunk_overlap < 0:
            raise ValueError(
                f"chunk_overlap must be non-negative, got {self.chunk_overlap}"
            )
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be strictly less "
                f"than chunk_size ({self.chunk_size}) to ensure forward "
                f"progress in the chunking loop"
            )
```

### 6.5 `assemblyzero/rag/store.py` (Add)

**Complete file contents:**

```python
"""VectorStore — ChromaDB lifecycle and persistence management.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import StoreCorruptedError, StoreNotInitializedError

if TYPE_CHECKING:
    import chromadb


class VectorStore:
    """Manages ChromaDB lifecycle and persistence.

    The store is lazy-initialized: constructing a VectorStore does not
    connect to ChromaDB. Call initialize() to create/open the persistent
    client.
    """

    def __init__(self, config: RAGConfig | None = None) -> None:
        """Initialize with optional config. Does NOT connect yet (lazy init).

        Args:
            config: RAG configuration. Uses defaults if None.
        """
        self._config = config or RAGConfig()
        self._client: chromadb.ClientAPI | None = None

    def initialize(self) -> None:
        """Create or open the persistent ChromaDB client.

        Creates persist_directory if it doesn't exist.

        Raises:
            StoreCorruptedError: If existing store path is a file (not dir).
            ImportError: If chromadb is not installed.
        """
        if self._client is not None:
            return  # Already initialized (idempotent)

        try:
            import chromadb as _chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for RAG infrastructure. "
                "Install with: pip install chromadb"
            )

        persist_path = self._config.persist_directory

        if persist_path.exists() and not persist_path.is_dir():
            raise StoreCorruptedError(
                f"Store path {persist_path} exists but is not a directory"
            )

        persist_path.mkdir(parents=True, exist_ok=True)

        try:
            self._client = _chromadb.PersistentClient(path=str(persist_path))
        except Exception as exc:
            raise StoreCorruptedError(
                f"Failed to open ChromaDB at {persist_path}: {exc}"
            ) from exc

    @property
    def is_initialized(self) -> bool:
        """Whether the store has been initialized and is ready.

        Returns:
            True if initialize() has been called and client is available.
        """
        return self._client is not None

    def get_client(self) -> chromadb.ClientAPI:
        """Return the underlying ChromaDB client.

        Raises:
            StoreNotInitializedError: If not initialized.

        Returns:
            The ChromaDB client instance.
        """
        if self._client is None:
            raise StoreNotInitializedError(
                "Store not initialized - call initialize() first"
            )
        return self._client

    def reset(self) -> None:
        """Delete all data and reinitialize. DESTRUCTIVE.

        Removes the persist directory and re-creates the store.
        """
        self.close()
        persist_path = self._config.persist_directory
        if persist_path.exists():
            shutil.rmtree(persist_path)
        self.initialize()

    def close(self) -> None:
        """Clean shutdown of the store.

        Sets client to None. Store can be re-initialized after close.
        """
        self._client = None
```

### 6.6 `assemblyzero/rag/embeddings.py` (Add)

**Complete file contents:**

```python
"""EmbeddingProvider — local embedding generation using SentenceTransformers.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from assemblyzero.rag.errors import EmbeddingError

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class EmbeddingProvider:
    """Local embedding generation using SentenceTransformers.

    The model is loaded lazily on first use to avoid startup cost.
    Uses all-MiniLM-L6-v2 by default (384 dimensions, ~80MB).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize with model name. Model loaded lazily on first use.

        Args:
            model_name: SentenceTransformers model identifier.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    def _load_model(self) -> None:
        """Load the SentenceTransformer model into memory.

        Raises:
            ImportError: If sentence-transformers is not installed.
            EmbeddingError: If model loading fails.
        """
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer as _ST
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for RAG infrastructure. "
                "Install with: pip install sentence-transformers"
            )

        try:
            self._model = _ST(self._model_name)
            # Determine dimension from a test encoding
            test_embedding = self._model.encode(["test"], convert_to_numpy=True)
            self._dimension = int(test_embedding.shape[1])
        except Exception as exc:
            self._model = None
            self._dimension = None
            raise EmbeddingError(
                f"Failed to load model '{self._model_name}': {exc}"
            ) from exc

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of float vectors, one per input text.

        Raises:
            ImportError: If sentence-transformers is not installed.
            EmbeddingError: On model failure.
        """
        self._load_model()
        assert self._model is not None  # guaranteed by _load_model

        try:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return [vec.tolist() for vec in embeddings]
        except Exception as exc:
            raise EmbeddingError(
                f"Failed to encode texts: {exc}"
            ) from exc

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query string.

        Convenience wrapper around embed_texts.

        Args:
            query: Query text to embed.

        Returns:
            Float vector for the query.
        """
        results = self.embed_texts([query])
        return results[0]

    @property
    def dimension(self) -> int:
        """Return the embedding dimension for the loaded model.

        Loads the model if not already loaded.

        Returns:
            Integer dimension of embedding vectors.
        """
        if self._dimension is None:
            self._load_model()
        assert self._dimension is not None
        return self._dimension

    @property
    def is_loaded(self) -> bool:
        """Whether the model has been loaded into memory.

        Returns:
            True if model is loaded and ready for encoding.
        """
        return self._model is not None
```

### 6.7 `assemblyzero/rag/collections.py` (Add)

**Complete file contents:**

```python
"""CollectionManager — CRUD for named vector collections.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from assemblyzero.rag.errors import CollectionNotFoundError, RAGError

if TYPE_CHECKING:
    import chromadb
    from assemblyzero.rag.store import VectorStore

# Well-known collection names
COLLECTION_DOCUMENTATION: str = "documentation"
COLLECTION_CODEBASE: str = "codebase"

KNOWN_COLLECTIONS: frozenset[str] = frozenset({
    COLLECTION_DOCUMENTATION,
    COLLECTION_CODEBASE,
})


class CollectionManager:
    """CRUD operations for named vector collections.

    Wraps ChromaDB collection operations with error handling
    and the project's exception hierarchy.
    """

    def __init__(self, store: VectorStore) -> None:
        """Initialize with a VectorStore instance.

        Args:
            store: An initialized VectorStore.
        """
        self._store = store

    def create_collection(
        self,
        name: str,
        metadata: dict | None = None,
    ) -> chromadb.Collection:
        """Create a new collection.

        Args:
            name: Collection name.
            metadata: Optional collection-level metadata.

        Returns:
            The created ChromaDB Collection.

        Raises:
            RAGError: If collection already exists.
        """
        client = self._store.get_client()
        if self.collection_exists(name):
            raise RAGError(f"Collection '{name}' already exists")
        meta = metadata or {}
        return client.create_collection(name=name, metadata=meta)

    def get_collection(self, name: str) -> chromadb.Collection:
        """Get existing collection by name.

        Args:
            name: Collection name to retrieve.

        Returns:
            The ChromaDB Collection.

        Raises:
            CollectionNotFoundError: If collection does not exist.
        """
        client = self._store.get_client()
        try:
            return client.get_collection(name=name)
        except Exception:
            raise CollectionNotFoundError(name)

    def get_or_create_collection(
        self,
        name: str,
        metadata: dict | None = None,
    ) -> chromadb.Collection:
        """Get existing or create new collection.

        Args:
            name: Collection name.
            metadata: Optional collection-level metadata.

        Returns:
            The ChromaDB Collection (existing or newly created).
        """
        client = self._store.get_client()
        meta = metadata or {}
        return client.get_or_create_collection(name=name, metadata=meta)

    def delete_collection(self, name: str) -> None:
        """Delete a collection by name.

        Args:
            name: Collection name to delete.

        Raises:
            CollectionNotFoundError: If collection does not exist.
        """
        client = self._store.get_client()
        if not self.collection_exists(name):
            raise CollectionNotFoundError(name)
        client.delete_collection(name=name)

    def list_collections(self) -> list[str]:
        """Return names of all existing collections.

        Returns:
            List of collection name strings.
        """
        client = self._store.get_client()
        collections = client.list_collections()
        # ChromaDB may return strings or Collection objects depending on version
        names: list[str] = []
        for col in collections:
            if isinstance(col, str):
                names.append(col)
            else:
                names.append(col.name)
        return names

    def collection_exists(self, name: str) -> bool:
        """Check if a collection exists.

        Args:
            name: Collection name to check.

        Returns:
            True if collection exists, False otherwise.
        """
        return name in self.list_collections()

    def collection_count(self, name: str) -> int:
        """Return number of documents in a collection.

        Args:
            name: Collection name.

        Returns:
            Integer count of documents in the collection.

        Raises:
            CollectionNotFoundError: If collection does not exist.
        """
        col = self.get_collection(name)
        return col.count()
```

### 6.8 `assemblyzero/rag/chunking.py` (Add)

**Complete file contents:**

```python
"""TextChunker — document splitting for embedding.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TextChunk:
    """A chunk of text with provenance metadata.

    Attributes:
        text: The chunk text content.
        metadata: Source metadata (source_file, line range, etc.).
        chunk_index: Position within the source document (0-based).
    """

    text: str
    metadata: dict
    chunk_index: int


class TextChunker:
    """Split documents into chunks suitable for embedding.

    Uses a simple sliding window approach with configurable
    chunk size (in whitespace-delimited tokens) and overlap.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> None:
        """Initialize with chunk size (tokens) and overlap.

        Args:
            chunk_size: Maximum number of tokens per chunk.
            chunk_overlap: Number of overlapping tokens between chunks.

        Raises:
            ValueError: If chunk_overlap >= chunk_size or if either
                value is non-positive (chunk_size) or negative (chunk_overlap).
        """
        if chunk_size <= 0:
            raise ValueError(
                f"chunk_size must be positive, got {chunk_size}"
            )
        if chunk_overlap < 0:
            raise ValueError(
                f"chunk_overlap must be non-negative, got {chunk_overlap}"
            )
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be strictly less "
                f"than chunk_size ({chunk_size}) to ensure forward "
                f"progress in the chunking loop"
            )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def chunk_text(
        self,
        text: str,
        metadata: dict | None = None,
    ) -> list[TextChunk]:
        """Split text into overlapping chunks with metadata propagation.

        Tokenization is whitespace-based (not model-specific).
        Empty text returns empty list.

        Args:
            text: The text to split.
            metadata: Optional metadata to propagate to all chunks.

        Returns:
            List of TextChunk objects. Empty list for empty/whitespace text.
        """
        if not text or not text.strip():
            return []

        meta = metadata if metadata is not None else {}
        tokens = text.split()

        if len(tokens) <= self._chunk_size:
            return [TextChunk(text=text.strip(), metadata=dict(meta), chunk_index=0)]

        chunks: list[TextChunk] = []
        stride = self._chunk_size - self._chunk_overlap
        idx = 0
        chunk_index = 0

        while idx < len(tokens):
            end = min(idx + self._chunk_size, len(tokens))
            chunk_tokens = tokens[idx:end]
            chunk_text = " ".join(chunk_tokens)
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    metadata=dict(meta),
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1
            idx += stride
            # If next window would start past end, stop
            if idx >= len(tokens):
                break

        return chunks

    def chunk_file(
        self,
        file_path: Path,
        additional_metadata: dict | None = None,
        project_root: Path | None = None,
    ) -> list[TextChunk]:
        """Read file and chunk contents. Adds file path to metadata.

        Validates that file_path exists and resolves to a location
        within project_root (defaults to current working directory).

        Args:
            file_path: Path to the file to chunk.
            additional_metadata: Extra metadata to include in each chunk.
            project_root: Root directory for path traversal validation.
                Defaults to Path.cwd() if None.

        Returns:
            List of TextChunk objects with source_file in metadata.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If resolved file_path is outside project_root
                (path traversal protection).
        """
        root = (project_root or Path.cwd()).resolve()
        resolved_path = file_path.resolve()

        # Path traversal check
        try:
            resolved_path.relative_to(root)
        except ValueError:
            raise ValueError(
                f"Path traversal: {resolved_path} is outside {root}"
            )

        if not resolved_path.exists():
            raise FileNotFoundError(f"File not found: {resolved_path}")

        if not resolved_path.is_file():
            raise FileNotFoundError(f"Not a file: {resolved_path}")

        content = resolved_path.read_text(encoding="utf-8")

        meta = additional_metadata.copy() if additional_metadata else {}
        # Store relative path from project root for portability
        try:
            meta["source_file"] = str(resolved_path.relative_to(root))
        except ValueError:
            meta["source_file"] = str(resolved_path)

        return self.chunk_text(content, metadata=meta)
```

### 6.9 `assemblyzero/rag/query.py` (Add)

**Complete file contents:**

```python
"""QueryEngine — unified query interface across collections.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from assemblyzero.rag.collections import CollectionManager
from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import CollectionNotFoundError

if TYPE_CHECKING:
    from assemblyzero.rag.embeddings import EmbeddingProvider
    from assemblyzero.rag.store import VectorStore


@dataclass(frozen=True)
class QueryResult:
    """Single result from a vector similarity search.

    Attributes:
        document: The retrieved text chunk.
        metadata: Associated metadata (source file, line range, etc.).
        distance: Distance score (lower = more similar for cosine).
        collection_name: Which collection this came from.
        chunk_id: Unique ID of the chunk.
    """

    document: str
    metadata: dict
    distance: float
    collection_name: str
    chunk_id: str


@dataclass(frozen=True)
class QueryResponse:
    """Aggregated response from a query operation.

    Attributes:
        results: Ranked list of QueryResult objects.
        query_text: The original query text.
        collection_name: The queried collection.
        total_results: Number of results returned.
    """

    results: list[QueryResult]
    query_text: str
    collection_name: str
    total_results: int


def _generate_id(content: str) -> str:
    """Generate a deterministic SHA-256 ID from content.

    Args:
        content: Text content to hash.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class QueryEngine:
    """Unified query interface across collections.

    Provides add, query, delete, and get operations with
    automatic embedding generation.
    """

    def __init__(
        self,
        store: VectorStore,
        embedding_provider: EmbeddingProvider,
        config: RAGConfig | None = None,
    ) -> None:
        """Initialize with store and embedding provider.

        Args:
            store: An initialized VectorStore.
            embedding_provider: Provider for generating embeddings.
            config: Optional RAG configuration. Uses defaults if None.
        """
        self._store = store
        self._embedding_provider = embedding_provider
        self._config = config or RAGConfig()
        self._collection_manager = CollectionManager(store)

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """Add documents to a collection with auto-generated embeddings.

        Uses upsert for idempotency — adding the same content twice
        produces the same ID and does not create duplicates.

        Args:
            collection_name: Target collection name (auto-created if missing).
            documents: List of document text strings.
            metadatas: Optional list of metadata dicts (one per document).
            ids: Optional list of document IDs. Auto-generated (SHA-256) if None.

        Returns:
            List of document IDs.
        """
        collection = self._collection_manager.get_or_create_collection(
            collection_name
        )

        doc_ids = ids or [_generate_id(doc) for doc in documents]
        embeddings = self._embedding_provider.embed_texts(documents)

        metas = metadatas or [{} for _ in documents]

        collection.upsert(
            ids=doc_ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metas,
        )

        return doc_ids

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int | None = None,
        where: dict | None = None,
    ) -> QueryResponse:
        """Query a collection with natural language text.

        Args:
            collection_name: Collection to query.
            query_text: Natural language query text.
            n_results: Number of results to return. Defaults to config value.
            where: Optional metadata filter dict.

        Returns:
            QueryResponse with ranked results.

        Raises:
            CollectionNotFoundError: If collection doesn't exist.
        """
        if not self._collection_manager.collection_exists(collection_name):
            raise CollectionNotFoundError(collection_name)

        collection = self._collection_manager.get_collection(collection_name)
        n = n_results or self._config.default_n_results

        # Check if collection is empty
        if collection.count() == 0:
            return QueryResponse(
                results=[],
                query_text=query_text,
                collection_name=collection_name,
                total_results=0,
            )

        # Clamp n_results to collection size to avoid ChromaDB errors
        actual_n = min(n, collection.count())

        query_embedding = self._embedding_provider.embed_query(query_text)

        query_kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": actual_n,
            "include": ["documents", "metadatas", "distances"],
        }
        if where is not None:
            query_kwargs["where"] = where

        raw = collection.query(**query_kwargs)

        results: list[QueryResult] = []
        # ChromaDB returns batched results (list of lists)
        if raw["ids"] and raw["ids"][0]:
            for i, doc_id in enumerate(raw["ids"][0]):
                doc = raw["documents"][0][i] if raw["documents"] else ""
                meta = raw["metadatas"][0][i] if raw["metadatas"] else {}
                dist = raw["distances"][0][i] if raw["distances"] else 0.0
                results.append(
                    QueryResult(
                        document=doc,
                        metadata=meta or {},
                        distance=dist,
                        collection_name=collection_name,
                        chunk_id=doc_id,
                    )
                )

        return QueryResponse(
            results=results,
            query_text=query_text,
            collection_name=collection_name,
            total_results=len(results),
        )

    def delete_documents(
        self,
        collection_name: str,
        ids: list[str],
    ) -> None:
        """Remove documents by ID from a collection.

        Args:
            collection_name: Collection to delete from.
            ids: List of document IDs to remove.

        Raises:
            CollectionNotFoundError: If collection doesn't exist.
        """
        collection = self._collection_manager.get_collection(collection_name)
        collection.delete(ids=ids)

    def get_document(
        self,
        collection_name: str,
        doc_id: str,
    ) -> QueryResult | None:
        """Retrieve a specific document by ID.

        Args:
            collection_name: Collection to search.
            doc_id: Document ID to retrieve.

        Returns:
            QueryResult if found, None otherwise.
        """
        collection = self._collection_manager.get_collection(collection_name)
        raw = collection.get(
            ids=[doc_id],
            include=["documents", "metadatas"],
        )

        if not raw["ids"]:
            return None

        doc = raw["documents"][0] if raw["documents"] else ""
        meta = raw["metadatas"][0] if raw["metadatas"] else {}

        return QueryResult(
            document=doc,
            metadata=meta or {},
            distance=0.0,
            collection_name=collection_name,
            chunk_id=doc_id,
        )
```

### 6.10 `tests/fixtures/rag/sample_docs.json` (Add)

**Complete file contents:** (see Section 4.6 for the full JSON)

```json
{
    "chunks": [
        {
            "text": "The VectorStore class manages ChromaDB lifecycle and provides persistence across process restarts. It uses a PersistentClient that writes to the .assemblyzero/vector_store/ directory.",
            "metadata": {
                "source_file": "docs/api-reference.md",
                "section": "VectorStore",
                "start_line": 10,
                "end_line": 25
            }
        },
        {
            "text": "The EmbeddingProvider generates local embeddings using SentenceTransformers with the all-MiniLM-L6-v2 model. No network calls are made.",
            "metadata": {
                "source_file": "docs/api-reference.md",
                "section": "EmbeddingProvider",
                "start_line": 30,
                "end_line": 45
            }
        },
        {
            "text": "Collections provide isolated namespaces for different document types. The documentation collection stores parsed markdown files. The codebase collection stores source code chunks.",
            "metadata": {
                "source_file": "docs/architecture.md",
                "section": "Collections",
                "start_line": 1,
                "end_line": 15
            }
        },
        {
            "text": "The QueryEngine provides a unified interface for adding, querying, and deleting documents across any collection. It automatically generates embeddings for incoming documents.",
            "metadata": {
                "source_file": "docs/api-reference.md",
                "section": "QueryEngine",
                "start_line": 50,
                "end_line": 65
            }
        },
        {
            "text": "Text chunking splits large documents into overlapping windows of configurable size. The default chunk size is 512 tokens with a 50-token overlap for context continuity.",
            "metadata": {
                "source_file": "docs/api-reference.md",
                "section": "TextChunker",
                "start_line": 70,
                "end_line": 85
            }
        }
    ]
}
```

### 6.11 `tests/fixtures/rag/sample_code.json` (Add)

**Complete file contents:** (see Section 4.7 for the full JSON)

```json
{
    "chunks": [
        {
            "text": "class VectorStore:\n    \"\"\"Manages ChromaDB lifecycle and persistence.\"\"\"\n\n    def __init__(self, config=None):\n        self._config = config or RAGConfig()\n        self._client = None",
            "metadata": {
                "source_file": "assemblyzero/rag/store.py",
                "language": "python",
                "start_line": 1,
                "end_line": 6
            }
        },
        {
            "text": "class EmbeddingProvider:\n    \"\"\"Local embedding generation using SentenceTransformers.\"\"\"\n\n    def __init__(self, model_name='all-MiniLM-L6-v2'):\n        self._model_name = model_name\n        self._model = None",
            "metadata": {
                "source_file": "assemblyzero/rag/embeddings.py",
                "language": "python",
                "start_line": 1,
                "end_line": 6
            }
        },
        {
            "text": "def get_query_engine(config=None):\n    \"\"\"Get or create the singleton QueryEngine.\"\"\"\n    global _query_engine\n    if _query_engine is None:\n        store = get_store(config)\n        provider = EmbeddingProvider()",
            "metadata": {
                "source_file": "assemblyzero/rag/__init__.py",
                "language": "python",
                "start_line": 20,
                "end_line": 25
            }
        },
        {
            "text": "def chunk_text(self, text, metadata=None):\n    if not text or not text.strip():\n        return []\n    tokens = text.split()\n    chunks = []\n    stride = self._chunk_size - self._chunk_overlap",
            "metadata": {
                "source_file": "assemblyzero/rag/chunking.py",
                "language": "python",
                "start_line": 30,
                "end_line": 35
            }
        },
        {
            "text": "class CollectionNotFoundError(RAGError):\n    def __init__(self, collection_name):\n        self.collection_name = collection_name\n        super().__init__(f\"Collection '{collection_name}' not found\")",
            "metadata": {
                "source_file": "assemblyzero/rag/errors.py",
                "language": "python",
                "start_line": 15,
                "end_line": 18
            }
        }
    ]
}
```

### 6.12 `tests/unit/test_rag/__init__.py` (Add)

**Complete file contents:**

```python
"""Unit tests for the RAG infrastructure package."""
```

### 6.13 `tests/unit/test_rag/test_errors.py` (Add)

**Complete file contents:**

```python
"""Tests for RAG error hierarchy (T130).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from assemblyzero.rag.errors import (
    CollectionNotFoundError,
    EmbeddingError,
    RAGError,
    StoreCorruptedError,
    StoreNotInitializedError,
)


class TestErrorHierarchy:
    """T130: All error classes inherit from RAGError."""

    def test_rag_error_is_base(self) -> None:
        err = RAGError("test")
        assert isinstance(err, Exception)
        assert isinstance(err, RAGError)
        assert str(err) == "test"

    def test_store_not_initialized_inherits(self) -> None:
        err = StoreNotInitializedError("not init")
        assert isinstance(err, RAGError)
        assert isinstance(err, Exception)

    def test_collection_not_found_inherits(self) -> None:
        err = CollectionNotFoundError("my_collection")
        assert isinstance(err, RAGError)
        assert err.collection_name == "my_collection"
        assert "my_collection" in str(err)

    def test_embedding_error_inherits(self) -> None:
        err = EmbeddingError("embed fail")
        assert isinstance(err, RAGError)

    def test_store_corrupted_inherits(self) -> None:
        err = StoreCorruptedError("corrupted")
        assert isinstance(err, RAGError)

    def test_all_catchable_as_rag_error(self) -> None:
        """Consumers can catch RAGError for unified fallback."""
        errors = [
            RAGError("base"),
            StoreNotInitializedError("not init"),
            CollectionNotFoundError("col"),
            EmbeddingError("embed"),
            StoreCorruptedError("corrupt"),
        ]
        for err in errors:
            assert isinstance(err, RAGError)
```

### 6.14 `tests/unit/test_rag/test_config.py` (Add)

**Complete file contents:**

```python
"""Tests for RAGConfig validation (T330, T350).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.rag.config import RAGConfig


class TestConfigDefaults:
    """T330: Config defaults match specification."""

    def test_default_persist_directory(self) -> None:
        config = RAGConfig()
        assert config.persist_directory == Path(".assemblyzero/vector_store")

    def test_default_embedding_model(self) -> None:
        config = RAGConfig()
        assert config.embedding_model_name == "all-MiniLM-L6-v2"

    def test_default_embedding_dimension(self) -> None:
        config = RAGConfig()
        assert config.embedding_dimension == 384

    def test_default_chunk_size(self) -> None:
        config = RAGConfig()
        assert config.chunk_size == 512

    def test_default_chunk_overlap(self) -> None:
        config = RAGConfig()
        assert config.chunk_overlap == 50

    def test_default_n_results(self) -> None:
        config = RAGConfig()
        assert config.default_n_results == 5

    def test_default_distance_metric(self) -> None:
        config = RAGConfig()
        assert config.distance_metric == "cosine"

    def test_config_is_frozen(self) -> None:
        config = RAGConfig()
        with pytest.raises(AttributeError):
            config.chunk_size = 1024  # type: ignore[misc]


class TestConfigValidation:
    """T350: Config rejects invalid overlap settings."""

    def test_overlap_equal_to_size_raises(self) -> None:
        """chunk_overlap == chunk_size should raise ValueError.

        Input: RAGConfig(chunk_size=100, chunk_overlap=100)
        Expected: ValueError with message containing 'chunk_overlap (100) must be strictly less than chunk_size (100)'
        """
        with pytest.raises(ValueError, match="chunk_overlap.*100.*must be strictly less.*chunk_size.*100"):
            RAGConfig(chunk_size=100, chunk_overlap=100)

    def test_overlap_greater_than_size_raises(self) -> None:
        """chunk_overlap > chunk_size should raise ValueError.

        Input: RAGConfig(chunk_size=100, chunk_overlap=150)
        Expected: ValueError with message containing 'chunk_overlap (150) must be strictly less than chunk_size (100)'
        """
        with pytest.raises(ValueError, match="chunk_overlap.*150.*must be strictly less.*chunk_size.*100"):
            RAGConfig(chunk_size=100, chunk_overlap=150)

    def test_zero_overlap_is_valid(self) -> None:
        config = RAGConfig(chunk_overlap=0)
        assert config.chunk_overlap == 0

    def test_zero_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            RAGConfig(chunk_size=0)

    def test_negative_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            RAGConfig(chunk_size=-10)

    def test_negative_overlap_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
            RAGConfig(chunk_overlap=-1)

    def test_custom_persist_directory(self) -> None:
        config = RAGConfig(persist_directory=Path("/tmp/custom_store"))
        assert config.persist_directory == Path("/tmp/custom_store")
```

### 6.15 `tests/unit/test_rag/test_store.py` (Add)

**Complete file contents:**

```python
"""Tests for VectorStore lifecycle (T010, T020, T030, T140, T150, T110).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import StoreCorruptedError, StoreNotInitializedError
from assemblyzero.rag.store import VectorStore


@pytest.fixture
def store_config(tmp_path: Path) -> RAGConfig:
    """Create a RAGConfig with a temporary persist directory."""
    return RAGConfig(persist_directory=tmp_path / "vector_store")


@pytest.fixture
def store(store_config: RAGConfig) -> VectorStore:
    """Create an uninitialized VectorStore."""
    return VectorStore(store_config)


class TestStoreInit:
    """T010: Store initializes with default config."""

    def test_initialize_creates_directory(
        self, store: VectorStore, store_config: RAGConfig
    ) -> None:
        store.initialize()
        assert store.is_initialized is True
        assert store_config.persist_directory.exists()
        assert store_config.persist_directory.is_dir()

    def test_initialize_is_idempotent(self, store: VectorStore) -> None:
        store.initialize()
        client1 = store.get_client()
        store.initialize()  # Second call — no-op
        client2 = store.get_client()
        assert client1 is client2


class TestStoreNotInitialized:
    """T020: Store reports not-initialized before init."""

    def test_is_initialized_false_before_init(self, store: VectorStore) -> None:
        assert store.is_initialized is False

    def test_get_client_raises_before_init(self, store: VectorStore) -> None:
        with pytest.raises(StoreNotInitializedError, match="not initialized"):
            store.get_client()


class TestStoreCorrupted:
    """T030: Store raises on corrupt directory."""

    def test_file_at_persist_path_raises(self, tmp_path: Path) -> None:
        # Create a file where directory should be
        file_path = tmp_path / "vector_store"
        file_path.write_text("not a directory")

        config = RAGConfig(persist_directory=file_path)
        store = VectorStore(config)

        with pytest.raises(StoreCorruptedError, match="not a directory"):
            store.initialize()


class TestStorePersistence:
    """T140: Store persists across reinitialize."""

    def test_data_survives_close_and_reopen(
        self, store_config: RAGConfig
    ) -> None:
        # Open store, create a collection, add data
        store1 = VectorStore(store_config)
        store1.initialize()
        client1 = store1.get_client()
        col = client1.get_or_create_collection("test_persist")
        col.add(
            ids=["doc1"],
            documents=["persistent document"],
            metadatas=[{"key": "value"}],
        )
        assert col.count() == 1
        store1.close()

        # Reopen store, verify data is still there
        store2 = VectorStore(store_config)
        store2.initialize()
        client2 = store2.get_client()
        col2 = client2.get_collection("test_persist")
        assert col2.count() == 1
        result = col2.get(ids=["doc1"])
        assert result["documents"][0] == "persistent document"
        store2.close()


class TestStoreCustomPath:
    """T150: Persist directory created at correct path."""

    def test_custom_persist_directory(self, tmp_path: Path) -> None:
        custom_path = tmp_path / "custom" / "nested" / "store"
        config = RAGConfig(persist_directory=custom_path)
        store = VectorStore(config)
        store.initialize()
        assert custom_path.exists()
        assert custom_path.is_dir()
        store.close()


class TestStoreMissingDependency:
    """T110: Graceful error on missing chromadb."""

    def test_missing_chromadb_raises_import_error(
        self, store_config: RAGConfig
    ) -> None:
        store = VectorStore(store_config)
        with patch.dict("sys.modules", {"chromadb": None}):
            with pytest.raises(ImportError, match="chromadb"):
                store.initialize()


class TestStoreCloseAndReset:
    """Additional lifecycle tests."""

    def test_close_sets_not_initialized(self, store: VectorStore) -> None:
        store.initialize()
        assert store.is_initialized is True
        store.close()
        assert store.is_initialized is False

    def test_reset_clears_data(self, store: VectorStore) -> None:
        store.initialize()
        client = store.get_client()
        client.get_or_create_collection("to_delete")
        store.reset()
        assert store.is_initialized is True
        # After reset, collection should be gone
        collections = client.list_collections()
        # Handle both string and object returns
        names = [c if isinstance(c, str) else c.name for c in collections]
        assert "to_delete" not in names
```

### 6.16 `tests/unit/test_rag/test_embeddings.py` (Add)

**Complete file contents:**

```python
"""Tests for EmbeddingProvider (T060, T070, T080, T120).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.rag.embeddings import EmbeddingProvider


@pytest.fixture(scope="session")
def provider() -> EmbeddingProvider:
    """Session-scoped embedding provider to avoid reloading model per test."""
    return EmbeddingProvider()


class TestEmbedQuery:
    """T060: Embedding provider generates local vectors."""

    def test_embed_query_returns_384_floats(
        self, provider: EmbeddingProvider
    ) -> None:
        vector = provider.embed_query("hello world")
        assert isinstance(vector, list)
        assert len(vector) == 384
        assert all(isinstance(v, float) for v in vector)


class TestEmbedTexts:
    """T070: Embedding provider batch encoding."""

    def test_embed_texts_batch(self, provider: EmbeddingProvider) -> None:
        vectors = provider.embed_texts(["a", "b", "c"])
        assert len(vectors) == 3
        for vec in vectors:
            assert len(vec) == 384
            assert all(isinstance(v, float) for v in vec)


class TestLazyLoading:
    """T080: Embedding provider lazy loads model."""

    def test_is_loaded_false_before_use(self) -> None:
        fresh = EmbeddingProvider()
        assert fresh.is_loaded is False

    def test_is_loaded_true_after_use(
        self, provider: EmbeddingProvider
    ) -> None:
        provider.embed_query("trigger load")
        assert provider.is_loaded is True

    def test_dimension_property(self, provider: EmbeddingProvider) -> None:
        assert provider.dimension == 384


class TestMissingDependency:
    """T120: Graceful error on missing sentence-transformers."""

    def test_missing_sentence_transformers_raises(self) -> None:
        fresh = EmbeddingProvider()
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="sentence-transformers"):
                fresh.embed_query("test")
```

### 6.17 `tests/unit/test_rag/test_collections.py` (Add)

**Complete file contents:**

```python
"""Tests for CollectionManager (T040, T050, T090, T320).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.rag.collections import (
    COLLECTION_CODEBASE,
    COLLECTION_DOCUMENTATION,
    CollectionManager,
)
from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import CollectionNotFoundError, RAGError
from assemblyzero.rag.store import VectorStore


@pytest.fixture
def store(tmp_path: Path) -> VectorStore:
    """Create an initialized VectorStore with temp directory."""
    config = RAGConfig(persist_directory=tmp_path / "vector_store")
    s = VectorStore(config)
    s.initialize()
    return s


@pytest.fixture
def cm(store: VectorStore) -> CollectionManager:
    """Create a CollectionManager with initialized store."""
    return CollectionManager(store)


class TestCreateCollections:
    """T040: Create documentation and codebase collections."""

    def test_create_documentation_collection(
        self, cm: CollectionManager
    ) -> None:
        col = cm.create_collection(COLLECTION_DOCUMENTATION)
        assert col is not None
        retrieved = cm.get_collection(COLLECTION_DOCUMENTATION)
        assert retrieved is not None

    def test_create_codebase_collection(
        self, cm: CollectionManager
    ) -> None:
        col = cm.create_collection(COLLECTION_CODEBASE)
        assert col is not None
        retrieved = cm.get_collection(COLLECTION_CODEBASE)
        assert retrieved is not None

    def test_create_both_collections(self, cm: CollectionManager) -> None:
        cm.create_collection(COLLECTION_DOCUMENTATION)
        cm.create_collection(COLLECTION_CODEBASE)
        docs = cm.get_collection(COLLECTION_DOCUMENTATION)
        code = cm.get_collection(COLLECTION_CODEBASE)
        assert docs is not None
        assert code is not None

    def test_create_duplicate_raises(self, cm: CollectionManager) -> None:
        cm.create_collection("test_col")
        with pytest.raises(RAGError, match="already exists"):
            cm.create_collection("test_col")


class TestListCollections:
    """T050: List multiple collections."""

    def test_list_three_collections(self, cm: CollectionManager) -> None:
        cm.create_collection("alpha")
        cm.create_collection("beta")
        cm.create_collection("gamma")
        names = cm.list_collections()
        assert len(names) == 3
        assert set(names) == {"alpha", "beta", "gamma"}


class TestCollectionIsolation:
    """T090: Independent collection queries."""

    def test_add_to_docs_does_not_affect_codebase(
        self, cm: CollectionManager, store: VectorStore
    ) -> None:
        cm.create_collection(COLLECTION_DOCUMENTATION)
        cm.create_collection(COLLECTION_CODEBASE)

        doc_col = cm.get_collection(COLLECTION_DOCUMENTATION)
        doc_col.add(
            ids=["doc1"],
            documents=["A documentation paragraph."],
            metadatas=[{"source": "docs"}],
        )

        code_col = cm.get_collection(COLLECTION_CODEBASE)
        assert code_col.count() == 0
        assert doc_col.count() == 1


class TestCollectionCount:
    """T320: Collection count returns correct count."""

    def test_count_matches_added_documents(
        self, cm: CollectionManager
    ) -> None:
        cm.create_collection("test_count")
        col = cm.get_collection("test_count")
        for i in range(5):
            col.add(
                ids=[f"doc{i}"],
                documents=[f"Document {i} content"],
                metadatas=[{"index": str(i)}],
            )
        assert cm.collection_count("test_count") == 5

    def test_count_nonexistent_raises(self, cm: CollectionManager) -> None:
        with pytest.raises(CollectionNotFoundError):
            cm.collection_count("nonexistent")


class TestCollectionOps:
    """Additional collection operation tests."""

    def test_get_nonexistent_raises(self, cm: CollectionManager) -> None:
        with pytest.raises(CollectionNotFoundError):
            cm.get_collection("nonexistent")

    def test_delete_collection(self, cm: CollectionManager) -> None:
        cm.create_collection("to_delete")
        assert cm.collection_exists("to_delete") is True
        cm.delete_collection("to_delete")
        assert cm.collection_exists("to_delete") is False

    def test_delete_nonexistent_raises(self, cm: CollectionManager) -> None:
        with pytest.raises(CollectionNotFoundError):
            cm.delete_collection("nonexistent")

    def test_get_or_create_creates_new(self, cm: CollectionManager) -> None:
        col = cm.get_or_create_collection("new_col")
        assert col is not None
        assert cm.collection_exists("new_col") is True

    def test_get_or_create_returns_existing(
        self, cm: CollectionManager
    ) -> None:
        cm.create_collection("existing")
        col = cm.get_or_create_collection("existing")
        assert col is not None

    def test_collection_exists_false_for_missing(
        self, cm: CollectionManager
    ) -> None:
        assert cm.collection_exists("no_such_col") is False
```

### 6.18 `tests/unit/test_rag/test_chunking.py` (Add)

**Complete file contents:**

```python
"""Tests for TextChunker (T210–T250, T350, T360).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.rag.chunking import TextChunk, TextChunker


class TestChunkText:
    """T210: Text chunker splits correctly."""

    def test_larger_text_with_overlap(self) -> None:
        """Split 10-token text with chunk_size=4, overlap=1 into 3 chunks.

        Input:
            text = "one two three four five six seven eight nine ten"
            chunk_size = 4, chunk_overlap = 1

        Expected Output:
            3 TextChunk objects:
              - TextChunk(text="one two three four", metadata={}, chunk_index=0)
              - TextChunk(text="four five six seven", metadata={}, chunk_index=1)
              - TextChunk(text="seven eight nine ten", metadata={}, chunk_index=2)
        """
        chunker = TextChunker(chunk_size=4, chunk_overlap=1)
        chunks = chunker.chunk_text(
            "one two three four five six seven eight nine ten"
        )
        assert len(chunks) == 3
        assert chunks[0].text == "one two three four"
        assert chunks[0].chunk_index == 0
        assert chunks[1].text == "four five six seven"
        assert chunks[1].chunk_index == 1
        assert chunks[2].text == "seven eight nine ten"
        assert chunks[2].chunk_index == 2

    def test_chunk_size_boundary(self) -> None:
        chunker = TextChunker(chunk_size=200, chunk_overlap=50)
        # Generate a ~1000-token text
        tokens = [f"word{i}" for i in range(1000)]
        text = " ".join(tokens)
        chunks = chunker.chunk_text(text)
        # stride = 200 - 50 = 150, ceil(1000/150) ≈ 7 chunks
        assert len(chunks) >= 6
        for chunk in chunks:
            assert len(chunk.text.split()) <= 200


class TestChunkMetadata:
    """T220: Text chunker preserves metadata."""

    def test_metadata_propagated_to_all_chunks(self) -> None:
        chunker = TextChunker(chunk_size=4, chunk_overlap=1)
        meta = {"source": "test.md", "author": "tester"}
        chunks = chunker.chunk_text(
            "one two three four five six seven eight nine ten",
            metadata=meta,
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.metadata["source"] == "test.md"
            assert chunk.metadata["author"] == "tester"

    def test_none_metadata_gives_empty_dict(self) -> None:
        """When metadata=None, each chunk should have an empty dict.

        Input:
            text = "hello world foo bar baz"
            metadata = None (default)
            chunk_size = 3, chunk_overlap = 0

        Expected Output:
            2 TextChunk objects, each with metadata == {}
        """
        chunker = TextChunker(chunk_size=3, chunk_overlap=0)
        chunks = chunker.chunk_text("hello world foo bar baz")
        assert len(chunks) == 2
        for chunk in chunks:
            assert chunk.metadata == {}


class TestChunkEmptyText:
    """T230: Text chunker handles empty text."""

    def test_empty_string_returns_empty(self) -> None:
        chunker = TextChunker()
        assert chunker.chunk_text("") == []

    def test_whitespace_only_returns_empty(self) -> None:
        chunker = TextChunker()
        assert chunker.chunk_text("   \n\t  ") == []


class TestChunkShortText:
    """T240: Text chunker handles short text."""

    def test_short_text_single_chunk(self) -> None:
        chunker = TextChunker(chunk_size=512)
        chunks = chunker.chunk_text("short text")
        assert len(chunks) == 1
        assert chunks[0].text == "short text"
        assert chunks[0].chunk_index == 0


class TestChunkFile:
    """T250: Text chunker chunk_file reads from path."""

    def test_chunk_file_reads_content(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.md"
        test_file.write_text("word " * 100, encoding="utf-8")

        chunker = TextChunker(chunk_size=20, chunk_overlap=5)
        chunks = chunker.chunk_file(
            test_file,
            additional_metadata={"section": "test"},
            project_root=tmp_path,
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert "source_file" in chunk.metadata
            assert chunk.metadata["section"] == "test"

    def test_chunk_file_missing_raises(self, tmp_path: Path) -> None:
        chunker = TextChunker()
        with pytest.raises(FileNotFoundError):
            chunker.chunk_file(
                tmp_path / "nonexistent.md",
                project_root=tmp_path,
            )


class TestChunkOverlapValidation:
    """T350: Chunker rejects invalid overlap settings."""

    def test_overlap_equal_to_size_raises(self) -> None:
        """chunk_overlap == chunk_size should raise ValueError.

        Input: TextChunker(chunk_size=100, chunk_overlap=100)
        Expected: ValueError with message containing 'chunk_overlap (100) must be strictly less than chunk_size (100)'
        """
        with pytest.raises(ValueError, match="chunk_overlap.*100.*must be strictly less.*chunk_size.*100"):
            TextChunker(chunk_size=100, chunk_overlap=100)

    def test_overlap_greater_than_size_raises(self) -> None:
        """chunk_overlap > chunk_size should raise ValueError.

        Input: TextChunker(chunk_size=50, chunk_overlap=100)
        Expected: ValueError with message containing 'chunk_overlap (100) must be strictly less than chunk_size (50)'
        """
        with pytest.raises(ValueError, match="chunk_overlap.*100.*must be strictly less.*chunk_size.*50"):
            TextChunker(chunk_size=50, chunk_overlap=100)

    def test_zero_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            TextChunker(chunk_size=0, chunk_overlap=0)

    def test_negative_overlap_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
            TextChunker(chunk_size=100, chunk_overlap=-5)


class TestPathTraversal:
    """T360: chunk_file rejects path outside project root."""

    def test_absolute_path_outside_root_raises(self, tmp_path: Path) -> None:
        # Create a file outside the project root
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "evil.txt"
        outside_file.write_text("malicious content")

        project_root = tmp_path / "project"
        project_root.mkdir()

        chunker = TextChunker()
        with pytest.raises(ValueError, match="Path traversal"):
            chunker.chunk_file(outside_file, project_root=project_root)

    def test_relative_traversal_raises(self, tmp_path: Path) -> None:
        # Create project root and an outside file
        project_root = tmp_path / "project"
        project_root.mkdir()
        outside_file = tmp_path / "secret.txt"
        outside_file.write_text("secret data")

        chunker = TextChunker()
        # Use a relative path that traverses up
        traversal_path = project_root / ".." / "secret.txt"
        with pytest.raises(ValueError, match="Path traversal"):
            chunker.chunk_file(traversal_path, project_root=project_root)

    def test_valid_path_within_root_works(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        valid_file = project_root / "doc.md"
        valid_file.write_text("valid content here")

        chunker = TextChunker(chunk_size=100)
        chunks = chunker.chunk_file(valid_file, project_root=project_root)
        assert len(chunks) == 1
        assert chunks[0].metadata["source_file"] == "doc.md"
```

### 6.19 `tests/unit/test_rag/test_query.py` (Add)

**Complete file contents:**

```python
"""Tests for QueryEngine (T100, T160–T200, T260, T270, T280, T290, T300, T310, T340).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from assemblyzero.rag import _reset_singletons, get_query_engine, get_store
from assemblyzero.rag.collections import CollectionManager
from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.embeddings import EmbeddingProvider
from assemblyzero.rag.errors import CollectionNotFoundError
from assemblyzero.rag.query import QueryEngine, QueryResponse, QueryResult
from assemblyzero.rag.store import VectorStore


@pytest.fixture
def config(tmp_path: Path) -> RAGConfig:
    """RAGConfig with temp directory."""
    return RAGConfig(persist_directory=tmp_path / "vector_store")


@pytest.fixture
def store(config: RAGConfig) -> VectorStore:
    """Initialized VectorStore."""
    s = VectorStore(config)
    s.initialize()
    return s


@pytest.fixture(scope="session")
def embedding_provider() -> EmbeddingProvider:
    """Session-scoped embedding provider."""
    return EmbeddingProvider()


@pytest.fixture
def engine(
    store: VectorStore, embedding_provider: EmbeddingProvider, config: RAGConfig
) -> QueryEngine:
    """QueryEngine wired with store and embeddings."""
    return QueryEngine(store, embedding_provider, config)


class TestBothConsumers:
    """T100: Same API serves both consumers."""

    def test_single_engine_serves_both_collections(
        self, engine: QueryEngine
    ) -> None:
        # Add to documentation
        doc_ids = engine.add_documents(
            "documentation",
            ["ChromaDB manages vector storage."],
            [{"source": "docs"}],
        )
        assert len(doc_ids) == 1

        # Add to codebase
        code_ids = engine.add_documents(
            "codebase",
            ["class VectorStore: pass"],
            [{"source": "code"}],
        )
        assert len(code_ids) == 1

        # Query both
        doc_results = engine.query("documentation", "vector storage")
        code_results = engine.query("codebase", "VectorStore class")
        assert doc_results.total_results >= 1
        assert code_results.total_results >= 1


class TestAddDocuments:
    """T160: Add documents via QueryEngine."""

    def test_add_returns_sha256_ids(self, engine: QueryEngine) -> None:
        ids = engine.add_documents(
            "test_add",
            ["Document one", "Document two"],
            [{"key": "val1"}, {"key": "val2"}],
        )
        assert len(ids) == 2
        # SHA-256 hashes are 64 hex chars
        for doc_id in ids:
            assert len(doc_id) == 64
            assert all(c in "0123456789abcdef" for c in doc_id)


class TestQuery:
    """T170: Query returns ranked results."""

    def test_query_ranked_results(self, engine: QueryEngine) -> None:
        engine.add_documents(
            "test_ranked",
            [
                "Python is a programming language.",
                "The weather is sunny today.",
                "Python code uses indentation for blocks.",
            ],
        )
        response = engine.query("test_ranked", "Python programming")
        assert response.total_results >= 1
        assert isinstance(response, QueryResponse)
        assert len(response.results) >= 1
        # Most similar should be about Python
        assert "Python" in response.results[0].document or "python" in response.results[0].document.lower()


class TestDeleteDocuments:
    """T180: Delete documents via QueryEngine."""

    def test_delete_reduces_count(self, engine: QueryEngine) -> None:
        ids = engine.add_documents(
            "test_delete",
            ["doc one", "doc two", "doc three"],
        )
        assert len(ids) == 3
        engine.delete_documents("test_delete", [ids[0]])
        # Verify count decreased
        cm = CollectionManager(engine._store)
        assert cm.collection_count("test_delete") == 2


class TestQueryFilter:
    """T190: Query with metadata filter."""

    def test_where_filter_applied(self, engine: QueryEngine) -> None:
        engine.add_documents(
            "test_filter",
            ["Alpha document content", "Beta document content"],
            [{"category": "alpha"}, {"category": "beta"}],
        )
        response = engine.query(
            "test_filter",
            "document content",
            where={"category": "alpha"},
        )
        assert response.total_results >= 1
        for result in response.results:
            assert result.metadata.get("category") == "alpha"


class TestGetDocument:
    """T200: Get document by ID."""

    def test_get_existing_document(self, engine: QueryEngine) -> None:
        ids = engine.add_documents(
            "test_get",
            ["The specific document to retrieve."],
            [{"tag": "specific"}],
        )
        result = engine.get_document("test_get", ids[0])
        assert result is not None
        assert result.document == "The specific document to retrieve."
        assert result.metadata["tag"] == "specific"
        assert result.chunk_id == ids[0]

    def test_get_nonexistent_returns_none(self, engine: QueryEngine) -> None:
        engine.add_documents("test_get_none", ["placeholder"])
        result = engine.get_document("test_get_none", "nonexistent_id_12345")
        # ChromaDB get() with unknown ID returns empty
        assert result is None


class TestSingleton:
    """T260, T270: Singleton behavior."""

    def test_get_query_engine_singleton(self, tmp_path: Path) -> None:
        config = RAGConfig(persist_directory=tmp_path / "singleton_qe")
        try:
            e1 = get_query_engine(config)
            e2 = get_query_engine(config)
            assert id(e1) == id(e2)
        finally:
            _reset_singletons()

    def test_get_store_singleton(self, tmp_path: Path) -> None:
        config = RAGConfig(persist_directory=tmp_path / "singleton_store")
        try:
            s1 = get_store(config)
            s2 = get_store(config)
            assert id(s1) == id(s2)
        finally:
            _reset_singletons()


class TestDuplicateIdempotent:
    """T300: Duplicate add is idempotent."""

    def test_same_content_produces_same_id(self, engine: QueryEngine) -> None:
        ids1 = engine.add_documents("test_dedup", ["identical content"])
        ids2 = engine.add_documents("test_dedup", ["identical content"])
        assert ids1 == ids2
        cm = CollectionManager(engine._store)
        assert cm.collection_count("test_dedup") == 1


class TestQueryEmpty:
    """T310: Query empty collection returns empty."""

    def test_empty_collection_query(self, engine: QueryEngine) -> None:
        # Create empty collection
        cm = CollectionManager(engine._store)
        cm.get_or_create_collection("empty_col")
        response = engine.query("empty_col", "anything")
        assert response.total_results == 0
        assert response.results == []


class TestQueryNonexistent:
    """T340: Query non-existent collection raises error."""

    def test_query_nonexistent_raises(self, engine: QueryEngine) -> None:
        with pytest.raises(CollectionNotFoundError) as exc_info:
            engine.query("nonexistent_collection", "test query")
        assert exc_info.value.collection_name == "nonexistent_collection"


class TestTypeHints:
    """T280: All public functions have type hints."""

    def test_all_public_methods_have_return_annotations(self) -> None:
        classes = [VectorStore, EmbeddingProvider, CollectionManager, QueryEngine]
        for cls in classes:
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if name.startswith("_"):
                    continue
                hints = method.__annotations__
                assert "return" in hints, (
                    f"{cls.__name__}.{name}() missing return type hint"
                )


class TestDocstrings:
    """T290: All public functions have docstrings."""

    def test_all_public_methods_have_docstrings(self) -> None:
        classes = [VectorStore, EmbeddingProvider, CollectionManager, QueryEngine]
        for cls in classes:
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if name.startswith("_"):
                    continue
                assert method.__doc__ is not None and method.__doc__.strip(), (
                    f"{cls.__name__}.{name}() missing docstring"
                )
```


## 7. Pattern References

### 7.1 Existing Test Structure Pattern

**File:** `tests/e2e/test_issue_workflow_mock.py` (lines 1-80)

```python
# The existing tests use pytest fixtures, class-based test organization,
# and clear test names. RAG tests follow the same pattern:
# - Fixtures for setup/teardown
# - Class-based grouping by feature
# - Descriptive test names with test ID comments
```

**Relevance:** All new test files follow this same pattern — pytest fixtures, class grouping by test scenario, descriptive method names prefixed with `test_`.

### 7.2 Package Structure Pattern

**File:** `assemblyzero/` (directory)

```
assemblyzero/
├── __init__.py
├── rag/
│   ├── __init__.py
│   ├── config.py
│   ├── errors.py
│   ├── store.py
│   ├── embeddings.py
│   ├── collections.py
│   ├── chunking.py
│   └── query.py
```

**Relevance:** The `assemblyzero/rag/` package follows the existing project convention of placing domain modules under the `assemblyzero/` namespace. The `__init__.py` exports a clean public API while keeping internal wiring private.

### 7.3 Frozen Dataclass Pattern

**Relevance:** The project already uses dataclasses extensively. `RAGConfig`, `TextChunk`, `QueryResult`, and `QueryResponse` all use `@dataclass(frozen=True)` for immutability, consistent with Python best practices for configuration and value objects.


## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `from dataclasses import dataclass, field` | stdlib | `config.py`, `chunking.py`, `query.py` |
| `from pathlib import Path` | stdlib | `config.py`, `store.py`, `chunking.py` |
| `from typing import TYPE_CHECKING` | stdlib | `__init__.py`, `store.py`, `embeddings.py`, `collections.py`, `query.py` |
| `import hashlib` | stdlib | `query.py` |
| `import shutil` | stdlib | `store.py` |
| `import threading` | stdlib | `__init__.py` |
| `import inspect` | stdlib | `test_query.py` (T280, T290) |
| `import chromadb` | external (new) | `store.py` (runtime import) |
| `from sentence_transformers import SentenceTransformer` | external (new) | `embeddings.py` (runtime import) |
| `from assemblyzero.rag.config import RAGConfig` | internal | `__init__.py`, `store.py`, `query.py` |
| `from assemblyzero.rag.errors import *` | internal | `__init__.py`, `store.py`, `embeddings.py`, `collections.py`, `query.py` |
| `from assemblyzero.rag.store import VectorStore` | internal | `__init__.py`, `collections.py`, `query.py` |
| `from assemblyzero.rag.embeddings import EmbeddingProvider` | internal | `__init__.py`, `query.py` |
| `from assemblyzero.rag.collections import CollectionManager` | internal | `query.py` |
| `from assemblyzero.rag.chunking import TextChunk, TextChunker` | internal | `__init__.py` |
| `from assemblyzero.rag.query import QueryEngine, QueryResult, QueryResponse` | internal | `__init__.py` |
| `import pytest` | dev dep | All test files |

**New Dependencies:**

```toml
chromadb = ">=0.5.0,<1.0.0"
sentence-transformers = ">=3.0.0,<4.0.0"
```


## 9. Test Mapping

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


## 10. Implementation Notes

### 10.1 Error Handling Convention

All RAG errors inherit from `RAGError`. Consumers catch `RAGError` for unified fallback behavior. Specific exception types (`CollectionNotFoundError`, `EmbeddingError`, etc.) allow fine-grained handling when needed.

Pattern: fail-closed. If something goes wrong, raise an exception rather than returning empty/degraded results silently.

### 10.2 Logging Convention

No logging is added in this foundational layer. The `EmbeddingProvider._load_model()` could optionally print a message when downloading the model, but this is deferred to consumer-side logging configuration.

### 10.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `chunk_size` default | `512` | Matches `all-MiniLM-L6-v2` max context window |
| `chunk_overlap` default | `50` | ~10% overlap for context continuity |
| `embedding_dimension` | `384` | Fixed by `all-MiniLM-L6-v2` architecture |
| `default_n_results` | `5` | Reasonable default for similarity search |
| `distance_metric` | `"cosine"` | Standard for text similarity |
| `COLLECTION_DOCUMENTATION` | `"documentation"` | Well-known name for #88 |
| `COLLECTION_CODEBASE` | `"codebase"` | Well-known name for #92 |

### 10.4 ChromaDB API Notes

- `chromadb.PersistentClient(path=str)` — path must be a string, not Path
- `collection.upsert()` is used instead of `collection.add()` for idempotency
- `collection.query()` returns a dict with keys: `ids`, `documents`, `distances`, `metadatas` — each is a list of lists (batched)
- `client.list_collections()` behavior varies by ChromaDB version — the code handles both string and object returns
- `collection.get(ids=[...])` returns a dict with keys: `ids`, `documents`, `metadatas`

### 10.5 Singleton Reset for Testing

The `_reset_singletons()` function in `__init__.py` is exposed for test cleanup only (not in `__all__`). Tests that use `get_store()` or `get_query_engine()` must call `_reset_singletons()` in a try/finally block to avoid polluting other tests.

### 10.6 `.gitignore` Addition

The `.assemblyzero/vector_store/` directory should be in `.gitignore`. If `.assemblyzero/` is already gitignored (likely), no change needed. If not, add:

```
.assemblyzero/vector_store/
```


---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — `pyproject.toml`
- [x] Every data structure has a concrete JSON/YAML example (Section 4) — RAGConfig, TextChunk, QueryResult, QueryResponse, error hierarchy, fixtures
- [x] Every function has input/output examples with realistic values (Section 5) — 31 function specs
- [x] Change instructions are diff-level specific (Section 6) — pyproject.toml diff + complete file contents for all 19 files
- [x] Pattern references include file:line and are verified to exist (Section 7) — 3 patterns referenced
- [x] All imports are listed and verified (Section 8) — 22 imports listed
- [x] Test mapping covers all LLD test scenarios (Section 9) — all 36 tests mapped (T010–T360)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #113 |
| Verdict | DRAFT |
| Date | 2026-02-27 |
| Iterations | 2 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #113 |
| Verdict | APPROVED |
| Date | 2026-02-27 |
| Iterations | 1 |
| Finalized | 2026-02-27T06:56:44Z |

### Review Feedback Summary

Approved with suggestions:
1. **.gitignore Update:** Section 10.6 mentions updating `.gitignore` to exclude `.assemblyzero/vector_store/`, but this isn't listed in the "Files to Implement" table (Section 2) or given a specific "Change Instruction" block in Section 6. While likely handled by the environment or existing ignores, explicitly adding a task to verify/update `.gitignore` would guarantee the vector store isn't accidentally committed.


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    issue_workflow/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
    test_metrics/
    test_rag/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 14 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  telemetry/
  utils/
  workflow/
  workflows/
    implementation_spec/
      nodes/
    issue/
      nodes/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      runners/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_113.py
"""Test file for Issue #113.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from assemblyzero.rag.errors import *  # noqa: F401, F403


# Fixtures for mocking
@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    # TODO: Implement mock
    yield None


# Unit Tests
# -----------

def test_t010():
    """
    `VectorStore.__init__()` + `initialize()` | `VectorStore(config)` →
    `initialize()` | `is_initialized == True`, directory exists
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t010 works correctly
    assert False, 'TDD RED: test_t010 not implemented'


def test_t020():
    """
    `VectorStore.is_initialized` | `VectorStore()` (no init) | `False`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t020 works correctly
    assert False, 'TDD RED: test_t020 not implemented'


def test_t030():
    """
    `VectorStore.initialize()` | Path points to a file |
    `StoreCorruptedError`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t030 works correctly
    assert False, 'TDD RED: test_t030 not implemented'


def test_t040():
    """
    `CollectionManager.create_collection()` | `"documentation"`,
    `"codebase"` | Both accessible via `get_collection()`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t040 works correctly
    assert False, 'TDD RED: test_t040 not implemented'


def test_t050():
    """
    `CollectionManager.list_collections()` | 3 collections created | List
    of 3 names
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t050 works correctly
    assert False, 'TDD RED: test_t050 not implemented'


def test_t060():
    """
    `EmbeddingProvider.embed_query()` | `"hello world"` | `list[float]`
    of len 384
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t060 works correctly
    assert False, 'TDD RED: test_t060 not implemented'


def test_t070():
    """
    `EmbeddingProvider.embed_texts()` | `["a", "b", "c"]` | 3 vectors of
    len 384
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t070 works correctly
    assert False, 'TDD RED: test_t070 not implemented'


def test_t080():
    """
    `EmbeddingProvider.is_loaded` | Fresh `EmbeddingProvider()` | `False`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t080 works correctly
    assert False, 'TDD RED: test_t080 not implemented'


def test_t090():
    """
    `CollectionManager` isolation | Add to docs, check codebase |
    Codebase empty
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t090 works correctly
    assert False, 'TDD RED: test_t090 not implemented'


def test_t100():
    """
    `QueryEngine.add_documents()` + `query()` | Both collections via one
    engine | Both return correct results
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t100 works correctly
    assert False, 'TDD RED: test_t100 not implemented'


def test_t110(mock_external_service):
    """
    `VectorStore.initialize()` | chromadb mocked absent |
    `ImportError("chromadb")`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t110 works correctly
    assert False, 'TDD RED: test_t110 not implemented'


def test_t120(mock_external_service):
    """
    `EmbeddingProvider.embed_texts()` | sentence-transformers mocked
    absent | `ImportError("sentence-transformers")`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t120 works correctly
    assert False, 'TDD RED: test_t120 not implemented'


def test_t130():
    """
    All error classes | Instantiate each | All `isinstance(err,
    RAGError)`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t130 works correctly
    assert False, 'TDD RED: test_t130 not implemented'


def test_t140():
    """
    `VectorStore` close + reopen | Add data → close → reopen → query |
    Data still present
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t140 works correctly
    assert False, 'TDD RED: test_t140 not implemented'


def test_t150():
    """
    `VectorStore.initialize()` | Custom `persist_directory` | Directory
    exists at path
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t150 works correctly
    assert False, 'TDD RED: test_t150 not implemented'


def test_t160():
    """
    `QueryEngine.add_documents()` | 2 documents | 2 SHA-256 IDs returned
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t160 works correctly
    assert False, 'TDD RED: test_t160 not implemented'


def test_t170():
    """
    `QueryEngine.query()` | Query matching content | Results[0] most
    similar
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t170 works correctly
    assert False, 'TDD RED: test_t170 not implemented'


def test_t180():
    """
    `QueryEngine.delete_documents()` | Add 3, delete 1 | Count == 2
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t180 works correctly
    assert False, 'TDD RED: test_t180 not implemented'


def test_t190():
    """
    `QueryEngine.query(where=...)` | Filter on metadata key | Only
    matching docs
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t190 works correctly
    assert False, 'TDD RED: test_t190 not implemented'


def test_t200():
    """
    `QueryEngine.get_document()` | Known ID | Correct doc + metadata
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t200 works correctly
    assert False, 'TDD RED: test_t200 not implemented'


def test_t210():
    """
    `TextChunker.chunk_text()` | 10 tokens, size=4, overlap=1 | 3 chunks
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t210 works correctly
    assert False, 'TDD RED: test_t210 not implemented'


def test_t220():
    """
    `TextChunker.chunk_text(metadata=...)` | Text + metadata | All chunks
    have metadata
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t220 works correctly
    assert False, 'TDD RED: test_t220 not implemented'


def test_t230():
    """
    `TextChunker.chunk_text("")` | Empty string | `[]`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t230 works correctly
    assert False, 'TDD RED: test_t230 not implemented'


def test_t240():
    """
    `TextChunker.chunk_text("short")` | Short text | 1 chunk
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t240 works correctly
    assert False, 'TDD RED: test_t240 not implemented'


def test_t250():
    """
    `TextChunker.chunk_file()` | Real file path | Chunks with
    `source_file` in metadata
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t250 works correctly
    assert False, 'TDD RED: test_t250 not implemented'


def test_t260():
    """
    `get_query_engine()` x2 | Two calls | Same `id()`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t260 works correctly
    assert False, 'TDD RED: test_t260 not implemented'


def test_t270():
    """
    `get_store()` x2 | Two calls | Same `id()`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t270 works correctly
    assert False, 'TDD RED: test_t270 not implemented'


def test_t280():
    """
    `inspect.get_annotations()` on all public methods | All classes | All
    have return hints
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t280 works correctly
    assert False, 'TDD RED: test_t280 not implemented'


def test_t290():
    """
    `.__doc__` on all public methods | All classes | All non-empty
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t290 works correctly
    assert False, 'TDD RED: test_t290 not implemented'


def test_t300():
    """
    `QueryEngine.add_documents()` x2 same content | Same doc twice |
    Count == 1
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t300 works correctly
    assert False, 'TDD RED: test_t300 not implemented'


def test_t310():
    """
    `QueryEngine.query()` on empty collection | Empty collection |
    `total_results == 0`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t310 works correctly
    assert False, 'TDD RED: test_t310 not implemented'


def test_t320():
    """
    `CollectionManager.collection_count()` | 5 docs added | Returns 5
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t320 works correctly
    assert False, 'TDD RED: test_t320 not implemented'


def test_t330():
    """
    `RAGConfig()` | Default constructor | All defaults match spec
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t330 works correctly
    assert False, 'TDD RED: test_t330 not implemented'


def test_t340():
    """
    `QueryEngine.query("nonexistent", ...)` | Non-existent collection |
    `CollectionNotFoundError`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t340 works correctly
    assert False, 'TDD RED: test_t340 not implemented'


def test_t350():
    """
    `RAGConfig(chunk_overlap=chunk_size)` | overlap == size |
    `ValueError`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t350 works correctly
    assert False, 'TDD RED: test_t350 not implemented'


def test_t360():
    """
    `TextChunker.chunk_file(outside_path)` | Path outside project root |
    `ValueError("Path traversal")`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t360 works correctly
    assert False, 'TDD RED: test_t360 not implemented'




```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### pyproject.toml (signatures)

```python
[project]
name = "assemblyzero-tools"
version = "0.1.0"
description = "AssemblyZero configuration and tooling"
authors = [{name = "Marty McEnroe"}]
readme = "README.md"
license = "PolyForm-Noncommercial-1.0.0"
requires-python = "^3.10"
dependencies = [
    "keyring (>=25.7.0,<26.0.0)",
    "anthropic (>=0.78.0,<0.79.0)",
    "langgraph (>=1.0.7,<2.0.0)",
    "langgraph-checkpoint-sqlite (>=3.0.3,<4.0.0)",
    "langchain (>=1.2.8,<2.0.0)",
    "langchain-google-genai (>=4.2.0,<5.0.0)",
    "langchain-anthropic (>=1.3.1,<2.0.0)",
    "watchdog (>=6.0.0,<7.0.0)",
    "google-genai (>=1.60.0,<2.0.0)",
    "pygithub (>=2.8.1,<3.0.0)",
    "tiktoken (>=0.9.0,<1.0.0)",
    "langchain-core (>=1.2.9,<2.0.0)",
    "cryptography (>=46.0.4,<47.0.0)",
    "tenacity (>=9.1.3,<10.0.0)",
    "packaging (>=26.0,<27.0)",
    "pathspec (>=1.0.4,<2.0.0)",
    "aiosqlite (>=0.22.1,<0.23.0)",
    "jiter (>=0.13.0,<0.14.0)",
    "orjson (>=3.11.7,<4.0.0)",
    "langsmith (>=0.6.9,<0.7.0)",
    "google-auth (>=2.48.0,<3.0.0)",
    "pycparser (>=3.0,<4.0)",
    "boto3 (>=1.35.0,<2.0.0)",
    "chromadb (>=0.5.0,<1.0.0)",
    "sentence-transformers (>=3.0.0,<4.0.0)"
]

[tool.pytest.ini_options]
addopts = "-m 'not integration and not e2e'"
markers = [
    "integration: tests that call real external services (deselect with '-m \"not integration\"')",
    "e2e: end-to-end workflow tests requiring sandbox repo",
    "expensive: tests that use significant API quota",
]

[tool.poetry]
packages = [{include = "assemblyzero"}]

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
# ... (truncated, syntax error in original)

```

### assemblyzero/rag/__init__.py (signatures)

```python
"""RAG infrastructure for vector-based document retrieval.

Issue #113: Vector Database Infrastructure (RAG Foundation)

Public API:
    - get_store() — singleton VectorStore
    - get_query_engine() — singleton QueryEngine wired with store + embeddings
    - RAGConfig — configuration dataclass
    - TextChunker, TextChunk — document chunking utilities
    - QueryEngine, QueryResult, QueryResponse — query interface
    - VectorStore — store lifecycle management
    - EmbeddingProvider — local embedding generation
    - CollectionManager — collection CRUD
    - Error classes — RAGError hierarchy
"""

from __future__ import annotations

import threading

from typing import TYPE_CHECKING

from assemblyzero.rag.config import RAGConfig

from assemblyzero.rag.errors import (
    CollectionNotFoundError,
    EmbeddingError,
    RAGError,
    StoreCorruptedError,
    StoreNotInitializedError,
)

from assemblyzero.rag.chunking import TextChunk, TextChunker

def get_store(config: RAGConfig | None = None) -> VectorStore:
    """Get or create the singleton VectorStore instance.

Thread-safe. Returns existing instance if already created."""
    ...

def get_query_engine(config: RAGConfig | None = None) -> QueryEngine:
    """Get a fully wired QueryEngine with store + embeddings.

Convenience factory for consumers (#88, #92)."""
    ...

def _reset_singletons() -> None:
    """Reset singleton instances. For testing only.

Not included in __all__. Tests must call this in try/finally"""
    ...

_lock = threading.Lock()
```

### assemblyzero/rag/errors.py (signatures)

```python
"""Custom exception hierarchy for RAG infrastructure.

Issue #113: Vector Database Infrastructure (RAG Foundation)

All RAG errors inherit from RAGError. Consumers catch RAGError
for unified fallback behavior.
"""

from __future__ import annotations

class RAGError(Exception):

    """Base exception for all RAG infrastructure errors."""

class StoreNotInitializedError(RAGError):

    """Raised when operations attempted on uninitialized store."""

class CollectionNotFoundError(RAGError):

    """Raised when referencing a non-existent collection.

Attributes:"""

    def __init__(self, collection_name: str) -> None:
    ...

class EmbeddingError(RAGError):

    """Raised when embedding generation fails."""

class StoreCorruptedError(RAGError):

    """Raised when the persistent store is corrupted or unreadable."""
```

### assemblyzero/rag/config.py (full)

```python
"""RAG configuration dataclass and defaults.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RAGConfig:
    """Immutable configuration for the RAG infrastructure.

    Attributes:
        persist_directory: Path for ChromaDB persistent storage.
        embedding_model_name: SentenceTransformers model name.
        embedding_dimension: Vector dimension (must match model).
        chunk_size: Maximum tokens per chunk.
        chunk_overlap: Overlap tokens between consecutive chunks.
        default_n_results: Default number of query results.
        distance_metric: ChromaDB distance function.
    """

    persist_directory: Path = field(
        default_factory=lambda: Path(".assemblyzero/vector_store")
    )
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunk_size: int = 512
    chunk_overlap: int = 50
    default_n_results: int = 5
    distance_metric: str = "cosine"

    def __post_init__(self) -> None:
        """Validate configuration invariants.

        Raises:
            ValueError: If chunk_overlap >= chunk_size (would cause infinite
                loop in sliding window chunker) or if either value is <= 0.
        """
        if self.chunk_size <= 0:
            raise ValueError(
                f"chunk_size must be positive, got {self.chunk_size}"
            )
        if self.chunk_overlap < 0:
            raise ValueError(
                f"chunk_overlap must be non-negative, got {self.chunk_overlap}"
            )
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be strictly less "
                f"than chunk_size ({self.chunk_size}) to ensure forward "
                f"progress in the chunking loop"
            )
```

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
