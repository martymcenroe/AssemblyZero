

```json
[
    {
        "id": "DRIFT-001",
        "severity": "critical",
        "doc_file": "README.md",
        "doc_claim": "AssemblyZero includes 12+ specialized AI agents",
        "code_reality": "Found 36 persona TOML files in assemblyzero/personas/",
        "category": "count_mismatch",
        "confidence": 0.95,
        "evidence": "glob('assemblyzero/personas/*.toml') returned 36 matches"
    },
    {
        "id": "DRIFT-002",
        "severity": "major",
        "doc_file": "docs/architecture.md",
        "doc_claim": "System does not use vector embeddings",
        "code_reality": "RAG pipeline exists at assemblyzero/rag/",
        "category": "feature_contradiction",
        "confidence": 0.9,
        "evidence": "Directory assemblyzero/rag/ contains 8 Python files"
    }
]
```
