

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
