# Extracted Test Plan

## Scenarios

### test_class_extraction_with_docstring
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T010: AST extracts class with docstring and methods. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_function_extraction_with_type_hints
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T020: AST extracts top-level function with type hints. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_private_entity_skip
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T030: AST skips private entities. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_malformed_file_returns_empty
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T040: AST handles malformed Python file. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_malformed_logs_warning
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T040/T290: Malformed Python file returns [] and logs warning with file path. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_docstring_only_init
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T050: AST skips __init__.py with only docstring. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_empty_init
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T050 variant: AST skips completely empty __init__.py. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_type_hints_preserved
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T260: AST extracts ClassDef with type hints preserved in content. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_standard_path
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T060: Convert standard file path to module path. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_init_path
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T060 variant: Convert __init__.py path. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_camel_case
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T070: CamelCase splitting. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_snake_case
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T080: snake_case splitting. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_stopword_filtering
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T090: Stopwords are filtered out. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_max_keywords_limit
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T100: Keyword extraction limits to top N. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_fallback_on_sparse_input
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T110: Keyword extraction fallback on sparse CamelCase input. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_contains_expected_terms
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T250: Domain stopwords are comprehensive. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_threshold_filtering
- Type: unit
- Requirement: 
- Mock needed: True
- Description: T120: Nonsense query returns empty results with mocked low scores. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_module_deduplication
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T130: Two chunks from same module keeps only highest score. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_max_results_limit
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T140: Query returns at most max_results. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_missing_collection_graceful
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T150: Missing collection returns empty list with warning. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_similarity_threshold_boundary
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T280: Results at boundary — 0.76 passes, 0.74 fails. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_budget_drops_lowest
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T160: Budget for 1.5 chunks keeps only top 1. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_budget_keeps_all
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T170: All chunks within budget returns all. | unit | tests/unit/test_rag/test_codebase_retrieval.py

### test_markdown_formatting
- Type: unit
- Requirement: 
- Mock needed: False
- Description: T180: Output has header, instruction, and code blocks. | unit | tests/unit/test_rag/test_codebase_retrieval.py

